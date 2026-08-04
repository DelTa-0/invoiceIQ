"""Deterministic invoice PDF fixtures for tests + golden set generation.

Every figure is chosen so the deterministic rules layer and the arithmetic
validator agree: line net = qty*unit_price, VAT = net*rate/100, totals match.
"""

from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/times.ttf",
]

GERMAN_INVOICE: dict = {
    "supplier_name": "ACME Muster GmbH",
    "supplier_address": "Musterstraße 1, 10115 Berlin",
    "supplier_vat": "DE123456789",
    "invoice_number": "2024-0147",
    "invoice_date": "15.01.2024",
    "due_date": "14.02.2024",
    "currency": "EUR",
    "lines": [
        {
            "position": "1",
            "description": "Werkzeug-Set",
            "quantity": "2",
            "unit_price": "500,00",
            "net": "1000,00",
            "vat_rate": "19",
            "vat_amount": "190,00",
            "gross": "1190,00",
        }
    ],
    "subtotal": "1000,00",
    "vat_total": "190,00",
    "total": "1190,00",
    "iban": "DE89370400440532013000",
}


def make_blank_pdf() -> bytes:
    """A valid PDF with no text layer at all (scanned-like; must escalate)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    doc.build([])
    return buf.getvalue()


def make_invoice_pdf(spec: dict | None = None) -> bytes:
    """Render a reportlab PDF from a spec dict (defaults to the German one)."""
    s = spec or GERMAN_INVOICE
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(s["supplier_name"], styles["Heading2"]),
        Paragraph(s["supplier_address"], styles["Normal"]),
        Paragraph(f"USt-IdNr.: {s['supplier_vat']}", styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph(f"Rechnung Nr.: {s['invoice_number']}", styles["Normal"]),
        Paragraph(f"Rechnungsdatum: {s['invoice_date']}", styles["Normal"]),
        Paragraph(f"Fällig am: {s['due_date']}", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]
    header = ["Pos", "Beschreibung", "Menge", "Einzelpreis", "Netto", "MwSt %", "MwSt", "Brutto"]
    data = [[header[0], header[1], header[2], header[3], header[4], header[5], header[6], header[7]]]
    for line in s["lines"]:
        data.append(
            [
                line["position"],
                line["description"],
                line["quantity"],
                line["unit_price"],
                line["net"],
                line["vat_rate"],
                line["vat_amount"],
                line["gross"],
            ]
        )
    table = Table(data, colWidths=[16 * mm, 46 * mm, 16 * mm, 24 * mm, 22 * mm, 16 * mm, 20 * mm, 22 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Zwischensumme {s['subtotal']}", styles["Normal"]))
    story.append(Paragraph(f"MwSt. 19 % {s['vat_total']}", styles["Normal"]))
    story.append(Paragraph(f"Gesamtbetrag {s['total']} {s['currency']}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Zahlbar innerhalb von 30 Tagen. IBAN {s['iban']}", styles["Normal"]))
    doc.build(story)
    return buf.getvalue()


def make_scanned_image(spec: dict | None = None, *, dpi: int = 200) -> bytes:
    """Render the invoice as a raster image (no text layer) — a genuine scan.

    Uses a TrueType font when one is available so PaddleOCR can read it;
    falls back to PIL's tiny bitmap font otherwise.
    """
    s = spec or GERMAN_INVOICE
    page_w = int(A4[0] / 72 * dpi)
    page_h = int(A4[1] / 72 * dpi)
    img = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(img)

    font_path = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)
    font = ImageFont.truetype(font_path, int(dpi * 0.2)) if font_path else ImageFont.load_default()

    margin = int(dpi * 0.5)
    leading = int(dpi * 0.35)
    x, y = margin, margin

    def line(text: str) -> None:
        nonlocal y
        draw.text((x, y), text, fill="black", font=font)
        y += leading

    line(s["supplier_name"])
    line(s["supplier_address"])
    line(f"USt-IdNr.: {s['supplier_vat']}")
    y += leading
    line(f"Rechnung Nr.: {s['invoice_number']}")
    line(f"Rechnungsdatum: {s['invoice_date']}")
    line(f"Fällig am: {s['due_date']}")
    y += leading
    line("Pos  Beschreibung     Menge  Einzelpreis  Netto  MwSt %  MwSt  Brutto")
    for item in s["lines"]:
        line(
            f"{item['position']}  {item['description']}  {item['quantity']}  "
            f"{item['unit_price']}  {item['net']}  {item['vat_rate']}  "
            f"{item['vat_amount']}  {item['gross']}"
        )
    y += leading
    line(f"Zwischensumme {s['subtotal']}")
    line(f"MwSt. 19 % {s['vat_total']}")
    line(f"Gesamtbetrag {s['total']} {s['currency']}")
    y += leading
    line(f"Zahlbar innerhalb von 30 Tagen. IBAN {s['iban']}")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_scanned_pdf(spec: dict | None = None) -> bytes:
    """A PDF whose only content is an embedded scan image (no text layer)."""
    import fitz

    doc = fitz.open()
    try:
        page = doc.new_page(width=A4[0], height=A4[1])
        page.insert_image(page.rect, stream=make_scanned_image(spec))
        return doc.tobytes()
    finally:
        doc.close()
