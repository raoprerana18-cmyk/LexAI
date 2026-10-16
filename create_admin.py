import os
import sys
from getpass import getpass
from app import create_app
from extensions import db, bcrypt
from models.database_models import User

def create_admin():
    app = create_app()
    with app.app_context():
        # Ensure tables are created
        db.create_all()

        print("=== Create LexAI Admin Account ===")
        name = input("Admin Name: ").strip()
        email = input("Admin Email: ").strip()
        
        if not name or not email:
            print("Name and email are required.")
            sys.exit(1)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print("A user with this email already exists.")
            sys.exit(1)

        password = getpass("Admin Password: ")
        confirm = getpass("Confirm Password: ")

        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)

        if len(password) < 8:
            print("Password must be at least 8 characters long.")
            sys.exit(1)

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        admin_user = User(name=name, email=email, password_hash=hashed_pw, role='admin')
        
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"Admin account for {email} created successfully!")

if __name__ == "__main__":
    create_admin()
