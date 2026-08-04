"""Adapt LLM output into the shared candidate contract.

LLM values are raw strings; they are wrapped into the same value envelopes the
rules layer produces so merge + validation + confidence stay uniform. A value
is only trusted when it can be grounded back to a document block (`bbox`),
otherwise its confidence is cut (docs/13 §6)."""

from __future__ import annotations

from ..extract.rules import envelope, parse_decimal
from ..extract.schema import BBox, FieldCandidate, LineItemCandidate
from ..ocr import PageBlock
from .schema import LLMExtraction, LLMField

MONEY_FIELDS = {"subtotal", "total_vat", "total", "shipping", "other"}
DATE_FIELDS = {"invoice_date", "due_date"}


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def attach_bbox(blocks: list[tuple[int, PageBlock]], source_text: str | None) -> BBox | None:
    if not source_text:
        return None
    needle = _normalize(source_text)
    for page_no, block in blocks:
        hay = _normalize(block.text)
        if needle in hay or hay in needle:
            x0, y0, x1, y1 = block.bbox or [0.0, 0.0, 0.0, 0.0]
            return BBox(page=page_no, x0=x0, y0=y0, x1=x1, y1=y1)
    return None


def _envelope_for(field: str, value: str | float | int | None) -> dict:
    if field in MONEY_FIELDS:
        return envelope("money", value, numeric=parse_decimal(str(value)) if value is not None else None)
    if field in DATE_FIELDS:
        iso = str(value) if value else None
        return envelope("date", iso, iso=iso)
    if field == "supplier_vat":
        return envelope("vat", value)
    if field == "iban":
        return envelope("iban", value)
    if field == "currency":
        return envelope("currency", value)
    return envelope("text", value)


def field_candidate(
    field: str, llm: LLMField, blocks: list[tuple[int, PageBlock]]
) -> FieldCandidate | None:
    if llm.missing or llm.value is None:
        return None
    bbox = attach_bbox(blocks, llm.source_text)
    return FieldCandidate(
        field=field,
        value=_envelope_for(field, llm.value),
        confidence=0.85 if bbox else 0.6,
        method="llm",
        source_text=llm.source_text,
        bbox=bbox,
    )


def llm_to_candidates(
    llm: LLMExtraction, blocks: list[tuple[int, PageBlock]]
) -> dict[str, FieldCandidate]:
    out: dict[str, FieldCandidate] = {}
    for field, value in llm.fields.items():
        candidate = field_candidate(field, value, blocks)
        if candidate is not None:
            out[field] = candidate
    return out


def llm_line_items(llm: LLMExtraction) -> list[LineItemCandidate]:
    items: list[LineItemCandidate] = []
    for position, line in enumerate(llm.line_items, start=1):
        def parse(raw: str | None) -> float | None:
            return parse_decimal(raw) if raw else None

        items.append(
            LineItemCandidate(
                position=position,
                description=line.description,
                quantity=parse(line.quantity),
                unit_price=parse(line.unit_price),
                net=parse(line.net),
                vat_rate=parse(line.vat_rate),
                vat_amount=parse(line.vat_amount),
                gross=parse(line.gross),
                confidence=0.85 if line.source_text else 0.6,
            )
        )
    return items
