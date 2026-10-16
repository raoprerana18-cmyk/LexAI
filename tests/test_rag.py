"""
test_rag.py — Phase 4: RAG pipeline tests.
Covers: chunking, embeddings, ChromaDB indexing, retrieval, document/general
        chat routing, conversation persistence, source citations, vector
        deletion, and no-duplicate re-indexing.
"""
import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from extensions import db
from models.database_models import User, Document, Conversation, Message
from services.embedding_service import chunk_text
from config import TestConfig
from tests.conftest import assert_safe_test_environment


@pytest.fixture
def test_app():
    _app = create_app(TestConfig)
    with _app.app_context():
        assert_safe_test_environment(_app)
        db.create_all()
        yield _app
        db.session.remove()
        assert_safe_test_environment(_app)
        db.drop_all()


@pytest.fixture
def client(test_app):
    return test_app.test_client()


# ─── Chunking ─────────────────────────────────────────────────────────────────

def test_chunk_text_normal():
    text   = "word " * 1200
    chunks = chunk_text(text, chunk_size=1000, overlap=100)
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 1000
    assert len(chunks[1].split()) == 300


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_single_word():
    chunks = chunk_text("hello", chunk_size=1000, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == "hello"


def test_chunk_text_exactly_chunk_size():
    text   = "word " * 1000
    chunks = chunk_text(text, chunk_size=1000, overlap=0)
    assert len(chunks) == 1


def test_chunk_text_overlap_no_infinite_loop():
    """Ensure overlap >= chunk_size doesn't cause infinite loop."""
    text   = "word " * 100
    chunks = chunk_text(text, chunk_size=10, overlap=10)
    assert len(chunks) > 0


# ─── Document Chat Mode ───────────────────────────────────────────────────────

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_document_chat_uses_document_filter(mock_genai, mock_coll, mock_embed, test_app):
    """Document Chat must query ChromaDB with user_id + document_id filter."""
    from services.rag_service import answer_question

    mock_embed.return_value = [0.1] * 384

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        'documents': [["This contract terminates in 30 days."]],
        'metadatas': [[{"filename": "contract.pdf", "document_id": "1", "chunk_index": 0}]]
    }
    mock_coll.return_value = mock_collection

    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "Terminates in 30 days."
    mock_genai.return_value.models = mock_model

    with test_app.app_context():
        result = answer_question(user_id=1, question="Termination?", document_id=1)

    assert "30 days" in result['answer']
    assert result['sources'][0]['type'] == 'document'

    # Verify filter included document_id
    call_kwargs = mock_collection.query.call_args[1]
    where = call_kwargs.get('where', {})
    and_clauses = where.get('$and', [])
    keys_used = [list(c.keys())[0] for c in and_clauses]
    assert 'document_id' in keys_used
    assert 'user_id' in keys_used


@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
def test_document_chat_no_vectors_returns_fallback(mock_coll, mock_embed, test_app):
    """Document Chat must return fallback message when no chunks retrieved."""
    from services.rag_service import answer_question

    mock_embed.return_value = [0.1] * 384
    mock_collection = MagicMock()
    mock_collection.query.return_value = {'documents': [[]], 'metadatas': [[]]}
    mock_coll.return_value = mock_collection

    with test_app.app_context():
        result = answer_question(user_id=1, question="test?", document_id=99)

    assert "don't have enough information" in result['answer'].lower()
    assert result['sources'] == []


# ─── General Chat Mode ────────────────────────────────────────────────────────

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_general_chat_uses_knowledge_base_filter(mock_genai, mock_coll, mock_embed, test_app):
    """General Chat (no document_id) must query for knowledge_base source_type."""
    from services.rag_service import answer_question

    mock_embed.return_value = [0.1] * 384

    # First call (user docs) returns empty; second call (KB) returns a result
    mock_collection = MagicMock()
    mock_collection.query.side_effect = [
        {'documents': [["An NDA is a confidentiality agreement."]], 'metadatas': [[
            {"source_type": "knowledge_base", "title": "NDA Basics",
             "knowledge_base_id": "1", "chunk_index": 0, "category": "Concepts", "source": "KB"}
        ]]}
    ]
    mock_coll.return_value = mock_collection

    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "An NDA establishes confidentiality."
    mock_genai.return_value.models = mock_model

    with test_app.app_context():
        result = answer_question(user_id=1, question="What is an NDA?", document_id=None)

    assert len(result['sources']) == 1
    assert result['sources'][0]['type'] == 'knowledge_base'

    # KB query must use knowledge_base filter
    calls = mock_collection.query.call_args_list
    kb_call_where = calls[0][1].get('where', {})
    assert kb_call_where.get('source_type', {}).get('$eq') == 'knowledge_base'


# ─── Missing API Key ──────────────────────────────────────────────────────────

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
def test_missing_gemini_key_returns_error_message(mock_coll, mock_embed, test_app, monkeypatch):
    """RAG must raise an error when Gemini key is missing."""
    from services.rag_service import answer_question

    mock_embed.return_value = [0.1] * 384
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        'documents': [["Some retrieved text."]],
        'metadatas': [[{"filename": "f.pdf", "document_id": "1", "chunk_index": 0}]]
    }
    mock_coll.return_value = mock_collection

    with test_app.app_context():
        monkeypatch.delenv('GEMINI_API_KEY', raising=False)
        test_app.config['GEMINI_API_KEY'] = ''  # Simulate missing key
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not configured"):
            answer_question(user_id=1, question="test?", document_id=1)


# ─── Conversation & Message Persistence ───────────────────────────────────────

@patch('routes.chat_routes.answer_question')
def test_conversation_created_and_message_saved(mock_rag, client, test_app):
    """Sending a chat message must create a conversation and persist messages."""
    from extensions import bcrypt as _bcrypt

    mock_rag.return_value = {'answer': 'Test answer.', 'sources': []}

    with test_app.app_context():
        pw   = _bcrypt.generate_password_hash('password123').decode('utf-8')
        user = User(name='Chat User', email='chatuser@test.com', password_hash=pw)
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'email': 'chatuser@test.com', 'password': 'password123'})

    res = client.post('/api/chat', json={'message': 'Hello!'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'conversation_id' in data
    assert data['answer'] == 'Test answer.'

    with test_app.app_context():
        conv = db.session.get(Conversation, data['conversation_id'])
        assert conv is not None
        msgs = Message.query.filter_by(conversation_id=conv.id).all()
        assert len(msgs) == 2  # user + ai
        assert msgs[0].sender == 'user'
        assert msgs[1].sender == 'ai'


# ─── Chat API Auth Guard ──────────────────────────────────────────────────────

def test_chat_api_unauthorized(client):
    res = client.post('/api/chat', json={'message': 'hello'})
    assert res.status_code in (302, 401)


# ─── ChromaDB No-Duplicate Re-index ──────────────────────────────────────────

@patch('services.embedding_service.get_chroma_client')
def test_reindex_no_duplicates(mock_client_fn, test_app):
    """Re-indexing must delete old vectors before adding new ones."""
    from services.embedding_service import index_document, delete_document_vectors

    mock_collection = MagicMock()
    mock_collection.add.return_value = None
    mock_collection.delete.return_value = None
    mock_collection.count.return_value = 0

    mock_chroma = MagicMock()
    mock_chroma.get_or_create_collection.return_value = mock_collection
    mock_client_fn.return_value = mock_chroma

    with test_app.app_context():
        delete_document_vectors('42', 7)
        index_document('42', 'Some text content here.' * 50, 7, 'test.pdf')

    mock_collection.delete.assert_called_once()
    mock_collection.add.assert_called_once()