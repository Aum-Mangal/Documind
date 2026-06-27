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
* Sentence Transformers
* FAISS
* spaCy

### Deployment

* Railway
* Vercel
* Supabase

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
         Sentence Transformers
                     |
                     |
                  FAISS Index
```

## Running the Project

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

python -m spacy download en_core_web_sm
```

### Create a `.env` file

```env
DATABASE_URL=your supabase database_url
SECRET_KEY=your secret key
GROQ_API_KEY=your groq api key
```

### Run the backend

```bash
uvicorn main:app --reload
```

The backend will start at:

```
http://127.0.0.1:8000
```

Swagger API documentation is available at:

```
http://127.0.0.1:8000/docs
```

## API Endpoints

| Method | Endpoint                        | Description                      |
| ------ | ------------------------------- | -------------------------------- |
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



