"""Arithmetic reconciliation — the heart of the validation engine.

Deterministic, unit-tested, using Decimal with round-half-up to 2 decimals
(EU business convention). Never auto-corrects: mismatches are flagged for
human review. See docs/15 §1.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def d(value: object | None) -> Decimal:
    """Coerce a numeric (int/float/str/Decimal) to Decimal without float noise."""
    return Decimal(str(value)) if value is not None else Decimal("0")


def round2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_net(quantity: object | None, unit_price: object | None, discount_pct: object | None = 0) -> Decimal:
    q, u, disc = d(quantity), d(unit_price), d(discount_pct)
    return round2(q * u * (Decimal("1") - disc / Decimal("100")))


def line_vat(net: object | None, vat_rate: object | None) -> Decimal:
    return round2(d(net) * d(vat_rate) / Decimal("100"))


def line_gross(net: object | None, vat_amount: object | None) -> Decimal:
    return round2(d(net) + d(vat_amount))


def check_subtotal(line_nets: list[Decimal], subtotal, tolerance="0") -> bool:
    return abs(sum(line_nets, Decimal("0")) - d(subtotal)) <= d(tolerance)


def check_vat_total(line_vats: list[Decimal], total_vat, tolerance="0.02") -> bool:
    return abs(sum(line_vats, Decimal("0")) - d(total_vat)) <= d(tolerance)


def check_grand_total(subtotal, total_vat, shipping, other, total, tolerance="0.02") -> bool:
    expected = d(subtotal) + d(total_vat) + d(shipping) + d(other)
    return abs(expected - d(total)) <= d(tolerance)


def is_reverse_charge(vat_rates: list) -> bool:
    """True when every taxable line is zero-rated (reverse charge / intra-community / exempt)."""
    return all(d(r) == 0 for r in vat_rates)
