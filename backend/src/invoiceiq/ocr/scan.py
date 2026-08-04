"""Scan OCR path: images and text-less PDFs via PaddleOCR, Tesseract fallback.

Engine ladder (docs/14 §7): PaddleOCR PP-OCRv6 is primary; if a page comes
back empty or below `IIQ_OCR_MIN_SCORE`, the fallback engine gets a turn.
When both fail the page raises `OCRNoTextError` — never confident garbage.

The heavy models are loaded lazily on first `predict`, and the module is
import-safe without any OCR package installed (routing degrades gracefully).
"""

from __future__ import annotations

import importlib.util
import io
import logging
import shutil
from typing import Any

from PIL import Image, ImageOps

from ..settings import get_settings
from .base import OCRNoTextError, OCRPage, PageBlock

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_MIN_DPI = 200.0
_TARGET_DPI = 300.0


def image_suffixes() -> frozenset[str]:
    return frozenset(_IMAGE_SUFFIXES)


# ---------------------------------------------------------------------------
# Preprocessing (docs/14 §4)
# ---------------------------------------------------------------------------


def load_image(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data))
    except Exception as exc:
        raise OCRNoTextError(f"unreadable image: {exc}") from exc


def _upscale_low_dpi(image: Image.Image) -> Image.Image:
    dpi = image.info.get("dpi")
    if not dpi:
        return image
    try:
        current = float(dpi[0] if isinstance(dpi, tuple) else dpi)
    except (TypeError, ValueError):
        return image
    if 0 < current < _MIN_DPI:
        scale = _TARGET_DPI / current
        return image.resize(
            (int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS
        )
    return image


def prepare_image(data: bytes | Image.Image) -> Image.Image:
    """EXIF orient, upscale low-DPI scans, normalize to RGB."""
    image = ImageOps.exif_transpose(load_image(data) if isinstance(data, bytes) else data)
    image = _upscale_low_dpi(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return image


def _too_poor(page: OCRPage, min_score: float) -> bool:
    return not page.blocks or page.avg_confidence < min_score


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------


def paddle_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


class PaddleEngine:
    """PaddleOCR PP-OCRv6 text recognition (docs/14 §3 primary engine)."""

    name = "paddleocr"

    def __init__(self) -> None:
        self._ocr = None

    def _client(self, lang: str | None):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                lang=lang or "en",
                use_doc_orientation_classify=False,
                use_textline_orientation=False,
                use_doc_unwarping=False,
                enable_mkldnn=False,  # oneDNN on Windows raises NotImplementedError
            )
        return self._ocr

    def extract(self, image: Image.Image, *, lang: str | None = None) -> OCRPage:
        import numpy as np

        page = OCRPage(page_no=0, width=image.width, height=image.height, engine=self.name)
        result = self._client(lang).predict(np.array(image))
        if not result:
            return page
        rec = result[0]
        texts = rec.get("rec_texts")
        scores = rec.get("rec_scores")
        boxes = rec.get("rec_boxes")
        texts = [] if texts is None else texts
        scores = [] if scores is None else scores
        boxes = [] if boxes is None else boxes
        w, h = image.width, image.height
        ordered = sorted(
            (
                (float(score), _box_bbox(box, w, h), (text or "").strip())
                for box, score, text in zip(boxes, scores, texts, strict=False)
                if text and text.strip()
            ),
            key=lambda item: (item[2][1], item[2][0]),
        )
        for order, (conf, bbox, text) in enumerate(ordered):
            page.blocks.append(
                PageBlock(text=text, conf=conf, bbox=bbox, line_no=order, reading_order=order)
            )
        return page


def _box_bbox(box, width: int, height: int) -> list[float]:
    """4-point polygon -> normalized [x0, y0, x1, y1]."""
    try:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
    except (TypeError, IndexError):
        return []
    if not width or not height:
        return []
    return [min(xs) / width, min(ys) / height, max(xs) / width, max(ys) / height]


class TesseractEngine:
    """Tesseract v5 fallback for languages PaddleOCR covers poorly (docs/14 §7)."""

    name = "tesseract"

    @staticmethod
    def available() -> bool:
        return tesseract_available()

    def extract(self, image: Image.Image, *, lang: str | None = None) -> OCRPage:
        import pytesseract

        data = pytesseract.image_to_data(
            image, lang=lang or "eng", output_type=pytesseract.Output.DICT
        )
        page = OCRPage(page_no=0, width=image.width, height=image.height, engine=self.name)
        lines: dict[tuple[int, int, int], dict] = {}
        for word, conf, block, par, line, left, top, wid, hei in zip(
            data["text"],
            data["conf"],
            data["block_num"],
            data["par_num"],
            data["line_num"],
            data["left"],
            data["top"],
            data["width"],
            data["height"],
            strict=False,
        ):
            if not word or not word.strip() or int(conf) < 0:
                continue
            key = (int(block), int(par), int(line))
            entry = lines.setdefault(key, {"words": [], "conf": 0.0, "bbox": [left, top, left, top]})
            entry["words"].append(word.strip())
            entry["conf"] += float(conf)
            entry["bbox"][0] = min(entry["bbox"][0], int(left))
            entry["bbox"][1] = min(entry["bbox"][1], int(top))
            entry["bbox"][2] = max(entry["bbox"][2], int(left) + int(wid))
            entry["bbox"][3] = max(entry["bbox"][3], int(top) + int(hei))
        w, h = image.width, image.height
        for order, (_, entry) in enumerate(sorted(lines.items(), key=lambda kv: (kv[1]["bbox"][1], kv[1]["bbox"][0]))):
            conf = entry["conf"] / max(len(entry["words"]), 1) / 100.0
            x0, y0, x1, y1 = entry["bbox"]
            page.blocks.append(
                PageBlock(
                    text=" ".join(entry["words"]),
                    conf=min(conf, 1.0),
                    bbox=[x0 / w, y0 / h, x1 / w, y1 / h],
                    line_no=order,
                    reading_order=order,
                )
            )
        return page


# ---------------------------------------------------------------------------
# Selection & orchestration
# ---------------------------------------------------------------------------


def select_engine() -> Any:
    """Pick the OCR engine from settings (`IIQ_OCR_ENGINE`)."""
    engine = get_settings().ocr_engine
    if engine == "paddleocr":
        if not paddle_available():
            raise OCRNoTextError("ocr engine 'paddleocr' requested but not installed")
        return PaddleEngine()
    if engine == "tesseract":
        if not TesseractEngine.available():
            raise OCRNoTextError("ocr engine 'tesseract' requested but not installed")
        return TesseractEngine()
    if paddle_available():
        return PaddleEngine()
    if TesseractEngine.available():
        return TesseractEngine()
    raise OCRNoTextError("no OCR engine available (install paddleocr or tesseract)")


def _fallback_for(engine: Any) -> Any | None:
    if isinstance(engine, PaddleEngine):
        return TesseractEngine() if TesseractEngine.available() else None
    if isinstance(engine, TesseractEngine):
        return PaddleEngine() if paddle_available() else None
    return None


def scan_image(data: bytes, *, lang: str | None = None, engine: Any | None = None) -> OCRPage:
    """OCR a single image with the escalation ladder (docs/14 §7)."""
    return scan_prepared(prepare_image(data), lang=lang, engine=engine)


def scan_prepared(image: Image.Image, *, lang: str | None = None, engine: Any | None = None) -> OCRPage:
    """OCR an already-prepared PIL image (used for rasterized PDF pages)."""
    primary = engine or select_engine()
    min_score = get_settings().ocr_min_score
    page = primary.extract(image, lang=lang)
    if _too_poor(page, min_score):
        fallback = _fallback_for(primary)
        if fallback is not None:
            candidate = fallback.extract(image, lang=lang)
            if candidate.blocks and (not page.blocks or candidate.avg_confidence > page.avg_confidence):
                page = candidate
                logger.warning("scan OCR escalated to fallback engine: %s", fallback.name)
    if not page.blocks:
        raise OCRNoTextError("scan OCR found no readable text")
    return page
