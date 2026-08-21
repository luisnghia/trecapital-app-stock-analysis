from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

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


def _df(rows):
    return pd.DataFrame(rows)


def test_balance_sheet_debt_does_not_double_count_current_portion_or_bonds():
    df = _df([
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            # Synthetic legacy direct zero must not override real debt components.
            "interest_bearing_debt_bil": 0,
            # Enriched short bucket already includes current portion.
            "short_term_debt_bil": 3566,
            "current_portion_long_term_debt_bil": 50,
            "long_term_debt_bil": 24,
            # Bond detail is assumed inside aggregate long bucket and must not be added again.
            "bonds_payable_bil": 500,
            "cash_equivalents_bil": 1000,
            "ebitda_bil": 3000,
            "ebit_bil": 2500,
            "interest_expense_bil": -100,
        }
    ])
    row = balance_sheet_leverage(df).rows[0]
    assert row["Total Debt"] == pytest.approx(3590)
    assert row["Net Debt"] == pytest.approx(2590)
    assert row["Debt/EBITDA"] == pytest.approx(3590 / 3000)
    assert row["EBIT/Interest"] == pytest.approx(25.0)


def test_missing_debt_remains_unknown_instead_of_zero():
    df = _df([{"period": "2025", "period_type": "Y", "year": 2025, "ebitda_bil": 100}])
    row = balance_sheet_leverage(df).rows[0]
    assert row["Total Debt"] is None
    assert row["Debt/EBITDA"] is None


def test_roic_preserves_trecapital_standard_and_labels_shearn_variants():
    df = _df([
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            "roic_pct": 12.3,
            "ebit_bil": 100,
            "pretax_profit_bil": 90,
            "income_tax_expense_bil": 18,
            "total_equity_bil": 500,
            "interest_bearing_debt_bil": 100,
            "cash_equivalents_bil": 50,
            "goodwill_bil": 50,
        }
    ])
    row = roic_quality(df).rows[0]
    assert row["ROIC Trecapital"] == pytest.approx(12.3)
    # NOPAT = 100 * (1 - 20%) = 80; standard/ex-cash IC = 500+100-50 = 550.
    assert row["ROIC Shearn – Ex Cash"] == pytest.approx(80 / 550 * 100)
    assert row["ROIC Shearn – Incl Cash"] == pytest.approx(80 / 600 * 100)
    assert row["ROIC Shearn – Ex Goodwill"] == pytest.approx(80 / 500 * 100)


def test_roic_uses_average_investment_base_on_later_periods():
    df = _df([
        {
            "period": "2024", "period_type": "Y", "year": 2024,
            "ebit_bil": 100, "pretax_profit_bil": 90, "income_tax_expense_bil": 18,
            "total_equity_bil": 500, "interest_bearing_debt_bil": 100, "cash_equivalents_bil": 50,
        },
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            "ebit_bil": 120, "pretax_profit_bil": 108, "income_tax_expense_bil": 21.6,
            "total_equity_bil": 600, "interest_bearing_debt_bil": 100, "cash_equivalents_bil": 50,
        },
    ])
    rows = roic_quality(df).rows
    assert rows[1]["Avg Invested Capital"] == pytest.approx((550 + 650) / 2)


def test_operating_leverage_matches_shearn_formula():
    df = _df([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 100, "ebit_bil": 10},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 110, "ebit_bil": 12},
    ])
    row = operating_leverage(df).rows[1]
    assert row["Revenue growth"] == pytest.approx(10.0)
    assert row["EBIT growth"] == pytest.approx(20.0)
    assert row["DOL"] == pytest.approx(2.0)


def test_operating_leverage_suppresses_near_zero_sales_change_and_loss_base():
    df = _df([
        {"period": "2023", "period_type": "Y", "year": 2023, "revenue_bil": 100, "ebit_bil": -10},
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 110, "ebit_bil": 10},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 110.5, "ebit_bil": 12},
    ])
    rows = operating_leverage(df).rows
    assert rows[1]["DOL"] is None  # prior EBIT is a loss
    assert rows[2]["DOL"] is None  # revenue move < 1%


def test_operating_leverage_stress_is_explicit_scenario_extension():
    df = _df([
        {"period": "2023", "period_type": "Y", "year": 2023, "revenue_bil": 100, "ebit_bil": 10},
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 110, "ebit_bil": 12},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 121, "ebit_bil": 14.4},
    ])
    stress = operating_leverage_stress(df)
    assert [r["Revenue shock"] for r in stress] == [-5.0, -10.0, -20.0]
    assert stress[0]["DOL used"] == pytest.approx(2.0)


def test_working_capital_uses_average_balances_and_cash_absorption_sign():
    df = _df([
        {
            "period": "2024", "period_type": "Y", "year": 2024,
            "revenue_bil": 1000, "gross_profit_bil": 400,
            "accounts_receivable_bil": 100, "inventory_bil": 200, "accounts_payable_bil": 150,
        },
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            "revenue_bil": 1100, "gross_profit_bil": 440,
            "accounts_receivable_bil": 120, "inventory_bil": 220, "accounts_payable_bil": 180,
        },
    ])
    row = working_capital(df).rows[1]
    assert row["DSO"] == pytest.approx(110 / 1100 * 365)
    assert row["DIO"] == pytest.approx(210 / 660 * 365)
    assert row["DPO"] == pytest.approx(165 / 660 * 365)
    assert row["CCC"] == pytest.approx(row["DIO"] + row["DSO"] - row["DPO"])
    assert row["Δ Operating WC"] == pytest.approx(10)
    assert row["Cash released/(absorbed)"] == pytest.approx(-10)


def test_direct_ccc_from_trecapital_has_priority_over_proxy():
    df = _df([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 1000, "gross_profit_bil": 400,
         "accounts_receivable_bil": 100, "inventory_bil": 200, "accounts_payable_bil": 150},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 1100, "gross_profit_bil": 440,
         "accounts_receivable_bil": 120, "inventory_bil": 220, "accounts_payable_bil": 180, "ccc_days": 42},
    ])
    assert working_capital(df).rows[1]["CCC"] == 42


def test_maintenance_capex_context_does_not_claim_depreciation_is_actual_maintenance_capex():
    df = _df([
        {
            "period": "2025", "period_type": "Y", "year": 2025,
            "revenue_bil": 1000, "capex_bil": -100, "depreciation_bil": 80, "cfo_bil": 200,
        }
    ])
    result = maintenance_capex_context(df)
    row = result.rows[0]
    assert row["Capex"] == 100
    assert row["Capex / Revenue"] == pytest.approx(10.0)
    assert row["Capex / D&A"] == pytest.approx(1.25)
    assert row["FCF"] == pytest.approx(100)
    assert any("rough approximation" in note for note in result.notes)


def test_buyback_analyzer_uses_prior_share_count_for_eps_without_share_change():
    df = _df([
        {"period": "2024", "period_type": "Y", "year": 2024, "shares_outstanding_mil": 100, "net_profit_bil": 800},
        {"period": "2025", "period_type": "Y", "year": 2025, "shares_outstanding_mil": 90, "net_profit_bil": 900,
         "shares_repurchased_mil": 12, "shares_issued_mil": 2},
    ])
    row = buyback_dilution(df).rows[1]
    assert row["Net share reduction"] == pytest.approx(10)
    assert row["Net buyback after dilution"] == pytest.approx(10)
    assert row["EPS actual"] == pytest.approx(10000)
    assert row["EPS without share-count change"] == pytest.approx(9000)
    assert row["EPS uplift from share-count change"] == pytest.approx((10000 / 9000 - 1) * 100)


def test_buyback_missing_gross_or_esop_stays_unknown_not_zero():
    df = _df([{"period": "2025", "period_type": "Y", "year": 2025, "shares_outstanding_mil": 100}])
    row = buyback_dilution(df).rows[0]
    assert row["Gross buyback shares"] is None
    assert row["Shares issued / ESOP / options"] is None
    assert row["Net buyback after dilution"] is None


def test_operating_driver_flags_eps_growth_against_declining_driver():
    df = _df([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 100, "eps_vnd": 1000},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 90, "eps_vnd": 1100},
    ])
    row = operating_driver_eps(df).rows[1]
    assert row["Revenue growth"] == pytest.approx(-10.0)
    assert row["EPS growth"] == pytest.approx(10.0)
    assert "EPS ↑" in row["Signal"]


def test_operating_driver_can_derive_eps_from_net_income_and_shares():
    df = _df([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 100, "net_profit_bil": 100, "shares_outstanding_mil": 100},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 110, "net_profit_bil": 121, "shares_outstanding_mil": 100},
    ])
    rows = operating_driver_eps(df).rows
    assert rows[0]["EPS"] == pytest.approx(1000)
    assert rows[1]["EPS"] == pytest.approx(1210)


def test_accounting_quality_is_evidence_only_and_missing_reserve_remains_blank():
    df = _df([
        {"period": "2025", "period_type": "Y", "year": 2025, "net_profit_bil": 100, "cfo_bil": 110,
         "revenue_bil": 1000, "accounts_receivable_bil": 100, "inventory_bil": 200},
    ])
    result = accounting_quality_proxy(df)
    row = result.rows[0]
    assert row["CFO / Net income"] == pytest.approx(1.1)
    assert row["Provision"] is None
    assert row["Actual charge-off/write-off"] is None
    assert any("Không tính Beneish lần thứ hai" in note for note in result.notes)


def test_quantitative_engine_has_no_parallel_network_client():
    source = Path("modules/investment_checklist/quantitative_tools.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "import httpx" not in lowered
    assert "import requests" not in lowered
    assert "urllib.request" not in lowered
