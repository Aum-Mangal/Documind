"""Validates uploaded files and turns them into plain text."""
import io
import logging
import os
import re

from docx import Document as DocxDocument

from app.services.ocr import ExtractionError, extract_text_from_image, extract_text_from_pdf

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS_MESSAGE = "Supported formats: PDF, DOCX, TXT, PNG, JPG, JPEG, WEBP"


def clean_filename(filename: str | None) -> str:
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "untitled"


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


def extract_text(file_bytes: bytes, filename: str, max_pdf_pages: int) -> str:
    """Raises ExtractionError with a user-safe message when the file can't be used."""
    ext = os.path.splitext(filename.lower())[1]
    if not _matches_signature(ext, file_bytes):
        raise ExtractionError(SUPPORTED_FORMATS_MESSAGE)

    try:
        if ext == ".pdf":
            return extract_text_from_pdf(file_bytes, max_pages=max_pdf_pages)

        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            return extract_text_from_image(file_bytes)

        if ext == ".docx":
            docx = DocxDocument(io.BytesIO(file_bytes))
            return "\n".join(para.text for para in docx.paragraphs)

        return file_bytes.decode("utf-8", errors="replace")
    except ExtractionError:
        raise
    except Exception as e:
        logger.exception("Text extraction failed for %s", filename)
        raise ExtractionError("Could not read this file. It may be corrupted.") from e
