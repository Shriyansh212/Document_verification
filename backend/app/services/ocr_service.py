from dataclasses import dataclass, field
import io
import shutil
from statistics import mean

from PIL import Image, ImageFilter, ImageOps
from pypdf import PdfReader
import pytesseract

from app.core.config import get_settings


class OCRProcessingError(Exception):
    """Raised when OCR extraction cannot be performed on the provided file."""


@dataclass
class OCRResult:
    text: str
    engine: str
    confidence: float
    pages: int = 1
    warnings: list[str] = field(default_factory=list)


def _configure_tesseract() -> None:
    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def is_tesseract_available() -> bool:
    _configure_tesseract()
    if shutil.which(pytesseract.pytesseract.tesseract_cmd) is None:
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Enhance image contrast and resolution before running Tesseract OCR."""
    processed = ImageOps.exif_transpose(image)
    if processed.mode != "L":
        processed = processed.convert("L")

    # Upscale small scans to improve OCR accuracy
    min_dim = min(processed.size)
    if min_dim < 900:
        scale = min(2.5, 900 / max(min_dim, 1))
        new_size = (int(processed.width * scale), int(processed.height * scale))
        processed = processed.resize(new_size, Image.Resampling.LANCZOS)

    processed = ImageOps.autocontrast(processed)
    processed = processed.filter(ImageFilter.SHARPEN)
    return processed


def _run_tesseract_on_image(image: Image.Image) -> tuple[str, float]:
    _configure_tesseract()
    processed = _preprocess_image(image)
    config = "--oem 3 --psm 6"

    data = pytesseract.image_to_data(
        processed,
        config=config,
        output_type=pytesseract.Output.DICT,
    )
    confidences = [
        float(conf) / 100.0
        for conf, word in zip(data.get("conf", []), data.get("text", []))
        if str(word).strip() and str(conf) not in ("-1", "")
    ]
    text = pytesseract.image_to_string(processed, config=config).strip()
    avg_conf = round(mean(confidences), 4) if confidences else (0.5 if text else 0.0)
    return text, avg_conf


def extract_text_from_file(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> OCRResult:
    """Extract text from images, PDFs, or plain-text documents."""
    lower_name = filename.lower()
    lower_ct = (content_type or "").lower()

    if lower_ct.startswith("text/") or lower_name.endswith(".txt"):
        decoded = file_bytes.decode("utf-8", errors="replace").strip()
        return OCRResult(
            text=decoded,
            engine="plain_text",
            confidence=1.0 if decoded else 0.0,
            pages=1,
        )

    if lower_ct == "application/pdf" or lower_name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            page_texts: list[str] = []
            for page in reader.pages:
                extracted = (page.extract_text() or "").strip()
                if extracted:
                    page_texts.append(extracted)

            combined = "\n\n".join(page_texts).strip()
            if combined:
                return OCRResult(
                    text=combined,
                    engine="pypdf_text_layer",
                    confidence=0.95,
                    pages=len(reader.pages),
                )

            # Fallback: extract embedded images from scanned PDF pages and run Tesseract
            if is_tesseract_available():
                ocr_chunks: list[str] = []
                confs: list[float] = []
                for page in reader.pages:
                    for img_file in getattr(page, "images", []):
                        with Image.open(io.BytesIO(img_file.data)) as img:
                            chunk, conf = _run_tesseract_on_image(img)
                            if chunk:
                                ocr_chunks.append(chunk)
                                confs.append(conf)
                if ocr_chunks:
                    return OCRResult(
                        text="\n\n".join(ocr_chunks),
                        engine="tesseract_ocr_pdf",
                        confidence=round(mean(confs), 4),
                        pages=len(reader.pages),
                    )

            return OCRResult(
                text="",
                engine="pypdf_text_layer",
                confidence=0.0,
                pages=len(reader.pages),
                warnings=["No extractable text layer found in PDF."],
            )
        except Exception as exc:
            raise OCRProcessingError(f"Failed to read PDF document: {exc}") from exc

    # Image documents
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            if not is_tesseract_available():
                raise OCRProcessingError(
                    "Tesseract OCR binary is not installed on this host. "
                    "Install Tesseract OCR (or set TESSERACT_CMD), upload a text-based PDF/TXT, "
                    "or run one of the built-in sample scenarios."
                )
            text, confidence = _run_tesseract_on_image(img)
            return OCRResult(
                text=text,
                engine="tesseract_ocr",
                confidence=confidence,
                pages=1,
            )
    except OCRProcessingError:
        raise
    except Exception as exc:
        raise OCRProcessingError(f"Unsupported or corrupted image file: {exc}") from exc
