# DocuMind

DocuMind is an AI-powered document intelligence platform that allows users to upload documents, generate concise summaries, extract important information, and ask questions about the document using natural language.

The project was built to explore how modern AI applications combine large language models, vector search, and traditional backend development into a single system.

## Features

* **Interactive Knowledge Graph**: Document-level and global multi-document entity co-occurrence networks powered by Cytoscape.js
* **OCR Support**: Automatic PyMuPDF extraction with Tesseract OCR engine fallback for scanned documents and image files (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.docx`, `.txt`)
* **RAG Pipeline**: Sliding-window chunking (500 words with 50-word overlap), cited source snippets, and retrieval confidence scoring
* **Modern React Frontend**: Clean, dark-themed UI built with React 18, Vite, Tailwind CSS, and Lucide icons
* **PostgreSQL + pgvector**: Versioned schema with Alembic migrations, async access with SQLAlchemy 2.0 + asyncpg
* **User Authentication**: JWT bearer tokens, bcrypt password hashing

## Tech Stack

### Frontend
* **React 18** (Vite build system)
* **Tailwind CSS** (Dark mode styling)
* **Cytoscape.js** (Interactive graph visualization)
* **Lucide React** (Modern iconography)

### Backend
* **Python 3.13** / **FastAPI**
* **PostgreSQL 17 + pgvector**, **SQLAlchemy 2.0 (async)**, **Alembic**
* **Redis** (caching and rate limiting)
* **S3-compatible object storage** (SeaweedFS locally, Cloudflare R2 in production)
* **Tesseract OCR** & **PyMuPDF (fitz)**
* **FastEmbed ONNX** (`BAAI/bge-small-en-v1.5`, CPU-optimized)
* **Groq API** (model set by `GROQ_MODEL`, default `openai/gpt-oss-20b`)
* **spaCy** (`en_core_web_sm` NER)

## Architecture

```text
       React + Vite Frontend (Tailwind + Cytoscape.js)
                             |
                     REST / JSON  (/api/*)
                             |
                      FastAPI Backend
       ______________________|_______________________________
      |              |               |            |          |
  PyMuPDF &       spaCy NER       FastEmbed   PostgreSQL   Redis    S3 storage
  Tesseract    Entity Extraction    (ONNX)    + pgvector   (cache)  (files)
     OCR             |               |
      |       Knowledge Graph     Cosine
 Document      Co-occurrence    Similarity
 Parsing          Matrix        Search
      |______________________________|
                     |
         Groq LLM (RAG with Citations)
```

## Project Layout

```text
backend/
  app/
    core/       config (env settings), security (passwords, JWT)
    db/         SQLAlchemy models and async session
    api/        routes: auth, documents, health
    services/   extraction, OCR, NER, graph, RAG, LLM, storage, cache
    main.py     FastAPI app
  alembic/      database migrations
docker-compose.yml   Postgres + pgvector, Redis, SeaweedFS (S3), API
```

## Running Locally

You need [Docker](https://www.docker.com/products/docker-desktop/) and, for frontend work, Node.js.

### 1. Clone and configure

```bash
git clone https://github.com/Aum-Mangal/Documind.git
cd Documind
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set `SECRET_KEY` (at least 32 random characters) and `GROQ_API_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2a. Run everything in Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`. Migrations run automatically when the API container starts.

### 2b. Or run the API on your machine (with hot reload)

Start only the services, then the API:

```bash
docker compose up -d db redis s3
cd backend
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1    Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Make sure `DATABASE_URL` in `backend/.env` points at the local database (`postgresql://documind:documind@localhost:5432/documind`) and not at a hosted one.

For frontend hot-reloading: `cd frontend && npm install && npm run dev` (proxies `/api` to port 8000).

### Configuration

All settings come from environment variables or `backend/.env`; see [`backend/.env.example`](backend/.env.example) for the full list. The app refuses to start without a valid `SECRET_KEY` and a PostgreSQL `DATABASE_URL`.

### Database migrations

```bash
cd backend
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "describe it"  # create a migration after changing models
```

A database created by an older version of DocuMind can be upgraded in place with `alembic upgrade head`: the baseline migration detects the existing tables.

### Tests and linting

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .
pytest                      # no database or services needed

cd ../frontend
npm run lint

# against a running stack (docker compose up), using the SECRET_KEY from backend/.env:
python scripts/smoke_test.py --base http://127.0.0.1:8000 --secret-key "<SECRET_KEY>"
```

GitHub Actions runs the same checks on every push, plus migrations against a real Postgres + pgvector database (including upgrading a database created by the old schema) and a smoke test of the full Docker stack.

---

## API Endpoints

All `/api/documents` and `/api/graph` endpoints require an `Authorization: Bearer <access_token>` header, using the token returned by `/api/auth/login`. Set `ENABLE_API_DOCS=true` to browse them at `/api/docs`.

| Method | Endpoint                          | Description                                 |
| ------ | --------------------------------- | ------------------------------------------- |
| GET    | `/`                               | Serves the React single-page app            |
| GET    | `/api/health`                     | Liveness check                              |
| GET    | `/api/health/ready`               | Readiness: database, Redis, storage         |
| POST   | `/api/auth/signup`                | Register a new account                      |
| POST   | `/api/auth/login`                 | Authenticate and obtain a JWT               |
| POST   | `/api/documents`                  | Upload a document or scanned image          |
| GET    | `/api/documents`                  | List your documents                         |
| GET    | `/api/documents/{id}/entities`    | Named entities in a document                |
| GET    | `/api/documents/{id}/graph`       | Document entity co-occurrence graph         |
| POST   | `/api/documents/{id}/chat`        | RAG question answering with citations       |
| GET    | `/api/graph`                      | Cross-document entity graph                 |
