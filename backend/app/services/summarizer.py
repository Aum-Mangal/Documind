from app.services.llm import complete


def summarize(text: str) -> str:
    if len(text) > 3000:
        text = text[:3000]

    if len(text) < 50:
        return "Document too short to summarize."

    return complete(
        system="You are a helpful assistant. Summarize the given document in 3-5 clear sentences.",
        user=f"Summarize this document:\n\n{text}",
    )
