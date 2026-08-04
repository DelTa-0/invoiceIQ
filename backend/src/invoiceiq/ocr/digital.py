"""Digital PDF text-layer engine (pdfplumber). Cost ≈ 0, exact bboxes.

This is the cheapest path in docs/14 §2: PDFs that carry a real text layer
are read verbatim, never OCR'd. Word-level bboxes are normalized to 0..1 and
line-grouped so the document model feeds the rules + LLM layers uniformly.
"""

from __future__ import annotations

import io

import pdfplumber
from pdfplumber.page import Page

from .base import OCRNoTextError, OCRPage, OCRTable, PageBlock, TableCell

LINE_TOLERANCE_PT = 3.0  # words within ~this vertical distance form one visual line


class DigitalPDFEngine:
    """Implements the `DigitalTextEngine` contract for PDF bytes."""

    name = "pdfplumber"

    def extract(self, pdf_bytes: bytes) -> list[OCRPage]:
        if not pdf_bytes.lstrip().startswith(b"%PDF"):
            raise OCRNoTextError("not a PDF byte stream")
        pages: list[OCRPage] = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_no, page in enumerate(pdf.pages):
                    pages.append(self._extract_page(page, page_no))
        except OCRNoTextError:
            raise
        except Exception as exc:
            raise OCRNoTextError(f"pdfplumber failed to parse: {exc}") from exc
        if not pages:
            raise OCRNoTextError("empty PDF")
        return pages

    def _extract_page(self, page: Page, page_no: int) -> OCRPage:
        width, height = page.width, page.height
        words = page.extract_words(keep_blank_chars=False)
        blocks = self._words_to_blocks(words, width, height)
        tables = self._extract_tables(page, page_no, width, height)
        return OCRPage(
            page_no=page_no,
            width=int(width),
            height=int(height),
            engine=self.name,
            text_layer=bool(page.chars),
            blocks=blocks,
            tables=tables,
        )

    def _words_to_blocks(
        self, words: list[dict], width: float, height: float
    ) -> list[PageBlock]:
        if not words:
            return []
        ordered = sorted(words, key=lambda w: (w["top"], w["x0"]))
        lines: list[list[dict]] = []
        current: list[dict] = []
        for word in ordered:
            if not current:
                current = [word]
            elif abs(word["top"] - current[0]["top"]) <= LINE_TOLERANCE_PT:
                current.append(word)
            else:
                lines.append(current)
                current = [word]
        if current:
            lines.append(current)

        blocks: list[PageBlock] = []
        for line_no, line in enumerate(lines):
            by_x = sorted(line, key=lambda w: w["x0"])
            text = " ".join(w["text"] for w in by_x if w["text"].strip())
            if not text.strip():
                continue
            blocks.append(
                PageBlock(
                    text=text,
                    conf=1.0,
                    bbox=[
                        min(w["x0"] for w in by_x) / width,
                        min(w["top"] for w in by_x) / height,
                        max(w["x1"] for w in by_x) / width,
                        max(w["bottom"] for w in by_x) / height,
                    ],
                    line_no=line_no,
                    reading_order=line_no,
                    role="text",
                )
            )
        return blocks

    def _extract_tables(
        self, page: Page, page_no: int, width: float, height: float
    ) -> list[OCRTable]:
        tables: list[OCRTable] = []
        found = page.find_tables()
        for table in found:
            extracted = table.extract()
            rows: list[list[TableCell]] = []
            for row_idx, row in enumerate(table.rows):
                cells: list[TableCell] = []
                for col_idx, cell_bbox in enumerate(row.cells):
                    if cell_bbox is None:
                        cells.append(TableCell(text="", bbox=[]))
                        continue
                    x0, top, x1, bottom = cell_bbox
                    text = ""
                    if row_idx < len(extracted) and col_idx < len(extracted[row_idx]):
                        text = extracted[row_idx][col_idx] or ""
                    cells.append(
                        TableCell(
                            text=text.strip(),
                            bbox=[x0 / width, top / height, x1 / width, bottom / height],
                        )
                    )
                rows.append(cells)
            tables.append(OCRTable(page_no=page_no, conf=1.0, rows=rows))
        return tables
