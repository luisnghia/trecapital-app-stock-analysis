from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import pandas as pd


@dataclass
class ProviderResult:
    overview: pd.DataFrame
    annual: pd.DataFrame
    quarterly: pd.DataFrame
    raw_path: Path | None = None
    note: str = ""


class FinancialDataProvider(Protocol):
    def fetch(self, ticker: str) -> ProviderResult:
        """Return normalized Tổng quan doanh nghiệp dataframes for one ticker."""
        ...


MODULE1_OVERVIEW_COLUMNS = [
    "ticker", "company_name", "exchange", "industry", "sub_industry", "market_cap_bil",
    "shares_outstanding_mil", "current_price", "eps", "pe", "pb", "ps", "roe", "roa", "roic", "updated_at",
]

MODULE1_TIMESERIES_COLUMNS = [
    "ticker", "period_type", "period", "year", "quarter",
    "revenue_bil", "gross_revenue_bil", "gross_profit_bil", "operating_profit_bil", "core_operating_profit_bil", "net_profit_bil", "pretax_profit_bil",
    "financial_income_bil", "financial_expense_bil", "selling_expense_bil", "admin_expense_bil", "tax_expense_bil", "nopat_bil",
    "cfo_bil", "cfi_bil", "cff_bil", "capex_bil", "cash_dividend_bil", "cash_dividend_yield_pct", "year_end_price",
    "noncash_adjustments_bil", "operating_cash_before_wc_bil", "receivables_change_bil", "inventory_change_bil", "payables_change_bil",
    "prepaid_change_bil", "other_current_assets_change_bil", "interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil",
    "equity_issued_bil", "buyback_bil", "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "cash_and_short_investments_bil", "cash_and_short_investments_change_bil",
    "shares_outstanding_mil", "free_cash_flow_bil", "owner_earnings_bil", "maintenance_capex_bil", "eps_vnd", "oeps_vnd",
    "roe_pct", "roe_actual_pct", "roa_pct", "roic_pct", "roce_pct", "roic_operating_profit_pct", "roic_owner_earnings_pct", "roic_standard_pct", "roic_lilu_pct", "roic_fireant_pct", "gross_margin_pct", "net_margin_pct",
    "asset_turnover", "equity_multiplier", "roe_dupont_pct",
    "current_assets_bil", "current_liabilities_bil", "accounts_receivable_bil", "accounts_payable_bil", "working_capital_bil", "roic_working_capital_bil", "operating_working_capital_bil", "fixed_assets_bil",
    "cash_equivalents_bil", "short_term_investments_bil", "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil", "bonds_payable_bil", "lease_liabilities_bil", "finance_lease_liabilities_bil", "interest_bearing_debt_bil", "avg_interest_bearing_debt_bil", "capital_employed_bil", "avg_capital_employed_bil", "deployed_capital_bil", "avg_deployed_capital_bil",
    "inventory_bil", "investment_subsidiary_bil", "expansion_investment_bil", "total_investment_bil",
    "cost_of_goods_sold_bil", "total_assets_bil", "equity_bil", "avg_equity_bil", "avg_total_assets_bil", "liabilities_bil",
    "revenue_growth_yoy_pct", "net_profit_growth_yoy_pct", "eps_growth_yoy_pct", "total_assets_growth_yoy_pct", "equity_growth_yoy_pct",
    "core_operating_margin_pct", "ebitda_bil", "ebitda_margin_pct", "financial_income_to_revenue_pct", "roa_actual_pct",
    "current_ratio", "quick_ratio", "net_liquid_assets_bil", "equity_to_assets_pct", "liabilities_to_assets_pct", "liabilities_to_equity", "net_debt_bil", "net_debt_to_equity", "interest_coverage", "net_debt_to_ebitda",
    "receivables_turnover", "dso_days", "inventory_turnover", "dio_days", "payables_turnover", "dpo_days", "cash_conversion_cycle_days",
    "wacc_pct", "cfo_to_net_profit", "fcf_to_net_profit", "fcf_to_pretax", "nibt_to_fcf", "noncash_to_pretax", "wc_to_pretax", "capex_to_pretax",
]


def normalize_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return df with exactly the requested columns without fragmenting the DataFrame."""
    out = df.copy()
    missing = [col for col in columns if col not in out.columns]
    if missing:
        out = pd.concat([out, pd.DataFrame({col: [None] * len(out) for col in missing}, index=out.index)], axis=1)
    return out.reindex(columns=columns)
