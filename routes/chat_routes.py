from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from extensions import db
from models.database_models import Document, Conversation, Message
from services.rag_service import answer_question
import traceback

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat', methods=['GET'])
@chat_bp.route('/chat/<int:document_id>', methods=['GET'])
@login_required
def chat_ui(document_id=None):
    doc = None
    if document_id:
        doc = db.get_or_404(Document, document_id)
        if doc.user_id != current_user.id and current_user.role != 'admin':
            abort(403)

    conversation_id = request.args.get('conversation_id', type=int)

    if conversation_id:
        conversation = db.get_or_404(Conversation, conversation_id)
        if conversation.user_id != current_user.id:
            abort(403)

    conversations = Conversation.query.filter_by(
        user_id=current_user.id
    ).order_by(Conversation.updated_at.desc()).all()
    print("DATABASE:", db.engine.url.database)
    print("USER ID:", current_user.id)
    documents = Document.query.filter_by(
        user_id=current_user.id, status='completed'
    ).all()

    return render_template(
        'chatbot.html',
        document=doc,
        conversations=conversations,
        documents=documents,
        conversation_id=conversation_id
    )
@chat_bp.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.json
    question = data.get('message')
    document_id = data.get('document_id') or None
    conversation_id = data.get('conversation_id') or None
    
    if not question:
        return jsonify({"error": "Message is required"}), 400
        
    doc = None
    if document_id:
        doc = db.session.get(Document, document_id)
        if not doc or (doc.user_id != current_user.id and current_user.role != 'admin'):
            return jsonify({"error": "Unauthorized document"}), 403

    try:
        # Load or create conversation
        if conversation_id:
            conversation = db.session.get(Conversation, conversation_id)
            if not conversation or conversation.user_id != current_user.id:
                return jsonify({"error": "Unauthorized conversation"}), 403
        else:
            title = doc.original_filename if doc else "General Chat"
            conversation = Conversation(user_id=current_user.id, document_id=document_id, title=title)
            db.session.add(conversation)
            db.session.commit()
            
        # Save user message
        user_msg = Message(conversation_id=conversation.id, sender='user', message=question)
        db.session.add(user_msg)
        
        # Get AI response via RAG
        rag_result = answer_question(current_user.id, question, document_id)
        
        # Save AI message
        ai_msg = Message(conversation_id=conversation.id, sender='ai', message=rag_result['answer'])
        db.session.add(ai_msg)
        
        # Update conversation timestamp
        conversation.updated_at = db.func.current_timestamp()
        
        db.session.commit()
        
        return jsonify({
            "conversation_id": conversation.id,
            "answer": rag_result['answer'],
            "sources": rag_result['sources']
        })
        
    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Chat API Error: {traceback.format_exc()}")
        
        error_msg = str(e).lower()
        status_code = 500
        if "quota" in error_msg or "429" in error_msg or "busy" in error_msg:
            status_code = 429
            
        return jsonify({
            "success": False,
            "error": str(e)
        }), status_code

@chat_bp.route('/api/conversations/<int:conversation_id>/messages', methods=['GET'])
@login_required
def get_messages(conversation_id):
    conversation = db.get_or_404(Conversation, conversation_id)
    if conversation.user_id != current_user.id:
        abort(403)
        
    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.created_at.asc()).all()
    
    return jsonify({
        "messages": [
            {"sender": m.sender, "message": m.message, "created_at": m.created_at.isoformat()}
            for m in messages
        ]
    })


@chat_bp.route('/history', methods=['GET'])
@login_required
def chat_history():
    print("DATABASE:", db.engine.url.database)
    print("USER ID:", current_user.id)

    conversations = Conversation.query.filter_by(
        user_id=current_user.id
    ).order_by(Conversation.updated_at.desc()).all()

    print("CHAT HISTORY COUNT:", len(conversations))

    return render_template(
        'chat_history.html',
        conversations=conversations
    )
