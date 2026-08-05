"""Export engine orchestrator.

Dispatches to format-specific exporters and records the export
in the database.  See docs/14 §8.
"""

from __future__ import annotations

from .csv_exporter import export_csv
from .json_exporter import export_json
from .webhook import dispatch_webhook
from .xlsx_exporter import export_xlsx


class ExportEngine:
    def __init__(self) -> None:
        pass

    def export(
        self,
        results: list,
        fmt: str,
        config: dict,
    ) -> bytes:
        if fmt == "csv":
            return export_csv(results, config)
        if fmt == "xlsx":
            return export_xlsx(results, config)
        if fmt == "json":
            return export_json(results, config)
        raise ValueError(f"unsupported format: {fmt}")

    async def dispatch_webhook(
        self,
        url: str,
        payload: dict,
    ) -> dict:
        return await dispatch_webhook(url, payload)