from __future__ import annotations

import pandas as pd
from streamlit.testing.v1 import AppTest

# Register app-specific Watchlist extensions before inspecting the registry.
from modules.investment_checklist import book_guidance_extensions as _extensions  # noqa: F401
from modules.investment_checklist.book_guidance import BOOK_GUIDANCE, uncovered_metrics
from modules.investment_checklist.quantitative_tools import (
    accounting_quality_proxy,
    balance_sheet_leverage,
    buyback_dilution,
    maintenance_capex_context,
    operating_driver_eps,
    operating_leverage,
    operating_leverage_stress,
    roic_quality,
    working_capital,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "period": "2024", "period_type": "Y", "year": 2024,
            "revenue_bil": 1000.0, "gross_profit_bil": 400.0, "core_operating_profit_bil": 120.0,
            "ebitda_bil": 170.0, "pretax_profit_bil": 105.0, "net_profit_bil": 84.0, "nopat_bil": 96.0,
            "cfo_bil": 150.0, "free_cash_flow_bil": 90.0, "capex_bil": -60.0,
            "maintenance_capex_bil": -45.0, "depreciation_bil": 50.0,
            "total_assets_bil": 1600.0, "current_assets_bil": 650.0, "current_liabilities_bil": 380.0,
            "capital_employed_bil": 1220.0, "roic_standard_pct": 8.1,
            "cash_and_short_investments_bil": 250.0, "interest_bearing_debt_bil": 300.0,
            "interest_expense_bil": -25.0, "accounts_receivable_bil": 120.0,
            "inventory_bil": 180.0, "accounts_payable_bil": 140.0, "cost_of_goods_sold_bil": 600.0,
            "shares_outstanding_mil": 100.0, "eps_vnd": 840.0,
            "bad_debt_provision_bil": 4.0, "charge_off_bil": 3.5,
            "goodwill_bil": 100.0, "net_ppe_bil": 600.0, "sga_bil": 180.0,
        },
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            "revenue_bil": 1120.0, "gross_profit_bil": 470.0, "core_operating_profit_bil": 150.0,
            "ebitda_bil": 205.0, "pretax_profit_bil": 132.0, "net_profit_bil": 105.0, "nopat_bil": 120.0,
            "cfo_bil": 185.0, "free_cash_flow_bil": 110.0, "capex_bil": -75.0,
            "maintenance_capex_bil": -52.0, "depreciation_bil": 55.0,
            "total_assets_bil": 1750.0, "current_assets_bil": 710.0, "current_liabilities_bil": 400.0,
            "capital_employed_bil": 1350.0, "roic_standard_pct": 9.3,
            "cash_and_short_investments_bil": 280.0, "interest_bearing_debt_bil": 290.0,
            "interest_expense_bil": -24.0, "accounts_receivable_bil": 130.0,
            "inventory_bil": 190.0, "accounts_payable_bil": 150.0, "cost_of_goods_sold_bil": 650.0,
            "shares_outstanding_mil": 96.0, "shares_repurchased_mil": 5.0, "shares_issued_mil": 1.0,
            "buyback_bil": 60.0, "eps_vnd": 1094.0, "bad_debt_provision_bil": 4.2, "charge_off_bil": 4.0,
            "goodwill_bil": 105.0, "net_ppe_bil": 620.0, "sga_bil": 190.0,
        },
    ])


def test_every_quantitative_output_column_has_book_guidance():
    df = _sample_df()
    results = [
        balance_sheet_leverage(df),
        roic_quality(df),
        accounting_quality_proxy(df),
        operating_leverage(df),
        working_capital(df),
        maintenance_capex_context(df),
        buyback_dilution(df),
        operating_driver_eps(df, driver_field="revenue_bil", driver_label="Revenue"),
    ]
    for result in results:
        assert result.rows, result.name
        columns = list(pd.DataFrame(result.rows).columns)
        assert uncovered_metrics(result.name, columns) == [], (result.name, uncovered_metrics(result.name, columns))

    stress = operating_leverage_stress(df)
    assert stress
    stress_columns = ["Scenario", *pd.DataFrame(stress).columns.tolist()]
    assert uncovered_metrics("Operating Leverage Stress", stress_columns) == []


def test_table11_all_ten_criteria_and_total_have_guidance():
    expected = {
        "Recurring Revenue", "Long Runway", "Proven Management", "Franchise/Moat", "Strong Financials",
        "High ROIC", "Limited Competition", "Low Capital Expenditures", "Diversified Customer Base",
        "Strong Balance Sheet", "Total",
    }
    assert expected == set(BOOK_GUIDANCE["Table 1.1"]["metrics"])


def test_table12_current_display_columns_have_guidance():
    columns = [
        "Kỳ", "Nguồn", "TEV", "EBIT", "EBITDA", "Normalized earnings", "TEV/EBIT", "TEV/EBITDA",
        "TEV/Norm.E", "Pre-tax yield", "Total Debt", "Debt/EBITDA", "EBIT/Interest", "FCF",
        "FCF Yield EV", "FCF Yield Mkt", "CCC", "Market cap", "Giá", "FCF est./share", "Target", "MOS",
    ]
    assert uncovered_metrics("Table 1.2", columns) == []


def test_watchlist_cagr_and_inventory_columns_have_guidance():
    columns = [
        "Mã CP", "Doanh nghiệp", "Kỳ dữ liệu", "CAGR DT 5Y", "CAGR LN 5Y", "CAGR kỳ",
        "Kỳ", "Nguồn", "TEV", "EBIT", "EBITDA", "Normalized earnings", "TEV/EBIT", "TEV/EBITDA",
        "TEV/Norm.E", "Pre-tax yield", "Total Debt", "Debt/EBITDA", "EBIT/Interest", "FCF",
        "FCF Yield EV", "FCF Yield Mkt", "CCC", "Market cap", "Giá", "FCF est./share", "Target", "MOS",
    ]
    assert uncovered_metrics("Watchlist — Opportunity Inventory", columns) == []


def test_guidance_sources_are_explicitly_book_grounded_or_labeled_extension():
    for key, spec in BOOK_GUIDANCE.items():
        source = str(spec.get("source") or "")
        assert source
        assert "Chương" in source or "Trecapital extension" in source, key
        assert spec.get("purpose"), key
        assert spec.get("principles"), key


def test_streamlit_guidance_card_renders_without_exception():
    app = r'''
from modules.investment_checklist.ui.book_guidance import render_book_guidance
render_book_guidance("Working Capital / CCC Analyzer", ["Kỳ", "DSO", "DIO", "DPO", "CCC", "Operating WC", "Δ Operating WC", "ΔWC / Revenue", "Cash released/(absorbed)"])
'''
    at = AppTest.from_string(app, default_timeout=10).run()
    assert len(at.exception) == 0
    assert len(at.expander) == 1
    assert "Hướng dẫn phân tích từ sách" in at.expander[0].label
