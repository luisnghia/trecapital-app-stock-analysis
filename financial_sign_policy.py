from __future__ import annotations

"""Shared sign policy for financial ratios used across Trecapital modules.

The helpers deliberately return ``None`` when a ratio would be mathematically
defined but economically misleading (for example CFO/LNST while LNST is a
loss, or Debt/EBITDA while EBITDA is non-positive).  Negative numerators remain
visible when the positive denominator is valid: CFO=-10 and LNST=100 is a
meaningful -0.1x cash-conversion warning.

In particular, a negative/negative division must never be converted into an
apparently favourable positive ratio.  Every economic denominator checked by
these helpers must be strictly positive before the ratio is eligible for
scoring.
"""

from typing import Any
import math


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
        return None if math.isnan(out) else out
    except (TypeError, ValueError):
        return None


def positive_denominator_ratio(numerator: Any, denominator: Any) -> float | None:
    """Return numerator/denominator only when the denominator is strictly positive."""
    num = _number(numerator)
    den = _number(denominator)
    if num is None or den is None or den <= 0:
        return None
    return num / den


def magnitude_ratio_on_positive_base(numerator: Any, denominator: Any) -> float | None:
    """Return abs(numerator)/denominator only for a strictly positive economic base."""
    num = _number(numerator)
    den = _number(denominator)
    if num is None or den is None or den <= 0:
        return None
    return abs(num) / den


def positive_base_growth(current: Any, previous: Any) -> float | None:
    """Return growth only when the prior-period base is positive.

    A move from a loss to a profit (or the reverse) is a transition, not a
    conventional percentage-growth observation.
    """
    cur = _number(current)
    prev = _number(previous)
    if cur is None or prev is None or prev <= 0:
        return None
    return cur / prev - 1.0


def conversion_state(cash_flow: Any, earnings: Any) -> str:
    """Classify cash-flow/earnings signs without manufacturing a ratio."""
    cash = _number(cash_flow)
    profit = _number(earnings)
    if cash is None or profit is None:
        return "missing"
    if profit > 0:
        return "valid_positive_base" if cash > 0 else "positive_profit_nonpositive_cash"
    if cash > 0:
        return "loss_but_positive_cash"
    return "loss_and_nonpositive_cash"


__all__ = [
    "positive_denominator_ratio",
    "magnitude_ratio_on_positive_base",
    "positive_base_growth",
    "conversion_state",
]
