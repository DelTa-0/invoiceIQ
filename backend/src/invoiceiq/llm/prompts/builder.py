"""Dynamic prompt builder + JSON schema generator.

Converts user-defined extraction fields into a strict JSON schema
and an optimized LLM extraction prompt.  Replaces the hardcoded
invoice-only prompt for generic sessions (docs/13 §3).
"""

from __future__ import annotations

import json
from enum import StrEnum

from .extract import document_to_text


class FieldType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


_TYPE_MAP: dict[str, FieldType] = {
    "string": FieldType.STRING,
    "number": FieldType.NUMBER,
    "date": FieldType.DATE,
    "currency": FieldType.CURRENCY,
    "boolean": FieldType.BOOLEAN,
    "array": FieldType.ARRAY,
    "object": FieldType.OBJECT,
}


def infer_field_type(name: str, description: str = "") -> FieldType:
    """Heuristic type inference from field name and description."""
    lowered = (name + " " + description).lower()
    if any(kw in lowered for kw in ["date", "time", "when", "deadline", "start", "end"]):
        return FieldType.DATE
    if any(kw in lowered for kw in ["amount", "price", "total", "sum", "cost", "fee", "vat", "tax", "discount", "net", "gross", "money", "eur", "usd", "gbp"]):
        return FieldType.CURRENCY
    if any(kw in lowered for kw in ["count", "quantity", "num", "number of", "qty"]):
        return FieldType.NUMBER
    if any(kw in lowered for kw in ["is ", "has ", "includes ", "contains ", "bool", "yes/no", "true/false"]):
        return FieldType.BOOLEAN
    if any(kw in lowered for kw in ["items", "line", "list", "every", "all ", "each "]):
        return FieldType.ARRAY
    return FieldType.STRING


def build_json_schema(fields: list[dict]) -> dict:
    """Generate a strict JSON schema from field definitions.

    Each field dict has keys: name, type (optional), description (optional).
    """
    properties: dict[str, dict] = {}
    required: list[str] = []

    for field in fields:
        name = field["name"]
        desc = field.get("description", "")
        raw_type = field.get("type", "")

        field_type = _TYPE_MAP[raw_type] if raw_type in _TYPE_MAP else infer_field_type(name, desc)

        prop: dict = {"description": desc or name}

        if field_type == FieldType.DATE:
            prop["type"] = ["string", "null"]
            prop["format"] = "date"
        elif field_type == FieldType.CURRENCY or field_type == FieldType.NUMBER:
            prop["type"] = ["number", "null"]
        elif field_type == FieldType.BOOLEAN:
            prop["type"] = ["boolean", "null"]
        elif field_type == FieldType.ARRAY:
            prop["type"] = ["array", "null"]
            prop["items"] = {"type": "string"}
        elif field_type == FieldType.OBJECT:
            prop["type"] = ["object", "null"]
        else:
            prop["type"] = ["string", "null"]

        properties[name] = prop
        required.append(name)

    return {
        "$schema": "http://json-schema.org/draft-2020-12/schema",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def build_extraction_prompt(
    pages: list,
    fields: list[dict],
    doc_type: str | None = None,
    language: str | None = None,
    country: str | None = None,
) -> list[dict]:
    """Build extraction messages for the LLM.

    Args:
        pages: OCRPage list from the document.
        fields: List of field definitions [{"name": ..., "type": ..., "description": ...}].
        doc_type: Auto-detected document type (optional).
        language: Auto-detected language (optional).
        country: Auto-detected country (optional).

    Returns:
        Messages list for the LLM chat API.
    """
    schema = build_json_schema(fields)
    field_list = "\n".join(
        f"  - {f['name']} ({f.get('type', infer_field_type(f['name'], f.get('description', ''))).value}): {f.get('description', f['name'])}"
        for f in fields
    )

    hints: list[str] = []
    if language:
        hints.append(f"language: {language}")
    if country:
        hints.append(f"country: {country}")
    if doc_type:
        hints.append(f"document type: {doc_type}")

    header = f"Document model ({', '.join(hints) if hints else 'language/country unknown'}):\n"

    system = SYSTEM_TEMPLATE.format(
        field_list=field_list,
        schema=json.dumps(schema, indent=2),
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": header + document_to_text(pages)},
    ]


SYSTEM_TEMPLATE = """\
You are a structured document extraction engine. Extract ONLY the requested fields from the document.

Requested fields:
{field_list}

Strict JSON schema the output MUST conform to:
{schema}

Rules:
- Return ONLY valid JSON. No markdown, no explanation outside the JSON.
- If a field is not found in the document, set it to null.
- NEVER fabricate values.
- For monetary amounts, use numbers (not strings with currency symbols).
- For dates, use ISO 8601 format (YYYY-MM-DD).
- For arrays, include all items found.
- Include reasoning for each extracted value.

Return ONLY valid JSON. No markdown, no explanation outside the JSON."""