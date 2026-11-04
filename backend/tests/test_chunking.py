import pytest

from app.ingestion.chunking import chunk_pages, estimate_tokens
from app.services.extraction import Page


def sentences(n: int, page: int | None = 1, prefix: str = "Sentence") -> Page:
    return Page(page, " ".join(f"{prefix} {i} has exactly seven words here." for i in range(n)))


def test_empty_pages_have_no_chunks():
    assert chunk_pages([Page(1, ""), Page(2, "   \n\n  ")]) == []


def test_short_text_is_one_chunk_with_its_page():
    [chunk] = chunk_pages([Page(3, "One short sentence. And another.")])
    assert chunk.content == "One short sentence. And another."
    assert (chunk.page_start, chunk.page_end) == (3, 3)


def test_chunks_respect_the_token_budget():
    chunks = chunk_pages([sentences(200)], target_tokens=100, overlap_tokens=20)
    assert len(chunks) > 5
    assert all(c.token_count <= 100 for c in chunks)


def test_chunks_end_on_sentence_boundaries():
    for chunk in chunk_pages([sentences(80)], target_tokens=100, overlap_tokens=20):
        assert chunk.content.startswith("Sentence ")
        assert chunk.content.endswith("here.")


def test_consecutive_chunks_overlap():
    chunks = chunk_pages([sentences(80)], target_tokens=100, overlap_tokens=20)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        last_sentence = previous.content.rsplit("Sentence ", 1)[1]
        assert ("Sentence " + last_sentence) in current.content


def test_no_text_is_lost():
    text_page = sentences(120)
    chunks = chunk_pages([text_page], target_tokens=100, overlap_tokens=20)
    for i in range(120):
        assert any(f"Sentence {i} has" in c.content for c in chunks), i


def test_chunks_record_the_pages_they_span():
    pages = [sentences(3, page=1, prefix="First"), sentences(3, page=2, prefix="Second")]
    [chunk] = chunk_pages(pages, target_tokens=300, overlap_tokens=20)
    assert (chunk.page_start, chunk.page_end) == (1, 2)


def test_long_pages_start_a_new_chunk_at_the_page_break():
    # Each page holds ~two thirds of the budget: merging them would overflow, and splitting
    # mid-page would blur citations, so each page becomes its own chunk
    pages = [sentences(20, page=1, prefix="First"), sentences(20, page=2, prefix="Second")]
    chunks = chunk_pages(pages, target_tokens=300, overlap_tokens=20)
    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (2, 2)]


def test_overlap_does_not_drag_a_page_into_the_next_chunk_alone():
    pages = [sentences(20, page=1, prefix="First"), sentences(20, page=2, prefix="Second")]
    chunks = chunk_pages(pages, target_tokens=300, overlap_tokens=20)
    assert chunks[1].content.startswith("Second")


def test_documents_without_pages_have_no_page_numbers():
    [chunk] = chunk_pages([Page(None, "A note. With two sentences.")])
    assert (chunk.page_start, chunk.page_end) == (None, None)


def test_paragraph_breaks_are_kept():
    [chunk] = chunk_pages([Page(1, "First paragraph.\n\nSecond paragraph.")])
    assert chunk.content == "First paragraph.\n\nSecond paragraph."


def test_a_single_huge_sentence_is_split():
    giant = Page(1, " ".join(["word"] * 1000) + ".")
    chunks = chunk_pages([giant], target_tokens=100, overlap_tokens=0)
    assert len(chunks) > 1 and all(c.token_count <= 100 for c in chunks)


def test_layout_whitespace_is_normalised():
    [chunk] = chunk_pages([Page(1, "Broken   across\nlines   in a PDF.")])
    assert chunk.content == "Broken across lines in a PDF."


@pytest.mark.parametrize(("target", "overlap"), [(100, 100), (100, 150), (100, -1)])
def test_invalid_overlap_is_rejected(target, overlap):
    with pytest.raises(ValueError):
        chunk_pages([Page(1, "text")], target_tokens=target, overlap_tokens=overlap)


def test_token_estimate():
    assert estimate_tokens("one two three four five six seven eight nine ten") == 13
    assert estimate_tokens("") == 1
