from __future__ import annotations

import pandas as pd
import pytest

from module1_engine import CompanyOverview, build_cashflow_scorecard, ensure_derived_metrics
from module2_engine import build_accrual_quality_table, build_porter_moat_scorecard
from modules.investment_checklist.quantitative_tools import buyback_dilution, operating_driver_eps


def _company() -> CompanyOverview:
    return CompanyOverview("TST", "Test", "HOSE", "Industrial", "", None, None, None, None, None, None, None, None, None, None)


def test_negative_profit_denominators_never_create_positive_conversion_ratios():
    out = ensure_derived_metrics(pd.DataFrame([{
        "net_profit_bil": -100, "pretax_profit_bil": -90, "cfo_bil": -50,
        "capex_bil": -10, "free_cash_flow_bil": -60, "ebitda_bil": -20,
        "net_debt_bil": 200, "cash_equivalents_bil": 0, "short_term_investments_bil": 0,
    }])).iloc[0]
    assert pd.isna(out["cfo_to_net_profit"])
    assert pd.isna(out["fcf_to_net_profit"])
    assert pd.isna(out["fcf_to_pretax"])
    assert pd.isna(out["net_debt_to_ebitda"])


def test_negative_cfo_capex_intensity_is_warning_not_full_score_regression():
    df = pd.DataFrame([{
        "period": "TTM", "period_type": "TTM", "net_profit_bil": 2570,
        "pretax_profit_bil": 3000, "cfo_bil": -2650, "capex_bil": -668,
        "free_cash_flow_bil": -3318, "owner_earnings_bil": -3318,
    }])
    score = build_cashflow_scorecard(df)
    row = score[score["Nhóm tiêu chí"].str.startswith("5.")].iloc[0]
    assert row["Điểm"] == 0
    assert row["Tín hiệu"] == "Cảnh báo"
    assert "CFO âm/bằng 0" in row["Nhận xét tự động"]


def test_positive_cfo_keeps_standard_capex_intensity_evaluation():
    df = pd.DataFrame([{
        "period": "2025", "period_type": "Y", "net_profit_bil": 100,
        "pretax_profit_bil": 120, "cfo_bil": 200, "capex_bil": -80,
        "free_cash_flow_bil": 120, "owner_earnings_bil": 120,
    }])
    row = build_cashflow_scorecard(df).query("`Nhóm tiêu chí`.str.startswith('5.')", engine="python").iloc[0]
    assert row["Điểm"] == 10
    assert "40.0%" in row["Nhận xét tự động"]


def test_accrual_layer_marks_loss_base_without_negative_over_negative_ratio():
    df = pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "total_assets_bil": 1000, "net_profit_bil": 10, "cfo_bil": 20, "free_cash_flow_bil": 10},
        {"period": "2025", "period_type": "Y", "year": 2025, "total_assets_bil": 900, "net_profit_bil": -100, "cfo_bil": -50, "free_cash_flow_bil": -60},
    ])
    row = build_accrual_quality_table(_company(), df).iloc[-1]
    assert pd.isna(row["CFO/LNST"])
    assert pd.isna(row["FCF/LNST"])
    assert "không dùng âm chia âm" in row["Tín hiệu"]
    assert row["Mức cảnh báo"] in {"Theo dõi", "Rủi ro cao", "Rủi ro rất cao"}


def test_moat_cash_quality_gets_zero_when_latest_profit_and_cfo_are_negative():
    df = pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "net_profit_bil": 100, "cfo_bil": 110, "free_cash_flow_bil": 80},
        {"period": "2025", "period_type": "Y", "year": 2025, "net_profit_bil": -50, "cfo_bil": -30, "free_cash_flow_bil": -40},
    ])
    row = build_porter_moat_scorecard(_company(), df).query("`Nhóm Porter/Moat` == 'Chất lượng dòng tiền'").iloc[0]
    assert row["Điểm đạt"] == 0
    assert "âm chia âm" in row["Diễn giải"]


def test_eps_growth_and_buyback_uplift_are_not_computed_on_loss_base():
    df = pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 100, "eps_vnd": -100, "net_profit_bil": -10, "shares_outstanding_mil": 100},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 110, "eps_vnd": 100, "net_profit_bil": 10, "shares_outstanding_mil": 90},
    ])
    driver = operating_driver_eps(df).rows[-1]
    assert driver["EPS growth"] is None
    assert "lỗ sang lãi" in driver["Signal"]

    loss_buyback = buyback_dilution(pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "net_profit_bil": -10, "shares_outstanding_mil": 100},
        {"period": "2025", "period_type": "Y", "year": 2025, "net_profit_bil": -9, "shares_outstanding_mil": 90},
    ])).rows[-1]
    assert loss_buyback["EPS uplift from share-count change"] is None
