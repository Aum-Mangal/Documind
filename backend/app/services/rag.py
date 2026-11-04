import numpy as np
from fastembed import TextEmbedding

from app.services.llm import complete

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _embedder

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be at least 0 and smaller than chunk_size")
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def answer_question(question: str, text: str) -> dict:
    chunks = chunk_text(text)
    if not chunks:
        return {
            "answer": "This document contains no text to analyze.",
            "sources": [],
            "confidence": 0
        }

    embedder = get_embedder()
    chunk_embeddings = np.array(list(embedder.embed(chunks)), dtype=np.float32)
    question_embedding = np.array(list(embedder.embed([question]))[0], dtype=np.float32)

    q_norm = question_embedding / (np.linalg.norm(question_embedding) + 1e-8)
    c_norms = chunk_embeddings / (np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-8)

    scores = np.dot(c_norms, q_norm)
    k = min(3, len(chunks))
    top_indices = np.argsort(scores)[::-1][:k]

    # Assemble formatted numbered context blocks with source labels
    context_blocks = []
    sources = []
    for rank, idx in enumerate(top_indices):
        chunk = chunks[idx]
        score = float(scores[idx])
        context_blocks.append(f"[Source {rank + 1}]:\n{chunk}")
        sources.append({
            "source_id": rank + 1,
            "chunk_index": int(idx),
            "score": round(score, 3),
            "text": chunk[:280] + ("..." if len(chunk) > 280 else "")
        })

    context = "\n\n".join(context_blocks)
    top_score = float(scores[top_indices[0]])
    confidence = int(min(100, max(25, round(top_score * 100))))

    answer_text = complete(
        system=(
            "You are DocuMind's advanced document intelligence assistant. "
            "Answer the user's question accurately and objectively using ONLY the provided document context. "
            "Reference specific source numbers like [Source 1] when citing facts. "
            "If the answer is not supported by the context, state: 'I could not find that information in the document.'"
        ),
        user=f"Document context:\n{context}\n\nQuestion: {question}",
    )

    return {
        "answer": answer_text,
        "sources": sources,
        "confidence": confidence
    }
