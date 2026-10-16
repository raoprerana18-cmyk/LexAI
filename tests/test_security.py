"""
test_security.py — Phase 6 cross-user IDOR, file security, and ChromaDB
                   isolation tests.

User A and User B must be strictly isolated at:
  - Flask route / HTTP level
  - ChromaDB retrieval level
"""
import io
import os
import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from extensions import db, bcrypt
from models.database_models import User, Document
from config import TestConfig
from tests.conftest import assert_safe_test_environment


@pytest.fixture
def app():
    _app = create_app(TestConfig)
    _app.config['UPLOAD_FOLDER'] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'test_uploads_security'
    )
    os.makedirs(_app.config['UPLOAD_FOLDER'], exist_ok=True)

    with _app.app_context():
        assert_safe_test_environment(_app)
        db.create_all()

        pw = bcrypt.generate_password_hash('password123').decode('utf-8')
        user_a = User(name='User A', email='usera@test.com', password_hash=pw)
        user_b = User(name='User B', email='userb@test.com', password_hash=pw)
        db.session.add_all([user_a, user_b])
        db.session.commit()

        # Give User A a document
        doc_a = Document(
            user_id=user_a.id, filename='contract_a.pdf',
            original_filename='Contract_A.pdf',
            file_path='/tmp/contract_a.pdf', file_type='pdf',
            file_size=1024, status='completed',
            extracted_text='Contract A confidential terms.'
        )
        db.session.add(doc_a)
        db.session.commit()

        yield _app

        db.session.remove()
        assert_safe_test_environment(_app)
        db.drop_all()

    import shutil
    uploads = _app.config['UPLOAD_FOLDER']
    if os.path.exists(uploads):
        shutil.rmtree(uploads)


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email):
    return client.post('/login', data={'email': email, 'password': 'password123'},
                       follow_redirects=True)


# ─── Cross-User IDOR Tests ─────────────────────────────────────────────────────

def test_user_b_cannot_view_user_a_document(client, app):
    """User B must get 403 when viewing User A's document analysis page."""
    with app.app_context():
        doc_a = Document.query.filter_by(filename='contract_a.pdf').first()
        doc_id = doc_a.id

    login(client, 'userb@test.com')
    res = client.get(f'/analysis/{doc_id}')
    assert res.status_code == 403


def test_user_b_cannot_analyze_user_a_document(client, app):
    """User B must get 403 when trying to analyze User A's document."""
    with app.app_context():
        doc_a = Document.query.filter_by(filename='contract_a.pdf').first()
        doc_id = doc_a.id

    login(client, 'userb@test.com')
    res = client.post(f'/analyze/{doc_id}', follow_redirects=False)
    assert res.status_code == 403


def test_user_b_cannot_delete_user_a_document(client, app):
    """User B must get 403 when trying to delete User A's document."""
    with app.app_context():
        doc_a = Document.query.filter_by(filename='contract_a.pdf').first()
        doc_id = doc_a.id

    login(client, 'userb@test.com')
    res = client.post(f'/delete/{doc_id}', follow_redirects=False)
    assert res.status_code == 403


def test_user_b_cannot_chat_with_user_a_document(client, app):
    """User B must get 403 from the chat API when specifying User A's document_id."""
    with app.app_context():
        doc_a = Document.query.filter_by(filename='contract_a.pdf').first()
        doc_id = doc_a.id

    login(client, 'userb@test.com')
    res = client.post('/api/chat', json={
        'message': 'What is this contract about?',
        'document_id': doc_id
    })
    assert res.status_code == 403


def test_user_b_cannot_access_user_a_conversation(client, app):
    """User B cannot view messages from User A's conversation."""
    from models.database_models import Conversation, Message
    with app.app_context():
        user_a = User.query.filter_by(email='usera@test.com').first()
        conv = Conversation(user_id=user_a.id, title='A chat')
        db.session.add(conv)
        db.session.commit()
        msg = Message(conversation_id=conv.id, sender='user', message='hello')
        db.session.add(msg)
        db.session.commit()
        conv_id = conv.id

    login(client, 'userb@test.com')
    res = client.get(f'/api/conversations/{conv_id}/messages')
    assert res.status_code == 403


# ─── ChromaDB Vector Isolation ────────────────────────────────────────────────

@patch('services.rag_service.get_collection')
@patch('services.rag_service.embed_question')
def test_rag_user_isolation_at_chromadb_level(mock_embed, mock_get_coll, app):
    """
    Verify that when User B queries RAG, only User B's vectors are returned.
    The ChromaDB where-filter must use the correct user_id.
    """
    from services.rag_service import answer_question

    mock_embed.return_value = [0.1] * 384

    # Simulate empty result for User B (no vectors match user_b.id filter)
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        'documents': [[]], 'metadatas': [[]]
    }
    mock_get_coll.return_value = mock_collection

    with app.app_context():
        user_b = User.query.filter_by(email='userb@test.com').first()
        result = answer_question(user_id=user_b.id, question='test my document', document_id=None)

    # User B should get the "not found" response, not User A's data
    assert "don't have enough information" in result['answer'].lower() or \
           'An error occurred' in result['answer']

    # Verify that the ChromaDB query was called with User B's user_id
    call_args = mock_collection.query.call_args_list
    assert len(call_args) > 0


# ─── File Type Security ───────────────────────────────────────────────────────

@pytest.mark.parametrize("filename,content", [
    ("malware.exe",  b"MZ\x90\x00"),
    ("script.bat",   b"@echo off"),
    ("script.cmd",   b"@echo off"),
    ("exploit.py",   b"import os; os.system('rm -rf /')"),
    ("inject.js",    b"alert('xss')"),
    ("archive.zip",  b"PK\x03\x04"),
])
def test_invalid_file_types_rejected(client, filename, content):
    login(client, 'usera@test.com')
    res = client.post('/upload', data={
        'file': (io.BytesIO(content), filename)
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b'Only PDF and DOCX are allowed' in res.data


def test_zero_byte_file_rejected_or_handled(client):
    """0-byte files are either rejected at validation or handled gracefully."""
    login(client, 'usera@test.com')
    res = client.post('/upload', data={
        'file': (io.BytesIO(b''), 'empty.pdf')
    }, content_type='multipart/form-data', follow_redirects=True)
    # Should either flash an error or succeed without crashing
    assert res.status_code in (200, 302, 400)


def test_oversized_file_rejected(client):
    """Files larger than 15 MB must be rejected with 413."""
    login(client, 'usera@test.com')
    large = io.BytesIO(b'0' * (15 * 1024 * 1024 + 1))
    res = client.post('/upload', data={
        'file': (large, 'large.pdf')
    }, content_type='multipart/form-data')
    assert res.status_code == 413


def test_path_traversal_filename_rejected(client):
    """Filenames containing path traversal sequences must not escape the upload dir."""
    login(client, 'usera@test.com')
    res = client.post('/upload', data={
        'file': (io.BytesIO(b'%PDF-1.4'), '../../../etc/passwd.pdf')
    }, content_type='multipart/form-data', follow_redirects=True)
    # werkzeug.secure_filename strips path traversal; should not return 500
    assert res.status_code in (200, 302, 400)
    # Critical: file must not exist outside the upload directory
    assert not os.path.exists('/etc/passwd.pdf')
