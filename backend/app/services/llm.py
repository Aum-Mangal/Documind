from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache

from groq import Groq

from app.core.config import get_settings


class LLMNotConfigured(Exception):
    """Raised when an LLM call is attempted without an API key."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# The usage tally of whatever request or job is running. asyncio.to_thread copies the
# context into its thread, and the Usage object is shared, so calls made there count too.
_current_usage: ContextVar[Usage | None] = ContextVar("llm_usage", default=None)


@contextmanager
def track_usage() -> Iterator[Usage]:
    usage = Usage()
    token = _current_usage.set(usage)
    try:
        yield usage
    finally:
        _current_usage.reset(token)


def record_usage(prompt_tokens: int, completion_tokens: int) -> None:
    usage = _current_usage.get()
    if usage is not None:
        usage.prompt_tokens += prompt_tokens
        usage.completion_tokens += completion_tokens
        usage.calls += 1


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
    if response.usage:
        record_usage(response.usage.prompt_tokens or 0, response.usage.completion_tokens or 0)
    return response.choices[0].message.content or ""
