"""OCR engine routing helpers (docs/14 §2)."""

from __future__ import annotations

from pathlib import Path

from .base import OCRNoTextError, OCRPage
from .digital import DigitalPDFEngine

_PDF_SUFFIXES = {".pdf"}


def suffix_of(filename: str) -> str:
    return Path(filename or "unnamed").suffix.lower()


def normalize_document(data: bytes, filename: str) -> list[OCRPage]:
    """Route raw upload bytes to the right engine and return normalized pages.

    Phase 1 slice A: the digital text-layer path only. Images/scanned PDFs
    raise `OCRNoTextError` until the PaddleOCR path lands (docs/14 §7 ladder).
    """
    suffix = suffix_of(filename)
    if suffix in _PDF_SUFFIXES:
        return DigitalPDFEngine().extract(data)
    raise OCRNoTextError(f"no OCR engine for .{suffix or 'unknown'} yet (scan path is Phase 1 slice B)")
