import pandas as pd

from modules.investment_checklist.contracts import CompanyContext, InventorySourceData
from modules.investment_checklist.source_policy import SourcePolicyDataProvider


class Provider:
    def __init__(self, annual_df):
        self.annual_df = annual_df

    def get_inventory_source_data(self, company):
        return InventorySourceData(
            as_of_date="TTM",
            tev=12_000,
            ebit=1_200,
            ebitda=1_500,
            normalized_earnings=1_000,  # inner bridge raw pre-tax baseline
            total_debt=2_000,
            interest_expense=100,
            fcf_current=900,
            market_cap=11_000,
            market_price=20_000,
            target_price=25_000,
        )

    def get_inventory_proxy_history(self, years=10):
        return [
            {"period": "2025", "tev": 10_000, "ebit": 1_000, "ebitda": 1_200, "normalized_earnings": 950, "total_debt": 2_000, "interest_expense": 100, "fcf_current": 800, "market_cap": 9_000, "market_price": 18_000, "target_price": None},
            {"period": "TTM", "tev": 12_000, "ebit": 1_200, "ebitda": 1_500, "normalized_earnings": 1_000, "total_debt": 2_000, "interest_expense": 100, "fcf_current": 900, "market_cap": 11_000, "market_price": 20_000, "target_price": 25_000},
        ]


def test_old_annual_normalization_does_not_authorize_raw_ttm_for_cyclical():
    provider = Provider(pd.DataFrame([
        {"period": "2025", "pretax_profit_bil": 950, "normalized_earnings_bil": 800},
        {"period": "TTM", "pretax_profit_bil": 1_000, "normalized_earnings_bil": None},
    ]))
    wrapped = SourcePolicyDataProvider(provider, "cyclical")
    out = wrapped.get_inventory_source_data(CompanyContext("T:C", "C", "Cyclical", company_type="cyclical"))
    assert out.normalized_earnings is None

    hist = wrapped.get_inventory_proxy_history(10)
    by_period = {x["period"]: x for x in hist}
    assert by_period["2025"]["normalized_earnings"] == 800
    assert by_period["2025"]["tev_normalized_earnings"] == 12.5
    assert by_period["TTM"]["normalized_earnings"] is None
    assert by_period["TTM"]["tev_normalized_earnings"] is None


def test_matching_ttm_normalized_value_replaces_inner_raw_pretax_proxy():
    provider = Provider(pd.DataFrame([
        {"period": "2025", "pretax_profit_bil": 950, "normalized_earnings_bil": 800},
        {"period": "TTM", "pretax_profit_bil": 1_000, "normalized_earnings_bil": 875},
    ]))
    wrapped = SourcePolicyDataProvider(provider, "cyclical")
    out = wrapped.get_inventory_source_data(CompanyContext("T:C2", "C2", "Cyclical", company_type="cyclical"))
    assert out.normalized_earnings == 875
    assert any("cùng kỳ" in x.lower() for x in out.source_notes)

    hist = wrapped.get_inventory_proxy_history(10)
    by_period = {x["period"]: x for x in hist}
    assert by_period["TTM"]["normalized_earnings"] == 875
    assert by_period["TTM"]["tev_normalized_earnings"] == 12_000 / 875
