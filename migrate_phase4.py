from app import create_app
from extensions import db
from models.database_models import Conversation, Message

app = create_app()

with app.app_context():
    print("Creating Phase 4 tables (conversations, messages)...")
    Conversation.__table__.create(db.engine, checkfirst=True)
    Message.__table__.create(db.engine, checkfirst=True)
    print("Migration successful! Tables created.")
