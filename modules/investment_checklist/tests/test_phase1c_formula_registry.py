from modules.investment_checklist.formula_assumptions import EVALUATION_RULES, FORMULA_ROWS
from modules.investment_checklist.services.formulas import inventory_metrics


def test_formula_registry_covers_core_table12_metrics_and_source_rules():
    names = {row["Chỉ tiêu"] for row in FORMULA_ROWS}
    required = {
        "Quality tally", "Research Completion", "Assessment", "TEV", "TEV / EBIT",
        "TEV / EBITDA", "Normalized Earnings", "TEV / Normalized Earnings",
        "Pre-tax Earnings Yield", "Debt / EBITDA", "EBIT / Interest Expense", "FCF",
        "FCF Yield EV", "FCF Yield Market", "Dividend Yield", "Stock Price vs Target",
        "MOS", "CCC", "TTM",
    }
    assert required.issubset(names)
    text = " ".join(EVALUATION_RULES).lower()
    assert "unknown" in text and "neutral" in text
    assert "cyclical" in text
    assert "bank/insurance/securities" in text


def test_inventory_formula_arithmetic_matches_documented_table12_definitions():
    m = inventory_metrics(
        tev=12_000,
        ebit=1_200,
        ebitda=1_500,
        normalized_earnings=1_000,
        total_debt=2_000,
        interest_expense=100,
        fcf_current=900,
        market_cap=11_000,
        dividend_per_share=1_000,
        market_price=20_000,
        target_price=25_000,
    )
    assert m["tev_ebit"] == 10.0
    assert m["tev_ebitda"] == 8.0
    assert m["tev_normalized_earnings"] == 12.0
    assert m["pretax_earnings_yield"] == 1 / 12
    assert m["debt_ebitda"] == 2_000 / 1_500
    assert m["ebit_interest"] == 12.0
    assert m["fcf_yield_ev"] == 0.075
    assert m["fcf_yield_market"] == 900 / 11_000
    assert m["dividend_yield"] == 0.05
    assert m["price_vs_target"] == 0.8


def test_missing_denominators_never_become_zero_or_fake_metrics():
    m = inventory_metrics(
        tev=None,
        ebit=1_200,
        ebitda=0,
        normalized_earnings=None,
        total_debt=None,
        interest_expense=0,
        fcf_current=900,
        market_cap=None,
        dividend_per_share=1_000,
        market_price=0,
        target_price=0,
    )
    assert m["tev_ebit"] is None
    assert m["tev_ebitda"] is None
    assert m["tev_normalized_earnings"] is None
    assert m["pretax_earnings_yield"] is None
    assert m["debt_ebitda"] is None
    assert m["ebit_interest"] is None
    assert m["fcf_yield_ev"] is None
    assert m["fcf_yield_market"] is None
    assert m["dividend_yield"] is None
    assert m["price_vs_target"] is None


def test_negative_earnings_do_not_render_fake_cheap_multiples_but_negative_yields_remain_visible():
    m = inventory_metrics(
        tev=12_000,
        ebit=-1_200,
        ebitda=-500,
        normalized_earnings=-1_000,
        total_debt=2_000,
        interest_expense=100,
        fcf_current=-900,
        market_cap=11_000,
        dividend_per_share=0,
        market_price=20_000,
        target_price=25_000,
    )
    # Negative valuation/leverage multiples are economically non-comparable, not "cheap".
    assert m["tev_ebit"] is None
    assert m["tev_ebitda"] is None
    assert m["tev_normalized_earnings"] is None
    assert m["debt_ebitda"] is None
    # Negative numerator yields/coverage are retained as risk signals when denominator is valid.
    assert m["pretax_earnings_yield"] == -1_000 / 12_000
    assert m["ebit_interest"] == -12.0
    assert m["fcf_yield_ev"] == -900 / 12_000
    assert m["fcf_yield_market"] == -900 / 11_000
    assert m["dividend_yield"] == 0.0
