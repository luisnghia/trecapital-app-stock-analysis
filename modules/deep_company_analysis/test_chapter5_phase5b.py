from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter5_quant import (
    build_balance_sheet_context,
    build_chapter5_quant_context,
    build_q22_context,
    build_reinvestment_context,
    build_roic_distortion_diagnostics,
    build_roic_variants,
)


def _sample() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "period_type": "Y", "period": "2023", "year": 2023,
            "revenue_bil": 1000, "gross_profit_bil": 300, "core_operating_profit_bil": 180,
            "pretax_profit_bil": 170, "tax_expense_bil": 34, "cfo_bil": 170, "capex_bil": 80,
            "free_cash_flow_bil": 90, "roic_pct": 15.0, "cash_bil": 100, "total_debt_bil": 300,
            "short_term_debt_bil": 100,
            "equity_bil": 600, "ebitda_bil": 230, "interest_expense_bil": 30,
            "current_assets_bil": 500, "current_liabilities_bil": 250, "total_assets_bil": 1200,
            "goodwill_bil": 60, "net_ppe_bil": 500, "gross_ppe_bil": 850,
            "invested_capital_bil": 800,
        },
        {
            "period_type": "Y", "period": "2024", "year": 2024,
            "revenue_bil": 1120, "gross_profit_bil": 350, "core_operating_profit_bil": 200,
            "pretax_profit_bil": 190, "tax_expense_bil": 38, "cfo_bil": 190, "capex_bil": 90,
            "free_cash_flow_bil": 100, "roic_pct": 17.0, "cash_bil": 120, "total_debt_bil": 280,
            "short_term_debt_bil": 90,
            "equity_bil": 650, "ebitda_bil": 250, "interest_expense_bil": 28,
            "current_assets_bil": 560, "current_liabilities_bil": 260, "total_assets_bil": 1280,
            "goodwill_bil": 60, "net_ppe_bil": 470, "gross_ppe_bil": 870,
            "invested_capital_bil": 830,
        },
        {
            "period_type": "Y", "period": "2025", "year": 2025,
            "revenue_bil": 1250, "gross_profit_bil": 410, "core_operating_profit_bil": 205,
            "pretax_profit_bil": 198, "tax_expense_bil": 39.6, "cfo_bil": 210, "capex_bil": 95,
            "free_cash_flow_bil": 115, "roic_pct": 20.5, "cash_bil": 150, "total_debt_bil": 250,
            "short_term_debt_bil": 70,
            "equity_bil": 700, "ebitda_bil": 260, "interest_expense_bil": 25,
            "current_assets_bil": 620, "current_liabilities_bil": 250, "total_assets_bil": 1350,
            "goodwill_bil": 60, "net_ppe_bil": 420, "gross_ppe_bil": 900,
            "invested_capital_bil": 860,
        },
    ])


def test_q22_context_is_historical_and_no_qualitative_conclusion():
    df = build_q22_context(_sample())
    assert list(df["Kỳ"]) == ["2023", "2024", "2025"]
    assert "ROIC canonical %" in df.columns
    assert not any("quality" in str(c).lower() or "healthy" in str(c).lower() for c in df.columns)


def test_balance_sheet_context_calculates_descriptive_ratios():
    df = build_balance_sheet_context(_sample())
    latest = df.iloc[-1]
    assert round(float(latest["Nợ vay ròng (tỷ)"]), 1) == 100.0
    assert round(float(latest["Debt/EBITDA (x)"]), 3) == round(250 / 260, 3)
    assert round(float(latest["EBIT/Interest (x)"]), 1) == 8.2
    assert round(float(latest["Current Ratio (x)"]), 2) == 2.48


def test_canonical_roic_stays_separate_from_analytical_variants():
    variants = build_roic_variants(_sample())
    canonical = variants[variants["Origin"] == "Trecapital canonical"]
    analytical = variants[variants["Origin"] == "Shearn analytical"]
    assert len(canonical) == 1
    assert float(canonical.iloc[0]["Value %"]) == 20.5
    assert len(analytical) == 6


def test_excess_cash_variant_is_unknown_without_analyst_adjustment():
    variants = build_roic_variants(_sample())
    row = variants[variants["ROIC View"] == "ROIC ex excess cash"].iloc[0]
    assert pd.isna(row["Value %"])
    assert "analyst-confirmed" in str(row["Status / Requirement"])


def test_excess_cash_and_off_bs_variants_require_explicit_included_adjustments():
    adjustments = [
        {"Adjustment": "Excess cash", "Numerator / Denominator": "Denominator", "Amount": 100, "Included?": "Yes"},
        {"Adjustment": "Off-BS obligations", "Numerator / Denominator": "Denominator", "Amount": 50, "Included?": "Yes"},
    ]
    variants = build_roic_variants(_sample(), adjustments=adjustments)
    ex_cash = variants[variants["ROIC View"] == "ROIC ex excess cash"].iloc[0]
    off_bs = variants[variants["ROIC View"] == "ROIC off-BS adjusted"].iloc[0]
    assert pd.notna(ex_cash["Value %"])
    assert pd.notna(off_bs["Value %"])
    assert "EBIT" in str(ex_cash["Numerator Source"])


def test_reinvestment_context_is_descriptive_not_compounder_score():
    df = build_reinvestment_context(_sample())
    assert len(df) == 2
    assert "Incremental ROIC %" in df.columns
    assert all("Analyst only" in str(x) for x in df["Interpretation"])


def test_distortion_diagnostics_never_auto_conclude():
    df = build_roic_distortion_diagnostics(_sample())
    assert not df.empty
    assert set(df["Auto conclusion?"]) == {"No"}


def test_full_context_guardrails_all_false():
    ctx = build_chapter5_quant_context("DGC", "Duc Giang", _sample())
    assert ctx["canonical_roic_latest"] == 20.5
    assert ctx["guardrails"]
    assert all(value is False for value in ctx["guardrails"].values())
