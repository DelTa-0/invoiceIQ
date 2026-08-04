"""Composite field-confidence engine. A score is computed, never claimed.
See docs/12 §5."""

from dataclasses import dataclass

# (method, ocr, consistency, validator) weight tuples per field class
WEIGHTS = {
    "money": (0.45, 0.25, 0.15, 0.15),
    "identity": (0.40, 0.30, 0.15, 0.15),
    "text": (0.35, 0.35, 0.10, 0.20),
}

# validator status -> factor
VALIDATOR_FACTOR = {"pass": 1.0, "warn": 0.7, "fail": 0.0, None: 0.8}

MONEY_FIELDS = {"subtotal", "total_vat", "total", "shipping", "other"}
IDENTITY_FIELDS = {"supplier_name", "supplier_vat", "iban", "bic", "vat_number", "invoice_number"}


def field_class(field: str) -> str:
    if field in MONEY_FIELDS:
        return "money"
    if field in IDENTITY_FIELDS:
        return "identity"
    return "text"


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def field_confidence(
    *,
    method_conf: float,
    ocr_conf: float,
    consistency: float = 1.0,
    validator_status: str | None = None,
    field: str = "",
) -> float:
    """Weighted composite per docs/12 §5."""
    wm, wo, wc, wv = WEIGHTS[field_class(field)]
    score = (
        wm * _clamp(method_conf)
        + wo * _clamp(ocr_conf)
        + wc * _clamp(consistency)
        + wv * VALIDATOR_FACTOR.get(validator_status, 0.8)
    )
    # A money field failing its arithmetic check is by definition wrong —
    # collapse confidence so the document floors into the review queue.
    if field_class(field) == "money" and validator_status == "fail":
        score *= 0.2
    return round(_clamp(score), 4)


@dataclass
class DocumentConfidence:
    score: float
    min_money_conf: float
    status: str  # completed | requires_review


def document_confidence(
    field_confs: dict[str, float],
    threshold: float = 0.85,
) -> DocumentConfidence:
    """Document-level = mean, but money fields dominate via a floor."""
    if not field_confs:
        return DocumentConfidence(score=0.0, min_money_conf=0.0, status="requires_review")
    money = [c for f, c in field_confs.items() if field_class(f) == "money" and c is not None]
    mean = sum(field_confs.values()) / len(field_confs)
    floor = min(money) if money else mean
    score = min(mean, floor)
    status = "completed" if score >= threshold else "requires_review"
    return DocumentConfidence(score=round(score, 4), min_money_conf=round(floor, 4), status=status)
