"""Extraction orchestrator: normalized pages -> ExtractionResult.

Rules-first (docs/12 §2): deterministic extractors resolve every well-formed
field, then the LLM fills the residual (supplier name, wording, line
descriptions, corroboration) and merge reconciles both sources. With no LLM
client configured (no API key), the rules result stands on its own."""

from __future__ import annotations

from ..llm.adapter import llm_line_items as adapter_line_items
from ..llm.adapter import llm_to_candidates
from ..llm.client import LLMClient, complete_structured
from ..llm.prompts.extract import build_messages
from ..llm.schema import LLMExtraction
from ..ocr import OCRPage, PageBlock
from ..validate.engine import vat_country
from .merge import merge_fields
from .rules import (
    classify_doc_type,
    detect_language,
    extract_line_items,
    find_currency,
    find_dates,
    find_iban,
    find_invoice_number,
    find_money,
    find_supplier_name,
    find_vat,
    scalar,
)
from .schema import ExtractionResult, FieldCandidate


def _blocks(pages: list[OCRPage]) -> list[tuple[int, PageBlock]]:
    return [(page_no, block) for page_no, page in enumerate(pages) for block in page.blocks]


def extract_from_pages(
    pages: list[OCRPage],
    *,
    client: LLMClient | None = None,
) -> ExtractionResult:
    """Run the full rules -> LLM -> merge chain over normalized pages."""
    blocks = _blocks(pages)
    text = "\n".join(block.text for _, block in blocks)

    doc_type, _ = classify_doc_type(text)
    language, _ = detect_language(text)
    vat = find_vat(blocks)
    country = vat_country(scalar(vat)) if vat else None

    fields: dict[str, FieldCandidate] = {}
    for candidate in (
        vat,
        find_iban(blocks),
        find_invoice_number(blocks),
        find_currency(blocks),
        find_supplier_name(blocks),
    ):
        if candidate is not None:
            fields[candidate.field] = candidate
    invoice_date, due_date = find_dates(blocks)
    for candidate in (invoice_date, due_date):
        if candidate is not None:
            fields[candidate.field] = candidate
    fields.update(find_money(blocks))

    line_items = extract_line_items(pages)

    if client is not None:
        llm = complete_structured(
            client, build_messages(pages, language=language, country=country), LLMExtraction
        )
        fields = dict(merge_fields(fields, llm_to_candidates(llm, blocks)))
        if not line_items and llm.line_items:
            line_items = adapter_line_items(llm)
        if llm.doc_type:
            doc_type = llm.doc_type
        if llm.language:
            language = llm.language
        if llm.country:
            country = llm.country.upper()

    return ExtractionResult(
        doc_type=doc_type,
        language=language,
        country=country,
        fields=fields,
        line_items=line_items,
    )
