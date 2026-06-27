from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv
import faiss
import numpy as np
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def build_index(chunks: list):
    embeddings = embedder.encode(chunks)
    embeddings = np.array(embeddings).astype("float32")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    return index, embeddings

def answer_question(question: str, text: str) -> str:
    chunks = chunk_text(text)
    if not chunks:
        return "Document is empty."

    index, _ = build_index(chunks)

    question_embedding = embedder.encode([question])
    question_embedding = np.array(question_embedding).astype("float32")

    k = min(3, len(chunks))
    distances, indices = index.search(question_embedding, k)
    relevant_chunks = [chunks[i] for i in indices[0]]
    context = "\n\n".join(relevant_chunks)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer the user's question using only the provided document context. If the answer is not in the context, say 'I could not find that information in the document.'"
            },
            {
                "role": "user",
                "content": f"Context from document:\n{context}\n\nQuestion: {question}"
            }
        ]
    )
    return response.choices[0].message.content