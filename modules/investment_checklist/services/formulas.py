from __future__ import annotations

from typing import Optional


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def inventory_metrics(*, tev=None, ebit=None, ebitda=None, normalized_earnings=None,
                      total_debt=None, interest_expense=None, fcf_current=None,
                      market_cap=None, dividend_per_share=None, market_price=None,
                      target_price=None) -> dict:
    return {
        "tev_ebit": safe_div(tev, ebit),
        "tev_ebitda": safe_div(tev, ebitda),
        "tev_normalized_earnings": safe_div(tev, normalized_earnings),
        "pretax_earnings_yield": safe_div(normalized_earnings, tev),
        "debt_ebitda": safe_div(total_debt, ebitda),
        "ebit_interest": safe_div(ebit, interest_expense),
        "fcf_yield_ev": safe_div(fcf_current, tev),
        "fcf_yield_market": safe_div(fcf_current, market_cap),
        "dividend_yield": safe_div(dividend_per_share, market_price),
        "price_vs_target": safe_div(market_price, target_price),
    }
