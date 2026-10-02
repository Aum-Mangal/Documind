# DocuMind

DocuMind is an AI-powered document intelligence platform that allows users to upload documents, generate concise summaries, extract important information, and ask questions about the document using natural language.

The project was built to explore how modern AI applications combine large language models, vector search, and traditional backend development into a single system.

## Features

* User authentication using JWT
* Upload PDF, DOCX, and TXT documents
* AI-generated document summaries using Groq Llama 3.1
* Named Entity Recognition (NER) for extracting people, organizations, dates, and locations
* Chat with uploaded documents using Retrieval-Augmented Generation (RAG)
* Personal dashboard to manage uploaded documents

## Tech Stack

### Frontend

* HTML
* CSS
* JavaScript

### Backend

* Python
* FastAPI
* SQLAlchemy
* PostgreSQL (Supabase)
* JWT Authentication

### AI & Machine Learning

* Groq API
* Llama 3.1
* FastEmbed (ONNX Runtime — CPU Optimized)
* spaCy

### Deployment

* Render (Free Web Service) — Backend
* Vercel — Frontend
* Supabase — Database

## Architecture

```text
                 Browser
                     |
                     |
         HTML / CSS / JavaScript
                     |
                     |
               FastAPI Backend
                     |
     ------------------------------------
     |                |                 |
     |                |                 |
 Groq Llama 3.1     spaCy NER      PostgreSQL
                                      |
                                      |
                                   Supabase
                     |
                     |
                 FastEmbed (ONNX)
                     |
                     |
             NumPy Similarity
```

## Running Locally

### Clone the repository

```bash
git clone https://github.com/Aum-Mangal/documind.git
cd documind
```

### Backend Setup

```bash
cd backend

python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Create a `.env` file inside the `backend/` folder

```env
DATABASE_URL=your_supabase_database_url
SECRET_KEY=your_secret_key
GROQ_API_KEY=your_groq_api_key
```

### Run the backend

```bash
uvicorn main:app --reload
```

The backend will start at `http://127.0.0.1:8000`.  
Swagger docs available at `http://127.0.0.1:8000/docs`.

### Run the frontend

Open `frontend/index.html` in your browser, or serve it with any static file server.

---

## Deploying to Render (Free Tier)

DocuMind is optimized with **FastEmbed ONNX runtime** to run under **220 MB RAM**, fitting easily inside Render's **512 MB Free Web Service** tier.

### 1. Connect GitHub Repository to Render

1. Go to [render.com](https://render.com) and log in.
2. Click **New +** → **Web Service**.
3. Connect your `documind` GitHub repository.

### 2. Configure Service Settings

* **Name**: `documind-backend`
* **Environment**: `Python 3`
* **Build Command**: `pip install -r backend/requirements.txt`
* **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Add Environment Variables

Under **Environment Variables**, add:

| Key            | Value                        |
|----------------|------------------------------|
| `DATABASE_URL` | Your Supabase connection URL |
| `SECRET_KEY`   | Your JWT secret key          |
| `GROQ_API_KEY` | Your Groq API key            |

Click **Create Web Service**. Render will deploy your backend!

### 4. Update the Frontend API URL

Once deployed, copy your Render URL (e.g., `https://documind-backend.onrender.com`).  
Open [`frontend/config.js`](file:///c:/Users/Saran/documind/frontend/config.js) and update `DEFAULT_API_URL`:

```js
const DEFAULT_API_URL = "https://documind-backend.onrender.com";
```

---

## API Endpoints

| Method | Endpoint                        | Description                      |
| ------ | ------------------------------- | -------------------------------- |
| GET    | `/`                             | Health check / API root          |
| GET    | `/health`                       | Health probe                     |
| POST   | `/auth/signup`                  | Register a new user              |
| POST   | `/auth/login`                   | Authenticate a user              |
| POST   | `/docs/upload`                  | Upload a document                |
| GET    | `/docs/documents`               | Retrieve uploaded documents      |
| GET    | `/docs/documents/{id}/entities` | Extract entities from a document |
| POST   | `/docs/documents/{id}/chat`     | Ask questions about a document   |

## Future Improvements

* OCR support for scanned PDFs
* Multi-document conversations
* Semantic search across all uploaded documents
* Document sharing
* Better frontend interface
