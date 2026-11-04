import io
import logging
import shutil

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# Check if tesseract binary is available on PATH
HAS_TESSERACT = shutil.which("tesseract") is not None

class ExtractionError(Exception):
    """Raised when a file can't be read. The message is safe to show to the user."""

def extract_text_from_image(image_bytes: bytes) -> str:
    """Extracts text from an image (PNG, JPG, JPEG) using OCR."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Image.DecompressionBombError as e:
        raise ExtractionError("Image dimensions are too large to process.") from e
    except Exception as e:
        logger.exception("Failed to open image")
        raise ExtractionError("Could not read this image file.") from e

    if HAS_TESSERACT:
        return pytesseract.image_to_string(image).strip()
    return f"[OCR Notice] Image received ({image.format} {image.width}x{image.height}px). Tesseract OCR is enabled on server deployment."

def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int) -> str:
    """
    Extracts text from PDF.
    If the PDF is scanned (little or no text extracted), automatically performs OCR on page images.
    """
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

        native_text = ""
        for page in pdf:
            native_text += page.get_text()

        # If document has sufficient native text, return it
        if len(native_text.strip()) > 60:
            return native_text.strip()

        # Document is likely scanned or image-only — fallback to OCR
        if HAS_TESSERACT:
            ocr_pages = []
            for i, page in enumerate(pdf):
                try:
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    page_text = pytesseract.image_to_string(img)
                    if page_text.strip():
                        ocr_pages.append(page_text.strip())
                except Exception:
                    logger.warning("OCR failed on page %d", i + 1, exc_info=True)
            if ocr_pages:
                return "\n\n".join(ocr_pages)

    return native_text.strip() if native_text.strip() else "[Document Notice] Scanned PDF detected."
