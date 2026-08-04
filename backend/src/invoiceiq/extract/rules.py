"""Deterministic, auditable field extractors — the rules-first layer.

Every rule returns `FieldCandidate`/`LineItemCandidate` with `method="rules"`,
a grounded `source_text`, a normalized bbox, and a conservative confidence.
The LLM only ever sees the residue these rules cannot resolve (docs/12 §2).

Value envelope convention (stored in `FieldCandidate.value` as JSON):
    {"type": "text"|"date"|"money"|"vat"|"iban"|"number"|"currency",
     "value": <raw string as printed>,
     "numeric": <parsed float when applicable>,
     "iso": <ISO-8601 when applicable>}
"""

from __future__ import annotations

import re
from datetime import date

from ..ocr import OCRPage, PageBlock, TableCell
from ..validate.engine import VAT_PATTERNS, check_iban
from .schema import BBox, FieldCandidate, LineItemCandidate

# ---------------------------------------------------------------------------
# Value envelope helpers
# ---------------------------------------------------------------------------


def envelope(kind: str, value, *, numeric: float | None = None, iso: str | None = None) -> dict:
    out: dict = {"type": kind, "value": value}
    if numeric is not None:
        out["numeric"] = numeric
    if iso is not None:
        out["iso"] = iso
    return out


def scalar(candidate: FieldCandidate | None):
    """The human-readable value inside a candidate's envelope."""
    if candidate is None:
        return None
    v = candidate.value
    return v.get("value") if isinstance(v, dict) else v


def numeric(candidate: FieldCandidate | None) -> float | None:
    if candidate is None:
        return None
    v = candidate.value
    if isinstance(v, dict) and v.get("numeric") is not None:
        return v["numeric"]
    return None


def iso_value(candidate: FieldCandidate | None) -> str | None:
    if candidate is None:
        return None
    v = candidate.value
    return v.get("iso") if isinstance(v, dict) else None


def _bbox(block: PageBlock, page_no: int) -> BBox:
    x0, y0, x1, y1 = block.bbox or [0.0, 0.0, 0.0, 0.0]
    return BBox(page=page_no, x0=x0, y0=y0, x1=x1, y1=y1)


def _cand(
    field: str,
    value: dict,
    conf: float,
    *,
    source_text: str | None,
    block: PageBlock | None = None,
    page_no: int = 0,
    method: str = "rules",
) -> FieldCandidate:
    return FieldCandidate(
        field=field,
        value=value,
        confidence=round(conf, 4),
        method=method,
        source_text=source_text,
        bbox=_bbox(block, page_no) if block is not None else None,
    )


# ---------------------------------------------------------------------------
# Number parsing
# ---------------------------------------------------------------------------


def parse_decimal(raw: str) -> float | None:
    """Parse a printed number ('1.234,56', '1234.56', '1.234') to float.

    Locale ambiguity resolved by convention: the LAST separator is the decimal
    mark; anything before it is a thousands group separator.
    """
    s = re.sub(r"[^\d.,\-]", "", raw)
    if not s:
        return None
    negative = s.startswith("-")
    s = s.lstrip("-")
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        whole, sep, frac = s.partition(",")
        s = f"{whole}.{frac}" if len(frac) <= 2 else s.replace(",", "")
    elif "." in s:
        whole, sep, frac = s.partition(".")
        s = f"{whole}.{frac}" if len(frac) <= 2 else s.replace(".", "")
    try:
        value = float(s)
    except ValueError:
        return None
    return -value if negative else value


MONEY_RE = re.compile(
    r"(?P<cur>EUR|USD|GBP|CHF|PLN|SEK|NOK|DKK|CZK|HUF|RON|BGN|HRK|€|\$|£)"
    r"\s*(?P<num>\d[\d.,]{1,15})"
    r"|(?P<num2>\d[\d.,]{1,15})\s*"
    r"(?P<cur2>EUR|USD|GBP|CHF|PLN|SEK|NOK|DKK|CZK|HUF|RON|BGN|HRK|€|\$|£)"
    r"|(?P<num3>\d[\d.,]{1,15})",
    re.IGNORECASE,
)

CURRENCY_RE = re.compile(
    r"\b(EUR|USD|GBP|CHF|PLN|SEK|NOK|DKK|CZK|HUF|RON|BGN|HRK)\b|€|\$|£", re.IGNORECASE
)


def _amounts_in(text: str) -> list[tuple[float, str]]:
    """All currency-like amounts in a line, (value, raw token), low→high."""
    found: list[tuple[float, str]] = []
    for m in MONEY_RE.finditer(text):
        token = (
            m.group("num")
            or m.group("num2")
            or m.group("num3")
            or ""
        ).strip()
        value = parse_decimal(token)
        if value is None:
            continue
        if 0.0 <= value <= 1e9:
            found.append((value, token))
    return found


# ---------------------------------------------------------------------------
# Document-level classification & language
# ---------------------------------------------------------------------------

INVOICE_KW = ("rechnung", "invoice", "faktura", "facture", "fattura", "factuur", "fatura")
CREDIT_KW = (
    "gutschrift",
    "credit note",
    "creditnote",
    "credit memo",
    "avoir",
    "nota de credito",
    "nota de crédito",
    "nota di credito",
    "creditnota",
    "kreditnota",
)
PROFORMA_KW = ("proforma", "pro-forma", "pro forma", "vorabrechnung")

LANG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "de": (
        "rechnung", "zwischensumme", "gesamtbetrag", "mehrwertsteuer", "mwst", "mws", "ust",
        "rechnungsdatum", "fällig", "fälligkeit", "zahlbar", "netto", "brutto", "einzelpreis",
        "menge", "beschreibung", "rechnungsnummer",
    ),
    "en": (
        "invoice", "subtotal", "total", "vat", "quantity", "unit price", "description",
        "amount due", "due date", "net", "gross", "invoice number",
    ),
    "fr": (
        "facture", "sous-total", "total", "tva", "quantité", "prix unitaire", "description",
        "échéance", "net", "brut", "montant", "numéro de facture",
    ),
    "it": (
        "fattura", "importo", "iva", "quantità", "prezzo unitario", "descrizione", "totale",
        "netto", "scadenza", "numero fattura",
    ),
    "es": (
        "factura", "total", "iva", "cantidad", "precio unitario", "descripción", "base imponible",
        "importe", "neto", "bruto", "número de factura",
    ),
    "nl": (
        "factuur", "subtotaal", "totaal", "btw", "aantal", "eenheidsprijs", "omschrijving",
        "netto", "bruto", "vervaldatum", "factuurnummer",
    ),
}

COUNTRY_BY_LANG = {"de": "DE", "en": "GB", "fr": "FR", "it": "IT", "es": "ES", "nl": "NL"}


def classify_doc_type(text: str) -> tuple[str | None, float]:
    low = text.lower()
    if any(k in low for k in PROFORMA_KW):
        return "proforma", 0.9
    if any(k in low for k in CREDIT_KW):
        return "credit_note", 0.9
    if any(k in low for k in INVOICE_KW):
        return "invoice", 0.9
    return "other", 0.5


def detect_language(text: str) -> tuple[str | None, float]:
    low = text.lower()
    best, best_score = None, 0
    for lang, keywords in LANG_KEYWORDS.items():
        score = sum(1 for k in keywords if k in low)
        if score > best_score:
            best, best_score = lang, score
    if best is None:
        return None, 0.0
    return best, min(0.95, 0.5 + 0.1 * best_score)


# ---------------------------------------------------------------------------
# Field rules
# ---------------------------------------------------------------------------


_VAT_TOKEN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{6,14}\b")


def find_vat(blocks: list[tuple[int, PageBlock]]) -> FieldCandidate | None:
    for page_no, block in blocks:
        for token in _VAT_TOKEN_RE.findall(block.text.upper()):
            compact = token.replace(" ", "")
            for pattern in VAT_PATTERNS.values():
                if pattern.match(compact):
                    return _cand(
                        "supplier_vat",
                        envelope("vat", compact, iso=compact),
                        0.98,
                        source_text=block.text,
                        block=block,
                        page_no=page_no,
                    )
    return None


def find_iban(blocks: list[tuple[int, PageBlock]]) -> FieldCandidate | None:
    for page_no, block in blocks:
        for token in re.findall(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){12,30}\b", block.text.upper()):
            if check_iban(token).status == "pass":
                return _cand(
                    "iban",
                    envelope("iban", re.sub(r"\s+", "", token)),
                    0.98,
                    source_text=block.text,
                    block=block,
                    page_no=page_no,
                )
    return None


_INVNO_RE = re.compile(
    r"(?:invoice|rechnung|faktura|facture|fattura|factuur|fatura)"
    r"(?:\s*(?:nr\.?|no\.?|nummer|number|n°|n)?\.?\s*[:#]?\s*)"
    r"([A-Z0-9][A-Z0-9\-/._]{1,40})",
    re.IGNORECASE,
)


def find_invoice_number(blocks: list[tuple[int, PageBlock]]) -> FieldCandidate | None:
    for page_no, block in blocks:
        m = _INVNO_RE.search(block.text)
        if m:
            token = m.group(1).strip().strip(":.,;")
            if not re.fullmatch(r"\d{4}", token):  # unlikely to be just a year
                return _cand(
                    "invoice_number",
                    envelope("text", token),
                    0.85,
                    source_text=block.text,
                    block=block,
                    page_no=page_no,
                )
    return None


_DATE_RE = re.compile(r"\b(?P<d>\d{1,2})[./\-](?P<m>\d{1,2})[./\-](?P<y>(?:19|20)\d{2})\b")
_ISO_DATE_RE = re.compile(r"\b(?P<y>(?:19|20)\d{2})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})\b")
DUE_KEYWORDS = (
    "due", "fällig", "fälligkeit", "scadenza", "echeance", "échéance", "vencimiento",
    "vervaldatum", "vervaldag", "betaaldatum", "zahlbar", "payment date",
)


def _dates_in(block: PageBlock) -> list[tuple[date, str]]:
    out: list[tuple[date, str]] = []
    for regex in (_DATE_RE, _ISO_DATE_RE):
        for m in regex.finditer(block.text):
            y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
            if not (1 <= mo <= 12 and 1 <= d <= 31):
                continue
            try:
                out.append((date(y, mo, d), m.group(0)))
            except ValueError:
                continue
    return out


def find_dates(blocks: list[tuple[int, PageBlock]]) -> tuple[FieldCandidate | None, FieldCandidate | None]:
    invoice_cand: FieldCandidate | None = None
    due_cand: FieldCandidate | None = None
    for page_no, block in blocks:
        hits = _dates_in(block)
        if not hits:
            continue
        low = block.text.lower()
        if any(k in low for k in DUE_KEYWORDS) and due_cand is None:
            d, raw = hits[0]
            due_cand = _cand(
                "due_date", envelope("date", raw, iso=d.isoformat()), 0.9,
                source_text=block.text, block=block, page_no=page_no,
            )
        elif invoice_cand is None:
            d, raw = hits[0]
            invoice_cand = _cand(
                "invoice_date", envelope("date", raw, iso=d.isoformat()), 0.9,
                source_text=block.text, block=block, page_no=page_no,
            )
    return invoice_cand, due_cand


def find_currency(blocks: list[tuple[int, PageBlock]]) -> FieldCandidate | None:
    counts: dict[str, int] = {}
    hits: dict[str, tuple[PageBlock, int]] = {}
    for page_no, block in blocks:
        for m in CURRENCY_RE.finditer(block.text):
            code = (m.group(1) or m.group(0)).upper()
            if code in ("€", "$", "£"):
                code = {"€": "EUR", "$": "USD", "£": "GBP"}[code]
            counts[code] = counts.get(code, 0) + 1
            hits.setdefault(code, (block, page_no))
    if not counts:
        return None
    top = max(counts, key=counts.__getitem__)
    block, page_no = hits[top]
    return _cand(
        "currency", envelope("currency", top), 0.9,
        source_text=block.text, block=block, page_no=page_no,
    )


SUBTOTAL_KW = re.compile(
    r"subtotal|zwischensumme|sous-total|subtotaal|total net|net total|base imponible|"
    r"importo imponibile|totaal netto|\bnetto\b",
    re.IGNORECASE,
)
VAT_KW = re.compile(
    r"mehrwertsteuer|umsatzsteuer|mwst|mws|\bust\b|\bvat\b|\btva\b|\biva\b|\bbtw\b|"
    r"omzetbelasting|taxe|imposta|impuesto|\btax\b",
    re.IGNORECASE,
)
TOTAL_KW = re.compile(
    r"rechnungsbetrag|endbetrag|gesamtbetrag|gesamt|grand total|amount due|total a payer|"
    r"total à payer|totaalbedrag|totaal te betalen|importo totale|montant total|\btotale\b|"
    r"montant|\btotal\b|betrag|summe",
    re.IGNORECASE,
)


def find_money(blocks: list[tuple[int, PageBlock]]) -> dict[str, FieldCandidate]:
    """Locate subtotal / total_vat / total from keyword+amount lines."""
    results: dict[str, FieldCandidate] = {}
    for page_no, block in blocks:
        amounts = _amounts_in(block.text)
        if not amounts:
            continue
        value, raw = amounts[-1]
        if SUBTOTAL_KW.search(block.text):
            results["subtotal"] = _cand(
                "subtotal", envelope("money", raw, numeric=value), 0.9,
                source_text=block.text, block=block, page_no=page_no,
            )
        elif VAT_KW.search(block.text):
            results["total_vat"] = _cand(
                "total_vat", envelope("money", raw, numeric=value), 0.9,
                source_text=block.text, block=block, page_no=page_no,
            )
        elif TOTAL_KW.search(block.text):
            results["total"] = _cand(
                "total", envelope("money", raw, numeric=value), 0.9,
                source_text=block.text, block=block, page_no=page_no,
            )
    return results


_SUPPLIER_SKIP = (
    "rechnung", "invoice", "faktura", "facture", "fattura", "factuur", "fatura",
    "gutschrift", "angebot", "bestellung", "auftrag", "order", "offer", "credit note",
    "pos", "beschreibung", "description", "menge", "quantity", "einzelpreis", "unit price",
    "netto", "brutto", "mwst", "vat", "total", "summe", "betrag", "mit freundlichen",
)


def find_supplier_name(blocks: list[tuple[int, PageBlock]]) -> FieldCandidate | None:
    for page_no, block in blocks:
        text = block.text.strip()
        low = text.lower()
        if ":" in text or any(k in low for k in _SUPPLIER_SKIP):
            continue
        if len(text.split()) < 2 or sum(ch.isdigit() for ch in text) > 6:
            continue
        if block.bbox and block.bbox[1] > 0.6:  # must sit in the top 60% of the page
            continue
        if block.bbox and block.bbox[0] > 0.4:  # avoid centered footers/graphics
            continue
        return _cand(
            "supplier_name", envelope("text", text), 0.6,
            source_text=text, block=block, page_no=page_no,
        )
    return None


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

_TOTAL_ROW_KW = ("gesamt", "total", "summe", "betrag", "brutto", "netto", "zwischensumme")


def _classify_column(header: str) -> str:
    t = header.strip().lower()
    if any(k in t for k in ("beschreibung", "description", "bezeichnung", "article", "artikel", "product")):
        return "description"
    if any(k in t for k in ("menge", "quantity", "qty", "anzahl", "quantità", "cantidad", "hoeveelheid")):
        return "quantity"
    if any(k in t for k in ("einzelpreis", "unit price", "unitprice", "unit cost", "prix unitaire", "prezzo unitario")):
        return "unit_price"
    if "%" in t and any(k in t for k in ("vat", "mwst", "mws", "ust", "tva", "iva", "btw", "tax")):
        return "vat_rate"
    if any(k in t for k in ("netto", "net total", "total net", "montant ht", "base imponible", "imponibile")):
        return "net"
    if any(k in t for k in ("brutto", "bruto", "gross", "montant ttc", "total ttc")):
        return "gross"
    if t in ("vat", "mwst", "mws", "ust", "tva", "iva", "btw", "tax", "imposta", "impuesto"):
        return "vat_amount"
    if any(k in t for k in ("pos", "position", "nr", "lfd", "item no")):
        return "position"
    return "text"


def _parse_row(
    row: list[TableCell], columns: dict[str, int], position: int
) -> LineItemCandidate | None:
    texts = [c.text.strip() for c in row]
    if not any(texts):
        return None
    def num(col: str) -> float | None:
        idx = columns.get(col)
        if idx is None:
            return None
        return parse_decimal(texts[idx])

    desc_idx = columns.get("description")
    description = texts[desc_idx] if desc_idx is not None and texts[desc_idx] else None
    if description is None:
        for t in texts:
            if t and parse_decimal(t) is None:
                description = t
                break
    if description and any(k in description.lower() for k in _TOTAL_ROW_KW):
        return None

    quantity = num("quantity")
    unit_price = num("unit_price")
    net = num("net")
    vat_rate = num("vat_rate")
    vat_amount = num("vat_amount")
    gross = num("gross")

    if net is None and quantity is not None and unit_price is not None:
        net = round(quantity * unit_price, 2)
    if vat_amount is None and net is not None and vat_rate is not None:
        vat_amount = round(net * vat_rate / 100, 2)
    if gross is None and net is not None and vat_amount is not None:
        gross = round(net + vat_amount, 2)

    numbers = [quantity, unit_price, net, vat_rate, vat_amount, gross]
    if description is None and not any(v is not None for v in numbers):
        return None
    if description is None:
        description = ""

    return LineItemCandidate(
        position=position,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        net=net,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        gross=gross,
        confidence=0.85 if description else 0.6,
    )


def extract_line_items(pages: list[OCRPage]) -> list[LineItemCandidate]:
    items: list[LineItemCandidate] = []
    for page in pages:
        for table in page.tables:
            rows = [r for r in table.rows if any(c.text.strip() for c in r)]
            if len(rows) < 2:
                continue
            header_row = next(
                (i for i in range(min(3, len(rows))) if _classify_column(rows[i][0].text) != "text"),
                0,
            )
            columns: dict[str, int] = {}
            for idx, cell in enumerate(rows[header_row]):
                role = _classify_column(cell.text)
                if role != "text" and role not in columns:
                    columns[role] = idx
            if not columns:
                continue
            position = len(items) + 1
            for row in rows[header_row + 1 :]:
                item = _parse_row(row, columns, position)
                if item is not None:
                    items.append(item)
                    position += 1
    return items
