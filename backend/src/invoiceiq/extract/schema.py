"""The extraction contract — the single shape shared by the pipeline, the
review UI, exports, and the SDK. See docs/12 and docs/05 §7.
"""


from pydantic import BaseModel, Field


class BBox(BaseModel):
    page: int = 0
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0


class ValidatorResult(BaseModel):
    status: str | None = None  # pass | warn | fail | null
    rule: str | None = None
    detail: dict = Field(default_factory=dict)


class FieldCandidate(BaseModel):
    field: str
    value: dict | None = None
    confidence: float | None = None
    method: str | None = None  # rules | llm | vlm | user
    source_text: str | None = None
    bbox: BBox | None = None
    validator: ValidatorResult = Field(default_factory=ValidatorResult)
    status: str = "accepted"  # accepted | flagged | edited


class LineItemCandidate(BaseModel):
    position: int
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    discount_pct: float | None = None
    net: float | None = None
    vat_rate: float | None = None
    vat_amount: float | None = None
    gross: float | None = None
    sku: str | None = None
    confidence: float | None = None


class ExtractionResult(BaseModel):
    doc_type: str | None = None  # invoice | credit_note | proforma | other
    language: str | None = None
    country: str | None = None
    fields: dict[str, FieldCandidate] = Field(default_factory=dict)
    line_items: list[LineItemCandidate] = Field(default_factory=list)
