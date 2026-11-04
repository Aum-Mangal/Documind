"""Validates uploaded files and turns them into text, page by page."""
import io
import logging
import os
import re
from dataclasses import dataclass

from docx import Document as DocxDocument

from app.services.ocr import ExtractionError, extract_pdf_pages, extract_text_from_image

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS_MESSAGE = "Supported formats: PDF, DOCX, TXT, PNG, JPG, JPEG, WEBP"

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class Page:
    # 1-based page number; None for formats without pages (DOCX, TXT)
    number: int | None
    text: str


def clean_filename(filename: str | None) -> str:
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "untitled"


def file_extension(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


def _matches_signature(ext: str, data: bytes) -> bool:
    """Checks the file's leading bytes so a renamed file can't pose as another type."""
    if ext == ".pdf":
        return data.startswith(b"%PDF-")
    if ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == ".docx":
        return data.startswith(b"PK\x03\x04")
    if ext == ".txt":
        return b"\x00" not in data[:8192]
    return False


def validate_upload(file_bytes: bytes, filename: str) -> str:
    """Cheap check done at upload time. Returns the MIME type, or raises ExtractionError."""
    ext = file_extension(filename)
    if ext not in MIME_TYPES or not _matches_signature(ext, file_bytes):
        raise ExtractionError(SUPPORTED_FORMATS_MESSAGE)
    return MIME_TYPES[ext]


def extract_pages(file_bytes: bytes, filename: str, max_pdf_pages: int) -> list[Page]:
    """Raises ExtractionError with a user-safe message when the file can't be used."""
    validate_upload(file_bytes, filename)
    ext = file_extension(filename)

    try:
        if ext == ".pdf":
            pages = [Page(number, text) for number, text in extract_pdf_pages(file_bytes, max_pdf_pages)]
        elif ext in (".png", ".jpg", ".jpeg", ".webp"):
            pages = [Page(1, extract_text_from_image(file_bytes))]
        elif ext == ".docx":
            docx = DocxDocument(io.BytesIO(file_bytes))
            pages = [Page(None, "\n\n".join(p.text for p in docx.paragraphs if p.text.strip()))]
        else:
            pages = [Page(None, file_bytes.decode("utf-8", errors="replace"))]
    except ExtractionError:
        raise
    except Exception as e:
        logger.exception("Text extraction failed for %s", filename)
        raise ExtractionError("Could not read this file. It may be corrupted.") from e

    if not any(p.text.strip() for p in pages):
        raise ExtractionError("No readable text was found in this file.")
    return pages


def extract_text(file_bytes: bytes, filename: str, max_pdf_pages: int) -> str:
    return "\n\n".join(p.text for p in extract_pages(file_bytes, filename, max_pdf_pages) if p.text)
