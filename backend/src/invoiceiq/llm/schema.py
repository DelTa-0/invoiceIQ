"""LLM output contract — a lenient subset of the extraction result that the
prompt is asked to fill. Money/numbers come back as RAW printed strings; the
rules layer + validators do the math (docs/13 §6)."""

from pydantic import BaseModel, Field


class LLMField(BaseModel):
    value: str | float | int | None = None
    missing: bool = False
    source_text: str | None = None


class LLMLineItem(BaseModel):
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    net: str | None = None
    vat_rate: str | None = None
    vat_amount: str | None = None
    gross: str | None = None
    source_text: str | None = None


class LLMExtraction(BaseModel):
    doc_type: str | None = None
    language: str | None = None
    country: str | None = None
    fields: dict[str, LLMField] = Field(default_factory=dict)
    line_items: list[LLMLineItem] = Field(default_factory=list)
