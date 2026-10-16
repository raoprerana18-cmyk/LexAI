from app import create_app
from extensions import db
from models.database_models import DocumentAnalysis

app = create_app()

with app.app_context():
    # Create only the new table
    print("Creating document_analysis table...")
    DocumentAnalysis.__table__.create(db.engine, checkfirst=True)
    print("Migration Phase 3 complete.")
