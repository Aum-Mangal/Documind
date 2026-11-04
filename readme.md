# DocuMind

DocuMind is an AI-powered document intelligence platform that allows users to upload documents, generate concise summaries, extract important information, and ask questions about the document using natural language.

The project was built to explore how modern AI applications combine large language models, vector search, and traditional backend development into a single system.

## Features

* **Interactive Knowledge Graph**: Document-level and global multi-document entity co-occurrence networks powered by Cytoscape.js
* **OCR Support**: Automatic PyMuPDF extraction with Tesseract OCR engine fallback for scanned documents and image files (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.docx`, `.txt`)
* **Background ingestion**: uploads return immediately; a crash-safe Postgres job queue (`FOR UPDATE SKIP LOCKED`, retries with backoff, stale-job recovery) extracts text page by page, OCRs only scanned pages, and embeds sentence-aware chunks into pgvector, with live progress over server-sent events
* **Hybrid retrieval**: pgvector HNSW similarity and Postgres full-text search fused with Reciprocal Rank Fusion in a single SQL query, then reranked by a cross-encoder
* **Grounded chat**: answers cite the document and page of each passage, decline when nothing relevant is found, and treat document text as untrusted data; conversations are saved, can span all documents or a chosen few, and follow-up questions are rewritten into standalone searches
* **Limits and caching**: Redis-backed rate limits on sign-in, sign-up, chat and uploads; per-user daily AI token and storage quotas; cached query embeddings and answers (invalidated automatically when documents change); logout revokes the token. Without Redis everything falls back to in-memory, and a Redis outage fails open rather than locking users out
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
* **FastEmbed ONNX** (`BAAI/bge-small-en-v1.5` embeddings, `ms-marco-MiniLM-L-6-v2` reranker, CPU-only)
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
pytest                      # unit tests: no database or services needed

# integration tests against a real Postgres + pgvector (e.g. the compose one); the named
# database is dropped and recreated
TEST_DATABASE_URL=postgresql://documind:documind@localhost:5432/documind_test pytest tests/integration

cd ../frontend
npm run lint

# against a running stack (docker compose up), using the SECRET_KEY from backend/.env:
python scripts/smoke_test.py --base http://127.0.0.1:8000 --secret-key "<SECRET_KEY>"
```

GitHub Actions runs the same checks on every push, plus migrations against a real Postgres + pgvector database (including upgrading a database created by the old schema) and a smoke test of the full Docker stack.

## Evaluation

`backend/eval` measures retrieval on a **synthetic** corpus: 6 fictional company documents (25 PDF pages) with 66 labelled questions (lookups, paraphrases, exact codes and numbers, cross-document distractors) and 8 unanswerable ones. The PDFs go through the real ingestion pipeline, and a hit is a retrieved passage from the right document containing the labelled evidence phrase.

| Mode | Recall@1 | Recall@5 | MRR@10 | p50 latency |
|---|---|---|---|---|
| vector | 82% | 98% | 0.894 | 8 ms |
| keyword | 67% | 96% | 0.802 | 7 ms |
| hybrid | 82% | 98% | 0.896 | 7 ms |
| hybrid+rerank | 89% | 98% | 0.936 | 324 ms |

End to end with the LLM (`openai/gpt-oss-20b`): 97% of answerable questions answered, 100% of those citing a passage that contains the evidence, and 100% of unanswerable questions declined. The reranker threshold only declines clearly unrelated questions; near-misses ("revenue in Q2 2025" when the report covers Q3 2026) are declined by the model, which is told to answer only from the sources.

What the evaluation changed:
- Keyword search required every term of a question to match, which natural questions rarely do: keyword-only recall@5 was 30%. Matching any term, ranked by `ts_rank_cd`, raised it to 96%.
- With keyword search now strong, equal-weight fusion let its less precise top hits displace better vector hits (hybrid recall@1 fell from 83% to 73%); a keyword weight of 0.5 in Reciprocal Rank Fusion restored it.
- Reranking the top 10 candidates instead of 30 gave identical quality at about 40% lower latency.
- The abstention threshold was chosen from a sweep over the same scores (see `eval/results/end-to-end.md`).

This corpus is small enough that vector search alone already performs well; treat the numbers as a regression baseline, not a benchmark. CI runs the retrieval part on every push and fails if hybrid+rerank recall@5 drops below 0.95 or MRR below 0.90.

```bash
cd backend
python -m eval.run --database-url postgresql://documind:documind@localhost:5432/documind_eval            # retrieval only, no LLM
python -m eval.run --database-url postgresql://documind:documind@localhost:5432/documind_eval --with-llm # also end to end (~110k Groq tokens)
```

---

## API Endpoints

All `/api/documents` and `/api/graph` endpoints require an `Authorization: Bearer <access_token>` header, using the token returned by `/api/auth/login`. Set `ENABLE_API_DOCS=true` to browse them at `/api/docs`.

| Method | Endpoint                          | Description                                       |
| ------ | --------------------------------- | ------------------------------------------------- |
| GET    | `/`                               | Serves the React single-page app                  |
| GET    | `/api/health`                     | Liveness check                                    |
| GET    | `/api/health/ready`               | Readiness: database, Redis, storage               |
| POST   | `/api/auth/signup`                | Register a new account                            |
| POST   | `/api/auth/login`                 | Authenticate and obtain a JWT                     |
| POST   | `/api/auth/logout`                | Revoke the current token                          |
| GET    | `/api/auth/me`                    | Current user and quota usage                      |
| POST   | `/api/documents`                  | Upload a file; returns 202 and processes it in the background |
| GET    | `/api/documents`                  | List your documents with processing status        |
| GET    | `/api/documents/{id}`             | One document                                      |
| GET    | `/api/documents/{id}/events`      | Live processing progress (server-sent events)     |
| GET    | `/api/documents/{id}/file`        | Download the original file                        |
| POST   | `/api/documents/{id}/reprocess`   | Process a document again                          |
| DELETE | `/api/documents/{id}`             | Delete a document, its file and its passages      |
| GET    | `/api/documents/{id}/entities`    | Named entities in a document                      |
| GET    | `/api/documents/{id}/graph`       | Document entity co-occurrence graph               |
| GET    | `/api/graph`                      | Cross-document entity graph                       |
| POST   | `/api/chat`                       | Ask a question (new or existing conversation)     |
| GET    | `/api/conversations`              | List saved conversations                          |
| GET    | `/api/conversations/{id}`         | A conversation with its messages                  |
| DELETE | `/api/conversations/{id}`         | Delete a conversation                             |
