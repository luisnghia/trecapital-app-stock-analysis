from __future__ import annotations

import pandas as pd
import pytest

from adapters.vn_public_crawler import _extract_fireant_statement_timeseries_exact
from module1_engine import CompanyOverview, append_ttm_row, build_mos_valuation_table, ensure_derived_metrics, format_table_for_display
from modules.deep_company_analysis.financial_semantics import period_display, semantic_warnings, semantics_table
from modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context


def _income_payload(quarter: int, year: int, consolidated_bil: float, parent_bil: float):
    return [
        {"ID": 3, "Name": "Doanh thu thuần", "Values": [{"Year": year, "Quarter": quarter, "Value": 2_400_000_000_000}]},
        {"ID": 19, "Name": "Lợi nhuận sau thuế", "Values": [{"Year": year, "Quarter": quarter, "Value": consolidated_bil * 1_000_000_000}]},
        {"ID": 21, "Name": "Lợi nhuận sau thuế của cổ đông của công ty mẹ", "Values": [{"Year": year, "Quarter": quarter, "Value": parent_bil * 1_000_000_000}]},
    ]


def test_fireant_exact_parser_preserves_consolidated_and_parent_profit_scope():
    df = _extract_fireant_statement_timeseries_exact([_income_payload(2, 2026, 440.8, 388.55)], "DGC")
    row = df.iloc[0]
    assert row["net_profit_consolidated_bil"] == pytest.approx(440.8)
    assert row["net_profit_parent_bil"] == pytest.approx(388.55)
    assert row["net_profit_bil"] == pytest.approx(388.55)
    assert row["net_profit_scope"] == "parent_attributable"


def test_explicit_consolidated_only_profit_does_not_generate_fake_eps():
    df = pd.DataFrame([
        {
            "period": "Q2/2026", "period_type": "Q", "year": 2026, "quarter": 2,
            "net_profit_consolidated_bil": 440.8, "shares_outstanding_mil": 379.8,
        }
    ])
    out = ensure_derived_metrics(df)
    row = out.iloc[0]
    assert row["net_profit_scope"] == "consolidated"
    assert row["net_profit_bil"] == pytest.approx(440.8)  # backward-compatible legacy alias
    assert pd.isna(row["eps_vnd"])



def test_consolidated_only_profit_cannot_feed_eps_based_mos_fallback():
    company = CompanyOverview(
        ticker="DGC", company_name="Duc Giang", exchange="HOSE", industry="Chemicals", sub_industry="",
        market_cap_bil=None, shares_outstanding_mil=100.0, current_price=50_000.0,
        eps=None, pe=None, pb=None, ps=None, roe=None, roa=None, roic=None,
    )
    annual = pd.DataFrame([{
        "period": "2025", "period_type": "Y", "year": 2025,
        "net_profit_consolidated_bil": 500.0, "shares_outstanding_mil": 100.0,
        "equity_bil": 1_000.0,
    }])
    valuation = build_mos_valuation_table(company, annual)
    assert valuation.empty


def test_ttm_requires_four_complete_flow_quarters_and_labels_end_period():
    annual = pd.DataFrame([
        {"ticker": "DGC", "period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 11_262.0, "net_profit_parent_bil": 3_154.0}
    ])
    quarterly = pd.DataFrame([
        {"ticker": "DGC", "period": "Q3/2025", "period_type": "Q", "year": 2025, "quarter": 3, "revenue_bil": 2816.7, "net_profit_parent_bil": 804.4},
        {"ticker": "DGC", "period": "Q4/2025", "period_type": "Q", "year": 2025, "quarter": 4, "revenue_bil": 2740.6, "net_profit_parent_bil": 656.9},
        {"ticker": "DGC", "period": "Q1/2026", "period_type": "Q", "year": 2026, "quarter": 1, "revenue_bil": 2124.6, "net_profit_parent_bil": 408.5},
        {"ticker": "DGC", "period": "Q2/2026", "period_type": "Q", "year": 2026, "quarter": 2, "revenue_bil": 2415.4, "net_profit_parent_bil": 388.55},
    ])
    out = append_ttm_row(annual, quarterly)
    ttm = out[out["period"].eq("TTM")].iloc[-1]
    assert ttm["period_display"] == "TTM đến Q2/2026"
    assert ttm["ttm_end_period"] == "Q2/2026"
    assert ttm["revenue_bil"] == pytest.approx(10097.3)
    assert ttm["net_profit_parent_bil"] == pytest.approx(2258.35)
    assert ttm["net_profit_bil"] == pytest.approx(2258.35)
    assert ttm["net_profit_scope"] == "parent_attributable"

    quarterly.loc[2, "revenue_bil"] = None
    incomplete = append_ttm_row(annual, quarterly)
    ttm_incomplete = incomplete[incomplete["period"].eq("TTM")].iloc[-1]
    assert pd.isna(ttm_incomplete["revenue_bil"])


def test_semantics_table_has_required_provenance_shape_and_no_scope_inference():
    df = pd.DataFrame([
        {
            "period": "TTM", "period_type": "Y", "year": 2026, "quarter": 2,
            "period_display": "TTM đến Q2/2026", "ttm_end_period": "Q2/2026",
            "net_profit_bil": 2258.35, "net_profit_parent_bil": 2258.35,
            "net_profit_consolidated_bil": 2332.2, "net_profit_scope": "parent_attributable",
            "eps_vnd": 5946.0, "comparability_status": "review",
            "comparability_note": "Historical reclassification requires analyst review",
        }
    ])
    table = semantics_table(df, source_label="FireAnt exact statement")
    required = {"Source Field", "Source Module", "Source Period", "Data Origin", "Profit Scope", "Comparability"}
    assert required.issubset(set(table.columns))
    assert set(table["Source Period"]) == {"TTM đến Q2/2026"}
    assert table.loc[table["Metric"].eq("LNST hợp nhất"), "Profit Scope"].iloc[0] == "consolidated"
    assert table.loc[table["Metric"].eq("LNST thuộc CĐ công ty mẹ"), "Profit Scope"].iloc[0] == "parent_attributable"
    assert semantic_warnings(df) == []


def test_chapter6_consumes_period_display_and_exposes_profit_scopes_without_score():
    rows = []
    for year in range(2017, 2026):
        rows.append({
            "period": str(year), "period_type": "Y", "year": year,
            "revenue_bil": 1000 + (year - 2017) * 100,
            "net_profit_parent_bil": 100 + (year - 2017) * 10,
            "net_profit_consolidated_bil": 105 + (year - 2017) * 10,
            "cfo_bil": 120 + (year - 2017) * 10,
        })
    rows.append({
        "period": "TTM", "period_type": "Y", "period_display": "TTM đến Q2/2026", "ttm_end_period": "Q2/2026",
        "year": 2026, "quarter": 2, "revenue_bil": 2100,
        "net_profit_parent_bil": 220, "net_profit_consolidated_bil": 230, "net_profit_bil": 220,
        "net_profit_scope": "parent_attributable", "cfo_bil": 250,
    })
    ctx = build_chapter6_quant_context("DGC", "Duc Giang", pd.DataFrame(rows), source_label="canonical test")
    assert ctx["latest_period"] == "TTM đến Q2/2026"
    q27 = ctx["q27_accounting_quality"]
    assert q27.iloc[-1]["Kỳ"] == "TTM đến Q2/2026"
    assert q27.iloc[-1]["LNST hợp nhất (tỷ)"] == pytest.approx(230)
    assert q27.iloc[-1]["LNST CĐ công ty mẹ (tỷ)"] == pytest.approx(220)
    assert "overall_score" not in ctx and "buy_hold_sell" not in ctx


def test_display_table_uses_dated_ttm_and_explicit_profit_labels():
    df = pd.DataFrame([{
        "period": "TTM", "period_display": "TTM đến Q2/2026", "net_profit_bil": 388.55,
        "net_profit_consolidated_bil": 440.8, "net_profit_parent_bil": 388.55,
        "net_profit_scope": "parent_attributable",
    }])
    out = format_table_for_display(df)
    assert out.iloc[0]["Kỳ"] == "TTM đến Q2/2026"
    assert "LNST hợp nhất (tỷ)" in out.columns
    assert "LNST CĐ công ty mẹ (tỷ)" in out.columns
    assert "Phạm vi LNST canonical" in out.columns


def test_period_display_never_mislabels_ttm_as_fy():
    assert period_display({"period": "TTM", "year": 2026, "quarter": 2}) == "TTM đến Q2/2026"
    assert period_display({"period": "TTM"}) == "TTM"
