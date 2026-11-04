"""The persisted knowledge graph, against a real database."""
from sqlalchemy import func, select

from app.db.models import Entity, EntityMention, Relation
from app.retrieval.search import hybrid_search
from app.services.embeddings import embed_query
from tests.integration.conftest import make_user, run
from tests.integration.test_ingestion import make_pdf, upload


def count(session_factory, model):
    async def go():
        async with session_factory() as session:
            return (await session.execute(select(func.count()).select_from(model))).scalar()
    return run(go())


def test_ingestion_builds_entities_mentions_and_relations(api, worker, session_factory):
    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]
    run(worker.run_until_idle())

    entities = api.get(f"/api/documents/{doc_id}/entities", headers=headers).json()["entities"]
    by_name = {e["text"]: e for e in entities}
    assert {"Maria Okafor", "Halden & Rowe", "Lisbon"} <= set(by_name)
    # The LLM's corrections were applied (spaCy's small model calls Porto a person)
    assert by_name["Porto"]["label"] == "PLACE"
    assert "Board" not in by_name
    # Numbers and dates aren't graph entities
    assert not any(e["label"] in ("DATE", "MONEY", "PERCENT", "CARDINAL") for e in entities)

    graph = api.get(f"/api/documents/{doc_id}/graph", headers=headers).json()
    labels = {n["id"]: n["label"] for n in graph["nodes"]}
    relations = {(labels[e["source"]], e["label"], labels[e["target"]]) for e in graph["edges"] if e["kind"] == "relation"}
    assert ("Halden & Rowe", "appointed", "Maria Okafor") in relations
    assert ("Daniel Weiss", "leads", "Porto") in relations
    # The invented name the fake LLM returned never became a node or edge
    assert "Nobody Invented" not in labels.values()
    assert all(e["source"] in labels and e["target"] in labels for e in graph["edges"])
    # A pair connected by a relation isn't drawn twice
    pairs = [frozenset((e["source"], e["target"])) for e in graph["edges"]]
    assert len(pairs) == len(set(pairs))


def test_entities_are_shared_across_documents(api, worker):
    headers = make_user(api)
    upload(api, headers)
    upload(api, headers, "lisbon-note.pdf", make_pdf(["Maria Okafor visited the Lisbon office and met the Porto team. " * 4]))
    run(worker.run_until_idle())
    graph = api.get("/api/graph", headers=headers).json()
    by_label = {n["label"]: n for n in graph["nodes"]}
    assert by_label["Maria Okafor"]["doc_count"] == 2
    assert by_label["Lisbon"]["doc_count"] == 2


def test_deleting_a_document_removes_entities_only_it_mentioned(api, worker, session_factory):
    headers = make_user(api)
    report = upload(api, headers).json()["document"]["id"]
    note = upload(api, headers, "note.pdf", make_pdf(["Kestrel Components met Maria Okafor in Lisbon. " * 4])).json()["document"]["id"]
    run(worker.run_until_idle())

    api.delete(f"/api/documents/{note}", headers=headers)
    names = {n["label"] for n in api.get("/api/graph", headers=headers).json()["nodes"]}
    assert "Kestrel Components" not in names  # only the deleted note mentioned it
    assert "Maria Okafor" in names            # the report still does

    api.delete(f"/api/documents/{report}", headers=headers)
    assert count(session_factory, Entity) == 0
    assert count(session_factory, EntityMention) == 0
    assert count(session_factory, Relation) == 0


def test_reprocessing_does_not_duplicate_the_graph(api, worker, session_factory):
    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]
    run(worker.run_until_idle())
    before = (count(session_factory, Entity), count(session_factory, EntityMention), count(session_factory, Relation))
    api.post(f"/api/documents/{doc_id}/reprocess", headers=headers)
    run(worker.run_until_idle())
    assert (count(session_factory, Entity), count(session_factory, EntityMention), count(session_factory, Relation)) == before


def test_graph_assisted_search_finds_passages_naming_the_entity(api, worker, session_factory):
    headers = make_user(api)
    upload(api, headers)
    run(worker.run_until_idle())

    async def go():
        async with session_factory() as session:
            q = "What happened with Northwind Supply?"
            return await hybrid_search(session, 1, q, embed_query(q), None, limit=10, use_graph=True)

    results = run(go())
    graph_hits = [r for r in results if r.graph_rank is not None]
    assert graph_hits and all("Northwind" in r.content for r in graph_hits)


def test_graph_endpoints_need_ownership(api, worker):
    alice = make_user(api, "alice@documind.dev")
    bob = make_user(api, "bob@documind.dev")
    doc_id = upload(api, alice).json()["document"]["id"]
    run(worker.run_until_idle())
    assert api.get(f"/api/documents/{doc_id}/graph", headers=bob).status_code == 404
    assert api.get(f"/api/documents/{doc_id}/entities", headers=bob).status_code == 404
    assert api.get("/api/graph", headers=bob).json() == {"nodes": [], "edges": []}


def test_short_and_long_names_join_across_documents(api, worker):
    headers = make_user(api)
    upload(api, headers)  # names "Northwind Supply"
    run(worker.run_until_idle())
    upload(api, headers, "vendor.pdf", make_pdf(["Northwind shipped late again. Northwind blamed the fire. " * 4]))
    run(worker.run_until_idle())
    names = [n["label"] for n in api.get("/api/graph", headers=headers).json()["nodes"]]
    assert names.count("Northwind Supply") + names.count("Northwind") == 1
