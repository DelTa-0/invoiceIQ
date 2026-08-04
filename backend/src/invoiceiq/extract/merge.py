"""Merge rule vs LLM candidates per docs/12 §2.

- Agree  -> accept, confidence boosted by agreement.
- Disagree -> well-formed fields (VAT/IBAN/numbers/dates) trust the rule and
  demote the LLM value to a `warn`; text fields trust the LLM.
- The merged candidate carries the last effective source in `method`.
"""

from __future__ import annotations

import math

from .rules import iso_value, numeric, scalar
from .schema import FieldCandidate, ValidatorResult

WELL_FORMED = {
    "supplier_vat",
    "iban",
    "invoice_number",
    "invoice_date",
    "due_date",
    "currency",
    "subtotal",
    "total_vat",
    "total",
    "shipping",
    "other",
}


def _values_equal(field: str, rule: FieldCandidate, llm: FieldCandidate) -> bool:
    if field in ("subtotal", "total_vat", "total", "shipping", "other"):
        na, nb = numeric(rule), numeric(llm)
        if na is None or nb is None:
            return False
        return math.isclose(na, nb, abs_tol=0.02)
    if field in ("invoice_date", "due_date"):
        ia, ib = iso_value(rule), iso_value(llm)
        if ia and ib:
            return ia == ib
    sa, sb = scalar(rule), scalar(llm)
    if sa is None or sb is None:
        return False
    return str(sa).casefold().replace(" ", "") == str(sb).casefold().replace(" ", "")


def _warn(candidate: FieldCandidate, rule_value, llm_value) -> FieldCandidate:
    candidate.validator = ValidatorResult(
        status="warn",
        rule="RULE_LLM_DISAGREE",
        detail={"rule": rule_value, "llm": llm_value},
    )
    return candidate


def merge_field(field: str, rule: FieldCandidate | None, llm: FieldCandidate | None) -> FieldCandidate | None:
    """Single-field merge. Returns the winning candidate (or None)."""
    if rule is None and llm is None:
        return None
    if rule is None:
        return llm
    if llm is None:
        return rule

    if _values_equal(field, rule, llm):
        winner = rule.model_copy(deep=True)
        winner.confidence = round(min(1.0, max(rule.confidence or 0, llm.confidence or 0) + 0.05), 4)
        if field in WELL_FORMED:
            winner.method = "rules"
        return winner

    if field in WELL_FORMED:
        winner = rule.model_copy(deep=True)
        winner.confidence = max(0.0, round((rule.confidence or 0) - 0.1, 4))
        return _warn(winner, scalar(rule), scalar(llm))

    winner = llm.model_copy(deep=True)
    return _warn(winner, scalar(rule), scalar(llm))


def merge_fields(
    rules: dict[str, FieldCandidate], llm: dict[str, FieldCandidate]
) -> dict[str, FieldCandidate]:
    merged = dict(rules)
    for field in set(rules) | set(llm):
        winner = merge_field(field, rules.get(field), llm.get(field))
        if winner is not None:
            merged[field] = winner
    return merged
