import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from models.database_models import Document, DocumentAnalysis
from extensions import db
from services.document_service import validate_file, save_uploaded_file, process_document
from services.ai_service import analyze_legal_document

document_bp = Blueprint('document', __name__)

@document_bp.route('/analysis')
@login_required
def analysis_redirect():
    return redirect(url_for('document.upload'))

@document_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(request.url)
            
        try:
            # Check file size (15MB max)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            if file_size > 15 * 1024 * 1024:
                flash('File is too large. Maximum size is 15 MB.', 'danger')
                return redirect(request.url)
            file.seek(0)
            
            # Save file and db record
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            doc = save_uploaded_file(file, current_user.id, upload_folder)
            
            # Process document text extraction (synchronously for now to keep Phase 2 simple)
            success = process_document(doc.id)
            if success:
                flash(f'Document {doc.original_filename} uploaded and processed successfully!', 'success')
            else:
                flash(f'Document {doc.original_filename} uploaded but text extraction failed.', 'warning')
                
            return redirect(url_for('document.analysis', document_id=doc.id))
            
        except Exception as e:
            flash(f'An error occurred during upload: {str(e)}', 'danger')
            return redirect(request.url)
            
    return render_template('upload.html')

@document_bp.route('/document-history')
@login_required
def history():
    user_docs = Document.query.filter_by(
        user_id=current_user.id
    ).order_by(Document.uploaded_at.desc()).all()

    return render_template(
        'document_history.html',
        documents=user_docs
    )
@document_bp.route('/analyze/<int:document_id>', methods=['POST'])
@login_required
def analyze(document_id):
    doc = db.get_or_404(Document, document_id)
    
    # Ownership check
    if doc.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
        
    if not doc.extracted_text:
        flash('No extracted text available for analysis.', 'danger')
        return redirect(url_for('document.analysis', document_id=doc.id))
        
    try:
        # Perform AI analysis
        result_json = analyze_legal_document(doc.extracted_text)
        
        # Check if an analysis already exists for this document
        analysis_record = DocumentAnalysis.query.filter_by(document_id=doc.id).first()
        if not analysis_record:
            analysis_record = DocumentAnalysis(document_id=doc.id, user_id=current_user.id)
            db.session.add(analysis_record)
            
        # Update the record with structured data
        analysis_record.document_type = result_json.get('document_type')
        analysis_record.summary = result_json.get('summary')
        analysis_record.parties = result_json.get('parties')
        analysis_record.key_clauses = result_json.get('key_clauses')
        analysis_record.important_dates = result_json.get('important_dates')
        analysis_record.obligations = result_json.get('obligations')
        analysis_record.risks = result_json.get('risks')
        analysis_record.red_flags = result_json.get('red_flags')
        analysis_record.financial_terms = result_json.get('financial_terms')
        analysis_record.termination_conditions = result_json.get('termination_conditions')
        analysis_record.rights = result_json.get('rights')
        analysis_record.recommendations = result_json.get('recommendations')
        analysis_record.confidence = result_json.get('confidence')
        analysis_record.disclaimer = result_json.get('disclaimer')
        
        db.session.commit()
        flash('AI Analysis completed successfully.', 'success')
        
    except ValueError as ve:
        db.session.rollback()
        error_msg = str(ve)
        if "temporarily unavailable" in error_msg:
            flash(error_msg, 'warning')
        elif "AI Analysis failed" in error_msg:
            flash(error_msg, 'danger')
        else:
            flash(f'Validation error: {error_msg}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during AI analysis: {str(e)}', 'danger')
        
    return redirect(url_for('document.analysis', document_id=doc.id))

@document_bp.route('/analysis/<int:document_id>')
@login_required
def analysis(document_id):
    doc = db.get_or_404(Document, document_id)
    
    # Ownership check
    if doc.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
        
    analysis_record = DocumentAnalysis.query.filter_by(document_id=doc.id).first()
    return render_template('analysis.html', document=doc, analysis=analysis_record)

@document_bp.route('/delete/<int:document_id>', methods=['POST'])
@login_required
def delete(document_id):
    doc = db.get_or_404(Document, document_id)
    
    # Ownership check
    if doc.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
        
    try:
        # Delete vectors from ChromaDB
        from services.embedding_service import delete_document_vectors
        delete_document_vectors(str(doc.id), doc.user_id)

        # Delete physical file and its folder
        file_dir = os.path.dirname(doc.file_path)
        if os.path.exists(file_dir):
            shutil.rmtree(file_dir)
            
        # Delete DB record
        db.session.delete(doc)
        db.session.commit()
        
        flash('Document deleted successfully.', 'success')
    except Exception as e:
        flash(f'An error occurred while deleting the document: {str(e)}', 'danger')
        
    return redirect(url_for('document.history'))

@document_bp.route('/index/<int:document_id>', methods=['POST'])
@login_required
def index(document_id):
    doc = db.get_or_404(Document, document_id)
    
    # Ownership check
    if doc.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
        
    if not doc.extracted_text:
        flash('No text to index. Please wait for extraction.', 'warning')
        return redirect(url_for('document.analysis', document_id=doc.id))
        
    from services.embedding_service import delete_document_vectors, index_document
    
    # Re-indexing: delete existing vectors first
    delete_document_vectors(str(doc.id), doc.user_id)
    
    success = index_document(str(doc.id), doc.extracted_text, doc.user_id, doc.original_filename)
    if success:
        doc.status = 'completed'
        db.session.commit()
        flash('Document indexed successfully for chat.', 'success')
    else:
        doc.status = 'indexed_failed'
        db.session.commit()
        flash('Failed to index document.', 'danger')
        
    return redirect(url_for('document.analysis', document_id=doc.id))
