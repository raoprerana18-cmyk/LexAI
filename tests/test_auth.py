"""
test_auth.py — Phase 1: Authentication tests.
Covers: registration, login, logout, password validation, admin authorization.
"""
import pytest
from app import create_app
from extensions import db, bcrypt
from models.database_models import User
from config import TestConfig
from tests.conftest import assert_safe_test_environment


@pytest.fixture
def app():
    _app = create_app(TestConfig)
    with _app.app_context():
        assert_safe_test_environment(_app)
        db.create_all()
        yield _app
        db.session.remove()
        assert_safe_test_environment(_app)
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ─── Registration ──────────────────────────────────────────────────────────────

def test_successful_registration(client):
    res = client.post('/register', data={
        'name': 'Test User', 'email': 'test@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    }, follow_redirects=True)
    assert b'Your account has been created' in res.data


def test_duplicate_email_registration(client):
    client.post('/register', data={
        'name': 'Test User', 'email': 'test@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    })
    res = client.post('/register', data={
        'name': 'Test User 2', 'email': 'test@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    }, follow_redirects=True)
    assert b'Email already registered' in res.data


def test_password_mismatch(client):
    res = client.post('/register', data={
        'name': 'Test User', 'email': 'test2@example.com',
        'password': 'password123', 'confirm_password': 'different'
    }, follow_redirects=True)
    assert b'Passwords must match' in res.data


def test_short_password_rejected(client):
    res = client.post('/register', data={
        'name': 'Test User', 'email': 'short@example.com',
        'password': 'abc', 'confirm_password': 'abc'
    }, follow_redirects=True)
    assert b'at least 8 characters' in res.data


def test_invalid_email_format(client):
    res = client.post('/register', data={
        'name': 'Test User', 'email': 'not-an-email',
        'password': 'password123', 'confirm_password': 'password123'
    }, follow_redirects=True)
    assert b'Invalid email format' in res.data


def test_missing_registration_fields(client):
    res = client.post('/register', data={
        'name': '', 'email': '', 'password': '', 'confirm_password': ''
    }, follow_redirects=True)
    assert b'required' in res.data.lower()


# ─── Login ─────────────────────────────────────────────────────────────────────

def test_successful_login(client):
    client.post('/register', data={
        'name': 'Login User', 'email': 'login@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    })
    res = client.post('/login', data={
        'email': 'login@example.com', 'password': 'password123'
    }, follow_redirects=True)
    assert b'Welcome back, Login User' in res.data


def test_wrong_password(client):
    client.post('/register', data={
        'name': 'Login User', 'email': 'wrong@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    })
    res = client.post('/login', data={
        'email': 'wrong@example.com', 'password': 'wrongpassword'
    }, follow_redirects=True)
    assert b'Invalid email or password' in res.data


def test_nonexistent_user_login(client):
    res = client.post('/login', data={
        'email': 'nobody@example.com', 'password': 'password123'
    }, follow_redirects=True)
    assert b'Invalid email or password' in res.data


# ─── Logout ───────────────────────────────────────────────────────────────────

def test_logout(client):
    client.post('/register', data={
        'name': 'Logout User', 'email': 'logout@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    })
    client.post('/login', data={'email': 'logout@example.com', 'password': 'password123'})
    res = client.get('/logout', follow_redirects=True)
    assert b'Login' in res.data


# ─── Auth Protection ──────────────────────────────────────────────────────────

def test_protected_dashboard_without_login(client):
    res = client.get('/dashboard', follow_redirects=True)
    assert b'Sign in to your legal workspace' in res.data


# ─── Admin Authorization ──────────────────────────────────────────────────────

def test_admin_access(app, client):
    from utils import admin_required

    @app.route('/admin_test')
    @admin_required
    def admin_test():
        return "Admin Area"

    # Regular user should be denied
    client.post('/register', data={
        'name': 'Normal', 'email': 'normal@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    })
    client.post('/login', data={'email': 'normal@example.com', 'password': 'password123'})
    res = client.get('/admin_test', follow_redirects=True)
    assert b'You do not have permission' in res.data

    client.get('/logout')

    # Promote user to admin
    client.post('/register', data={
        'name': 'Admin', 'email': 'admin@example.com',
        'password': 'password123', 'confirm_password': 'password123'
    })
    with app.app_context():
        admin = User.query.filter_by(email='admin@example.com').first()
        admin.role = 'admin'
        db.session.commit()

    client.post('/login', data={'email': 'admin@example.com', 'password': 'password123'})
    res = client.get('/admin_test')
    assert b'Admin Area' in res.data
