"""
conftest.py — Global test safety infrastructure for LexAI.

CRITICAL GUARANTEES:
1. Tests NEVER connect to the production 'lexai_db' MySQL database.
2. Tests NEVER use the production 'chroma_db/' ChromaDB directory.
3. Any fixture calling db.drop_all() or db.create_all() is verified
   against both guards before proceeding.
4. If either guard fails, RuntimeError is raised immediately and
   no destructive teardown occurs.
"""
import os
import urllib.parse
import pytest
from config import TestConfig
from app import create_app
from extensions import db

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
PRODUCTION_DB_NAME    = "lexai_db"
SAFE_TEST_DB_NAME     = "lexai_test"          # case-insensitive comparison
PRODUCTION_CHROMA_DIR = "chroma_db"           # folder name only (not chroma_db_test)
SAFE_TEST_CHROMA_DIR  = "chroma_db_test"


# ──────────────────────────────────────────────
# Helper: extract DB name from SQLAlchemy URI
# ──────────────────────────────────────────────
def _extract_db_name(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    return parsed.path.lstrip("/")


# ──────────────────────────────────────────────
# Helper: extract ChromaDB folder name from path
# ──────────────────────────────────────────────
def _extract_chroma_dir(path: str) -> str:
    """Returns just the final folder name, e.g. 'chroma_db_test'."""
    return os.path.basename(os.path.normpath(path))


# ──────────────────────────────────────────────
# Core Safety Assertion (used by fixtures)
# ──────────────────────────────────────────────
def assert_safe_test_environment(app=None):
    """
    Verifies that:
      1. The active DB is NOT 'lexai_db'.
      2. The ChromaDB path is NOT the production 'chroma_db/'.

    Raises RuntimeError immediately if either check fails.
    Call this BEFORE any db.drop_all() or db.create_all().
    """
    # ── DB check via TestConfig URI ──────────────────────────
    config_db_name = _extract_db_name(TestConfig.SQLALCHEMY_DATABASE_URI)
    if config_db_name.lower() == PRODUCTION_DB_NAME:
        raise RuntimeError(
            f"TEST SAFETY ERROR: Production database '{PRODUCTION_DB_NAME}' "
            f"detected in TestConfig URI. Refusing to run destructive teardown."
        )

    # ── DB check via active app engine (if app provided) ─────
    if app is not None:
        with app.app_context():
            engine_db = db.engine.url.database
            if engine_db and engine_db.lower() == PRODUCTION_DB_NAME:
                raise RuntimeError(
                    f"TEST SAFETY ERROR: Active SQLAlchemy engine is connected to "
                    f"production '{PRODUCTION_DB_NAME}'. Refusing teardown."
                )

    # ── ChromaDB path check ───────────────────────────────────
    chroma_path = TestConfig.CHROMA_DB_PATH
    chroma_dir  = _extract_chroma_dir(chroma_path)
    if chroma_dir.lower() == PRODUCTION_CHROMA_DIR:
        raise RuntimeError(
            f"TEST SAFETY ERROR: ChromaDB path '{chroma_path}' resolves to "
            f"the production directory '{PRODUCTION_CHROMA_DIR}'. "
            f"Refusing teardown to protect production vectors."
        )


# ──────────────────────────────────────────────
# Session-level startup audit
# ──────────────────────────────────────────────
def pytest_sessionstart(session):
    """Fires before any test. Audits and prints the test environment."""
    uri        = TestConfig.SQLALCHEMY_DATABASE_URI
    db_name    = _extract_db_name(uri)
    chroma_dir = _extract_chroma_dir(TestConfig.CHROMA_DB_PATH)

    print(f"\n{'='*60}")
    print(f"[LexAI Test Audit] Database   : '{db_name}'")
    print(f"[LexAI Test Audit] ChromaDB   : '{chroma_dir}'")
    print(f"{'='*60}\n")

    # Hard stop if production targets detected
    if db_name.lower() == PRODUCTION_DB_NAME:
        raise RuntimeError(
            f"CRITICAL: pytest is configured with the production database "
            f"'{PRODUCTION_DB_NAME}'. All tests halted."
        )
    if chroma_dir.lower() == PRODUCTION_CHROMA_DIR:
        raise RuntimeError(
            f"CRITICAL: pytest ChromaDB path resolves to production "
            f"'{PRODUCTION_CHROMA_DIR}'. All tests halted."
        )


# ──────────────────────────────────────────────
# Per-test autouse guard
# ──────────────────────────────────────────────
@pytest.fixture(scope='function', autouse=True)
def _per_test_safety_check(request):
    """
    Before every test function, if 'app' or 'test_app' fixtures are
    active, verify the active engine is not production.
    """
    for fixture_name in ('app', 'test_app'):
        if fixture_name in request.fixturenames:
            _app = request.getfixturevalue(fixture_name)
            with _app.app_context():
                engine_db = db.engine.url.database or ""
                if engine_db.lower() == PRODUCTION_DB_NAME:
                    raise RuntimeError(
                        f"TEST SAFETY ERROR: Engine is connected to production "
                        f"'{PRODUCTION_DB_NAME}' during test '{request.node.name}'. "
                        f"Halting test."
                    )
            break  # only need to check one
