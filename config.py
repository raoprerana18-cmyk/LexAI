import os
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

class Config:
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database Configuration
    DB_USER     = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST     = os.getenv('DB_HOST', 'localhost')
    DB_PORT     = os.getenv('DB_PORT', '3306')
    DB_NAME     = os.getenv('DB_NAME', 'lexai_db')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{urllib.parse.quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI Configuration
    AI_PROVIDER    = os.getenv('AI_PROVIDER', 'gemini')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    AI_MODEL       = os.getenv('AI_MODEL', 'gemini-3.6-flash')

    # Upload Configuration
    UPLOAD_FOLDER      = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB

    # ChromaDB Configuration
    CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chroma_db')


class TestConfig(Config):
    TESTING       = True
    DEBUG         = True
    DB_NAME       = 'LexAI_test'
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{Config.DB_USER}:{urllib.parse.quote_plus(Config.DB_PASSWORD)}"
        f"@{Config.DB_HOST}:{Config.DB_PORT}/{DB_NAME}"
    )
    WTF_CSRF_ENABLED = False
    CHROMA_DB_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chroma_db_test')
