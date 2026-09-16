"""KHDN Ops V2.31.2 - locale-safe monetary amount parsing.

The legacy parser removed every non-digit character. That was fine for integer
VND values such as ``1.000.000`` but corrupts foreign-currency decimals such as
``23.834,18`` by turning the separators into nothing.

This patch accepts both Vietnamese and international money formats and keeps the
fractional part in storage/display:
- 23.834,18  -> 23834.18
- 23834,18   -> 23834.18
- 23,834.18  -> 23834.18
- 23834.18   -> 23834.18
- 1.000.000  -> 1000000
- 1,000,000  -> 1000000
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

PATCH_VERSION = "2.31.2"
_INSTALL_FLAG = "_KHDN_AMOUNT_DECIMAL_V2312"


def parse_amount_text_locale(value: Any) -> float:
    """Parse a user-entered monetary value using VN or international separators.

    Rules are deliberately deterministic for financial entry:
    - When both comma and dot exist, the right-most separator is decimal and the
      other separator is thousands grouping.
    - With one separator type, a final group of 1-2 digits is treated as decimal.
    - A final group of exactly 3 digits is treated as thousands grouping.
    - Repeated groups of 3 digits are treated as thousands grouping.
    """
    text = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"[^0-9,\.\-]", "", text)
    if not re.search(r"\d", text):
        return 0.0

    negative = text.startswith("-")
    text = text.replace("-", "")

    def as_number(integer_digits: str, fraction_digits: str = "") -> float:
        integer_digits = re.sub(r"\D", "", integer_digits) or "0"
        fraction_digits = re.sub(r"\D", "", fraction_digits)
        normalized = integer_digits
        if fraction_digits:
            normalized += "." + fraction_digits
        try:
            number = float(normalized)
        except Exception:
            return 0.0
        return -number if negative else number

    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        integer_part, fraction_part = text.rsplit(decimal_sep, 1)
        return as_number(integer_part, fraction_part)

    sep = "," if has_comma else "." if has_dot else None
    if sep is None:
        return as_number(text)

    parts = text.split(sep)
    if len(parts) == 2:
        left, right = parts
        # Monetary entry: 1 or 2 trailing digits clearly means a decimal part.
        if len(right) in (1, 2):
            return as_number(left, right)
        # 23.834 / 23,834 is overwhelmingly a thousands-grouping pattern here.
        if len(right) == 3:
            return as_number(left + right)
        # Allow explicit higher-precision decimal only for a 0.x style amount;
        # otherwise preserve the historical grouping interpretation.
        if (left in {"", "0"}) and right:
            return as_number(left, right)
        return as_number(left + right)

    # More than one equal separator: standard grouped thousands if every tail
    # block is 3 digits (1.234.567 / 1,234,567).
    if all(len(p) == 3 for p in parts[1:]):
        return as_number("".join(parts))

    # Non-standard but still recoverable input such as 1.234.567,8 is handled by
    # the mixed-separator branch above. For same-separator text, use a 1-2 digit
    # final group as decimal and treat earlier separators as grouping.
    if len(parts[-1]) in (1, 2):
        return as_number("".join(parts[:-1]), parts[-1])

    return as_number("".join(parts))


def money_vi(value: Any) -> str:
    """Format monetary values using dot thousands and comma decimals.

    Integer values stay unchanged compared with prior KHDN output. Fractional
    values retain two decimals, so 23834.18 is shown as ``23.834,18``.
    """
    try:
        number = float(value)
        if not math.isfinite(number):
            return "0"
    except Exception:
        return "0"

    rounded = round(number, 2)
    decimals = 0 if abs(rounded - round(rounded)) < 1e-9 else 2
    raw = f"{rounded:,.{decimals}f}"
    return raw.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def install(ns: dict[str, Any]) -> None:
    """Install decimal-safe parsing/formatting before app() renders any form."""
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True

    ns["parse_amount_text"] = parse_amount_text_locale
    ns["money"] = money_vi
    ns["APP_VERSION"] = PATCH_VERSION

    logging.getLogger("khdn_ops").info(
        "PATCH_INSTALL version=%s amount_parser=locale_decimal", PATCH_VERSION
    )
