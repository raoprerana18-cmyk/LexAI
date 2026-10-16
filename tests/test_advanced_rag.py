import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from config import TestConfig
from services.rag_service import answer_question, classify_intent
from models.database_models import User, Document

@pytest.fixture
def test_app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app

@patch('services.rag_service.genai.Client')
@patch('services.rag_service.get_collection')
@patch('services.rag_service.embed_question')
def test_complex_legal_question_structure(mock_embed, mock_get_coll, mock_genai_client, test_app):
    mock_embed.return_value = [0.1] * 384
    mock_collection = MagicMock()
    mock_get_coll.return_value = mock_collection
    
    mock_collection.query.return_value = {
        'documents': [['Breach of contract means...']],
        'metadatas': [[{'source_type': 'knowledge_base', 'title': 'Breach of Contract Basics'}]],
        'distances': [[0.5]]
    }
    
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    
    mock_intent_response = MagicMock()
    mock_intent_response.text = "GENERAL_LEGAL"
    
    mock_answer_response = MagicMock()
    mock_answer_response.text = "# Direct Answer\nBreach of contract occurs when...\n# Disclaimer\nThis information is AI-generated..."
    
    mock_client_instance.models.generate_content.side_effect = [mock_intent_response, mock_answer_response]
    
    with test_app.app_context():
        result = answer_question(user_id=1, question="What is a breach of contract?", document_id=None)
        
    assert "# Direct Answer" in result['answer']
    assert "# Disclaimer" in result['answer']
    assert "Breach of Contract Basics" in [s['title'] for s in result['sources']]

@patch('services.rag_service.genai.Client')
def test_document_specific_question_intent(mock_genai_client, test_app):
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    mock_intent_response = MagicMock()
    mock_intent_response.text = "DOCUMENT_SPECIFIC"
    mock_client_instance.models.generate_content.return_value = mock_intent_response
    
    with test_app.app_context():
        intent = classify_intent("What does my uploaded contract say about termination?", "dummy_key", "gemini-3.6-flash")
        
    assert intent == "DOCUMENT_SPECIFIC"

@patch('services.rag_service.genai.Client')
def test_summarize_resume_intent(mock_genai_client, test_app):
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    mock_intent_response = MagicMock()
    mock_intent_response.text = "DOCUMENT_SPECIFIC"
    mock_client_instance.models.generate_content.return_value = mock_intent_response
    
    with test_app.app_context():
        intent = classify_intent("Summarize my uploaded resume", "dummy_key", "gemini-3.6-flash")
        
    assert intent == "DOCUMENT_SPECIFIC"

