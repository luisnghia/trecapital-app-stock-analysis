from __future__ import annotations

import pandas as pd
import pytest

from modules.investment_checklist.quantitative_tools import maintenance_capex_context, roic_quality, working_capital


def test_roic_quality_reads_module1_roic_standard_pct_field():
    df = pd.DataFrame([{
        "period": "2025", "period_type": "Y", "year": 2025,
        "roic_standard_pct": 18.7,
        "nopat_bil": 100,
        "capital_employed_bil": 500,
        "cash_and_short_investments_bil": 100,
    }])
    row = roic_quality(df).rows[0]
    assert row["ROIC Trecapital"] == pytest.approx(18.7)
    assert row["ROIC Shearn – Incl Cash"] == pytest.approx(20.0)
    assert row["ROIC Shearn – Ex Cash"] == pytest.approx(25.0)


def test_working_capital_prefers_canonical_cost_of_goods_sold_field():
    df = pd.DataFrame([
        {
            "period": "2024", "period_type": "Y", "year": 2024,
            "revenue_bil": 1000, "gross_profit_bil": 999, "cost_of_goods_sold_bil": 600,
            "accounts_receivable_bil": 100, "inventory_bil": 200, "accounts_payable_bil": 150,
        },
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            "revenue_bil": 1100, "gross_profit_bil": 1099, "cost_of_goods_sold_bil": 660,
            "accounts_receivable_bil": 120, "inventory_bil": 220, "accounts_payable_bil": 180,
        },
    ])
    row = working_capital(df).rows[1]
    assert row["DIO"] == pytest.approx(210 / 660 * 365)
    assert row["DPO"] == pytest.approx(165 / 660 * 365)


def test_maintenance_capex_keeps_trecapital_estimate_separate_from_depreciation_proxy():
    df = pd.DataFrame([{
        "period": "2025", "period_type": "Y", "year": 2025,
        "revenue_bil": 1000, "capex_bil": -150, "maintenance_capex_bil": -90,
        "depreciation_bil": 80, "cfo_bil": 250, "free_cash_flow_bil": 100,
    }])
    row = maintenance_capex_context(df).rows[0]
    assert row["Maintenance Capex Trecapital (ước tính)"] == pytest.approx(90)
    assert row["D&A rough proxy"] == pytest.approx(80)
    assert row["Maintenance Capex Trecapital (ước tính)"] != row["D&A rough proxy"]
