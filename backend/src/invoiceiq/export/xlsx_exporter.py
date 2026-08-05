"""Excel (.xlsx) export using openpyxl."""

from __future__ import annotations

import io

from openpyxl import Workbook

from ..extract.schema import ExtractionResult


def export_xlsx(results: list[ExtractionResult], config: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Extraction Results"

    fields = config.get("columns")
    if not fields:
        all_fields: set[str] = set()
        for r in results:
            all_fields.update(r.fields.keys())
        fields = sorted(all_fields)

    header = [c.get("header", c["field"]) if isinstance(c, dict) else c for c in fields]
    ws.append(header)

    for result in results:
        row = []
        for c in fields:
            field_name = c["field"] if isinstance(c, dict) else c
            candidate = result.fields.get(field_name)
            if candidate and candidate.value:
                val = candidate.value.get("value") if isinstance(candidate.value, dict) else candidate.value
                row.append(val if val is not None else "")
            else:
                row.append("")
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()