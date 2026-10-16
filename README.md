# LexAI - AI Legal Assistant & Contract Intelligence Platform

## Project Purpose
LexAI is a Web-Based AI Legal Assistant designed as an academic project. It provides secure, automated legal document analysis, custom document chatbot conversations using Retrieval-Augmented Generation (RAG), and a curated Legal Knowledge Base.

---

## Technology Stack
* **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons
* **Backend**: Python 3.11+, Flask Web Framework
* **Database**: MySQL 9.x (Relational Storage), SQLAlchemy ORM
* **Vector Database**: ChromaDB (Vector Search Storage)
* **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (Local Execution)
* **LLM Model**: Google Gemini (`gemini-3.6-flash` via the official `google-genai` SDK)

---

## Installation & Setup

### 1. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# Install required libraries
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory based on `.env.example`:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=lexai_db

GEMINI_API_KEY=your_gemini_api_key
AI_MODEL=gemini-3.6-flash
SECRET_KEY=generate_a_random_flask_key
```

### 3. Initialize Databases
1. Ensure your local MySQL instance is running.
2. Initialize tables and admin account:
```bash
python init_db.py
python create_admin.py
```
3. Run Phase 5 Knowledge Base schema migrations:
```bash
python migrate_phase5.py
```

### 4. Running the Application
```bash
# Set Flask entrypoint
$env:FLASK_APP="app.py"
# Launch development server
flask run
```
Access the interface at: `http://127.0.0.1:5000`

---

## Retrieval-Augmented Generation (RAG) Architecture

```
                    ┌──────────────────┐
                    │   Bootstrap UI   │
                    │   HTML/CSS/JS    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │      Flask       │
                    │   Routes & APIs  │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
         MySQL            ChromaDB         Gemini
      (Relational)        (Vectors)      (AI Gen)
```

### RAG Search Scope & Isolation
LexAI implements strict user data separation at the query execution level. 
* **Specific Document Chat**: Chunks are retrieved from ChromaDB filtered by `user_id` AND `document_id`.
* **General Chat**: Combines search results from the user's private documents (`user_id` filter) and public Knowledge Base articles (`source_type = "knowledge_base"` metadata filter).
* **Strict Privacy Isolation**: Under no circumstances can User A retrieve documents or vectors belonging to User B.

---

## Critical Test Database Isolation
To prevent accidental data loss in production:
* Tests always run against a dedicated `LexAI_test` database (configured in `config.TestConfig`).
* A mandatory safety check is defined in `tests/conftest.py` that intercepts startup and execution. If the configured database name resolves to the production `lexai_db`, the suite immediately halts execution and refuses any teardown (`db.drop_all()`).

Run the automated tests:
```bash
pytest -v
```

---

## Disclaimer
**LexAI provides AI-generated legal information for informational purposes only and does not constitute professional legal advice.**
