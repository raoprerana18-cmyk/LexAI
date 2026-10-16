import os
from app import create_app
from extensions import db
from sqlalchemy import text

def run_migration():
    app = create_app()
    with app.app_context():
        # Drop the existing empty tables if they exist
        print("Checking for existing 'documents' and 'document_analysis' tables...")
        try:
            db.session.execute(text('DROP TABLE IF EXISTS document_analysis'))
            db.session.execute(text('DROP TABLE IF EXISTS documents'))
            db.session.commit()
            print("Dropped old tables if they existed.")
        except Exception as e:
            print(f"Error dropping tables: {e}")
            db.session.rollback()

        # Create new tables
        print("Creating new tables based on models...")
        db.create_all()
        print("Migration complete. 'documents' table is ready.")

if __name__ == '__main__':
    run_migration()
