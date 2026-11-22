from pathlib import Path
import fitz
from PIL import Image
import io

ALLOWED = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
def extract_text(data: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        doc = fitz.open(stream=data, filetype="pdf")
        return "\n".join(page.get_text() for page in doc).strip()
    # Image OCR is deliberately not guessed. Tesseract may be added separately.
    if content_type.startswith("image/"):
        Image.open(io.BytesIO(data)).verify()
        return ""
    raise ValueError("Unsupported file type")
