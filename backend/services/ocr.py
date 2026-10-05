import io
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import shutil

# Check if tesseract binary is available on PATH
HAS_TESSERACT = shutil.which("tesseract") is not None

def extract_text_from_image(image_bytes: bytes) -> str:
    """Extracts text from an image (PNG, JPG, JPEG) using OCR."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if HAS_TESSERACT:
            text = pytesseract.image_to_string(image)
            return text.strip()
        else:
            return f"[OCR Notice] Image received ({image.format} {image.width}x{image.height}px). Tesseract OCR is enabled on server deployment."
    except Exception as e:
        return f"[OCR Error] Failed to process image: {str(e)}"

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts text from PDF.
    If the PDF is scanned (little or no text extracted), automatically performs OCR on page images.
    """
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
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
            except Exception as e:
                print(f"[OCR Warning] Failed on page {i+1}: {e}")
        if ocr_pages:
            return "\n\n".join(ocr_pages)

    return native_text.strip() if native_text.strip() else "[Document Notice] Scanned PDF detected."
