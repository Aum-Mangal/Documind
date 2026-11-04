from functools import lru_cache

from groq import Groq

from app.core.config import get_settings


class LLMNotConfigured(Exception):
    """Raised when an LLM call is attempted without an API key."""


@lru_cache
def get_groq_client() -> Groq:
    # Created on first use, so the app can start (and serve everything else) without a key
    settings = get_settings()
    if not settings.groq_api_key:
        raise LLMNotConfigured("GROQ_API_KEY is not set")
    return Groq(api_key=settings.groq_api_key, timeout=60, max_retries=2)


def complete(system: str, user: str) -> str:
    response = get_groq_client().chat.completions.create(
        model=get_settings().groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""
