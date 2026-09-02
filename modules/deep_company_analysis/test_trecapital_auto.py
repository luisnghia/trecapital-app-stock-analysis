from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from modules.deep_company_analysis.trecapital_auto import build_chapter1_auto_data, build_quantitative_suggestions


def _source(**overrides):
    base = dict(
        as_of_date="TTM",
        tev=9000.0,
        ebit=1500.0,
        ebitda=1800.0,
        normalized_earnings=1400.0,
        total_debt=500.0,
        interest_expense=100.0,
        fcf_current=1200.0,
        market_cap=10000.0,
        dividend_per_share=2000.0,
        market_price=50000.0,
        target_price=70000.0,
        mos=(70000.0 - 50000.0) / 70000.0,
        source_module="module1_normalized_cache+module2_valuation",
        source_notes=("test-note",),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _annual():
    return pd.DataFrame(
        [
            {"period": "2022", "revenue_bil": 10000.0, "cfo_bil": 1200.0, "capex_bil": -500.0, "roic_standard_pct": 17.0},
            {"period": "2023", "revenue_bil": 11000.0, "cfo_bil": 1300.0, "capex_bil": -550.0, "roic_standard_pct": 18.0},
            {"period": "2024", "revenue_bil": 12000.0, "cfo_bil": 1400.0, "capex_bil": -600.0, "roic_standard_pct": 19.0},
            {"period": "2025", "revenue_bil": 13000.0, "cfo_bil": 1500.0, "capex_bil": -650.0, "roic_standard_pct": 20.0},
            {"period": "TTM", "revenue_bil": 14000.0, "cfo_bil": 1600.0, "capex_bil": -700.0, "roic_standard_pct": 21.0},
        ]
    )


def test_quantitative_suggestions_are_conservative_and_three_level():
    suggestions = build_quantitative_suggestions(_source(), _annual())
    assert set(suggestions) == {"strong_financials", "high_roic", "low_capex", "strong_balance_sheet"}
    assert suggestions["strong_financials"]["status"] == "✓ Có"
    assert suggestions["high_roic"]["status"] == "✓ Có"
    assert suggestions["high_roic"]["confidence"] == 3
    assert suggestions["low_capex"]["status"] == "✓ Có"
    assert suggestions["low_capex"]["confidence"] <= 2  # total capex proxy must never be High confidence
    assert suggestions["strong_balance_sheet"]["status"] == "✓ Có"  # TEV < market cap => net cash proxy
    assert all(item["confidence"] in {1, 2, 3} for item in suggestions.values())


def test_negative_fcf_blocks_strong_financials():
    suggestions = build_quantitative_suggestions(_source(fcf_current=-100.0), _annual())
    assert suggestions["strong_financials"]["status"] == "X Không"


def test_canonical_small_roic_pct_is_not_multiplied_by_100():
    annual = _annual()
    annual["roic_standard_pct"] = [1.5, 1.5, 1.5, 1.5, 1.5]
    suggestions = build_quantitative_suggestions(_source(), annual)
    assert suggestions["high_roic"]["status"] == "X Không"
    assert "1.5%" in suggestions["high_roic"]["evidence"]


def test_auto_data_maps_table_12_fields():
    source = _source()

    class Provider:
        def get_inventory_source_data(self, _ctx):
            return source

    result = build_chapter1_auto_data(Provider(), _annual())
    valuation = result["valuation"]
    assert valuation["current_price"] == 50000.0
    assert valuation["target_price"] == 70000.0
    assert round(valuation["tev_ebit"], 2) == 6.0
    assert round(valuation["tev_ebitda"], 2) == 5.0
    assert round(valuation["debt_ebitda"], 3) == round(500 / 1800, 3)
    assert valuation["ebit_interest"] == 15.0
    assert round(valuation["fcf_yield_pct"], 1) == 12.0
    assert round(valuation["dividend_yield_pct"], 1) == 4.0
    assert round(valuation["stock_price_vs_target_pct"], 1) == 71.4
    assert result["source_module"].startswith("module1_normalized_cache")
