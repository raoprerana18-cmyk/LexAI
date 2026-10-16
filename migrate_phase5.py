from app import create_app
from extensions import db
from models.database_models import KnowledgeBase

app = create_app()

with app.app_context():
    print("Creating Phase 5 tables (knowledge_base) safely...")
    KnowledgeBase.__table__.create(db.engine, checkfirst=True)
    print("Migration successful! knowledge_base table created.")
