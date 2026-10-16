import os
import pytest
from unittest.mock import patch
from io import BytesIO
from app import create_app
from extensions import db, bcrypt
from models.database_models import User, Document, DocumentAnalysis
from config import TestConfig
from tests.conftest import assert_safe_test_environment

@pytest.fixture
def app():
    app = create_app(TestConfig)

    # Use a temporary upload folder for tests
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        assert_safe_test_environment(app)
        db.create_all()

        # Create test users
        hashed_pw = bcrypt.generate_password_hash('password123').decode('utf-8')
        user1 = User(name='Test User 1', email='user1@example.com', password_hash=hashed_pw)
        user2 = User(name='Test User 2', email='user2@example.com', password_hash=hashed_pw)
        db.session.add(user1)
        db.session.add(user2)

        # Create a dummy document for user1
        doc1 = Document(
            user_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='test.pdf',
            file_type='pdf',
            file_size=1024,
            status='completed',
            extracted_text='This is a dummy contract text.'
        )
        db.session.add(doc1)
        db.session.commit()

    yield app

    with app.app_context():
        db.session.remove()
        assert_safe_test_environment(app)
        db.drop_all()

    # Clean up test uploads
    import shutil
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        shutil.rmtree(app.config['UPLOAD_FOLDER'])


@pytest.fixture
def client(app):
    return app.test_client()

def login(client, email, password):
    return client.post('/login', data=dict(
        email=email,
        password=password
    ), follow_redirects=True)

@patch('routes.document_routes.analyze_legal_document')
def test_successful_ai_analysis(mock_analyze, client, app):
    # Mock the AI service response
    mock_analyze.return_value = {
        "document_type": "Dummy Contract",
        "summary": "This is a summary.",
        "parties": ["Party A", "Party B"],
        "risks": [{"description": "High risk", "severity": "HIGH"}]
    }
    
    login(client, 'user1@example.com', 'password123')
    
    response = client.post('/analyze/1', follow_redirects=True)
    assert response.status_code == 200
    assert b'AI Analysis completed successfully.' in response.data
    
    with app.app_context():
        analysis = DocumentAnalysis.query.filter_by(document_id=1).first()
        assert analysis is not None
        assert analysis.document_type == "Dummy Contract"
        assert analysis.summary == "This is a summary."
        assert len(analysis.parties) == 2

def test_unauthenticated_analysis_rejected(client):
    response = client.post('/analyze/1', follow_redirects=True)
    assert b'Please log in to access this page.' in response.data

def test_user_cannot_analyze_another_users_document(client):
    login(client, 'user2@example.com', 'password123')
    response = client.post('/analyze/1', follow_redirects=True)
    assert response.status_code == 403

@patch('routes.document_routes.analyze_legal_document')
def test_malformed_ai_response_handled(mock_analyze, client, app):
    # Mock an exception raised by the AI service (e.g. JSON decode error)
    mock_analyze.side_effect = ValueError("Failed to parse JSON")
    
    login(client, 'user1@example.com', 'password123')
    
    response = client.post('/analyze/1', follow_redirects=True)
    assert response.status_code == 200
    assert b'Validation error: Failed to parse JSON' in response.data
    
    with app.app_context():
        analysis = DocumentAnalysis.query.filter_by(document_id=1).first()
        assert analysis is None
