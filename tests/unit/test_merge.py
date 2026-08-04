"""Rule vs LLM merge tests (docs/12 §2)."""

from __future__ import annotations

from invoiceiq.extract.merge import merge_field
from invoiceiq.extract.rules import envelope, scalar
from invoiceiq.extract.schema import FieldCandidate


def _money(field: str, value: str, conf: float, method: str) -> FieldCandidate:
    return FieldCandidate(
        field=field,
        value=envelope("money", value, numeric=float(value.replace(",", "."))),
        confidence=conf,
        method=method,
    )


def test_agreement_boosts_confidence_and_prefers_rules():
    merged = merge_field("total", _money("total", "1190,00", 0.9, "rules"), _money("total", "1190.00", 0.8, "llm"))
    assert merged.confidence > 0.9
    assert merged.method == "rules"
    assert scalar(merged) == "1190,00"


def test_money_disagreement_prefers_rule_and_warns():
    merged = merge_field("total", _money("total", "1190,00", 0.9, "rules"), _money("total", "999.00", 0.8, "llm"))
    assert scalar(merged) == "1190,00"
    assert merged.validator.status == "warn"
    assert merged.validator.rule == "RULE_LLM_DISAGREE"


def test_text_disagreement_prefers_llm():
    rule = FieldCandidate(field="supplier_name", value=envelope("text", "ACME GmbH"), confidence=0.6, method="rules")
    llm = FieldCandidate(field="supplier_name", value=envelope("text", "ACME Muster GmbH"), confidence=0.85, method="llm")
    merged = merge_field("supplier_name", rule, llm)
    assert scalar(merged) == "ACME Muster GmbH"


def test_single_source_passes_through():
    assert merge_field("total", None, _money("total", "100.00", 0.8, "llm")).method == "llm"
    assert merge_field("total", _money("total", "100,00", 0.9, "rules"), None).method == "rules"
    assert merge_field("total", None, None) is None
