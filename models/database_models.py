from extensions import db
from flask_login import UserMixin
from datetime import datetime, timezone


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # 'user' or 'admin'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<User {self.email} (Role: {self.role})>"

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False) # 'pdf' or 'docx'
    file_size = db.Column(db.Integer, nullable=False) # in bytes
    status = db.Column(db.String(20), nullable=False, default='processing') # processing, completed, failed
    extracted_text = db.Column(db.Text, nullable=True)
    page_count = db.Column(db.Integer, default=0)
    word_count = db.Column(db.Integer, default=0)
    character_count = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('documents', lazy=True, cascade="all, delete"))

    def __repr__(self):
        return f"<Document {self.original_filename} (User: {self.user_id})>"

class DocumentAnalysis(db.Model):
    __tablename__ = 'document_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    document_type = db.Column(db.String(100), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    parties = db.Column(db.JSON, nullable=True)
    key_clauses = db.Column(db.JSON, nullable=True)
    important_dates = db.Column(db.JSON, nullable=True)
    obligations = db.Column(db.JSON, nullable=True)
    risks = db.Column(db.JSON, nullable=True)
    red_flags = db.Column(db.JSON, nullable=True)
    financial_terms = db.Column(db.JSON, nullable=True)
    termination_conditions = db.Column(db.JSON, nullable=True)
    rights = db.Column(db.JSON, nullable=True)
    recommendations = db.Column(db.JSON, nullable=True)
    confidence = db.Column(db.String(50), nullable=True)
    disclaimer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    document = db.relationship('Document', backref=db.backref('analysis', uselist=False, cascade="all, delete"))
    user = db.relationship('User', backref=db.backref('analyses', lazy=True, cascade="all, delete"))

    def __repr__(self):
        return f"<DocumentAnalysis (Doc ID: {self.document_id})>"

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('conversations', lazy=True, cascade="all, delete"))
    document = db.relationship('Document', backref=db.backref('conversations', lazy=True, cascade="all, delete"))
    
    def __repr__(self):
        return f"<Conversation {self.id} (User: {self.user_id})>"

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    sender = db.Column(db.String(50), nullable=False) # 'user' or 'ai'
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    conversation = db.relationship('Conversation', backref=db.backref('messages', lazy=True, cascade="all, delete", order_by="Message.created_at"))
    
    def __repr__(self):
        return f"<Message {self.id} (Sender: {self.sender})>"

class KnowledgeBase(db.Model):
    __tablename__ = 'knowledge_base'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active') # 'active' or 'inactive'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    creator = db.relationship('User', backref=db.backref('kb_entries', lazy=True))
    
    def __repr__(self):
        return f"<KnowledgeBase {self.title} (Category: {self.category})>"
