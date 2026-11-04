import pytest

from app.services import llm
from app.services.summarizer import summarize

# ── Summaries and the LLM client ─────────────────────

def test_short_documents_are_not_sent_to_the_llm():
    assert summarize("Too short.") == "Document too short to summarize."


def test_llm_without_api_key_raises_a_clear_error():
    llm.get_groq_client.cache_clear()
    with pytest.raises(llm.LLMNotConfigured):
        llm.complete("system", "user")
