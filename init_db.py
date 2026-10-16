from app import create_app
from extensions import db
from models.database_models import User, Document, DocumentAnalysis, Conversation, Message
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Initializing Database tables safely (CREATE TABLE IF NOT EXISTS)...")
    db.create_all()
    print("Database tables initialized.")
    
    # Verify tables
    res = db.session.execute(text('SHOW TABLES;')).fetchall()
    print('Current Tables in DB:', [r[0] for r in res])
