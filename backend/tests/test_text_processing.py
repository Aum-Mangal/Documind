import pytest

from app.services import llm
from app.services.graph import generate_document_graph, generate_global_graph
from app.services.rag import chunk_text
from app.services.summarizer import summarize

# ── Chunking ─────────────────────────────────────────

def test_empty_text_has_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("a few words only") == ["a few words only"]


def test_chunks_are_sized_and_overlap():
    words = [f"w{i}" for i in range(1200)]
    chunks = [c.split() for c in chunk_text(" ".join(words), chunk_size=500, overlap=50)]

    assert [len(c) for c in chunks] == [500, 500, 300]
    # each chunk starts with the last 50 words of the one before
    assert chunks[1][:50] == chunks[0][-50:]
    assert chunks[2][:50] == chunks[1][-50:]
    # nothing is lost
    assert chunks[0][0] == "w0" and chunks[-1][-1] == "w1199"


@pytest.mark.parametrize(("size", "overlap"), [(100, 100), (100, 150), (100, -1)])
def test_invalid_overlap_is_rejected_instead_of_looping_forever(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("some text here", chunk_size=size, overlap=overlap)


# ── Summaries and the LLM client ─────────────────────

def test_short_documents_are_not_sent_to_the_llm():
    assert summarize("Too short.") == "Document too short to summarize."


def test_llm_without_api_key_raises_a_clear_error():
    llm.get_groq_client.cache_clear()
    with pytest.raises(llm.LLMNotConfigured):
        llm.complete("system", "user")


# ── Knowledge graph ──────────────────────────────────

SAMPLE = (
    "Maria Okafor joined Halden & Rowe in Lisbon in 2024. She reports to Daniel Weiss.\n\n"
    "Halden & Rowe opened a second office in Porto, led by Daniel Weiss, with funding from Northwind Capital."
)


def _assert_valid_graph(graph):
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids, "expected some entities"
    for edge in graph["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids
        assert edge["source"] != edge["target"]
    for node in graph["nodes"]:
        assert node["degree"] == sum(node["id"] in (e["source"], e["target"]) for e in graph["edges"])


def test_document_graph_links_entities_in_the_same_paragraph():
    graph = generate_document_graph(SAMPLE)
    _assert_valid_graph(graph)
    labels = {n["label"] for n in graph["nodes"]}
    assert {"Lisbon", "Porto"} <= labels


def test_document_graph_respects_max_nodes():
    assert len(generate_document_graph(SAMPLE, max_nodes=2)["nodes"]) <= 2


def test_document_graph_of_empty_text_is_empty():
    assert generate_document_graph("") == {"nodes": [], "edges": []}


class _Doc:
    def __init__(self, filename, raw_text):
        self.filename = filename
        self.raw_text = raw_text


def test_global_graph_counts_documents_per_entity():
    docs = [_Doc("a.txt", SAMPLE), _Doc("b.txt", "Daniel Weiss visited Lisbon again."), _Doc("empty.txt", None)]
    graph = generate_global_graph(docs)
    _assert_valid_graph(graph)
    by_label = {n["label"]: n for n in graph["nodes"]}
    assert by_label["Lisbon"]["doc_count"] == 2


def test_entity_text_has_layout_whitespace_collapsed():
    from app.services.ner import extract_entities

    # PDF text often breaks lines inside a name; the entity should still read as one phrase
    texts = {e["text"] for e in extract_entities("The board met Maria\nOkafor in Lisbon on Monday.")}
    assert not any("\n" in t or "  " in t for t in texts)
    assert "Maria Okafor" in texts
