"""Scan-path tests: preprocessing, rasterization, routing, escalation ladder.

Real-engine cases (PaddleOCR / Tesseract) are skipped when no OCR engine is
installed so the suite stays green on bare CI; the routing and escalation
logic itself is tested with injected fake engines.
"""

from __future__ import annotations

import io

import pytest
from invoiceiq.ocr import (
    OCRNoTextError,
    OCRPage,
    PageBlock,
    paddle_available,
    prepare_image,
    rasterize_pdf,
    scan_image,
    tesseract_available,
)
from invoiceiq.ocr.normalize import normalize_document
from PIL import Image

from tests.helpers.pdf import make_invoice_pdf, make_scanned_image, make_scanned_pdf

_OCR_AVAILABLE = paddle_available() or tesseract_available()


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def test_prepare_image_applies_exif_orientation():
    img = Image.new("RGB", (100, 200), "white")
    exif = Image.Exif()
    exif[274] = 6  # Orientation: rotate 90 CW for display
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif, dpi=(300, 300))

    prepared = prepare_image(buf.getvalue())
    assert prepared.size == (200, 100)


def test_prepare_image_upscales_low_dpi_scan():
    img = Image.new("RGB", (200, 300), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(72, 72))

    prepared = prepare_image(buf.getvalue())
    assert prepared.width > 200 and prepared.height > 300


def test_prepare_image_keeps_good_dpi():
    img = Image.new("RGB", (200, 300), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(300, 300))

    prepared = prepare_image(buf.getvalue())
    assert prepared.size == (200, 300)


def test_rasterize_pdf_returns_images():
    pages = rasterize_pdf(make_scanned_pdf())
    assert len(pages) == 1
    assert pages[0].mode == "RGB"
    assert pages[0].width > 1000


# ---------------------------------------------------------------------------
# Routing (docs/14 §2)
# ---------------------------------------------------------------------------


def test_normalize_digital_pdf_stays_on_digital_path():
    pages = normalize_document(make_invoice_pdf(), "invoice.pdf")
    assert pages
    assert all(p.engine == "pdfplumber" for p in pages)
    assert any(p.blocks for p in pages)


def test_normalize_rejects_unknown_suffix():
    with pytest.raises(OCRNoTextError):
        normalize_document(b"data", "note.txt")


@pytest.mark.skipif(not _OCR_AVAILABLE, reason="no OCR engine installed")
def test_normalize_scanned_pdf_routes_to_scan():
    pages = normalize_document(make_scanned_pdf(), "scan.pdf")
    assert pages
    assert all(p.engine in ("paddleocr", "tesseract") for p in pages)
    assert any(p.blocks for p in pages)


@pytest.mark.skipif(not _OCR_AVAILABLE, reason="no OCR engine installed")
def test_normalize_scanned_image_routes_to_scan():
    pages = normalize_document(make_scanned_image(), "scan.png")
    assert len(pages) == 1
    assert pages[0].engine in ("paddleocr", "tesseract")
    assert pages[0].blocks


# ---------------------------------------------------------------------------
# Escalation ladder (docs/14 §7) with injected fake engines
# ---------------------------------------------------------------------------


class _EmptyEngine:
    name = "empty"

    def extract(self, image, *, lang=None):
        return OCRPage(page_no=0, width=image.width, height=image.height, engine=self.name)


class _TextEngine:
    name = "text"

    def extract(self, image, *, lang=None):
        return OCRPage(
            page_no=0,
            width=image.width,
            height=image.height,
            engine=self.name,
            blocks=[PageBlock(text="Gesamtbetrag 1190,00 EUR", conf=0.9, bbox=[0.1, 0.1, 0.9, 0.2])],
        )


def _white_image() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_empty_result_escalates_to_no_text_error():
    with pytest.raises(OCRNoTextError):
        scan_image(_white_image(), engine=_EmptyEngine())


def test_fallback_rescues_empty_primary(monkeypatch):
    from invoiceiq.ocr import scan as scan_mod

    monkeypatch.setattr(scan_mod, "_fallback_for", lambda engine: _TextEngine())
    page = scan_image(_white_image(), engine=_EmptyEngine())
    assert page.engine == "text"
    assert page.blocks[0].text == "Gesamtbetrag 1190,00 EUR"


def test_stronger_fallback_replaces_weak_primary(monkeypatch):
    from invoiceiq.ocr import scan as scan_mod

    class _PoorEngine:
        name = "poor"

        def extract(self, image, *, lang=None):
            return OCRPage(
                page_no=0,
                width=image.width,
                height=image.height,
                engine=self.name,
                blocks=[PageBlock(text="x", conf=0.2, bbox=[0, 0, 1, 1])],
            )

    monkeypatch.setattr(scan_mod, "_fallback_for", lambda engine: _TextEngine())
    page = scan_image(_white_image(), engine=_PoorEngine())
    # fallback has higher avg confidence -> wins
    assert page.engine == "text"
