from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter5_quant import build_chapter5_quant_context, build_roic_variants


def _sample(explicit_nibcl: bool = True) -> pd.DataFrame:
    rows = [
        {
            "period_type": "Y", "period": "2024", "year": 2024,
            "core_operating_profit_bil": 200.0,
            "roic_pct": 17.0,
            "total_assets_bil": 1280.0,
            "current_liabilities_bil": 260.0,
            "short_term_debt_bil": 90.0,
            "total_debt_bil": 280.0,
            "equity_bil": 650.0,
            "cash_bil": 120.0,
            "goodwill_bil": 60.0,
            "net_ppe_bil": 470.0,
            "gross_ppe_bil": 870.0,
            "pretax_profit_bil": 190.0,
            "tax_expense_bil": 38.0,
        },
        {
            "period_type": "Y", "period": "2025", "year": 2025,
            "core_operating_profit_bil": 205.0,
            "roic_pct": 20.5,
            "total_assets_bil": 1350.0,
            "current_liabilities_bil": 250.0,
            "short_term_debt_bil": 70.0,
            "total_debt_bil": 250.0,
            "equity_bil": 700.0,
            "cash_bil": 150.0,
            "goodwill_bil": 60.0,
            "net_ppe_bil": 420.0,
            "gross_ppe_bil": 900.0,
            "pretax_profit_bil": 198.0,
            "tax_expense_bil": 39.6,
        },
    ]
    if explicit_nibcl:
        rows[0]["non_interest_bearing_current_liabilities_bil"] = 170.0
        rows[1]["non_interest_bearing_current_liabilities_bil"] = 180.0
    return pd.DataFrame(rows)


def _row(df: pd.DataFrame, name: str) -> pd.Series:
    return df[df["ROIC View"].eq(name)].iloc[0]


def test_canonical_roic_is_untouched_and_separate():
    variants = build_roic_variants(_sample())
    canonical = _row(variants, "Trecapital Canonical ROIC")
    assert float(canonical["Value %"]) == 20.5
    assert canonical["Origin"] == "Trecapital canonical"
    assert canonical["Status / Requirement"] == "Single Source of Truth"


def test_every_shearn_variant_uses_adjusted_ebit_not_nopat():
    adjustments = [
        {"Adjustment": "Excess cash", "Numerator / Denominator": "Denominator", "Amount": 100, "Included?": "Yes"},
        {"Adjustment": "Off-BS obligations", "Numerator / Denominator": "Denominator", "Amount": 50, "Included?": "Yes"},
    ]
    variants = build_roic_variants(_sample(), adjustments=adjustments)
    shearn = variants[variants["Origin"].eq("Shearn analytical")]
    assert len(shearn) == 6
    assert set(float(x) for x in shearn["Numerator (tỷ)"].dropna()) == {205.0}
    assert all("EBIT" in str(x) for x in shearn["Numerator Source"])
    assert all("NOPAT" not in str(x).upper() for x in shearn["Formula / Note"])


def test_roic_with_cash_uses_average_asset_based_investment_base():
    variants = build_roic_variants(_sample())
    row = _row(variants, "ROIC with cash")
    # 2024 base = 1280 - 170 = 1110; 2025 base = 1350 - 180 = 1170; average = 1140.
    assert round(float(row["Denominator (tỷ)"]), 6) == 1140.0
    assert round(float(row["Value %"]), 6) == round(205.0 / 1140.0 * 100.0, 6)
    assert "Total Assets" in row["Formula / Note"]
    assert "non-interest-bearing current liabilities" in row["Formula / Note"]


def test_nibcl_proxy_requires_explicit_short_term_interest_bearing_debt():
    variants = build_roic_variants(_sample(explicit_nibcl=False))
    row = _row(variants, "ROIC with cash")
    # Proxy: 2024 NIBCL = 260 - 90 = 170; 2025 NIBCL = 250 - 70 = 180.
    assert round(float(row["Denominator (tỷ)"]), 6) == 1140.0
    assert "Current Liabilities" in str(row["Denominator Source"])
    assert "short-term interest-bearing debt" in str(row["Denominator Source"])


def test_excess_cash_is_never_assumed_automatically():
    variants = build_roic_variants(_sample())
    ex_cash = _row(variants, "ROIC ex excess cash")
    assert pd.isna(ex_cash["Value %"])
    assert "analyst-confirmed Excess Cash" in str(ex_cash["Status / Requirement"])


def test_excess_cash_goodwill_gross_asset_and_off_bs_denominators():
    adjustments = [
        {"Adjustment": "Excess cash", "Numerator / Denominator": "Denominator", "Amount": 100, "Included?": "Yes"},
        {"Adjustment": "Off-BS obligations", "Numerator / Denominator": "Denominator", "Amount": 50, "Included?": "Yes"},
    ]
    variants = build_roic_variants(_sample(), adjustments=adjustments)

    ex_cash = _row(variants, "ROIC ex excess cash")
    incl_goodwill = _row(variants, "ROIC including goodwill")
    ex_goodwill = _row(variants, "ROIC ex goodwill")
    gross = _row(variants, "ROIC gross-asset adjusted")
    off_bs = _row(variants, "ROIC off-BS adjusted")

    assert round(float(ex_cash["Denominator (tỷ)"]), 6) == 1040.0
    assert round(float(incl_goodwill["Denominator (tỷ)"]), 6) == 1040.0
    assert round(float(ex_goodwill["Denominator (tỷ)"]), 6) == 980.0
    # Average Gross PP&E = 885; Average Net PP&E = 445; accumulated depreciation proxy = 440.
    assert round(float(gross["Denominator (tỷ)"]), 6) == 1480.0
    assert round(float(off_bs["Denominator (tỷ)"]), 6) == 1090.0


def test_signed_numerator_adjustment_is_analyst_controlled():
    adjustments = [
        {"Adjustment": "Excess cash", "Numerator / Denominator": "Denominator", "Amount": 100, "Included?": "Yes"},
        {"Adjustment": "Analyst normalization", "Numerator / Denominator": "Numerator", "Amount": 10, "Included?": "Yes"},
    ]
    variants = build_roic_variants(_sample(), adjustments=adjustments)
    row = _row(variants, "ROIC ex excess cash")
    assert float(row["Numerator (tỷ)"]) == 215.0
    assert round(float(row["Value %"]), 6) == round(215.0 / 1040.0 * 100.0, 6)

    adjustments[1]["Amount"] = -10
    variants2 = build_roic_variants(_sample(), adjustments=adjustments)
    row2 = _row(variants2, "ROIC ex excess cash")
    assert float(row2["Numerator (tỷ)"]) == 195.0


def test_denominator_adjustment_never_leaks_into_ebit_numerator():
    adjustments = [
        {"Adjustment": "Excess cash", "Numerator / Denominator": "Denominator", "Amount": 100, "Included?": "Yes"},
    ]
    variants = build_roic_variants(_sample(), adjustments=adjustments)
    assert float(_row(variants, "ROIC ex excess cash")["Numerator (tỷ)"]) == 205.0


def test_shearn_average_base_does_not_silently_fallback_to_single_period():
    one_period = _sample().iloc[-1:].copy()
    variants = build_roic_variants(one_period)
    row = _row(variants, "ROIC with cash")
    assert pd.isna(row["Value %"])
    assert pd.isna(row["Denominator (tỷ)"])


def test_full_context_guardrail_states_shearn_does_not_use_nopat():
    ctx = build_chapter5_quant_context("DGC", "Duc Giang", _sample())
    assert ctx["canonical_roic_latest"] == 20.5
    assert ctx["guardrails"]["shearn_variants_use_nopat"] is False
    assert all(value is False for value in ctx["guardrails"].values())
