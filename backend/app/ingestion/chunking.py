"""Split page text into overlapping chunks that end on sentence boundaries.

Token counts are estimated from words (about 1.3 tokens per English word), which is close
enough for sizing chunks for a 512-token embedding model without loading a tokenizer.
"""
import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.services.extraction import Page

TOKENS_PER_WORD = 1.3

# A sentence ends at . ! ? (optionally followed by a closing quote or bracket) before whitespace.
# Two fixed-width lookbehinds, since Python's re doesn't allow a variable-width one.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|(?<=[.!?][\"')\]])\s+")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class TextChunk:
    content: str
    page_start: int | None
    page_end: int | None
    token_count: int


@dataclass(frozen=True)
class _Unit:
    text: str
    page: int | None
    tokens: int
    starts_paragraph: bool


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text.split()) * TOKENS_PER_WORD))


def _split_long(text: str, max_tokens: int) -> list[str]:
    """Break a single over-long sentence into word windows."""
    words = text.split()
    size = max(1, int(max_tokens / TOKENS_PER_WORD))
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def _units(pages: Iterable[Page], target_tokens: int) -> list[_Unit]:
    units: list[_Unit] = []
    for page in pages:
        for paragraph in _PARAGRAPH_BREAK.split(page.text):
            paragraph = " ".join(paragraph.split())
            if not paragraph:
                continue
            first = True
            for sentence in _SENTENCE_END.split(paragraph):
                if not sentence.strip():
                    continue
                pieces = _split_long(sentence, target_tokens) if estimate_tokens(sentence) > target_tokens else [sentence]
                for piece in pieces:
                    units.append(_Unit(piece, page.number, estimate_tokens(piece), first))
                    first = False
    return units


def _join(units: list[_Unit]) -> str:
    out = ""
    for i, unit in enumerate(units):
        if i:
            out += "\n\n" if unit.starts_paragraph else " "
        out += unit.text
    return out


def _make_chunk(units: list[_Unit]) -> TextChunk:
    pages = [u.page for u in units if u.page is not None]
    return TextChunk(
        content=_join(units),
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
        token_count=sum(u.tokens for u in units),
    )


def chunk_pages(pages: Iterable[Page], target_tokens: int = 300, overlap_tokens: int = 50) -> list[TextChunk]:
    if not 0 <= overlap_tokens < target_tokens:
        raise ValueError("overlap_tokens must be at least 0 and smaller than target_tokens")

    chunks: list[TextChunk] = []
    current: list[_Unit] = []
    current_tokens = 0
    # Whether `current` holds anything beyond the overlap carried from the previous chunk
    has_new = False

    for unit in _units(pages, target_tokens):
        # Prefer to start a new chunk at a page break once the current one has some substance,
        # so citations can point at one page; short pages still merge rather than become fragments
        new_page = bool(current) and unit.page != current[-1].page and current_tokens >= target_tokens // 2
        if has_new and (current_tokens + unit.tokens > target_tokens or new_page):
            chunks.append(_make_chunk(current))
            # Start the next chunk with the trailing sentences of this one, up to the overlap budget.
            # A page break is a natural boundary, so nothing is carried across it.
            carried: list[_Unit] = []
            carried_tokens = 0
            for previous in ([] if new_page else reversed(current)):
                if carried_tokens + previous.tokens > overlap_tokens:
                    break
                carried.insert(0, previous)
                carried_tokens += previous.tokens
            current, current_tokens = carried, carried_tokens
        current.append(unit)
        current_tokens += unit.tokens
        has_new = True

    if has_new:
        chunks.append(_make_chunk(current))
    return chunks
