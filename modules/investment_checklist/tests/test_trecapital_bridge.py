from dataclasses import dataclass

import pandas as pd

from modules.investment_checklist.trecapital_bridge import CurrentRepoDataProvider


@dataclass
class Company:
    ticker: str
    market_cap_bil: float
    current_price: float
    shares_outstanding_mil: float | None = None


@dataclass
class ValuationRange:
    weighted_vnd: float
    mos_to_weighted_pct: float


def df(ticker, op, ebitda, pretax, debt, net_debt, fcf):
    return pd.DataFrame([{
        "ticker": ticker, "period": "2026 TTM", "operating_profit_bil": op,
        "ebitda_bil": ebitda, "pretax_profit_bil": pretax,
        "interest_bearing_debt_bil": debt, "net_debt_bil": net_debt,
        "free_cash_flow_bil": fcf,
    }])


def test_fpt_bridge_module1_module2():
    x = CurrentRepoDataProvider(
        Company("FPT", 210000, 105000),
        df("FPT", 12000, 14500, 11500, 8000, -5000, 9000),
        ValuationRange(135000, 22.2222),
    ).get_inventory_source_data(None)
    assert x.tev == 205000 and x.ebit == 12000 and x.target_price == 135000 and round(x.mos, 4) == 0.2222


def test_vcb_bridge_does_not_fake_interest_expense():
    x = CurrentRepoDataProvider(Company("VCB", 600000, 65000), df("VCB", 50000, 52000, 48000, 100000, 85000, 42000)).get_inventory_source_data(None)
    assert x.interest_expense is None and x.total_debt == 100000


def test_hpg_bridge_cyclical_facts_without_parallel_roic():
    d = df("HPG", 18000, 26000, 16500, 70000, 50000, 10000)
    d["roic_standard_pct"] = 12.3
    x = CurrentRepoDataProvider(Company("HPG", 180000, 27000), d).get_inventory_source_data(None)
    assert x.tev == 230000 and x.normalized_earnings == 16500 and not hasattr(x, "roic")


def test_ebitda_is_derived_only_when_ebit_and_da_exist():
    d = df("DCM", 2871.0, None, 2879.0, 0.0, -7257.0, -4210.0)
    d["depreciation_bil"] = 420.0
    x = CurrentRepoDataProvider(Company("DCM", 16570.0, 31300.0), d).get_inventory_source_data(None)
    assert x.ebitda == 3291.0
    assert any("EBITDA" in note for note in x.source_notes)


def test_ebitda_stays_missing_if_da_is_not_in_source():
    d = df("DCM", 2871.0, None, 2879.0, 0.0, -7257.0, -4210.0)
    x = CurrentRepoDataProvider(Company("DCM", 16570.0, 31300.0), d).get_inventory_source_data(None)
    assert x.ebitda is None


def test_interest_uses_interest_specific_alias_not_total_financial_expense():
    d = df("AAA", 1000, 1200, 900, 300, 250, 600)
    d["financial_expense_bil"] = 500.0
    d["interest_paid_bil"] = -125.0
    x = CurrentRepoDataProvider(Company("AAA", 5000, 20000), d).get_inventory_source_data(None)
    assert x.interest_expense == 125.0


def test_missing_operating_profit_uses_trecapital_pretax_plus_interest_proxy_then_da_for_ebitda():
    d = df("DCM", None, None, 2581.0, 2582.0, -6149.0, -811.0)
    d["interest_paid_bil"] = -83.0
    d["depreciation_bil"] = 420.0
    x = CurrentRepoDataProvider(Company("DCM", 18000.0, 31300.0), d).get_inventory_source_data(None)
    assert x.ebit == 2664.0
    assert x.ebitda == 3084.0
    assert x.interest_expense == 83.0
    assert any("EBIT proxy" in note and "LNTT" in note for note in x.source_notes)
    assert any("EBITDA" in note and "Khấu hao" in note for note in x.source_notes)


def test_fcf_is_derived_from_trecapital_cfo_and_capex_and_estimate_is_per_share_baseline():
    d = pd.DataFrame([{
        "ticker": "AAA", "period": "2026 TTM",
        "pretax_profit_bil": 900.0,
        "cfo_bil": 1500.0,
        "capex_bil": 400.0,  # provider may store capex positive; bridge treats it as an outflow
        "free_cash_flow_bil": None,
        "shares_outstanding_mil": 500.0,
    }])
    x = CurrentRepoDataProvider(Company("AAA", 10000.0, 20000.0, 500.0), d).get_inventory_source_data(None)
    assert x.fcf_current == 1100.0
    assert x.fcf_estimate == 2200.0  # 1,100 tỷ / 500 triệu cp = 2,200 VND/cp
    assert any("FCF 2026 TTM = CFO - |Capex|" in note for note in x.source_notes)
    assert any("FCF estimate/share tự động" in note for note in x.source_notes)


def test_module2_valuation_callable_is_lazy_until_inventory_prefill():
    called = {"n": 0}

    def valuation():
        called["n"] += 1
        return ValuationRange(35000, 20.0)

    provider = CurrentRepoDataProvider(Company("HPG", 180000, 27000), df("HPG", 18000, 26000, 16500, 70000, 50000, 10000), valuation)
    assert called["n"] == 0
    x = provider.get_inventory_source_data(None)
    assert called["n"] == 1 and x.target_price == 35000 and x.mos == 0.2


def test_dcm_like_bad_overview_units_are_reconciled_from_trecapital_financials():
    # Reproduces the deployed pathology: overview price/market-cap/share count are grossly
    # inconsistent with DCM's own Trecapital financial series. The bridge must not propagate
    # 363,470,000 "tỷ đồng" into Table 1.2 or Module 2.
    d = df("DCM", 2871.0, None, 2581.0, 2582.0, -100.0, -811.0)
    d["depreciation_bil"] = 420.0
    d["interest_paid_bil"] = -83.0
    d["shares_outstanding_mil"] = 3664.0
    d["net_profit_bil"] = 2000.0
    d["eps_vnd"] = 3778.0  # implies about 529.4m shares
    d["year_end_price"] = 31300.0
    d["cash_dividend_bil"] = -1000.0

    seen = {}

    def valuation(safe_company, safe_annual):
        seen["price"] = safe_company.current_price
        seen["market_cap"] = safe_company.market_cap_bil
        seen["shares"] = safe_company.shares_outstanding_mil
        ttm = safe_annual.iloc[-1]
        seen["ttm_shares"] = float(ttm["shares_outstanding_mil"])
        return ValuationRange(40000.0, 21.75)

    x = CurrentRepoDataProvider(
        Company("DCM", 363_470_000.0, 99_200.0, 3664.0), d, valuation
    ).get_inventory_source_data(None)

    inferred_shares = 2000.0 * 1000.0 / 3778.0
    expected_cap = 31300.0 * inferred_shares / 1000.0
    assert abs(x.shares_outstanding_mil - inferred_shares) < 0.01
    assert x.market_price == 31300.0
    assert abs(x.market_cap - expected_cap) < 1.0
    assert x.market_cap < 20_000.0
    assert x.ebit == 2871.0
    assert x.ebitda == 3291.0
    assert x.interest_expense == 83.0
    assert x.fcf_estimate is not None
    assert abs(x.fcf_estimate - (-811.0 * 1000.0 / inferred_shares)) < 0.01
    assert x.dividend_per_share is not None and x.dividend_per_share > 1800
    assert x.target_price == 40000.0 and round(x.mos, 4) == 0.2175
    assert abs(seen["price"] - 31300.0) < 0.01
    assert abs(seen["market_cap"] - expected_cap) < 1.0
    assert abs(seen["shares"] - inferred_shares) < 0.01
    assert abs(seen["ttm_shares"] - inferred_shares) < 0.01
    assert "reconciled_internal_data" in x.source_module
    assert any("Vốn hóa Tổng quan" in note for note in x.source_notes)
    assert any("Giá Tổng quan" in note for note in x.source_notes)


def test_ttm_blank_ebit_and_ebitda_fall_back_to_latest_trecapital_period():
    d = pd.DataFrame([
        {
            "ticker": "AAA", "period": "2025", "operating_profit_bil": 900.0,
            "depreciation_bil": 100.0, "pretax_profit_bil": 800.0,
            "free_cash_flow_bil": 500.0,
        },
        {
            "ticker": "AAA", "period": "2026 TTM", "operating_profit_bil": None,
            "ebitda_bil": None, "pretax_profit_bil": 850.0, "free_cash_flow_bil": 520.0,
        },
    ])
    x = CurrentRepoDataProvider(Company("AAA", 5000.0, 20000.0), d).get_inventory_source_data(None)
    assert x.ebit == 900.0
    assert x.ebitda == 1000.0
    assert any("EBIT TTM trống" in note for note in x.source_notes)
    assert any("EBITDA TTM trống" in note for note in x.source_notes)
