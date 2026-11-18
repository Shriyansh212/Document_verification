from collections import defaultdict
from dataclasses import dataclass, field
import io
import os
from pathlib import Path
import re
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
    cmd = pytesseract.pytesseract.tesseract_cmd
    if not Path(cmd).is_file() and shutil.which(cmd) is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Enhance image contrast and clamp dimensions for fast, low-memory Tesseract OCR."""
    processed = ImageOps.exif_transpose(image)
    if processed.mode != "L":
        processed = processed.convert("L")

    width, height = processed.size
    max_dim = max(width, height)
    min_dim = min(width, height)

    # Cap large screenshots/scans to prevent memory spikes on constrained containers
    max_allowed = 1600
    if max_dim > max_allowed:
        scale = max_allowed / max_dim
        processed = processed.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
    elif max_dim < 1000 and min_dim < 600:
        # Gently upscale tiny crops without ever exceeding max_allowed
        scale = min(2.0, max_allowed / max(max_dim, 1))
        processed = processed.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )

    processed = ImageOps.autocontrast(processed)
    processed = processed.filter(ImageFilter.SHARPEN)
    return processed


def _detect_osd_rotation(image: Image.Image) -> int:
    """Detect clockwise rotation angle (0, 90, 180, 270) needed to orient text upright."""
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT, timeout=10)
        rotate = int(osd.get("rotate", 0)) % 360
        if rotate in (90, 180, 270):
            return rotate
    except Exception:
        pass
    return 0


def _ocr_single_pass(image: Image.Image) -> tuple[str, float, float]:
    """Run one Tesseract pass and return (text, avg_confidence, quality_score)."""
    config = "--oem 3 --psm 6"
    data = pytesseract.image_to_data(
        image,
        config=config,
        output_type=pytesseract.Output.DICT,
        timeout=25,
    )

    lines: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    confidences: list[float] = []
    alpha_words = 0

    texts = data.get("text", [])
    confs = data.get("conf", [])
    blocks = data.get("block_num", [])
    pars = data.get("par_num", [])
    line_nums = data.get("line_num", [])

    for idx, raw_word in enumerate(texts):
        word = str(raw_word).strip()
        if not word:
            continue
        key = (
            int(blocks[idx]) if idx < len(blocks) else 0,
            int(pars[idx]) if idx < len(pars) else 0,
            int(line_nums[idx]) if idx < len(line_nums) else 0,
        )
        lines[key].append(word)
        if re.search(r"[A-Za-z0-9]{2,}", word):
            alpha_words += 1
        raw_conf = str(confs[idx]) if idx < len(confs) else "-1"
        if raw_conf not in ("-1", ""):
            try:
                conf_val = float(raw_conf)
                if conf_val >= 0:
                    confidences.append(conf_val / 100.0)
            except ValueError:
                pass

    text = "\n".join(" ".join(words) for words in lines.values()).strip()
    avg_conf = round(mean(confidences), 4) if confidences else (0.5 if text else 0.0)
    quality = avg_conf * max(alpha_words, 1)
    return text, avg_conf, quality


def _run_tesseract_on_image(image: Image.Image) -> tuple[str, float]:
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    _configure_tesseract()
    processed = _preprocess_image(image)

    try:
        # Step 1: Try Tesseract OSD to auto-correct 90/180/270-degree scans
        osd_rotate = _detect_osd_rotation(processed)
        if osd_rotate:
            rotated = processed.rotate(-osd_rotate, expand=True)
            processed.close()
            processed = rotated

        best_text, best_conf, best_quality = _ocr_single_pass(processed)

        # Step 2: If confidence or readable word yield is still low, test 90° and 270° rotations
        if best_conf < 0.62 or len(re.findall(r"[A-Za-z0-9]{3,}", best_text)) < 10:
            for angle in (90, 270):
                candidate = processed.rotate(angle, expand=True)
                try:
                    c_text, c_conf, c_quality = _ocr_single_pass(candidate)
                    if c_quality > best_quality:
                        best_text, best_conf, best_quality = c_text, c_conf, c_quality
                finally:
                    candidate.close()

        return best_text, best_conf
    finally:
        processed.close()


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
