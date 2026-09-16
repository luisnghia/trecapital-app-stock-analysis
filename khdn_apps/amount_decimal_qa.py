"""Deterministic QA for KHDN V2.31.2 monetary parsing/formatting."""
from __future__ import annotations

from khdn_apps.amount_decimal_patch import parse_amount_text_locale, money_vi


def main() -> None:
    cases = {
        "23.834,18": 23834.18,
        "23834,18": 23834.18,
        "23,834.18": 23834.18,
        "23834.18": 23834.18,
        "1.000.000": 1000000.0,
        "1,000,000": 1000000.0,
        "1.234.567,89": 1234567.89,
        "1,234,567.89": 1234567.89,
        "23.834": 23834.0,
        "23,834": 23834.0,
        "0,18": 0.18,
        "EUR 23.834,18": 23834.18,
    }
    for raw, expected in cases.items():
        actual = parse_amount_text_locale(raw)
        assert abs(actual - expected) < 1e-9, (raw, actual, expected)

    assert money_vi(23834.18) == "23.834,18"
    assert money_vi(23834) == "23.834"
    assert money_vi(1000000) == "1.000.000"
    assert money_vi(0.18) == "0,18"
    print("KHDN_AMOUNT_DECIMAL_QA PASS", len(cases), "parse cases + formatting")


if __name__ == "__main__":
    main()
