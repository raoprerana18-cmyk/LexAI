"""
test_phase5.py — Phase 5 & 6: Admin, Knowledge Base, Security, Error Handling.
"""
import io
import pytest
from app import create_app
from extensions import db, bcrypt
from models.database_models import User, Document, KnowledgeBase
from config import TestConfig
from unittest.mock import patch, MagicMock
from tests.conftest import assert_safe_test_environment


@pytest.fixture
def app():
    _app = create_app(TestConfig)
    with _app.app_context():
        assert_safe_test_environment(_app)
        db.create_all()

        pw    = bcrypt.generate_password_hash('password123').decode('utf-8')
        admin = User(name="Admin User", email="admin@lexai.com",
                     password_hash=pw, role="admin")
        user  = User(name="Normal User", email="user@lexai.com",
                     password_hash=pw, role="user")
        db.session.add_all([admin, user])
        db.session.commit()

        yield _app

        db.session.remove()
        assert_safe_test_environment(_app)
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login_client(client, email, password='password123'):
    return client.post('/login', data={'email': email, 'password': password},
                       follow_redirects=True)


# ─── Admin Access Control ─────────────────────────────────────────────────────

def test_admin_dashboard_unauthenticated_redirects(client):
    res = client.get('/admin/')
    assert res.status_code == 302


def test_admin_dashboard_normal_user_forbidden(client):
    login_client(client, 'user@lexai.com')
    res = client.get('/admin/')
    assert res.status_code == 302  # Redirected to index


def test_admin_dashboard_admin_allowed(client):
    login_client(client, 'admin@lexai.com')
    res = client.get('/admin/')
    assert res.status_code == 200


# ─── Last Admin Constraints ───────────────────────────────────────────────────

def test_last_admin_role_demotion_prevention(client, app):
    login_client(client, 'admin@lexai.com')
    with app.app_context():
        admin = User.query.filter_by(email="admin@lexai.com").first()
        res   = client.post(f'/admin/users/{admin.id}/role',
                            data={'role': 'user'}, follow_redirects=True)
        assert b"Cannot demote the last remaining admin." in res.data
        db.session.refresh(admin)
        assert admin.role == 'admin'


def test_last_admin_self_deletion_prevention(client, app):
    login_client(client, 'admin@lexai.com')
    with app.app_context():
        admin = User.query.filter_by(email="admin@lexai.com").first()
        res   = client.post(f'/admin/users/{admin.id}/delete', follow_redirects=True)
        assert b"You cannot delete your own logged-in account." in res.data


# ─── Knowledge Base CRUD ──────────────────────────────────────────────────────

@patch('routes.admin_routes.index_kb_entry')
@patch('routes.admin_routes.delete_kb_vectors')
def test_kb_crud_workflow(mock_del, mock_idx, client, app):
    mock_idx.return_value = True
    mock_del.return_value = True

    login_client(client, 'admin@lexai.com')

    # Create
    res = client.post('/admin/kb/add', data={
        'title': 'NDA Explained', 'category': 'Concepts',
        'content': 'An NDA is a confidentiality agreement.',
        'source': 'LexAI KB'
    }, follow_redirects=True)
    assert b"Knowledge Base entry added" in res.data
    mock_idx.assert_called_once()

    with app.app_context():
        kb = KnowledgeBase.query.filter_by(title='NDA Explained').first()
        assert kb is not None
        kb_id = kb.id

        # Edit
        res = client.post(f'/admin/kb/edit/{kb_id}', data={
            'title': 'NDA Updated', 'category': 'Concepts',
            'content': 'Updated NDA content.', 'source': 'LexAI KB'
        }, follow_redirects=True)
        assert b"updated successfully" in res.data
        db.session.refresh(kb)
        assert kb.title == 'NDA Updated'

        # Delete
        res = client.post(f'/admin/kb/delete/{kb_id}', follow_redirects=True)
        assert b"deleted successfully" in res.data
        assert db.session.get(KnowledgeBase, kb_id) is None


def test_kb_add_missing_fields_rejected(client):
    login_client(client, 'admin@lexai.com')
    res = client.post('/admin/kb/add', data={
        'title': '', 'category': 'FAQ', 'content': ''
    }, follow_redirects=True)
    assert b"mandatory" in res.data


def test_kb_crud_requires_admin(client):
    """Normal users cannot add KB entries."""
    login_client(client, 'user@lexai.com')
    res = client.post('/admin/kb/add', data={
        'title': 'Hack', 'category': 'X', 'content': 'test'
    }, follow_redirects=True)
    # Redirected away — not 200 with success message
    assert b"Knowledge Base entry added" not in res.data


# ─── File Upload Validation ───────────────────────────────────────────────────

def test_invalid_extension_rejected(client):
    login_client(client, 'user@lexai.com')
    res = client.post('/upload', data={
        'file': (io.BytesIO(b'evil'), 'script.exe')
    }, content_type='multipart/form-data', follow_redirects=True)
    assert b"Only PDF and DOCX are allowed." in res.data


def test_oversized_file_rejected_413(client):
    login_client(client, 'user@lexai.com')
    large = io.BytesIO(b'0' * (int(15.5 * 1024 * 1024)))
    res = client.post('/upload', data={
        'file': (large, 'large.pdf')
    }, content_type='multipart/form-data')
    assert res.status_code == 413


# ─── Error Pages ─────────────────────────────────────────────────────────────

def test_404_html_page(client):
    res = client.get('/this-page-does-not-exist-at-all-xyz')
    assert res.status_code == 404
    assert b'404' in res.data


def test_api_404_returns_json(client):
    res = client.get('/api/nonexistent-endpoint')
    assert res.status_code == 404
    assert res.is_json
    assert res.get_json()['error'] == 'Not Found'


# ─── Health Check ─────────────────────────────────────────────────────────────

def test_health_check_ok(client):
    res = client.get('/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert data['application'] == 'LexAI'


def test_health_detailed_ok(client):
    res = client.get('/health/detailed')
    # Status is 200 (ok) or 503 (degraded — e.g., if ChromaDB not init'd in test)
    assert res.status_code in (200, 503)
    data = res.get_json()
    assert 'checks' in data
    assert 'database' in data['checks']
    assert 'chromadb' in data['checks']


# ─── General Chat (no document) ───────────────────────────────────────────────

@patch('routes.chat_routes.answer_question')
def test_general_chat_no_document(mock_rag, client):
    mock_rag.return_value = {'answer': 'General answer.', 'sources': []}
    login_client(client, 'user@lexai.com')
    res = client.post('/api/chat', json={'message': 'What is an NDA?'})
    assert res.status_code == 200
    assert res.get_json()['answer'] == 'General answer.'
    # document_id should be None → general chat mode
    _, kwargs = mock_rag.call_args
    assert mock_rag.call_args[0][2] is None or mock_rag.call_args[1].get('document_id') is None


# ─── Conversation IDOR ────────────────────────────────────────────────────────

def test_user_cannot_view_other_user_messages(client, app):
    from models.database_models import Conversation, Message
    with app.app_context():
        admin = User.query.filter_by(email="admin@lexai.com").first()
        conv  = Conversation(user_id=admin.id, title='Admin conv')
        db.session.add(conv)
        db.session.commit()
        db.session.add(Message(conversation_id=conv.id, sender='user', message='secret'))
        db.session.commit()
        conv_id = conv.id

    login_client(client, 'user@lexai.com')
    res = client.get(f'/api/conversations/{conv_id}/messages')
    assert res.status_code == 403
