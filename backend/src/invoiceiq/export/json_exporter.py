"""JSON export."""

from __future__ import annotations

import json

from ..extract.schema import ExtractionResult


def export_json(results: list[ExtractionResult], config: dict) -> bytes:
    records = []
    for result in results:
        record: dict = {}
        for field_name, candidate in result.fields.items():
            if candidate.value:
                val = candidate.value.get("value") if isinstance(candidate.value, dict) else candidate.value
                record[field_name] = val
            else:
                record[field_name] = None
        if result.line_items:
            record["line_items"] = [
                {
                    "description": li.description,
                    "quantity": li.quantity,
                    "unit_price": li.unit_price,
                    "net": li.net,
                    "vat_rate": li.vat_rate,
                    "vat_amount": li.vat_amount,
                    "gross": li.gross,
                }
                for li in result.line_items
            ]
        records.append(record)

    output = {
        "results": records,
        "count": len(records),
        "doc_type": results[0].doc_type if results else None,
    }
    return json.dumps(output, indent=2, default=str).encode("utf-8")