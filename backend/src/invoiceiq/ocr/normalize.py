"""OCR engine routing helpers (docs/14 §2).

PDF with a real text layer  -> digital fast path (pdfplumber, cost ~ 0)
PDF without a text layer    -> rasterize (300 DPI) -> scan OCR per page
Images                      -> EXIF orient -> scan OCR
Anything else               -> `OCRNoTextError` (failed/UNSUPPORTED_FORMAT)
"""

from __future__ import annotations

from pathlib import Path

from .base import OCRNoTextError, OCRPage
from .digital import DigitalPDFEngine
from .rasterize import rasterize_pdf
from .scan import image_suffixes, scan_image, scan_prepared

_PDF_SUFFIXES = {".pdf"}


def suffix_of(filename: str) -> str:
    return Path(filename or "unnamed").suffix.lower()


def normalize_document(data: bytes, filename: str) -> list[OCRPage]:
    """Route raw upload bytes to the right engine and return normalized pages."""
    suffix = suffix_of(filename)
    if suffix in _PDF_SUFFIXES:
        return _normalize_pdf(data)
    if suffix in image_suffixes():
        return [scan_image(data)]
    raise OCRNoTextError(f"unsupported file type .{suffix or 'unknown'}")


def _normalize_pdf(data: bytes) -> list[OCRPage]:
    pages = DigitalPDFEngine().extract(data)
    if any(p.blocks for p in pages):
        return pages
    # Scanned / text-less PDF: rasterize and OCR each page (docs/14 §2, §7).
    return [scan_prepared(image) for image in rasterize_pdf(data)]
