from __future__ import annotations

from typing import Optional


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Mathematical division used when a negative numerator is economically informative."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def safe_positive_denominator_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Division for ratios that require a strictly positive economic denominator.

    Valuation multiples such as TEV/EBIT or Debt/EBITDA become misleading when EBIT/EBITDA is
    zero or negative. Returning None is preferable to displaying a mathematically valid but
    economically non-comparable negative multiple. Negative FCF/earnings yields are still retained
    where the negative numerator itself is an important warning signal.
    """
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def inventory_metrics(*, tev=None, ebit=None, ebitda=None, normalized_earnings=None,
                      total_debt=None, interest_expense=None, fcf_current=None,
                      market_cap=None, dividend_per_share=None, market_price=None,
                      target_price=None) -> dict:
    return {
        # Multiples require positive earnings denominators; negative multiples are not comparable
        # valuation metrics and are shown as unavailable rather than as a deceptively cheap number.
        "tev_ebit": safe_positive_denominator_div(tev, ebit),
        "tev_ebitda": safe_positive_denominator_div(tev, ebitda),
        "tev_normalized_earnings": safe_positive_denominator_div(tev, normalized_earnings),
        # A negative earnings/FCF yield is retained as a valid distress/cash-burn signal, but the
        # enterprise/market value denominator itself must be positive.
        "pretax_earnings_yield": safe_positive_denominator_div(normalized_earnings, tev),
        "debt_ebitda": safe_positive_denominator_div(total_debt, ebitda),
        "ebit_interest": safe_positive_denominator_div(ebit, interest_expense),
        "fcf_yield_ev": safe_positive_denominator_div(fcf_current, tev),
        "fcf_yield_market": safe_positive_denominator_div(fcf_current, market_cap),
        "dividend_yield": safe_positive_denominator_div(dividend_per_share, market_price),
        "price_vs_target": safe_positive_denominator_div(market_price, target_price),
    }
