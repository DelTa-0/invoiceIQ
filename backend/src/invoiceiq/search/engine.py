"""Natural-language search engine over extraction results.

Parses user queries into structured filters and queries the
extraction_fields table directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import ExtractionField


@dataclass
class SearchResult:
    field_id: str
    invoice_id: str
    field_name: str
    field_value: dict | None
    confidence: float | None
    method: str | None
    source_text: str | None
    validation_status: str | None


class SearchEngine:
    """Parses natural-language queries into structured filters and
    queries the extraction_fields table."""

    CURRENCY_RE = re.compile(r"(?:over|above|more than|greater than|>=|>)\s*([\d.,]+)\s*(\w{3})?", re.IGNORECASE)
    CURRENCY_RE_LT = re.compile(r"(?:under|below|less than|<=|<)\s*([\d.,]+)\s*(\w{3})?", re.IGNORECASE)
    DATE_AFTER = re.compile(r"(?:after|from|since|starting)\s+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", re.IGNORECASE)
    DATE_BEFORE = re.compile(r"(?:before|until|through|ending|to)\s+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", re.IGNORECASE)
    COUNTRY_RE = re.compile(r"(?:from|in|based in|located in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE)
    STATUS_RE = re.compile(r"(?:status|state)\s+(?:is|are|was|were)\s+(\w+)", re.IGNORECASE)
    DOCTYPE_RE = re.compile(r"(?:find|show|get|list)\s+(?:all\s+)?(?:invoice|receipt|po|purchase order|contract|shipping|customs|bank statement|tax document|report)s?", re.IGNORECASE)

    def search(
        self,
        session: Session,
        query: str,
        org_id: str,
        limit: int = 100,
    ) -> list[SearchResult]:
        """Execute a natural-language search across extraction results."""
        filters = self._parse(query)

        stmt = select(ExtractionField).where(
            ExtractionField.invoice_id.in_(
                select(ExtractionField.invoice_id)
            )
        )

        if filters.get("field_name"):
            stmt = stmt.where(ExtractionField.field.ilike(f"%{filters['field_name']}%"))

        if filters.get("min_confidence") is not None:
            stmt = stmt.where(ExtractionField.confidence >= filters["min_confidence"])

        if filters.get("max_confidence") is not None:
            stmt = stmt.where(ExtractionField.confidence <= filters["max_confidence"])

        if filters.get("validation_status"):
            stmt = stmt.where(ExtractionField.validator_status == filters["validation_status"])

        if filters.get("text_query"):
            stmt = stmt.where(
                or_(
                    ExtractionField.value.cast(str).ilike(f"%{filters['text_query']}%"),
                    ExtractionField.source_text.ilike(f"%{filters['text_query']}%"),
                )
            )

        if filters.get("min_amount"):
            stmt = stmt.where(ExtractionField.value.cast(str).ilike(f"%{filters['min_amount']}%"))

        if filters.get("max_amount"):
            stmt = stmt.where(ExtractionField.value.cast(str).ilike(f"%{filters['max_amount']}%"))

        if filters.get("date_after"):
            stmt = stmt.where(ExtractionField.value.cast(str).ilike(f"%{filters['date_after']}%"))

        if filters.get("date_before"):
            stmt = stmt.where(ExtractionField.value.cast(str).ilike(f"%{filters['date_before']}%"))

        if filters.get("country"):
            stmt = stmt.where(ExtractionField.source_text.ilike(f"%{filters['country']}%"))

        if filters.get("doc_type"):
            pass

        if filters.get("status"):
            stmt = stmt.where(ExtractionField.status == filters["status"])

        stmt = stmt.order_by(ExtractionField.confidence.desc().nulls_last())
        stmt = stmt.limit(limit)

        rows = session.execute(stmt).scalars().all()

        return [
            SearchResult(
                field_id=str(row.id),
                invoice_id=str(row.invoice_id),
                field_name=row.field,
                field_value=row.value,
                confidence=row.confidence,
                method=row.method,
                source_text=row.source_text,
                validation_status=row.validator_status,
            )
            for row in rows
        ]

    def _parse(self, query: str) -> dict:
        filters: dict = {}

        m = self.CURRENCY_RE.search(query)
        if m:
            filters["min_amount"] = m.group(1).replace(",", "")

        m = self.CURRENCY_RE_LT.search(query)
        if m:
            filters["max_amount"] = m.group(1).replace(",", "")

        m = self.DATE_AFTER.search(query)
        if m:
            filters["date_after"] = m.group(1)

        m = self.DATE_BEFORE.search(query)
        if m:
            filters["date_before"] = m.group(1)

        m = self.COUNTRY_RE.search(query)
        if m:
            filters["country"] = m.group(1)

        m = self.STATUS_RE.search(query)
        if m:
            filters["status"] = m.group(1).lower()

        m = self.DOCTYPE_RE.search(query)
        if m:
            doc_type_str = m.group(0).split()[-1].lower()
            type_map = {
                "invoice": "invoice",
                "receipt": "receipt",
                "po": "purchase_order",
                "purchase order": "purchase_order",
                "contract": "contract",
                "shipping": "shipping_document",
                "customs": "customs_form",
                "bank statement": "bank_statement",
                "tax document": "tax_document",
                "report": "financial_report",
            }
            filters["doc_type"] = type_map.get(doc_type_str)

        if any(kw in query.lower() for kw in ["high confidence", "confident", "reliable"]):
            filters["min_confidence"] = 0.8

        filter_keywords = {
            "over", "above", "more than", "greater than", "under", "below",
            "less than", "after", "from", "since", "starting", "before",
            "until", "through", "ending", "to", "is", "are", "was", "were",
            "find", "show", "get", "list", "every", "all",
        }
        words = [w for w in query.split() if w.lower() not in filter_keywords and not w.startswith(("€", "$", "£", ">=", "<=", ">", "<"))]
        if words:
            filters["text_query"] = " ".join(words)

        return filters