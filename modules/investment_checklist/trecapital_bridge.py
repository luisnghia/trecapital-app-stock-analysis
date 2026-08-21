from __future__ import annotations
from typing import Optional, Any
import pandas as pd
from .contracts import InventorySourceData


def _latest_row(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    if "period" in df.columns:
        ttm = df[df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        if not ttm.empty:
            return ttm.iloc[-1].to_dict()
    return df.iloc[-1].to_dict()


def _number(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        try:
            if value is not None and not pd.isna(value):
                return float(value)
        except Exception:
            continue
    return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


class CurrentRepoDataProvider:
    """Consume normalized Module 1 facts and Module 2 valuation; no parallel financial engine.

    The bridge deliberately does not invent missing financial facts. It resolves canonical aliases
    already present in the normalized data layer. EBITDA may be derived only from EBIT + D&A when
    both source components exist. ``valuation_range`` may be a callable so expensive valuation is
    computed only when Table 1.2 is actually opened, not on every Q01-Q59 selection rerun.
    """

    def __init__(self, company, annual_df: pd.DataFrame, valuation_range=None):
        self.company = company
        self.annual_df = annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame()
        self.valuation_range = valuation_range

    def _resolve_valuation_range(self):
        return self.valuation_range() if callable(self.valuation_range) else self.valuation_range

    def get_inventory_source_data(self, company_context):
        latest = _latest_row(self.annual_df)
        market_cap = _safe_float(getattr(self.company, "market_cap_bil", None))
        price = _safe_float(getattr(self.company, "current_price", None))
        net_debt = _number(latest, "net_debt_bil")
        tev = None if market_cap is None else market_cap + (net_debt or 0.0)

        ebit = _number(latest, "ebit_bil", "operating_profit_bil", "core_operating_profit_bil")
        ebitda = _number(latest, "ebitda_bil")
        depreciation_amortization = _number(
            latest,
            "depreciation_bil",
            "depreciation_amortization_bil",
            "depreciation_and_amortization_bil",
            "da_bil",
        )
        derived_ebitda = False
        if ebitda is None and ebit is not None and depreciation_amortization is not None:
            ebitda = ebit + abs(depreciation_amortization)
            derived_ebitda = True

        pretax = _number(latest, "pretax_profit_bil")
        debt = _number(latest, "interest_bearing_debt_bil")
        if debt is None:
            parts = [
                _number(latest, "short_term_debt_bil"),
                _number(latest, "current_portion_long_term_debt_bil"),
                _number(latest, "long_term_debt_bil"),
                _number(latest, "bonds_payable_bil"),
                _number(latest, "lease_liabilities_bil", "finance_lease_liabilities_bil"),
            ]
            if any(v is not None for v in parts):
                debt = sum(v or 0.0 for v in parts)

        # Do not use total financial expense as interest expense: it may include FX and other items.
        interest_expense = _number(
            latest,
            "interest_expense_bil",
            "interest_paid_bil",
            "borrowing_cost_bil",
        )
        fcf = _number(latest, "free_cash_flow_bil")
        dps = _number(
            latest,
            "dividend_per_share",
            "cash_dividend_per_share",
            "cash_dividend_per_share_vnd",
            "dps_vnd",
        )
        fcf_estimate = _number(latest, "fcf_estimate_bil", "normalized_fcf_bil")
        as_of = str(latest.get("period") or latest.get("year") or pd.Timestamp.today().date())

        target_price = None
        mos = None
        source_module = "module1_normalized_cache"
        if derived_ebitda:
            source_module += "+derived_ebitda_from_ebit_da"
        valuation_range = self._resolve_valuation_range()
        if valuation_range is not None:
            target_price = _safe_float(getattr(valuation_range, "weighted_vnd", None))
            mos_pct = _safe_float(getattr(valuation_range, "mos_to_weighted_pct", None))
            mos = None if mos_pct is None else mos_pct / 100.0
            source_module += "+module2_valuation"

        return InventorySourceData(
            as_of_date=as_of,
            tev=tev,
            ebit=ebit,
            ebitda=ebitda,
            normalized_earnings=pretax,
            total_debt=debt,
            interest_expense=interest_expense,
            fcf_current=fcf,
            market_cap=market_cap,
            dividend_per_share=dps,
            market_price=price,
            fcf_estimate=fcf_estimate,
            target_price=target_price,
            mos=mos,
            source_module=source_module,
        )
