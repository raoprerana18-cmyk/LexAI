from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/health')
def health_check():
    return jsonify({
        "status": "ok",
        "application": "LexAI"
    })

@main_bp.route('/health/detailed')
def health_detailed():
    """Detailed health check verifies DB and ChromaDB connectivity.
    Does NOT expose secrets, passwords, or internal tracebacks."""
    health = {"status": "ok", "application": "LexAI", "checks": {}}

    # Check MySQL
    try:
        db.session.execute(db.text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception:
        health["checks"]["database"] = "unreachable"
        health["status"] = "degraded"

    # Check ChromaDB
    try:
        from services.embedding_service import get_collection
        col = get_collection()
        _ = col.count()
        health["checks"]["chromadb"] = "ok"
    except Exception:
        health["checks"]["chromadb"] = "unreachable"
        health["status"] = "degraded"

    status_code = 200 if health["status"] == "ok" else 503
    return jsonify(health), status_code

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    from models.database_models import Document
    documents = Document.query.filter_by(user_id=current_user.id).order_by(Document.uploaded_at.desc()).limit(5).all()
    return render_template('dashboard.html', user=current_user, documents=documents)

@main_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@main_bp.route('/knowledge-base')
def knowledge_base():
    from models.database_models import KnowledgeBase
    
    q = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()
    
    # Determine categories dynamically from the DB or a static list
    categories = ["Contract Law", "Civil Law", "Consumer Law", "Corporate Law", "Intellectual Property", "Cyber Law", "Employment Law", "Criminal Law", "Concepts"]
    
    query = KnowledgeBase.query
    if q:
        search_term = f"%{q}%"
        query = query.filter(db.or_(
            KnowledgeBase.title.ilike(search_term),
            KnowledgeBase.category.ilike(search_term),
            KnowledgeBase.content.ilike(search_term)
        ))
        
    if category_filter:
        query = query.filter(KnowledgeBase.category == category_filter)
        
    articles = query.order_by(KnowledgeBase.category, KnowledgeBase.title).all()
    return render_template('knowledge_base.html', articles=articles, categories=categories, current_q=q, current_category=category_filter)
