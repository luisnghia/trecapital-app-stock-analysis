import pandas as pd

from modules.deep_company_analysis.chapter4_quant import build_company_snapshot
from modules.deep_company_analysis.chapter5_quant import (
    build_balance_sheet_context,
    build_q22_context,
    build_reinvestment_context,
    build_roic_variants,
)
from modules.deep_company_analysis.chapter6_quant import build_q30_dol


def _frame(with_ttm=True):
    rows = [
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 1000, "gross_profit_bil": 300, "core_operating_profit_bil": 120, "net_profit_bil": 80, "cfo_bil": 100, "capex_bil": -40, "free_cash_flow_bil": 60, "roic_pct": 15, "total_assets_bil": 900, "current_liabilities_bil": 250, "short_term_debt_bil": 50, "cash_equivalents_bil": 100, "equity_bil": 500, "ebitda_bil": 160, "interest_expense_bil": 15, "current_assets_bil": 400},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 1200, "gross_profit_bil": 360, "core_operating_profit_bil": 150, "net_profit_bil": 95, "cfo_bil": 120, "capex_bil": -45, "free_cash_flow_bil": 75, "roic_pct": 16, "total_assets_bil": 1000, "current_liabilities_bil": 280, "short_term_debt_bil": 60, "cash_equivalents_bil": 120, "equity_bil": 560, "ebitda_bil": 190, "interest_expense_bil": 16, "current_assets_bil": 450},
    ]
    if with_ttm:
        rows.append({"period": "TTM", "period_type": "TTM", "year": 2026, "revenue_bil": 1320, "gross_profit_bil": 410, "core_operating_profit_bil": 170, "net_profit_bil": 110, "cfo_bil": 145, "capex_bil": -55, "free_cash_flow_bil": 90, "roic_pct": 17, "total_assets_bil": 1080, "current_liabilities_bil": 300, "short_term_debt_bil": 60, "cash_equivalents_bil": 135, "equity_bil": 610, "ebitda_bil": 215, "interest_expense_bil": 17, "current_assets_bil": 490})
    return pd.DataFrame(rows)


def test_chapter4_history_reaches_ttm_but_annual_median_logic_stays_available():
    snap = build_company_snapshot("DGC", "DGC", _frame(True))
    assert snap["latest_period"] == "TTM"
    assert snap["history"][-1]["Kỳ"] == "TTM"


def test_chapter5_q22_q25_q26_reach_ttm():
    df = _frame(True)
    assert build_q22_context(df).iloc[-1]["Kỳ"] == "TTM"
    assert build_balance_sheet_context(df).iloc[-1]["Kỳ"] == "TTM"
    variants = build_roic_variants(df)
    assert not variants.empty
    assert variants["Kỳ"].eq("TTM").all()


def test_chapter5_reinvestment_displays_ttm_without_fy_vs_ttm_incremental_roic():
    out = build_reinvestment_context(_frame(True))
    assert out.iloc[-1]["Kỳ"] == "TTM"
    assert pd.isna(out.iloc[-1]["Incremental ROIC %"])
    assert "comparable prior TTM" in str(out.iloc[-1]["Interpretation"])


def test_chapter6_dol_reaches_ttm_but_does_not_fabricate_ttm_dol():
    table, summary = build_q30_dol(_frame(True))
    assert table.iloc[-1]["Kỳ"] == "TTM"
    assert table.iloc[-1]["Validity"] == "N/A"
    assert pd.isna(table.iloc[-1]["Historical DOL (x)"])
    assert "comparable prior TTM" in table.iloc[-1]["Invalid Reason"]
    assert summary["valid_observations"] >= 1


def test_no_ttm_row_is_fabricated_when_input_has_no_valid_ttm():
    df = _frame(False)
    assert build_q22_context(df).iloc[-1]["Kỳ"] == "2025"
    assert build_balance_sheet_context(df).iloc[-1]["Kỳ"] == "2025"
    table, _ = build_q30_dol(df)
    assert table.iloc[-1]["Kỳ"] == "2025"
