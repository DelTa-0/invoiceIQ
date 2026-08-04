"""OCR engine abstraction. See docs/14.

Concrete engines (PaddleOCR PP-OCRv4, Tesseract) ship in Phase 1. This
module defines the normalized output contract (`OCRPage`, `PageBlock`) that
the whole pipeline consumes.
"""

from typing import Protocol

from pydantic import BaseModel, Field


class PageBlock(BaseModel):
    text: str
    conf: float = 1.0
    bbox: list[float] = Field(default_factory=list)  # [x0, y0, x1, y1] normalized
    line_no: int | None = None
    reading_order: int | None = None
    role: str = "text"  # key_value|amount|date|company|address|header|footer|table|note|text
    table_cell: bool = False
    row_no: int | None = None
    col_no: int | None = None


class TableCell(BaseModel):
    text: str
    bbox: list[float] = Field(default_factory=list)


class OCRTable(BaseModel):
    page_no: int = 0
    conf: float = 1.0
    rows: list[list[TableCell]] = Field(default_factory=list)


class OCRPage(BaseModel):
    page_no: int
    width: int = 0
    height: int = 0
    engine: str = "none"  # none|paddleocr|tesseract
    text_layer: bool = False
    blocks: list[PageBlock] = Field(default_factory=list)
    tables: list[OCRTable] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    @property
    def avg_confidence(self) -> float:
        if not self.blocks:
            return 0.0
        return sum(b.conf for b in self.blocks) / len(self.blocks)


class OCRNoTextError(Exception):
    """Raised when a document yields no readable text (scanned/corrupt).

    The pipeline maps this to `OCR_NO_TEXT` and (per docs/14 §7) marks the
    invoice for VLM escalation or human review — never confident garbage.
    """


class OCREngine(Protocol):
    name: str

    def extract(self, image: bytes, *, lang: str | None = None) -> OCRPage: ...


class DigitalTextEngine(Protocol):
    """Reads an already-text-based PDF without OCR (cost ≈ 0)."""

    def extract(self, pdf_bytes: bytes) -> list[OCRPage]: ...
