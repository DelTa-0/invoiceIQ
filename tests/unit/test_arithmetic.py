"""Arithmetic reconciliation tests (docs/15 §1, docs/16 §1)."""

from decimal import Decimal

from invoiceiq.validate import arithmetic as arith


def test_line_net_basic():
    assert arith.line_net(2, "49.90") == Decimal("99.80")


def test_line_net_with_discount():
    assert arith.line_net(10, "10.00", "10") == Decimal("90.00")


def test_line_net_rounding_half_up():
    # 0.335 -> 0.34 (round-half-up)
    assert arith.line_net(1, "0.335") == Decimal("0.34")


def test_line_vat_rounding():
    assert arith.line_vat(Decimal("99.80"), 19) == Decimal("18.96")


def test_line_gross():
    assert arith.line_gross(Decimal("99.80"), Decimal("18.96")) == Decimal("118.76")


def test_subtotal_reconciles():
    nets = [Decimal("99.80"), Decimal("50.00"), Decimal("3.33")]
    assert arith.check_subtotal(nets, "153.13")
    assert not arith.check_subtotal(nets, "153.14")


def test_vat_total_tolerance():
    vats = [Decimal("18.96"), Decimal("10.50")]
    assert arith.check_vat_total(vats, "29.47")  # 29.46 vs 29.47 within 0.02
    assert not arith.check_vat_total(vats, "29.60")


def test_grand_total():
    assert arith.check_grand_total(Decimal("100"), Decimal("19"), Decimal("5"), Decimal("0"), "124.00")
    assert not arith.check_grand_total(Decimal("100"), Decimal("19"), Decimal("5"), Decimal("0"), "125.00")


def test_reverse_charge():
    assert arith.is_reverse_charge([0, 0, 0])
    assert not arith.is_reverse_charge([0, 19, 0])
