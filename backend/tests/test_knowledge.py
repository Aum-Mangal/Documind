import json

import pytest

from app.knowledge.entities import Entity, canonical, display_name, extract, merge_aliases, names_in, text_key
from app.knowledge.relations import parse_response, pick_chunks
from app.knowledge.store import apply_type_corrections

# ── Names ────────────────────────────────────────────

@pytest.mark.parametrize(
    ("surface", "display", "key"),
    [
        ("The Northwind Supply", "Northwind Supply", "northwind supply"),
        ("Northwind’s", "Northwind", "northwind"),
        ("Ms Okafor", "Okafor", "okafor"),
        ("Dr. Ines  Varga,", "Ines Varga", "ines varga"),
        ("Halden & Rowe", "Halden & Rowe", "halden & rowe"),
        ("  Lisbon. ", "Lisbon.", "lisbon"),
    ],
)
def test_display_names_and_keys(surface, display, key):
    assert display_name(surface) == display
    assert canonical(surface) == key


def test_text_key_pads_for_whole_word_matching():
    assert text_key("Who runs Porto's office?") == " who runs porto s office "


def entity(key, kind="ORG", mentions=None, name=None):
    return Entity(key, name or key.title(), kind, mentions or {0: 1})


def test_shorter_and_longer_names_merge_into_the_more_frequent_one():
    merged = merge_aliases({
        "northwind": entity("northwind", mentions={0: 3, 1: 2}),
        "northwind supply": entity("northwind supply", mentions={1: 1}),
    })
    assert list(merged) == ["northwind"]
    assert merged["northwind"].mentions == {0: 3, 1: 3}


def test_a_stray_long_phrase_folds_into_the_real_name():
    merged = merge_aliases({
        "halden & rowe": entity("halden & rowe", mentions={0: 5}),
        "halden & rowe quarterly report": entity("halden & rowe quarterly report", mentions={0: 1}),
    })
    assert list(merged) == ["halden & rowe"]


def test_a_lone_surname_joins_the_one_person_with_that_surname():
    merged = merge_aliases({
        "maria okafor": entity("maria okafor", "PERSON"),
        "okafor": entity("okafor", "PLACE", mentions={2: 1}),
    })
    assert list(merged) == ["maria okafor"] and merged["maria okafor"].mentions == {0: 1, 2: 1}


def test_an_ambiguous_surname_is_left_alone():
    merged = merge_aliases({
        "ana silva": entity("ana silva", "PERSON"),
        "rui silva": entity("rui silva", "PERSON"),
        "silva": entity("silva", "PERSON"),
    })
    assert set(merged) == {"ana silva", "rui silva", "silva"}


def test_merged_entities_take_the_majority_type():
    merged = merge_aliases({
        "atlas": entity("atlas", "PERSON", {0: 1}),
        "atlas x2": entity("atlas x2", "PRODUCT", {1: 4}),
    })
    [only] = merged.values()
    assert only.type == "PRODUCT"


def test_extract_skips_numbers_and_dates_and_keeps_named_entities():
    found = extract(["Maria Okafor joined Halden & Rowe in Lisbon on 3 March 2025 for 4.2 million euros."])
    kinds = {e.key: e.type for e in found.values()}
    assert "maria okafor" in kinds and "lisbon" in kinds
    assert not any(any(ch.isdigit() for ch in key) for key in kinds)


def test_names_in_matches_whole_words_only():
    known = [entity("porto"), entity("rowe")]
    assert [e.key for e in names_in("Who leads the Porto office?", known)] == ["porto"]
    assert names_in("Who leads Portoferraio?", known) == []


# ── Relation extraction (the LLM's reply) ────────────

NAMES = {"Maria Okafor": "maria okafor", "Halden & Rowe": "halden & rowe", "Board": "board"}


def test_relations_between_listed_names_are_kept():
    reply = 'Sure! {"types": {"Maria Okafor": "person", "Board": "NONE"}, "relations": [' \
            '{"subject": "halden & rowe", "relation": "Appointed", "object": "Maria Okafor"}]} Hope that helps.'
    result = parse_response(reply, NAMES, chunk_index=4)
    assert result.types == {"maria okafor": "PERSON", "board": "NONE"}
    [relation] = result.relations
    assert (relation.source, relation.target, relation.predicate, relation.chunk_index) == \
        ("halden & rowe", "maria okafor", "appointed", 4)


@pytest.mark.parametrize("relation", [
    {"subject": "Invented Corp", "relation": "owns", "object": "Maria Okafor"},     # name not in the list
    {"subject": "Maria Okafor", "relation": "leads", "object": "Maria Okafor"},     # self-loop
    {"subject": "Maria Okafor", "relation": "x" * 60, "object": "Halden & Rowe"},   # not a short phrase
    {"subject": "Maria Okafor", "relation": "DROP TABLE; --", "object": "Halden & Rowe"},
    "not even an object",
])
def test_invalid_relations_are_dropped(relation):
    assert parse_response(json.dumps({"relations": [relation]}), NAMES, 0).relations == []


@pytest.mark.parametrize("reply", ["", "no json here", "{broken json", '{"types": "wrong shape"}'])
def test_unusable_replies_yield_nothing(reply):
    result = parse_response(reply, NAMES, 0)
    assert result.relations == [] and result.types == {}


def test_unknown_types_are_ignored():
    assert parse_response('{"types": {"Board": "SPACESHIP"}}', NAMES, 0).types == {}


def test_pick_chunks_prefers_entity_dense_passages():
    entities = {
        "a": entity("a", mentions={0: 1, 1: 1, 2: 1}),
        "b": entity("b", mentions={1: 1, 2: 1}),
        "c": entity("c", mentions={2: 1}),
    }
    assert pick_chunks(entities, chunk_count=3, limit=5) == [2, 1]  # chunk 0 has a single entity
    assert pick_chunks(entities, chunk_count=3, limit=1) == [2]


def test_type_corrections_fix_and_remove_entities():
    entities = {"porto": entity("porto", "PERSON"), "board": entity("board")}
    apply_type_corrections(entities, {"porto": "PLACE", "board": "NONE", "unknown": "ORG"})
    assert list(entities) == ["porto"]
    assert entities["porto"].type == "PLACE" and entities["porto"].type_confirmed
