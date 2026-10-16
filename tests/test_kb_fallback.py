import pytest
from unittest.mock import patch, MagicMock
from services.rag_service import answer_question
from app import create_app
from extensions import db
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

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_kb_article_exists_gemini_succeeds(mock_client, mock_get_coll, mock_embed, test_app):
    mock_embed.return_value = [0.1] * 384
    mock_coll = MagicMock()
    mock_coll.query.return_value = {
        'documents': [["Source 1: Breach of Contract — Knowledge Base\nSome content."]],
        'metadatas': [[{"source_type": "knowledge_base", "title": "Breach of Contract"}]],
        'distances': [[0.5]]
    }
    mock_get_coll.return_value = mock_coll
    
    # Mock Gemini success
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "Gemini Detailed Answer."
    mock_client.return_value.models = mock_model
    
    with test_app.app_context():
        res = answer_question(user_id=1, question="test", document_id=None)
        assert "Gemini Detailed Answer" in res['answer']

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_kb_article_exists_gemini_429(mock_client, mock_get_coll, mock_embed, test_app):
    mock_embed.return_value = [0.1] * 384
    mock_coll = MagicMock()
    mock_coll.query.return_value = {
        'documents': [["Some definition of breach of contract."]],
        'metadatas': [[{"source_type": "knowledge_base", "title": "Breach of Contract"}]],
        'distances': [[0.5]]
    }
    mock_get_coll.return_value = mock_coll
    
    # Mock Gemini 429 Error
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    mock_client.return_value.models = mock_model
    
    with test_app.app_context():
        res = answer_question(user_id=1, question="test", document_id=None)
        # Should return fallback
        assert "LexAI Knowledge Base" in res['answer']
        assert "Breach of Contract" in res['answer']

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_no_relevant_kb_article_gemini_unavailable(mock_client, mock_get_coll, mock_embed, test_app):
    mock_embed.return_value = [0.1] * 384
    mock_coll = MagicMock()
    mock_coll.query.return_value = {
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    }
    mock_get_coll.return_value = mock_coll
    
    with test_app.app_context():
        res = answer_question(user_id=1, question="test", document_id=None)
        # Context blocks is empty, so it fails early.
        assert "I don't have enough information" in res['answer']

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_document_chat_gemini_429(mock_client, mock_get_coll, mock_embed, test_app):
    mock_embed.return_value = [0.1] * 384
    mock_coll = MagicMock()
    mock_coll.query.return_value = {
        'documents': [["User private document text."]],
        'metadatas': [[{"source_type": "document", "title": "My Doc"}]],
        'distances': [[0.5]]
    }
    mock_get_coll.return_value = mock_coll
    
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    mock_client.return_value.models = mock_model
    
    with test_app.app_context():
        with pytest.raises(RuntimeError, match="busy or out of quota"):
            answer_question(user_id=1, question="test", document_id=1)

@patch('services.rag_service.embed_question')
@patch('services.rag_service.get_collection')
@patch('google.genai.Client')
def test_fallback_does_not_contain_raw_separators_and_truncates(mock_client, mock_get_coll, mock_embed, test_app):
    mock_embed.return_value = [0.1] * 384
    mock_coll = MagicMock()
    long_content = "Word " * 300
    mock_coll.query.return_value = {
        'documents': [["Source 1: Breach of Contract - Knowledge Base\n--- # Explanation\nThis is a clean explanation.\n--- # Key Elements\n" + long_content]],
        'metadatas': [[{"source_type": "knowledge_base", "title": "Breach of Contract"}]],
        'distances': [[0.5]]
    }
    mock_get_coll.return_value = mock_coll
    
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    mock_client.return_value.models = mock_model
    
    with test_app.app_context():
        res = answer_question(user_id=1, question="element", document_id=None)
        
        # Check separators removed
        assert "--- #" not in res['answer']
        assert "### Direct Answer" in res['answer']
        assert "### Key Information" in res['answer']
        assert "LexAI Knowledge Base" in res['answer']
        
        # Check truncation
        words = res['answer'].split()
        # Max words should be well under 600 (since we cap at 250 per section)
        assert len(words) < 350
