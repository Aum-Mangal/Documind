from fastembed import TextEmbedding
from groq import Groq
from dotenv import load_dotenv
import numpy as np
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedder

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def answer_question(question: str, text: str) -> str:
    chunks = chunk_text(text)
    if not chunks:
        return "Document is empty."

    embedder = get_embedder()
    chunk_embeddings = np.array(list(embedder.embed(chunks)), dtype=np.float32)
    question_embedding = np.array(list(embedder.embed([question]))[0], dtype=np.float32)

    q_norm = question_embedding / (np.linalg.norm(question_embedding) + 1e-8)
    c_norms = chunk_embeddings / (np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-8)

    scores = np.dot(c_norms, q_norm)
    k = min(3, len(chunks))
    top_indices = np.argsort(scores)[::-1][:k]
    relevant_chunks = [chunks[i] for i in top_indices]

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