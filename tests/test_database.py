"""
test_database.py — Phase 6: Database cascade and integrity tests.
Verifies that deleting a parent record properly cascades to all children,
leaving no orphan records.
"""
import pytest
from app import create_app
from extensions import db, bcrypt
from models.database_models import User, Document, DocumentAnalysis, Conversation, Message, KnowledgeBase
from config import TestConfig
from tests.conftest import assert_safe_test_environment


@pytest.fixture
def app():
    _app = create_app(TestConfig)
    with _app.app_context():
        assert_safe_test_environment(_app)
        db.create_all()

        pw   = bcrypt.generate_password_hash('password123').decode('utf-8')
        user = User(name='Cascade User', email='cascade@test.com', password_hash=pw)
        db.session.add(user)
        db.session.commit()

        yield _app

        db.session.remove()
        assert_safe_test_environment(_app)
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_full_document_tree(app):
    """Creates user → document → analysis → conversation → messages.
    Returns (user_id, doc_id, analysis_id, conv_id, [msg_ids])."""
    with app.app_context():
        user = User.query.filter_by(email='cascade@test.com').first()
        doc  = Document(
            user_id=user.id, filename='test.pdf',
            original_filename='test.pdf', file_path='/tmp/test.pdf',
            file_type='pdf', file_size=100, status='completed',
            extracted_text='Some text.'
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(document_id=doc.id, user_id=user.id, summary='Summary')
        conv     = Conversation(user_id=user.id, document_id=doc.id, title='Chat')
        db.session.add_all([analysis, conv])
        db.session.commit()

        msg1 = Message(conversation_id=conv.id, sender='user', message='Hello')
        msg2 = Message(conversation_id=conv.id, sender='ai',   message='Hi')
        db.session.add_all([msg1, msg2])
        db.session.commit()

        return user.id, doc.id, analysis.id, conv.id, [msg1.id, msg2.id]


# ─── Document Cascade ─────────────────────────────────────────────────────────

def test_delete_document_cascades_to_analysis(app):
    """Deleting a document must cascade-delete its analysis."""
    user_id, doc_id, analysis_id, conv_id, msg_ids = _seed_full_document_tree(app)
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        db.session.delete(doc)
        db.session.commit()

        assert db.session.get(DocumentAnalysis, analysis_id) is None, \
            "DocumentAnalysis orphan record found after document deletion"


def test_delete_document_cascades_to_conversations(app):
    """Deleting a document must cascade-delete associated conversations."""
    user_id, doc_id, analysis_id, conv_id, msg_ids = _seed_full_document_tree(app)
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        db.session.delete(doc)
        db.session.commit()

        assert db.session.get(Conversation, conv_id) is None, \
            "Conversation orphan record found after document deletion"


def test_delete_document_cascades_to_messages(app):
    """Deleting a document must transitively cascade-delete all messages."""
    user_id, doc_id, analysis_id, conv_id, msg_ids = _seed_full_document_tree(app)
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        db.session.delete(doc)
        db.session.commit()

        for msg_id in msg_ids:
            assert db.session.get(Message, msg_id) is None, \
                f"Message {msg_id} orphan found after document deletion"


# ─── User Cascade ─────────────────────────────────────────────────────────────

def test_delete_user_cascades_to_documents(app):
    """Deleting a user must cascade-delete all their documents."""
    user_id, doc_id, _, _, _ = _seed_full_document_tree(app)
    with app.app_context():
        user = db.session.get(User, user_id)
        db.session.delete(user)
        db.session.commit()

        assert db.session.get(Document, doc_id) is None, \
            "Document orphan found after user deletion"


def test_delete_user_cascades_to_conversations(app):
    """Deleting a user must cascade-delete all their conversations."""
    user_id, _, _, conv_id, _ = _seed_full_document_tree(app)
    with app.app_context():
        user = db.session.get(User, user_id)
        db.session.delete(user)
        db.session.commit()

        assert db.session.get(Conversation, conv_id) is None, \
            "Conversation orphan found after user deletion"


# ─── Conversation / Message Cascade ──────────────────────────────────────────

def test_delete_conversation_cascades_to_messages(app):
    """Deleting a conversation must delete all its messages."""
    _, _, _, conv_id, msg_ids = _seed_full_document_tree(app)
    with app.app_context():
        conv = db.session.get(Conversation, conv_id)
        db.session.delete(conv)
        db.session.commit()

        for msg_id in msg_ids:
            assert db.session.get(Message, msg_id) is None, \
                f"Message {msg_id} orphan found after conversation deletion"


# ─── Analysis Standalone Delete ───────────────────────────────────────────────

def test_delete_analysis_does_not_delete_document(app):
    """Deleting an analysis must NOT delete the parent document."""
    user_id, doc_id, analysis_id, _, _ = _seed_full_document_tree(app)
    with app.app_context():
        analysis = db.session.get(DocumentAnalysis, analysis_id)
        db.session.delete(analysis)
        db.session.commit()

        assert db.session.get(Document, doc_id) is not None, \
            "Document was incorrectly deleted when its analysis was removed"
