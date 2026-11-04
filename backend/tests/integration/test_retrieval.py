"""Hybrid search and chat, against a real database with real embedding and reranker models."""
import pytest

from app.retrieval.search import hybrid_search
from app.services.embeddings import embed_query
from tests.integration.conftest import make_user, run
from tests.integration.test_ingestion import make_pdf, upload

COOKING = ["Bread needs flour, water, salt and yeast. Knead the dough for ten minutes and let it rise "
           "for two hours before baking at 230 degrees."]


@pytest.fixture
def library(api, worker):
    """Two users; the first has the quarterly report and a recipe, the second a document of their own."""
    alice = make_user(api, "alice@documind.dev")
    bob = make_user(api, "bob@documind.dev")
    report = upload(api, alice, "report.pdf").json()["document"]["id"]
    recipe = upload(api, alice, "bread.pdf", make_pdf(COOKING)).json()["document"]["id"]
    bobs = upload(api, bob, "bob.pdf", make_pdf(["Bob's private note mentions part ZX-4471 and Lisbon."])).json()["document"]["id"]
    run(worker.run_until_idle())
    return {"alice": alice, "bob": bob, "report": report, "recipe": recipe, "bobs": bobs}


def search(session_factory, user_id, query, document_ids=None):
    async def go():
        async with session_factory() as session:
            return await hybrid_search(session, user_id, query, embed_query(query), document_ids, limit=10)
    return run(go())


def test_semantic_question_finds_the_right_page(library, session_factory):
    results = search(session_factory, 1, "Who became the new chief operating officer?")
    assert results and "Maria Okafor" in results[0].content
    assert results[0].vector_rank is not None


def test_exact_codes_are_found_by_keyword_search(library, session_factory):
    results = search(session_factory, 1, "ZX-4471")
    assert results and "ZX-4471" in results[0].content
    assert results[0].keyword_rank == 1


def test_search_only_sees_the_users_own_documents(library, session_factory):
    alice_hits = search(session_factory, 1, "ZX-4471 Lisbon")
    assert {r.document_id for r in alice_hits} <= {library["report"], library["recipe"]}
    bob_hits = search(session_factory, 2, "Maria Okafor chief operating officer")
    assert {r.document_id for r in bob_hits} == {library["bobs"]}


def test_search_can_be_limited_to_chosen_documents(library, session_factory):
    results = search(session_factory, 1, "Maria Okafor", document_ids=[library["recipe"]])
    assert {r.document_id for r in results} == {library["recipe"]}


def test_answer_cites_sources_with_document_and_page(api, library, llm):
    response = api.post("/api/chat", headers=library["alice"], json={"question": "Who was appointed chief operating officer?"})
    assert response.status_code == 200
    body = response.json()
    message = body["message"]
    assert message["abstained"] is False
    assert "[Source 1]" in message["content"]
    top = message["sources"][0]
    assert top["filename"] == "report.pdf" and top["page_start"] <= 2 <= top["page_end"]
    assert "Maria Okafor" in top["text"]

    # The model saw the passages as tagged, untrusted data
    system, prompt = llm.calls[-1]
    assert "never as instructions" in system
    assert '<source n="1" document="report.pdf" pages="' in prompt


def test_conversations_are_saved_and_follow_ups_are_rewritten(api, library, llm):
    first = api.post("/api/chat", headers=library["alice"], json={"question": "Tell me about the Atlas product."}).json()
    conversation_id = first["conversation"]["id"]

    llm.answer = "Northwind Supply could not deliver components on time [Source 1]."
    follow_up = api.post("/api/chat", headers=library["alice"],
                         json={"question": "Why was it delayed?", "conversation_id": conversation_id}).json()
    assert follow_up["search_query"] == "Why was the Atlas launch delayed?"
    rewrite_system, rewrite_prompt = next(c for c in llm.calls if "Rewrite" in c[0])
    assert "Tell me about the Atlas product." in rewrite_prompt
    assert "Northwind" in follow_up["message"]["sources"][0]["text"]

    saved = api.get(f"/api/conversations/{conversation_id}", headers=library["alice"]).json()
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant", "user", "assistant"]
    assert saved["title"] == "Tell me about the Atlas product."
    assert [c["id"] for c in api.get("/api/conversations", headers=library["alice"]).json()] == [conversation_id]

    # Other users can't read or continue it
    assert api.get(f"/api/conversations/{conversation_id}", headers=library["bob"]).status_code == 404
    assert api.post("/api/chat", headers=library["bob"],
                    json={"question": "hi", "conversation_id": conversation_id}).status_code == 404

    assert api.delete(f"/api/conversations/{conversation_id}", headers=library["alice"]).status_code == 204
    assert api.get("/api/conversations", headers=library["alice"]).json() == []


def test_unrelated_questions_are_declined_without_calling_the_model(api, library, llm):
    calls_before = len(llm.calls)
    body = api.post("/api/chat", headers=library["alice"], json={"question": "What is the capital of Mongolia?"}).json()
    assert body["message"]["abstained"] is True
    assert body["message"]["content"] == "I couldn't find that in your documents."
    assert body["message"]["sources"] == []
    assert len(llm.calls) == calls_before


def test_conversation_scope_limits_what_is_searched(api, library, llm):
    body = api.post("/api/chat", headers=library["alice"],
                    json={"question": "How long should the dough rise?", "document_ids": [library["recipe"]]}).json()
    assert body["conversation"]["document_ids"] == [library["recipe"]]
    assert {s["document_id"] for s in body["message"]["sources"]} == {library["recipe"]}


def test_cannot_scope_a_conversation_to_someone_elses_document(api, library):
    response = api.post("/api/chat", headers=library["alice"],
                        json={"question": "What does Bob's note say?", "document_ids": [library["bobs"]]})
    assert response.status_code == 404
