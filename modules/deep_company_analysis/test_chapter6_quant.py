from __future__ import annotations

import math

import pandas as pd

from modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context, build_q30_dol


def _sample_rows() -> pd.DataFrame:
    rows = []
    for i, year in enumerate(range(2018, 2026)):
        revenue = 1000 + i * 100
        ebit = 120 + i * 18
        cfo = 105 + i * 15
        ni = 80 + i * 12
        ar = 120 + i * 8
        inv = 140 + i * 7
        ap = 90 + i * 6
        current_assets = 500 + i * 25
        current_liab = 280 + i * 13
        cash = 80 + i * 4
        sti = 20
        short_debt = 30
        capex = -(70 + i * 3)
        da = 50 + i * 2
        rows.append({
            "ticker": "AAA",
            "period": str(year),
            "period_type": "Y",
            "year": year,
            "revenue_bil": revenue,
            "gross_profit_bil": revenue * 0.30,
            "core_operating_profit_bil": ebit,
            "net_profit_bil": ni,
            "cfo_bil": cfo,
            "tax_expense_bil": 18 + i,
            "accounts_receivable_bil": ar,
            "inventory_bil": inv,
            "accounts_payable_bil": ap,
            "cost_of_goods_sold_bil": revenue * 0.70,
            "current_assets_bil": current_assets,
            "current_liabilities_bil": current_liab,
            "cash_equivalents_bil": cash,
            "short_term_investments_bil": sti,
            "short_term_debt_bil": short_debt,
            "capex_bil": capex,
            "depreciation_bil": da,
            "free_cash_flow_bil": cfo - abs(capex),
            "fixed_assets_bil": 350 + i * 15,
            "working_capital_change_bil": -(5 + i),
        })
    return pd.DataFrame(rows)


def test_phase6b_builds_all_quantitative_context_without_auto_judgement():
    ctx = build_chapter6_quant_context(
        "AAA",
        "Alpha",
        _sample_rows(),
        industry="Industrials",
        source_label="Unit test canonical",
    )
    assert not ctx["q27_accounting_quality"].empty
    assert not ctx["q29_cycle_history"].empty
    assert not ctx["q30_dol_history"].empty
    assert not ctx["q31_working_capital"].empty
    assert not ctx["q32_capex_history"].empty
    assert ctx["q31_summary"]["applicable"] is True
    assert ctx["guardrails"]["auto_distribution_width"] is False
    assert ctx["guardrails"]["auto_mos_change"] is False
    assert ctx["guardrails"]["auto_buy_hold_sell"] is False


def test_q27_does_not_substitute_tax_paid_for_current_tax():
    df = _sample_rows()
    df["tax_paid_bil"] = 15.0
    ctx = build_chapter6_quant_context("AAA", "Alpha", df, industry="Industrials")
    assert ctx["q27_summary"]["tax_comparison_available"] is False
    assert "tax_paid_bil" in ctx["q27_summary"]["tax_guardrail"]
    assert ctx["q27_accounting_quality"]["Current Tax (tỷ)"].isna().all()


def test_q28_never_infers_recurring_share():
    ctx = build_chapter6_quant_context("AAA", "Alpha", _sample_rows(), industry="Industrials")
    assert ctx["q28_disclosed_recurring"].empty
    assert any("does not infer" in warning for warning in ctx["coverage_warnings"])

    df = _sample_rows()
    df["recurring_revenue_pct"] = 64.4
    ctx = build_chapter6_quant_context("AAA", "Alpha", df, industry="Industrials")
    assert not ctx["q28_disclosed_recurring"].empty
    assert set(ctx["q28_disclosed_recurring"]["Source Field"]) == {"recurring_revenue_pct"}


def test_dol_keeps_invalid_rows_visible_and_excludes_them_from_median():
    df = _sample_rows().copy()
    # Create one near-flat revenue period and one EBIT sign shift.
    df.loc[df.index[3], "revenue_bil"] = df.loc[df.index[2], "revenue_bil"] * 1.005
    df.loc[df.index[5], "core_operating_profit_bil"] = -20.0
    table, summary = build_q30_dol(df)
    assert len(table) == len(df)
    assert (table["Validity"] == "Invalid").sum() >= 2
    valid = pd.to_numeric(table.loc[table["Validity"] == "Valid", "Historical DOL (x)"], errors="coerce").dropna()
    expected = float(valid.median()) if not valid.empty else None
    if expected is None:
        assert summary["median_dol"] is None
    else:
        assert math.isclose(summary["median_dol"], expected, rel_tol=1e-9)


def test_working_capital_cash_sign_and_financial_sector_na():
    df = _sample_rows()
    ctx = build_chapter6_quant_context("AAA", "Alpha", df, industry="Industrials")
    wc = ctx["q31_working_capital"].dropna(subset=["Δ OWC (tỷ)"]).iloc[-1]
    assert math.isclose(wc["Cash Impact from ΔOWC (tỷ)"], -wc["Δ OWC (tỷ)"], rel_tol=1e-9)

    bank = build_chapter6_quant_context("VCB", "Bank", df, industry="Ngân hàng")
    assert bank["q31_working_capital"].empty
    assert bank["q31_summary"]["applicable"] is False
    assert "N/A" in bank["q31_summary"]["status"]


def test_q32_uses_total_capex_magnitude_but_never_imports_maintenance_proxy():
    df = _sample_rows()
    df["maintenance_capex_bil"] = -999.0  # generic upstream OE proxy must not enter Ch6 Phase 6B.
    ctx = build_chapter6_quant_context("AAA", "Alpha", df, industry="Industrials")
    capex = ctx["q32_capex_history"]
    assert (capex["Total Capex (tỷ)"] > 0).all()
    assert "maintenance" not in " ".join(capex.columns).lower()
    assert "does NOT import Module-1 maintenance_capex_bil" in ctx["q32_summary"]["maintenance_capex_guardrail"]


def test_provenance_fields_are_present():
    ctx = build_chapter6_quant_context("AAA", "Alpha", _sample_rows(), industry="Industrials")
    prov = ctx["provenance"]
    assert prov["source_module"]
    assert prov["source_period"]
    assert prov["data_origin"]
    table = ctx["provenance_table"]
    assert set(table["Question"]) == {"Q27", "Q28", "Q29", "Q30", "Q31", "Q32"}
