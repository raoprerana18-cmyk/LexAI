import os
import chromadb
from sentence_transformers import SentenceTransformer
from flask import current_app

# Lazy-loaded globals
_embedding_model = None
_chroma_client = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        # Load lightweight model suitable for local dev
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model

def get_chroma_client():
    global _chroma_client
    try:
        db_path = current_app.config.get('CHROMA_DB_PATH')
    except RuntimeError:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'chroma_db')
        
    global _current_chroma_path
    if _chroma_client is None or globals().get('_current_chroma_path') != db_path:
        os.makedirs(db_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=db_path)
        globals()['_current_chroma_path'] = db_path
        
    return _chroma_client

def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name="lexai_documents")

def chunk_text(text, chunk_size=1000, overlap=150):
    """
    Splits text into meaningful chunks using a simple word-based sliding window.
    """
    if not text:
        return []
    
    words = text.split()
    chunks = []
    
    i = 0
    while i < len(words):
        end = min(i + chunk_size, len(words))
        chunk_words = words[i:end]
        chunk = " ".join(chunk_words)
        chunks.append(chunk)
        
        # Advance by chunk_size - overlap, unless it causes an infinite loop
        step = chunk_size - overlap
        if step <= 0:
            step = chunk_size
            
        i += step
        
    return chunks

def index_document(document_id, text, user_id, filename):
    """
    Chunks the document text, generates embeddings, and stores in ChromaDB.
    """
    if not text:
        return False
        
    try:
        chunks = chunk_text(text)
        if not chunks:
            return True # Nothing to index, but not a failure
            
        model = get_embedding_model()
        collection = get_collection()
        
        # Generate embeddings in batch
        embeddings = model.encode(chunks, convert_to_numpy=True).tolist()
        
        ids = []
        metadatas = []
        documents = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i
            })
            
        # Add to ChromaDB
        collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        return True
    except Exception as e:
        print(f"Failed to index document {document_id}: {e}")
        return False

def delete_document_vectors(document_id, user_id):
    """
    Deletes all vectors for a given document from ChromaDB.
    Enforces user_id for security.
    """
    try:
        collection = get_collection()
        # ChromaDB allows deleting by where clause
        collection.delete(
            where={
                "$and": [
                    {"document_id": {"$eq": document_id}},
                    {"user_id": {"$eq": user_id}}
                ]
            }
        )
        return True
    except Exception as e:
        print(f"Failed to delete vectors for document {document_id}: {e}")
        return False

def embed_question(question):
    """
    Converts user question into an embedding.
    """
    model = get_embedding_model()
    return model.encode(question, convert_to_numpy=True).tolist()

def index_kb_entry(kb_id, title, category, content, source):
    """
    Chunks a Knowledge Base entry, embeds it, and stores in ChromaDB.
    """
    if not content:
        return False
    try:
        chunks = chunk_text(content)
        if not chunks:
            return True
            
        model = get_embedding_model()
        collection = get_collection()
        
        embeddings = model.encode(chunks, convert_to_numpy=True).tolist()
        
        ids = []
        metadatas = []
        documents = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"kb_{kb_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "source_type": "knowledge_base",
                "knowledge_base_id": str(kb_id),
                "category": category,
                "title": title,
                "source": source or "LexAI KB",
                "chunk_index": i
            })
            
        collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        return True
    except Exception as e:
        print(f"Failed to index KB entry {kb_id}: {e}")
        return False

def delete_kb_vectors(kb_id):
    """
    Deletes all vectors for a given KB entry from ChromaDB.
    """
    try:
        collection = get_collection()
        collection.delete(
            where={"knowledge_base_id": {"$eq": str(kb_id)}}
        )
        return True
    except Exception as e:
        print(f"Failed to delete vectors for KB entry {kb_id}: {e}")
        return False
