"""Deterministic validation engine. Pure functions; zero I/O inside rules.
See docs/15. The LLM proposes; this engine disposes."""

import re
from decimal import Decimal

from pydantic import BaseModel, Field

from . import arithmetic as arith


class Check(BaseModel):
    check_name: str
    status: str  # pass | warn | fail
    severity: str = "info"  # info | warning | error
    reason: str
    evidence: dict = Field(default_factory=dict)


# --- IBAN ------------------------------------------------------------------


IBAN_LENGTHS = {
    "DE": 22, "IT": 27, "FR": 27, "ES": 24, "NL": 18,
    "BE": 16, "AT": 20, "LU": 20, "PT": 25, "IE": 22,
}


def iban_checksum(iban: str) -> int:
    """ISO 13616 MOD-97. Valid when result == 1."""
    s = re.sub(r"[^A-Za-z0-9]", "", iban).upper()
    rearranged = s[4:] + s[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    return int(digits) % 97


def check_iban(iban: str | None) -> Check:
    name = "iban"
    if not iban:
        return Check(check_name=name, status="fail", severity="warning", reason="missing", evidence={})
    compact = re.sub(r"\s+", "", iban).upper()
    country = compact[:2]
    expected_len = IBAN_LENGTHS.get(country)
    if expected_len is None:
        return Check(check_name=name, status="warn", severity="warning",
                     reason="unknown_country_prefix", evidence={"country": country})
    if len(compact) != expected_len:
        return Check(check_name=name, status="fail", severity="error", reason="bad_length",
                     evidence={"expected": expected_len, "actual": len(compact)})
    if iban_checksum(compact) != 1:
        return Check(check_name=name, status="fail", severity="error", reason="mod97_failed",
                     evidence={"mod97": iban_checksum(compact)})
    return Check(check_name=name, status="pass", severity="info", reason="valid", evidence={})


# --- VAT -------------------------------------------------------------------


VAT_PATTERNS = {
    "DE": re.compile(r"^DE\d{9}$"),
    "IT": re.compile(r"^IT\d{11}$"),
    "FR": re.compile(r"^FR[A-Za-z0-9]{2}\d{9}$"),
    "ES": re.compile(r"^ES[A-Za-z0-9]\d{7}[A-Za-z0-9]$"),
    "NL": re.compile(r"^NL\d{9}B\d{2}$"),
    "BE": re.compile(r"^BE\d{10}$"),
    "AT": re.compile(r"^ATU\d{8}$"),
    "LU": re.compile(r"^LU\d{8}$"),
    "PT": re.compile(r"^PT\d{9}$"),
    "IE": re.compile(r"^IE[A-Za-z0-9]\d{5}[A-Za-z0-9]{2,3}$"),
}


def vat_country(vat: str | None) -> str | None:
    if not vat:
        return None
    compact = re.sub(r"\s+", "", vat).upper()
    return compact[:2]


def check_vat_format(vat: str | None) -> Check:
    name = "vat_format"
    if not vat:
        return Check(check_name=name, status="fail", severity="warning", reason="missing", evidence={})
    compact = vat.replace(" ", "").upper()
    country = compact[:2]
    pattern = VAT_PATTERNS.get(country)
    if pattern is None:
        return Check(check_name=name, status="warn", severity="warning",
                     reason="unknown_country_prefix", evidence={"country": country})
    if pattern.match(compact):
        return Check(check_name=name, status="pass", severity="info", reason="valid", evidence={})
    return Check(check_name=name, status="fail", severity="error", reason="format_mismatch",
                 evidence={"value": vat, "country": country})


# --- Arithmetic ------------------------------------------------------------


def _rule_check(name: str, status: str, reason: str, evidence: dict) -> Check:
    return Check(
        check_name=name,
        status=status,
        severity="info" if status == "pass" else ("warning" if status == "warn" else "error"),
        reason=reason,
        evidence=evidence,
    )


def _jsonable(value):
    """Decimal -> str so evidence survives JSON columns (SQLite/Postgres)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def check_arithmetic(lines: list[dict], invoice: dict) -> list[Check]:
    """Run the 7 arithmetic rules, emitting pass/warn/fail for every evaluated
    rule (not just failures). `lines` are extracted line dicts; `invoice`
    carries subtotal/total_vat/shipping/other/total."""
    checks: list[Check] = []

    line_nets, line_vats, vat_rates = [], [], []
    for idx, line in enumerate(lines):
        net = arith.line_net(line.get("quantity"), line.get("unit_price"), line.get("discount_pct"))
        vat = arith.line_vat(net, line.get("vat_rate"))
        line_nets.append(net)
        line_vats.append(vat)
        vat_rates.append(line.get("vat_rate") or 0)
        if line.get("gross") is not None:
            expected_gross = arith.line_gross(net, vat)
            ok = abs(expected_gross - arith.d(line["gross"])) <= arith.d("0.01")
            checks.append(_rule_check(
                f"line_gross_{idx}",
                "pass" if ok else "fail",
                "line_gross_ok" if ok else "line_gross_mismatch",
                {"position": idx, "expected": str(expected_gross), "actual": str(line.get("gross"))},
            ))

    if invoice.get("subtotal") is not None:
        ok = arith.check_subtotal(line_nets, invoice.get("subtotal"))
        checks.append(_rule_check(
            "subtotal",
            "pass" if ok else "fail",
            "subtotal_ok" if ok else "subtotal_mismatch",
            {"expected": str(sum(line_nets, arith.d("0"))), "actual": str(invoice.get("subtotal"))},
        ))
    if invoice.get("total_vat") is not None:
        ok = arith.check_vat_total(line_vats, invoice.get("total_vat"))
        checks.append(_rule_check(
            "vat_total",
            "pass" if ok else "fail",
            "vat_total_ok" if ok else "vat_total_mismatch",
            {"expected": str(sum(line_vats, arith.d("0"))), "actual": str(invoice.get("total_vat"))},
        ))
    if invoice.get("total") is not None:
        ok = arith.check_grand_total(
            invoice.get("subtotal"), invoice.get("total_vat"),
            invoice.get("shipping"), invoice.get("other"), invoice.get("total"),
        )
        checks.append(_rule_check(
            "grand_total",
            "pass" if ok else "fail",
            "total_ok" if ok else "total_mismatch",
            {"invoice": _jsonable(invoice), "lines": len(lines)},
        ))

    if arith.is_reverse_charge(vat_rates):
        vat_zero = invoice.get("total_vat") in (None, 0)
        checks.append(_rule_check(
            "reverse_charge",
            "pass" if vat_zero else "fail",
            "vat_expected_zero",
            {"rates": vat_rates},
        ))
    return checks


def run_all(lines: list[dict], invoice: dict, *, iban: str | None = None, vat: str | None = None) -> list[Check]:
    checks = check_arithmetic(lines, invoice)
    checks.append(check_iban(iban))
    checks.append(check_vat_format(vat))
    return checks
