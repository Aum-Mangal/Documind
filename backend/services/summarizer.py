from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

def summarize(text: str) -> str:
    if len(text) > 3000:
        text = text[:3000]

    if len(text) < 50:
        return "Document too short to summarize."

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Summarize the given document in 3-5 clear sentences."
            },
            {
                "role": "user",
                "content": f"Summarize this document:\n\n{text}"
            }
        ]
    )
    return response.choices[0].message.content