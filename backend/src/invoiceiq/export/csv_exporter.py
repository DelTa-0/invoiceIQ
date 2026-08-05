"""CSV export.  UTF-8 BOM for Excel compatibility."""

from __future__ import annotations

import csv
import io

from ..extract.schema import ExtractionResult


def export_csv(results: list[ExtractionResult], config: dict) -> bytes:
    buf = io.BytesIO()
    writer = csv.writer(io.TextIOWrapper(buf, encoding="utf-8", newline="", write_through=True))

    fields = config.get("columns")
    if not fields:
        all_fields: set[str] = set()
        for r in results:
            all_fields.update(r.fields.keys())
        fields = sorted(all_fields)

    header = [c.get("header", c["field"]) if isinstance(c, dict) else c for c in fields]
    writer.writerow(header)

    for result in results:
        row = []
        for c in fields:
            field_name = c["field"] if isinstance(c, dict) else c
            candidate = result.fields.get(field_name)
            if candidate and candidate.value:
                val = candidate.value.get("value") if isinstance(candidate.value, dict) else candidate.value
                row.append(str(val) if val is not None else "")
            else:
                row.append("")
        writer.writerow(row)

    return buf.getvalue()