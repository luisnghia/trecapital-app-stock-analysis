from __future__ import annotations

from streamlit.testing.v1 import AppTest


APP = r'''
import pandas as pd
from modules.investment_checklist.ui.quant_tools import render_quantitative_tools

class Provider:
    def __init__(self):
        self.annual_df = pd.DataFrame([
            {
                "period": "2023", "period_type": "Y", "year": 2023,
                "revenue_bil": 1000.0, "gross_profit_bil": 400.0,
                "core_operating_profit_bil": 120.0, "ebitda_bil": 170.0,
                "pretax_profit_bil": 105.0, "net_profit_bil": 84.0, "nopat_bil": 96.0,
                "cfo_bil": 150.0, "free_cash_flow_bil": 90.0, "capex_bil": -60.0,
                "maintenance_capex_bil": -45.0, "depreciation_bil": 50.0,
                "total_assets_bil": 1600.0, "current_assets_bil": 650.0,
                "current_liabilities_bil": 380.0, "capital_employed_bil": 1220.0,
                "avg_capital_employed_bil": 1180.0, "roic_standard_pct": 8.1,
                "cash_and_short_investments_bil": 250.0, "interest_bearing_debt_bil": 300.0,
                "interest_expense_bil": -25.0, "accounts_receivable_bil": 120.0,
                "inventory_bil": 180.0, "accounts_payable_bil": 140.0,
                "cost_of_goods_sold_bil": 600.0, "shares_outstanding_mil": 100.0,
                "eps_vnd": 840.0,
            },
            {
                "period": "2024", "period_type": "Y", "year": 2024,
                "revenue_bil": 1120.0, "gross_profit_bil": 470.0,
                "core_operating_profit_bil": 150.0, "ebitda_bil": 205.0,
                "pretax_profit_bil": 132.0, "net_profit_bil": 105.0, "nopat_bil": 120.0,
                "cfo_bil": 185.0, "free_cash_flow_bil": 110.0, "capex_bil": -75.0,
                "maintenance_capex_bil": -52.0, "depreciation_bil": 55.0,
                "total_assets_bil": 1750.0, "current_assets_bil": 710.0,
                "current_liabilities_bil": 400.0, "capital_employed_bil": 1350.0,
                "avg_capital_employed_bil": 1285.0, "roic_standard_pct": 9.3,
                "cash_and_short_investments_bil": 280.0, "interest_bearing_debt_bil": 290.0,
                "interest_expense_bil": -24.0, "accounts_receivable_bil": 130.0,
                "inventory_bil": 190.0, "accounts_payable_bil": 150.0,
                "cost_of_goods_sold_bil": 650.0, "shares_outstanding_mil": 96.0,
                "shares_repurchased_mil": 5.0, "shares_issued_mil": 1.0, "eps_vnd": 1094.0,
            },
            {
                "period": "2025", "period_type": "Y", "year": 2025,
                "revenue_bil": 1260.0, "gross_profit_bil": 550.0,
                "core_operating_profit_bil": 190.0, "ebitda_bil": 250.0,
                "pretax_profit_bil": 168.0, "net_profit_bil": 134.0, "nopat_bil": 152.0,
                "cfo_bil": 225.0, "free_cash_flow_bil": 135.0, "capex_bil": -90.0,
                "maintenance_capex_bil": -60.0, "depreciation_bil": 60.0,
                "total_assets_bil": 1900.0, "current_assets_bil": 760.0,
                "current_liabilities_bil": 420.0, "capital_employed_bil": 1480.0,
                "avg_capital_employed_bil": 1415.0, "roic_standard_pct": 10.7,
                "cash_and_short_investments_bil": 320.0, "interest_bearing_debt_bil": 270.0,
                "interest_expense_bil": -22.0, "accounts_receivable_bil": 138.0,
                "inventory_bil": 198.0, "accounts_payable_bil": 165.0,
                "cost_of_goods_sold_bil": 710.0, "shares_outstanding_mil": 92.0,
                "shares_repurchased_mil": 5.0, "shares_issued_mil": 1.0, "eps_vnd": 1457.0,
                "dso_days": 39.0, "dio_days": 100.0, "dpo_days": 82.0,
                "cash_conversion_cycle_days": 57.0,
            },
            {
                "period": "TTM", "period_type": "TTM", "year": 2026,
                "revenue_bil": 1320.0, "gross_profit_bil": 585.0,
                "core_operating_profit_bil": 205.0, "ebitda_bil": 268.0,
                "pretax_profit_bil": 181.0, "net_profit_bil": 145.0, "nopat_bil": 164.0,
                "cfo_bil": 240.0, "free_cash_flow_bil": 145.0, "capex_bil": -95.0,
                "maintenance_capex_bil": -64.0, "depreciation_bil": 63.0,
                "total_assets_bil": 1960.0, "current_assets_bil": 790.0,
                "current_liabilities_bil": 430.0, "capital_employed_bil": 1530.0,
                "avg_capital_employed_bil": 1505.0, "roic_standard_pct": 10.9,
                "cash_and_short_investments_bil": 335.0, "interest_bearing_debt_bil": 260.0,
                "interest_expense_bil": -21.0, "accounts_receivable_bil": 142.0,
                "inventory_bil": 202.0, "accounts_payable_bil": 170.0,
                "cost_of_goods_sold_bil": 735.0, "shares_outstanding_mil": 91.0,
                "eps_vnd": 1593.0,
            },
        ])

render_quantitative_tools(Provider(), company_type="normal")
'''


def _assert_clean(at: AppTest) -> None:
    assert len(at.exception) == 0
    assert len(at.selectbox) >= 1
    assert len(at.dataframe) >= 1


def test_phase2_streamlit_smoke_all_tools_render_without_exception():
    at = AppTest.from_string(APP, default_timeout=10).run()
    _assert_clean(at)

    tool_options = [
        "5.1–5.2 · Balance Sheet & Leverage",
        "5.3–5.4 · ROIC Quality",
        "6.1–6.2 · Accounting Reserve Quality",
        "6.3–6.5 · Operating Leverage & Cost Structure",
        "6.6 · Working Capital / CCC",
        "Ch.6 Key Point · Maintenance Capex Context",
        "8.2–8.3 · Buyback & Dilution",
        "10.1 · Operating Driver → EPS",
    ]
    for option in tool_options:
        at.selectbox[0].select(option).run()
        _assert_clean(at)


def test_phase2_streamlit_smoke_financial_company_warning_does_not_break_ui():
    app = APP.replace('company_type="normal"', 'company_type="bank"')
    at = AppTest.from_string(app, default_timeout=10).run()
    _assert_clean(at)
    assert any("Doanh nghiệp tài chính" in warning.value for warning in at.warning)
