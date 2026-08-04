"""Rasterize text-less PDFs to images for the scan path (docs/14 §2, §4).

Only touched when a PDF carries no usable text layer, so the digital fast
path never pays for rendering.
"""

from __future__ import annotations

import fitz
from PIL import Image

from .base import OCRNoTextError

DEFAULT_DPI = 300.0


def rasterize_pdf(data: bytes, *, dpi: float = DEFAULT_DPI) -> list[Image.Image]:
    """Render every PDF page at `dpi` DPI into an RGB PIL image."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise OCRNoTextError(f"unreadable PDF: {exc}") from exc
    images: list[Image.Image] = []
    try:
        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        for page in doc:
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    finally:
        doc.close()
    if not images:
        raise OCRNoTextError("empty PDF")
    return images
