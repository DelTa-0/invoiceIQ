"""Deterministic invoice PDF fixtures for tests + golden set generation.

Every figure is chosen so the deterministic rules layer and the arithmetic
validator agree: line net = qty*unit_price, VAT = net*rate/100, totals match.
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
