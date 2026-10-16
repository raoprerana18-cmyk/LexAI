import os
import pytest
from io import BytesIO
from app import create_app
from extensions import db, bcrypt
from models.database_models import User, Document
from config import TestConfig
from tests.conftest import assert_safe_test_environment

@pytest.fixture
def app():
    _app = create_app(TestConfig)

    # Use a temporary upload folder for tests
    _app.config['UPLOAD_FOLDER'] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'test_uploads'
    )
    os.makedirs(_app.config['UPLOAD_FOLDER'], exist_ok=True)

    with _app.app_context():
        assert_safe_test_environment(_app)
        db.create_all()

        hashed_pw = bcrypt.generate_password_hash('password123').decode('utf-8')
        user1 = User(name='Test User 1', email='user1@example.com', password_hash=hashed_pw)
        user2 = User(name='Test User 2', email='user2@example.com', password_hash=hashed_pw)
        db.session.add_all([user1, user2])
        db.session.commit()

    yield _app

    with _app.app_context():
        db.session.remove()
        assert_safe_test_environment(_app)
        db.drop_all()

    import shutil
    if os.path.exists(_app.config['UPLOAD_FOLDER']):
        shutil.rmtree(_app.config['UPLOAD_FOLDER'])

@pytest.fixture
def client(app):
    return app.test_client()

def login(client, email, password):
    return client.post('/login', data=dict(
        email=email,
        password=password
    ), follow_redirects=True)

def create_dummy_pdf():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a dummy PDF file for testing.", fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def create_dummy_docx():
    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph('This is a dummy DOCX file for testing.')
    from io import BytesIO
    f = BytesIO()
    doc.save(f)
    return f.getvalue()

def test_unauthenticated_upload_rejected(client):
    response = client.get('/upload', follow_redirects=True)
    assert b'Please log in to access this page.' in response.data

def test_successful_pdf_upload(client, app):
    login(client, 'user1@example.com', 'password123')
    
    data = {
        'file': (BytesIO(create_dummy_pdf()), 'test.pdf')
    }
    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'uploaded and processed successfully!' in response.data
    
    with app.app_context():
        doc = Document.query.filter_by(original_filename='test.pdf').first()
        assert doc is not None
        assert doc.file_type == 'pdf'
        assert doc.status == 'completed'
        assert 'This is a dummy PDF' in doc.extracted_text
        assert doc.word_count > 0
        assert doc.page_count == 1

def test_successful_docx_upload(client, app):
    login(client, 'user1@example.com', 'password123')
    
    data = {
        'file': (BytesIO(create_dummy_docx()), 'test.docx')
    }
    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'uploaded and processed successfully!' in response.data
    
    with app.app_context():
        doc = Document.query.filter_by(original_filename='test.docx').first()
        assert doc is not None
        assert doc.file_type == 'docx'
        assert doc.status == 'completed'
        assert 'This is a dummy DOCX' in doc.extracted_text
        assert doc.word_count > 0

def test_invalid_file_type_rejected(client):
    login(client, 'user1@example.com', 'password123')
    
    data = {
        'file': (BytesIO(b"fake text data"), 'test.txt')
    }
    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    assert b'Invalid file type. Only PDF and DOCX are allowed.' in response.data

def test_user_can_list_own_documents(client, app):
    login(client, 'user1@example.com', 'password123')
    
    # Upload a doc
    data = {'file': (BytesIO(create_dummy_pdf()), 'user1_doc.pdf')}
    client.post('/upload', data=data, content_type='multipart/form-data')
    
    response = client.get('/history')
    assert b'user1_doc.pdf' in response.data

def test_user_cannot_access_another_users_document(client, app):
    login(client, 'user1@example.com', 'password123')
    
    # User 1 uploads
    data = {'file': (BytesIO(create_dummy_pdf()), 'secret.pdf')}
    client.post('/upload', data=data, content_type='multipart/form-data')
    
    with app.app_context():
        doc = Document.query.filter_by(original_filename='secret.pdf').first()
        doc_id = doc.id
        
    client.get('/logout')
    
    # User 2 logs in and tries to view
    login(client, 'user2@example.com', 'password123')
    response = client.get(f'/analysis/{doc_id}')
    
    assert response.status_code == 403

def test_delete_removes_document_and_file(client, app):
    login(client, 'user1@example.com', 'password123')
    
    data = {'file': (BytesIO(create_dummy_pdf()), 'to_delete.pdf')}
    client.post('/upload', data=data, content_type='multipart/form-data')
    
    with app.app_context():
        doc = Document.query.filter_by(original_filename='to_delete.pdf').first()
        doc_id = doc.id
        file_dir = os.path.dirname(doc.file_path)
        assert os.path.exists(file_dir)
        
    # Delete doc
    response = client.post(f'/delete/{doc_id}', follow_redirects=True)
    assert b'Document deleted successfully.' in response.data
    
    with app.app_context():
        doc = Document.query.filter_by(original_filename='to_delete.pdf').first()
        assert doc is None
        assert not os.path.exists(file_dir)
