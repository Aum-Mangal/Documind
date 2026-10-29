# DocuMind

DocuMind is an AI-powered document intelligence platform that allows users to upload documents, generate concise summaries, extract important information, and ask questions about the document using natural language.

The project was built to explore how modern AI applications combine large language models, vector search, and traditional backend development into a single system.

## Features

* **Interactive Knowledge Graph**: Document-level and global multi-document entity co-occurrence networks powered by Cytoscape.js
* **OCR Support**: Automatic PyMuPDF extraction with Tesseract OCR engine fallback for scanned documents and image files (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`, `.txt`)
* **Upgraded RAG Pipeline**: Sliding-window chunking (500 words with 100-word overlap), exact cited source snippets, and response confidence scoring
* **Modern React Frontend**: Clean, dark-themed UI built with React 18, Vite, Tailwind CSS, and Lucide icons
* **Zero-Config Database**: Seamless local SQLite fallback (`sqlite:///./documind.db`) alongside optional PostgreSQL / Supabase
* **User Authentication**: Secure JWT-based registration and token persistence

## Tech Stack

### Frontend
* **React 18** (Vite build system)
* **Tailwind CSS** (Dark mode styling)
* **Cytoscape.js** (Interactive graph visualization)
* **Lucide React** (Modern iconography)

### Backend
* **Python 3.11** / **FastAPI**
* **SQLAlchemy** (SQLite & PostgreSQL support)
* **Tesseract OCR** & **PyMuPDF (fitz)**
* **FastEmbed ONNX** (`BAAI/bge-small-en-v1.5`, CPU-optimized)
* **Groq API** (`llama-3.3-70b-versatile`)
* **spaCy** (`en_core_web_sm` NER)

## Architecture

```text
       React + Vite Frontend (Tailwind + Cytoscape.js)
                             |
                      REST / JSON API
                             |
                      FastAPI Backend
       ______________________|______________________
      |              |               |              |
  PyMuPDF &       spaCy NER       FastEmbed     SQLite /
  Tesseract    Entity Extraction    (ONNX)     PostgreSQL
     OCR             |               |              |
      |       Knowledge Graph     Cosine       Persistent
 Document      Co-occurrence    Similarity      Storage
 Parsing          Matrix        Search Engine
      |______________________________|
                     |
         Groq LLM (RAG with Citations)
```

## Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/Aum-Mangal/Documind.git
cd Documind
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root or `backend/` folder:

```env
# Optional: defaults to local SQLite (sqlite:///./documind.db) if omitted
DATABASE_URL=sqlite:///./documind.db
# Required, at least 32 random characters. The server refuses to start without it.
# Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=
GROQ_API_KEY=your_groq_api_key

# Optional
CORS_ORIGINS=            # comma-separated origins, only needed if the frontend is on another domain
ENABLE_API_DOCS=false    # true serves Swagger UI at /api-docs (keep off in production)
MAX_UPLOAD_MB=20
MAX_PDF_PAGES=200
ACCESS_TOKEN_TTL_HOURS=24
```

### 4. Run the Full Application

FastAPI directly serves the compiled React SPA:

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

*(For frontend development with hot-reloading: `cd frontend && npm install && npm run dev`)*

---

## API Endpoints

All `/docs/*` endpoints require an `Authorization: Bearer <access_token>` header, using the token returned by `/auth/login`.

| Method | Endpoint                        | Description                              |
| ------ | ------------------------------- | ---------------------------------------- |
| GET    | `/`                             | Serves React Single Page Application     |
| GET    | `/health`                       | Health & readiness check                 |
| POST   | `/auth/signup`                  | Register a new account                   |
| POST   | `/auth/login`                   | Authenticate and obtain JWT token        |
| POST   | `/docs/upload`                  | Upload document or scanned image         |
| GET    | `/docs/documents`               | Retrieve user documents & metadata       |
| GET    | `/docs/documents/{id}/graph`    | Document entity co-occurrence graph      |
| GET    | `/docs/graph/global`            | Multi-document cross-entity graph        |
| POST   | `/docs/documents/{id}/chat`     | RAG question-answering with citations    |
