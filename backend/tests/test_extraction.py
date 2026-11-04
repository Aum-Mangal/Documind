import io

import fitz
import pytest
from docx import Document as DocxDocument

from app.services.extraction import SUPPORTED_FORMATS_MESSAGE, clean_filename, extract_text
from app.services.ocr import ExtractionError, extract_text_from_image

MAX_PAGES = 5


def make_pdf(pages: int, text: str = "DocuMind reads the native text layer of this page.") -> bytes:
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Page {i + 1}. {text}")
    return doc.tobytes()


def make_docx(paragraphs: list[str]) -> bytes:
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ── Filenames ────────────────────────────────────────

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../../etc/passwd.txt", "passwd.txt"),
        ("..\\..\\windows\\system.ini", "system.ini"),
        ("bad\x00name\x1f.txt", "badname.txt"),
        ("  spaced.txt  ", "spaced.txt"),
        ("", "untitled"),
        (None, "untitled"),
    ],
)
def test_clean_filename(raw, expected):
    assert clean_filename(raw) == expected


def test_clean_filename_caps_length():
    assert len(clean_filename("a" * 400 + ".pdf")) == 255


# ── Type checks ──────────────────────────────────────

@pytest.mark.parametrize(
    ("filename", "data"),
    [
        ("fake.pdf", b"just some text"),
        ("fake.png", b"%PDF-1.7 not a png"),
        ("fake.docx", b"%PDF-1.7 not a zip"),
        ("binary.txt", b"MZ\x00\x00\x90"),
        ("program.exe", b"MZ\x90\x00"),
        ("noextension", b"hello"),
    ],
)
def test_content_must_match_extension(filename, data):
    with pytest.raises(ExtractionError, match="Supported formats"):
        extract_text(data, filename, MAX_PAGES)


def test_extension_check_is_case_insensitive():
    assert "Page 1" in extract_text(make_pdf(1), "REPORT.PDF", MAX_PAGES)


# ── Text extraction ──────────────────────────────────

def test_plain_text():
    assert extract_text("Grüße aus Köln".encode(), "notes.txt", MAX_PAGES) == "Grüße aus Köln"


def test_invalid_utf8_text_is_replaced_not_rejected():
    assert "�" in extract_text(b"caf\xe9", "latin1.txt", MAX_PAGES)


def test_pdf_text_from_every_page():
    text = extract_text(make_pdf(3), "report.pdf", MAX_PAGES)
    assert all(f"Page {n}." in text for n in (1, 2, 3))


def test_pdf_over_page_limit_is_rejected():
    with pytest.raises(ExtractionError, match=f"limit is {MAX_PAGES}"):
        extract_text(make_pdf(MAX_PAGES + 1), "long.pdf", MAX_PAGES)


def test_corrupt_pdf_gives_a_safe_message():
    with pytest.raises(ExtractionError) as excinfo:
        extract_text(b"%PDF-1.4 garbage that is not a pdf", "broken.pdf", MAX_PAGES)
    assert str(excinfo.value) == "Could not read this PDF file."


def test_password_protected_pdf_is_rejected():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret")
    locked = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    with pytest.raises(ExtractionError, match="Password-protected"):
        extract_text(locked, "locked.pdf", MAX_PAGES)


def test_docx_paragraphs():
    data = make_docx(["First paragraph.", "Second paragraph."])
    assert extract_text(data, "letter.docx", MAX_PAGES) == "First paragraph.\nSecond paragraph."


def test_corrupt_docx_gives_a_safe_message():
    with pytest.raises(ExtractionError, match="may be corrupted"):
        extract_text(b"PK\x03\x04 not really a zip archive", "broken.docx", MAX_PAGES)


def test_corrupt_image_gives_a_safe_message():
    with pytest.raises(ExtractionError, match="Could not read this image"):
        extract_text_from_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


def test_supported_formats_message_lists_webp():
    assert "WEBP" in SUPPORTED_FORMATS_MESSAGE
