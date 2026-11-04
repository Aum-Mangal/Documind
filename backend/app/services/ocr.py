import io
import logging
import shutil

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# Check if tesseract binary is available on PATH
HAS_TESSERACT = shutil.which("tesseract") is not None

# A page with less native text than this is treated as scanned and OCR'd
MIN_NATIVE_CHARS = 25
OCR_DPI = 200

NO_OCR_MESSAGE = "This looks like a scanned document, and text recognition (OCR) isn't available on this server."


class ExtractionError(Exception):
    """Raised when a file can't be read. The message is safe to show to the user."""


def _open_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        return image
    except Image.DecompressionBombError as e:
        raise ExtractionError("Image dimensions are too large to process.") from e
    except Exception as e:
        logger.exception("Failed to open image")
        raise ExtractionError("Could not read this image file.") from e


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extracts text from an image (PNG, JPG, WEBP) using OCR."""
    image = _open_image(image_bytes)
    if not HAS_TESSERACT:
        raise ExtractionError(NO_OCR_MESSAGE)
    return pytesseract.image_to_string(image).strip()


def extract_pdf_pages(pdf_bytes: bytes, max_pages: int) -> list[tuple[int, str]]:
    """Returns (page_number, text) for every page, OCR-ing only the pages without a text layer."""
    try:
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.exception("Failed to open PDF")
        raise ExtractionError("Could not read this PDF file.") from e

    with pdf:
        if pdf.needs_pass:
            raise ExtractionError("Password-protected PDFs are not supported.")
        if pdf.page_count > max_pages:
            raise ExtractionError(f"PDF has {pdf.page_count} pages; the limit is {max_pages}.")

        pages: list[tuple[int, str]] = []
        needed_ocr = False
        for number, page in enumerate(pdf, start=1):
            text = page.get_text().strip()
            if len(text) < MIN_NATIVE_CHARS:
                needed_ocr = True
                if HAS_TESSERACT:
                    try:
                        pix = page.get_pixmap(dpi=OCR_DPI)
                        ocr_text = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png")))).strip()
                        text = ocr_text if len(ocr_text) > len(text) else text
                    except Exception:
                        logger.warning("OCR failed on page %d", number, exc_info=True)
            pages.append((number, text))

    if not any(text for _, text in pages):
        raise ExtractionError(NO_OCR_MESSAGE if needed_ocr and not HAS_TESSERACT else "No readable text was found in this PDF.")
    return pages
