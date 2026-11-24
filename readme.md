# DocuMind

DocuMind is a document intelligence app you run on your own computer: upload PDFs, Word files, text files or scanned images, read short AI summaries, explore the people, organisations and places they mention as a knowledge graph, and ask questions answered from the documents themselves, with citations to the exact page.

Everything runs locally in Docker: your documents and the database stay on your machine. The only outside service is the Groq API, which writes the answers and summaries (free key, optional).

## Quick start

You need **Docker Desktop** ([Windows / macOS](https://www.docker.com/products/docker-desktop/)) or Docker Engine on Linux, running.

1. **Get the code**: `git clone https://github.com/Aum-Mangal/Documind.git` then `cd Documind`, or download the ZIP from GitHub (*Code → Download ZIP*) and unzip it.

2. **Add your AI key** (optional but recommended): get a free key at [console.groq.com/keys](https://console.groq.com/keys), then copy the settings template:

   ```bash
   cp backend/.env.example backend/.env
   ```

   (Windows PowerShell: `copy backend\.env.example backend\.env`.) Open `backend/.env` and set `GROQ_API_KEY=your-key`. Leave everything else as it is.

3. **Start it.** The first build downloads the models and takes about 5–10 minutes; later starts take seconds.

   ```bash
   docker compose up --build
   ```

4. Open **http://localhost:8000**, create an account and upload a document.

| To... | Run |
|---|---|
| Stop it (your documents are kept) | `docker compose down` |
| Start it again | `docker compose up` |
| Update after pulling new code | `docker compose up --build` |
| Delete everything, including all documents and accounts | `docker compose down -v` |

Without a Groq key everything except the AI-written parts works: uploads, search, entities and the knowledge graph. Summaries are skipped, and questions return a message saying AI isn't configured.

**Troubleshooting**
- *"Waiting for the server" banner*: the app is still starting (watch the terminal), or Docker isn't running.
- *Port already in use*: something else uses port 8000, 5432, 6379 or 8333. Stop it, or change the left-hand port numbers in `docker-compose.yml`.
- *"I couldn't find that in your documents"*: open the document (or choose it on the Ask page) and ask there; questions across the whole library only use the passages that match best.

## Features

* **Knowledge graph**: built once at ingestion and stored in Postgres. spaCy finds people, organisations, places and products (dates and numbers are left out); names are normalised and aliases merged within and across documents ("Ms Okafor" → "Maria Okafor", "Northwind" → "Northwind Supply"); the LLM corrects entity types and extracts typed relations ("Halden & Rowe —appointed→ Maria Okafor") from the most entity-dense passages, restricted to the names found so it cannot invent nodes. Shown with Cytoscape.js as labelled arrows plus co-occurrence links
* **OCR**: PyMuPDF text extraction with Tesseract OCR for scanned pages and images (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.docx`, `.txt`)
* **Background ingestion**: uploads return immediately; a crash-safe Postgres job queue (`FOR UPDATE SKIP LOCKED`, retries with backoff, stale-job recovery) extracts text page by page, OCRs only scanned pages, and embeds sentence-aware chunks into pgvector, with live progress over server-sent events
* **Hybrid retrieval**: pgvector HNSW similarity and Postgres full-text search fused with Reciprocal Rank Fusion in a single SQL query, then reranked by a cross-encoder
* **Grounded chat**: answers cite the document and page of each passage and treat document text as untrusted data; short chosen documents are read whole, so "summarise this" works; the model may rate or critique a document when asked, citing what it bases that on; conversations are saved, can span all documents or a chosen few, and follow-up questions are rewritten into standalone searches
* **Limits and caching**: Redis-backed rate limits on sign-in, sign-up, chat and uploads; per-user daily AI token and storage quotas; cached query embeddings and answers (invalidated automatically when documents change); logout revokes the token
* **Frontend**: React 18, Vite and Tailwind CSS with a warm paper palette, Lucide icons
* **PostgreSQL + pgvector**: versioned schema with Alembic migrations, async access with SQLAlchemy 2.0 + asyncpg
* **Accounts**: JWT bearer tokens and bcrypt password hashing; several people can share one installation, each seeing only their own documents

## Tech Stack

### Frontend
* **React 18** (Vite build system)
* **Tailwind CSS**
* **Cytoscape.js** (interactive graph visualization)
* **Lucide React** (icons)

### Backend
* **Python 3.13** / **FastAPI**
* **PostgreSQL 17 + pgvector**, **SQLAlchemy 2.0 (async)**, **Alembic**
* **Redis** (caching and rate limiting)
* **S3-compatible object storage** for uploaded files (SeaweedFS in Docker)
* **Tesseract OCR** & **PyMuPDF (fitz)**
* **FastEmbed ONNX** (`BAAI/bge-small-en-v1.5` embeddings, `ms-marco-MiniLM-L-6-v2` reranker, CPU-only, built into the image)
* **Groq API** (model set by `GROQ_MODEL`, default `openai/gpt-oss-20b`)
* **spaCy** (`en_core_web_sm` NER)

## Architecture

```text
       React + Vite Frontend (Tailwind + Cytoscape.js)
                             |
                     REST / JSON  (/api/*)
                             |
                      FastAPI Backend  --  ingestion worker (Postgres job queue)
       ______________________|_______________________________
      |              |               |            |          |
  PyMuPDF &       spaCy NER       FastEmbed   PostgreSQL   Redis    S3 storage
  Tesseract    + LLM relations   + reranker   + pgvector   (cache)  (files)
     OCR             |               |
      |       Knowledge graph   Hybrid search
      |______________________________|
                     |
         Groq LLM (answers with citations)
```

## Project Layout

```text
backend/
  app/
    core/        config (env settings), security, logging, rate limits
    db/          SQLAlchemy models and async session
    api/         routes: auth, documents, chat, health
    ingestion/   job queue worker, pipeline, chunking, progress events
    retrieval/   hybrid search, reranking, answers, caches
    knowledge/   entities, LLM relations, graph storage and queries
    services/    extraction, OCR, embeddings, LLM, storage, quotas
    main.py      FastAPI app
  alembic/       database migrations
  eval/          retrieval evaluation: corpus, labelled questions, runner, results
  tests/         unit tests; tests/integration needs a Postgres database
frontend/        React app
docker-compose.yml   Postgres + pgvector, Redis, SeaweedFS (S3), the app
scripts/             smoke test and k6 load test
```

## Performance

`scripts/loadtest.js` (k6) with 10 concurrent users for 2 minutes against the Docker stack on a laptop CPU, with no LLM calls: 0% errors; listing documents and conversations p95 180 ms; a cached answer p95 192 ms; a full search (query embedding, hybrid search and reranking) median 216 ms, p95 1.23 s.

```bash
docker run --rm -i -e BASE=http://host.docker.internal:8000 grafana/k6:1.8.2 run - < scripts/loadtest.js
```

## Development

### Run the API outside Docker (with hot reload)

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

Outside Docker, `backend/.env` needs a `SECRET_KEY` (see the comment there) and `DATABASE_URL=postgresql://documind:documind@localhost:5432/documind`.

For frontend hot-reloading: `cd frontend && npm install && npm run dev` (proxies `/api` to port 8000). To have uvicorn serve the UI itself instead, build it once with `npm run build` (the Docker image does this automatically).

### Configuration

All settings come from environment variables or `backend/.env`; see [`backend/.env.example`](backend/.env.example) for the full list, including rate limits and quotas.

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
- The abstention threshold was first chosen from a sweep over the same scores. Real documents then showed its limit: the reranker scores vague questions ("summarise this", "how would you rate it") and list-like text such as CVs around -9 to -11 even when they are answerable. The pre-LLM cutoff now applies only to questions across the whole library, at -10.5; questions about documents the user chose always reach the model, and short chosen documents (up to 12 chunks) are given to it whole. The end-to-end figures above were measured before this change and the move to allowing grounded assessments; re-run with `--with-llm` to refresh them.

- Graph-assisted retrieval (passages mentioning entities named in the question, as a third ranked list) lowered hybrid recall@1 from 82% to 73% and left hybrid+rerank unchanged, because every passage naming a common entity qualifies. It ships switched off (`RRF_GRAPH_WEIGHT=0`) and stays in the evaluation as an ablation.

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
