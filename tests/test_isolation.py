"""
test_isolation.py — Runtime verification that tests are using safe
test-only database and ChromaDB paths (not production resources).
"""
import os
import urllib.parse
import pytest
from config import TestConfig


def test_database_is_lexai_test():
    """Verify the configured test database is LexAI_test, not lexai_db."""
    uri     = TestConfig.SQLALCHEMY_DATABASE_URI
    parsed  = urllib.parse.urlparse(uri)
    db_name = parsed.path.lstrip('/')
    assert db_name.lower() == 'lexai_test', (
        f"TEST SAFETY FAILURE: Database is '{db_name}' but must be 'LexAI_test'. "
        f"Tests would otherwise target the production database."
    )


def test_chromadb_path_is_test_directory():
    """Verify ChromaDB path resolves to chroma_db_test, not chroma_db."""
    chroma_path = TestConfig.CHROMA_DB_PATH
    chroma_dir  = os.path.basename(os.path.normpath(chroma_path))
    assert chroma_dir.lower() == 'chroma_db_test', (
        f"TEST SAFETY FAILURE: ChromaDB dir is '{chroma_dir}' but must be 'chroma_db_test'. "
        f"Tests would otherwise wipe production vectors."
    )


def test_test_config_testing_flag():
    """Verify TESTING=True in TestConfig so Flask disables some behaviors."""
    assert TestConfig.TESTING is True


def test_production_chroma_db_is_separate():
    """Verify production chroma_db and test chroma_db_test are different paths."""
    from config import Config
    prod_path = os.path.normpath(Config.CHROMA_DB_PATH)
    test_path = os.path.normpath(TestConfig.CHROMA_DB_PATH)
    assert prod_path != test_path, (
        "Production and test ChromaDB paths must not be the same directory."
    )


def test_production_db_uri_differs_from_test():
    """Verify production DB URI and test DB URI differ."""
    from config import Config
    prod_uri = Config.SQLALCHEMY_DATABASE_URI
    test_uri = TestConfig.SQLALCHEMY_DATABASE_URI
    assert prod_uri != test_uri, (
        "Production and test SQLAlchemy URIs must not be identical."
    )
