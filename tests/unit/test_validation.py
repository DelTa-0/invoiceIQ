"""IBAN and VAT format validation tests (docs/15 §2-3)."""

from invoiceiq.validate import engine as ve


def test_iban_checksum_valid_de():
    assert ve.iban_checksum("DE89370400440532013000") == 1


def test_iban_checksum_valid_be():
    assert ve.iban_checksum("BE68539007547034") == 1


def test_iban_checksum_invalid():
    assert ve.iban_checksum("DE89370400440532013001") != 1


def test_iban_check_pass():
    check = ve.check_iban("DE89 3704 0044 0532 0130 00")
    assert check.status == "pass"


def test_iban_check_fail_checksum():
    check = ve.check_iban("DE89370400440532013001")
    assert check.status == "fail"
    assert check.reason == "mod97_failed"


def test_iban_check_fail_length():
    check = ve.check_iban("DE8937040")
    assert check.status == "fail"
    assert check.reason == "bad_length"


def test_vat_format_de():
    assert ve.check_vat_format("DE811123456").status == "pass"


def test_vat_format_de_invalid():
    assert ve.check_vat_format("DE123").status == "fail"


def test_vat_format_fr():
    assert ve.check_vat_format("FR12345678901").status == "pass"


def test_vat_format_nl():
    assert ve.check_vat_format("NL123456789B01").status == "pass"


def test_vat_format_at():
    assert ve.check_vat_format("ATU12345678").status == "pass"


def test_vat_format_unknown_country():
    assert ve.check_vat_format("XX12345678").status == "warn"


def test_run_all_combined():
    lines = [
        {"quantity": 2, "unit_price": "49.90", "vat_rate": 19, "gross": "118.76"},
        {"quantity": 1, "unit_price": "50.00", "vat_rate": 19, "gross": "59.50"},
    ]
    invoice = {"subtotal": "149.80", "total_vat": "28.46", "total": "178.26"}
    checks = ve.run_all(lines, invoice, iban="DE89370400440532013000", vat="DE811123456")
    by_name = {c.check_name: c for c in checks}
    assert not any(c.status == "fail" for c in checks)
    assert by_name["iban"].status == "pass"
    assert by_name["vat_format"].status == "pass"
