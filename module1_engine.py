from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import re
import warnings

import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)


@dataclass
class CompanyOverview:
    ticker: str
    company_name: str
    exchange: str
    industry: str
    sub_industry: str
    market_cap_bil: Optional[float]
    shares_outstanding_mil: Optional[float]
    current_price: Optional[float]
    eps: Optional[float]
    pe: Optional[float]
    pb: Optional[float]
    ps: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    roic: Optional[float]
    updated_at: str = ""


def _to_float(value: Any) -> Optional[float]:
    """Convert common spreadsheet/CSV values to float safely."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "nan", "None", "NaN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None




def _avg_current_and_previous(df: pd.DataFrame, value_col: str) -> pd.Series:
    """Average current and previous period value within annual/quarterly groups.

    First period falls back to ending/current-period value. This is safer than dividing by ending
    balance only when computing ROE/ROIC trends.
    """
    if value_col not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    if "period_type" in df.columns:
        sort_cols = [c for c in ["period_type", "year", "quarter"] if c in df.columns]
        tmp = df[sort_cols + [value_col]].copy().sort_values(sort_cols)
        prev = tmp.groupby("period_type", dropna=False)[value_col].shift(1)
        avg = (tmp[value_col] + prev) / 2
        avg = avg.fillna(tmp[value_col])
        return avg.reindex(df.index)
    prev = df[value_col].shift(1)
    return ((df[value_col] + prev) / 2).fillna(df[value_col])


def _safe_effective_tax_rate(df: pd.DataFrame) -> pd.Series:
    if {"tax_expense_bil", "pretax_profit_bil"}.issubset(df.columns):
        rate = pd.to_numeric(df["tax_expense_bil"], errors="coerce") / pd.to_numeric(df["pretax_profit_bil"], errors="coerce").replace({0: pd.NA})
        return rate.clip(lower=0, upper=0.5).fillna(0.20)
    return pd.Series(0.20, index=df.index, dtype="float64")


def _capex_signed_outflow(series: pd.Series) -> pd.Series:
    """Normalize capital expenditure as a cash-flow outflow.

    Some providers store capex as a negative CFS line, others store it as a
    positive expenditure amount.  FCF/OE formulas need a signed outflow, so this
    helper returns `-abs(capex)` while preserving NaN values.
    """
    capex = pd.to_numeric(series, errors="coerce")
    return -capex.abs()


def _interest_bearing_debt_series(df: pd.DataFrame) -> pd.Series:
    """Gross interest-bearing debt used consistently for net debt/WACC."""
    idx = df.index
    existing = pd.to_numeric(df.get("interest_bearing_debt_bil", pd.Series(float("nan"), index=idx)), errors="coerce")
    debt_cols = [
        "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil",
        "bonds_payable_bil", "lease_liabilities_bil", "finance_lease_liabilities_bil",
    ]
    component = pd.Series(0.0, index=idx)
    has_component = False
    for col in debt_cols:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").fillna(0)
            component = component + vals
            has_component = has_component or bool(vals.abs().sum() > 1e-9)
    if has_component:
        return existing.where(existing.notna() & (existing >= 0), component).fillna(0.0)
    return existing.fillna(0.0)


def _per_share_from_bil(value_bil: Optional[float], shares_mil: Optional[float]) -> Optional[float]:
    """Convert a VND-denominated value in billion VND to VND/share.

    1 tỷ đồng / 1 triệu cổ phiếu = 1.000 đồng/cp.  This helper prevents
    MOS calculations from falling back to a stale overview EPS when the latest
    TTM row lacks per-share fields.
    """
    value = _to_float(value_bil)
    shares = _to_float(shares_mil)
    if value is None or shares is None or abs(shares) < 1e-12:
        return None
    return value * 1000.0 / shares


def _fmt_num(value: Optional[float], suffix: str = "", digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:,.{digits}f}{suffix}"


def _fmt_money_bil(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:,.0f} tỷ đồng"


def _fmt_ratio(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:,.1f} lần"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:,.1f}%"


def load_overview_from_csv(csv_path: str | Path, ticker: str) -> CompanyOverview:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    required = {
        "ticker", "company_name", "exchange", "industry", "sub_industry",
        "market_cap_bil", "shares_outstanding_mil", "current_price",
        "eps", "pe", "pb", "ps", "roe", "roa", "roic"
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"CSV thiếu các cột bắt buộc: {', '.join(sorted(missing))}")

    ticker = ticker.strip().upper()
    found = df[df["ticker"].astype(str).str.upper() == ticker]
    if found.empty:
        raise LookupError(f"Không tìm thấy mã {ticker} trong file dữ liệu tổng quan.")
    row = found.iloc[0].to_dict()
    return CompanyOverview(
        ticker=str(row.get("ticker", "")).upper(),
        company_name=str(row.get("company_name", "")),
        exchange=str(row.get("exchange", "")),
        industry=str(row.get("industry", "")),
        sub_industry=str(row.get("sub_industry", "")),
        market_cap_bil=_to_float(row.get("market_cap_bil")),
        shares_outstanding_mil=_to_float(row.get("shares_outstanding_mil")),
        current_price=_to_float(row.get("current_price")),
        eps=_to_float(row.get("eps")),
        pe=_to_float(row.get("pe")),
        pb=_to_float(row.get("pb")),
        ps=_to_float(row.get("ps")),
        roe=_to_float(row.get("roe")),
        roa=_to_float(row.get("roa")),
        roic=_to_float(row.get("roic")),
        updated_at=str(row.get("updated_at", "")),
    )


def _year_sort_key(period: Any) -> Tuple[int, str]:
    """Return a clean year sort key. Prevent chart labels like 2024.0."""
    text = str(period).strip()
    m = re.search(r"(19\d{2}|20\d{2}|21\d{2}|22\d{2})", text)
    if m and "q" not in text.lower():
        y = int(m.group(1))
        return y, str(y)
    try:
        y = int(float(text))
        if 1900 <= y <= 2200:
            return y, str(y)
    except Exception:
        pass
    return 9999, text


def _quarter_sort_key(period: Any) -> Tuple[int, int, str]:
    """Return a clean quarter sort key. Supports Q1/2026 and 2026Q1."""
    text = str(period).strip().upper().replace(" ", "")
    m = re.match(r"Q([1-4])[/\-.](\d{4})", text)
    if m:
        return int(m.group(2)), int(m.group(1)), f"Q{int(m.group(1))}/{int(m.group(2))}"
    m = re.match(r"(\d{4})[/\-.]?Q([1-4])", text)
    if m:
        return int(m.group(1)), int(m.group(2)), f"Q{int(m.group(2))}/{int(m.group(1))}"
    y, label = _year_sort_key(text)
    return y, 0, label


def load_timeseries_from_csv(csv_path: str | Path, ticker: str, period_type: str, limit: int) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if "ticker" not in df.columns or "period" not in df.columns:
        raise ValueError(f"{path.name} thiếu cột ticker hoặc period.")
    ticker = ticker.upper().strip()
    df = df[df["ticker"].astype(str).str.upper() == ticker].copy()
    if df.empty:
        return df
    if period_type and "period_type" in df.columns:
        df = df[df["period_type"].astype(str).str.upper() == period_type.upper()].copy()
    if df.empty:
        return df

    if period_type.upper() == "Q":
        parsed = df["period"].map(_quarter_sort_key)
        df["_year_sort"] = parsed.map(lambda x: x[0])
        df["_quarter_sort"] = parsed.map(lambda x: x[1])
        df["period"] = parsed.map(lambda x: x[2])
        # De-duplicate quarters after normalizing labels. Keep the last non-empty row if a file has duplicates.
        df = df.sort_values(["_year_sort", "_quarter_sort"]).drop_duplicates(["_year_sort", "_quarter_sort"], keep="last")
        df = df.tail(limit).sort_values(["_year_sort", "_quarter_sort"]).drop(columns=["_year_sort", "_quarter_sort"])
    else:
        parsed = df["period"].map(_year_sort_key)
        df["_year_sort"] = parsed.map(lambda x: x[0])
        df["period"] = parsed.map(lambda x: x[1])
        df["year"] = df["_year_sort"]
        # De-duplicate years after normalizing labels. This fixes repeated-year charts.
        df = df.sort_values("_year_sort").drop_duplicates("_year_sort", keep="last")
        df = df.tail(limit).sort_values("_year_sort").drop(columns=["_year_sort"])
    return df.reset_index(drop=True)


def ensure_derived_metrics(df: pd.DataFrame, maintenance_capex_window: int = 5) -> pd.DataFrame:
    """Fill missing FCF / Owner Earnings / DuPont fields when source file has enough raw data."""
    if df.empty:
        return df
    df = df.copy()
    for col in [
        "revenue_bil", "gross_profit_bil", "operating_profit_bil", "core_operating_profit_bil", "net_profit_bil", "pretax_profit_bil",
        "financial_income_bil", "financial_expense_bil", "selling_expense_bil", "admin_expense_bil", "tax_expense_bil", "nopat_bil",
        "cfo_bil", "cfi_bil", "cff_bil", "capex_bil",
        "depreciation_bil", "noncash_adjustments_bil", "operating_cash_before_wc_bil", "working_capital_change_bil",
        "receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil",
        "interest_paid_bil", "interest_expense_bil", "borrowing_cost_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil",
        "equity_issued_bil", "buyback_bil", "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "cash_and_short_investments_bil", "cash_and_short_investments_change_bil",
        "free_cash_flow_bil", "owner_earnings_bil", "maintenance_capex_bil", "current_assets_bil", "current_liabilities_bil", "accounts_receivable_bil", "accounts_payable_bil",
        "working_capital_bil", "roic_working_capital_bil", "operating_working_capital_bil", "fixed_assets_bil", "cash_equivalents_bil", "short_term_investments_bil",
        "capital_employed_bil", "avg_capital_employed_bil", "deployed_capital_bil", "avg_deployed_capital_bil",
        "inventory_bil", "inventory_change_bil", "investment_subsidiary_bil",
        "expansion_investment_bil", "total_investment_bil", "cost_of_goods_sold_bil", "total_assets_bil", "avg_total_assets_bil", "liabilities_bil", "equity_bil", "avg_equity_bil",
        "shares_outstanding_mil", "year_end_price", "market_cap_bil", "beta", "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil", "bonds_payable_bil", "lease_liabilities_bil", "finance_lease_liabilities_bil", "interest_bearing_debt_bil", "avg_interest_bearing_debt_bil", "cost_of_debt_pct", "tax_rate_pct", "cost_of_equity_pct", "wacc_pct",
        "gross_margin_pct", "core_operating_margin_pct", "net_margin_pct", "ebitda_bil", "ebitda_margin_pct", "financial_income_to_revenue_pct", "asset_turnover", "equity_multiplier", "roe_dupont_pct", "roe_actual_pct", "roa_actual_pct", "cash_dividend_yield_pct",
        "revenue_growth_yoy_pct", "net_profit_growth_yoy_pct", "eps_growth_yoy_pct", "total_assets_growth_yoy_pct", "equity_growth_yoy_pct",
        "current_ratio", "quick_ratio", "net_liquid_assets_bil", "equity_to_assets_pct", "liabilities_to_assets_pct", "liabilities_to_equity", "net_debt_bil", "net_debt_to_equity", "interest_coverage", "net_debt_to_ebitda",
        "receivables_turnover", "dso_days", "inventory_turnover", "dio_days", "payables_turnover", "dpo_days", "cash_conversion_cycle_days",
        "roic_pct", "roce_pct", "roic_operating_profit_pct", "roic_owner_earnings_pct", "roic_standard_pct", "roic_lilu_pct", "roic_fireant_pct", "wacc_pct", "cfo_to_net_profit", "fcf_to_net_profit", "fcf_to_pretax", "nibt_to_fcf", "noncash_to_pretax", "wc_to_pretax", "capex_to_pretax",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if {"cfo_bil", "capex_bil"}.issubset(df.columns):
        if "free_cash_flow_bil" not in df.columns:
            df["free_cash_flow_bil"] = pd.NA
        capex_signed_outflow = _capex_signed_outflow(df["capex_bil"])
        # FCF = CFO - capex outflow.  Equivalent to CFO + capex when capex is already negative.
        df["free_cash_flow_bil"] = df["free_cash_flow_bil"].fillna(df["cfo_bil"] + capex_signed_outflow)

    # FCF-Years / FCF-Quarters logic: chuẩn hóa các dòng phân tích sinh tiền và dụng tiền.
    # V23.62: Change in WC chỉ gồm các khoản vận hành; lãi vay, thuế và dòng khác là bridge CFO riêng,
    # không gộp vào vốn lưu động để tránh sai bản chất phân tích.
    wc_parts = [c for c in ["receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil"] if c in df.columns]
    if "working_capital_change_bil" not in df.columns:
        df["working_capital_change_bil"] = pd.NA
    if wc_parts:
        df["working_capital_change_bil"] = df["working_capital_change_bil"].fillna(df[wc_parts].sum(axis=1, min_count=1))
    if "noncash_adjustments_bil" not in df.columns:
        df["noncash_adjustments_bil"] = pd.NA
    if "operating_cash_before_wc_bil" in df.columns and "pretax_profit_bil" in df.columns:
        df["noncash_adjustments_bil"] = df["noncash_adjustments_bil"].fillna(df["operating_cash_before_wc_bil"] - df["pretax_profit_bil"])
    if "depreciation_bil" in df.columns:
        df["noncash_adjustments_bil"] = df["noncash_adjustments_bil"].fillna(df["depreciation_bil"])
    if "operating_cash_before_wc_bil" not in df.columns:
        df["operating_cash_before_wc_bil"] = pd.NA
    if {"pretax_profit_bil", "noncash_adjustments_bil"}.issubset(df.columns):
        df["operating_cash_before_wc_bil"] = df["operating_cash_before_wc_bil"].fillna(df["pretax_profit_bil"] + df["noncash_adjustments_bil"])
    if {"cfo_bil", "pretax_profit_bil", "noncash_adjustments_bil"}.issubset(df.columns):
        non_wc_bridge_cols = [c for c in ["interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil"] if c in df.columns]
        has_non_wc_bridge = False
        if non_wc_bridge_cols:
            has_non_wc_bridge = bool(df[non_wc_bridge_cols].apply(pd.to_numeric, errors="coerce").notna().any(axis=None))
        # Chỉ dùng residual CFO làm proxy WC khi không có các dòng bridge lãi vay/thuế/khác riêng.
        if not has_non_wc_bridge:
            df["working_capital_change_bil"] = df["working_capital_change_bil"].fillna(df["cfo_bil"] - df["pretax_profit_bil"] - df["noncash_adjustments_bil"])
    if {"debt_raised_bil", "debt_repaid_bil"}.issubset(df.columns):
        if "net_debt_cashflow_bil" not in df.columns:
            df["net_debt_cashflow_bil"] = pd.NA
        df["net_debt_cashflow_bil"] = df["net_debt_cashflow_bil"].fillna(df["debt_raised_bil"] + df["debt_repaid_bil"])
    if {"cash_equivalents_bil", "short_term_investments_bil"}.issubset(df.columns):
        if "cash_and_short_investments_bil" not in df.columns:
            df["cash_and_short_investments_bil"] = pd.NA
        df["cash_and_short_investments_bil"] = df["cash_and_short_investments_bil"].fillna(df["cash_equivalents_bil"] + df["short_term_investments_bil"])

    # Theo thống nhất V19: bảng FCF chỉ dùng tăng/giảm trong kỳ, không hiển thị số dư cuối kỳ.
    if "cash_and_short_investments_bil" in df.columns:
        if "cash_and_short_investments_change_bil" not in df.columns:
            df["cash_and_short_investments_change_bil"] = pd.NA
        sort_cols = [c for c in ["period_type", "year", "quarter"] if c in df.columns]
        if sort_cols:
            tmp = df.sort_values(sort_cols)
            if "period_type" in tmp.columns:
                change = tmp.groupby("period_type")["cash_and_short_investments_bil"].diff()
            else:
                change = tmp["cash_and_short_investments_bil"].diff()
            df.loc[tmp.index, "cash_and_short_investments_change_bil"] = df.loc[tmp.index, "cash_and_short_investments_change_bil"].fillna(change)
        else:
            df["cash_and_short_investments_change_bil"] = df["cash_and_short_investments_change_bil"].fillna(df["cash_and_short_investments_bil"].diff())

    # ROIC V14: tách ROIC chuẩn và ROIC Li Lu/Deployed.
    # Lỗi V13: dùng lợi nhuận HĐKD có cả doanh thu tài chính trong khi mẫu số loại tiền/đầu tư tài chính,
    # làm các DN nhiều tiền như DGC cho ROIC quá cao.
    if {"gross_profit_bil", "selling_expense_bil", "admin_expense_bil"}.issubset(df.columns):
        if "core_operating_profit_bil" not in df.columns:
            df["core_operating_profit_bil"] = pd.NA
        core = df["gross_profit_bil"] - df["selling_expense_bil"].abs() - df["admin_expense_bil"].abs()
        df["core_operating_profit_bil"] = df["core_operating_profit_bil"].fillna(core)
    elif {"operating_profit_bil", "financial_income_bil", "financial_expense_bil"}.issubset(df.columns):
        if "core_operating_profit_bil" not in df.columns:
            df["core_operating_profit_bil"] = pd.NA
        core = df["operating_profit_bil"] - df["financial_income_bil"].fillna(0) + df["financial_expense_bil"].fillna(0)
        df["core_operating_profit_bil"] = df["core_operating_profit_bil"].fillna(core)
    elif "operating_profit_bil" in df.columns:
        if "core_operating_profit_bil" not in df.columns:
            df["core_operating_profit_bil"] = pd.NA
        df["core_operating_profit_bil"] = df["core_operating_profit_bil"].fillna(df["operating_profit_bil"])

    if "nopat_bil" not in df.columns:
        df["nopat_bil"] = pd.NA
    if "core_operating_profit_bil" in df.columns:
        tax_rate = _safe_effective_tax_rate(df)
        df["nopat_bil"] = df["nopat_bil"].fillna(df["core_operating_profit_bil"] * (1 - tax_rate))

    if {"current_assets_bil", "current_liabilities_bil"}.issubset(df.columns):
        if "working_capital_bil" not in df.columns:
            df["working_capital_bil"] = pd.NA
        df["working_capital_bil"] = df["working_capital_bil"].fillna(df["current_assets_bil"] - df["current_liabilities_bil"])
        cash = df["cash_equivalents_bil"] if "cash_equivalents_bil" in df.columns else 0
        sti = df["short_term_investments_bil"] if "short_term_investments_bil" in df.columns else 0
        current_debt = pd.Series(0.0, index=df.index)
        for debt_col in ["short_term_debt_bil", "current_portion_long_term_debt_bil"]:
            if debt_col in df.columns:
                current_debt = current_debt + pd.to_numeric(df[debt_col], errors="coerce").fillna(0).abs()
        # Operating WC follows the source definition: current operational assets minus
        # current operational liabilities, excluding cash, investments and debt.
        operating_current_liabilities = (df["current_liabilities_bil"] - current_debt).clip(lower=0)
        if "operating_working_capital_bil" not in df.columns:
            df["operating_working_capital_bil"] = pd.NA
        df["operating_working_capital_bil"] = df["operating_working_capital_bil"].fillna(
            df["current_assets_bil"] - cash - sti - operating_current_liabilities
        )
    if {"total_assets_bil", "current_liabilities_bil"}.issubset(df.columns):
        if "capital_employed_bil" not in df.columns:
            df["capital_employed_bil"] = pd.NA
        df["capital_employed_bil"] = df["capital_employed_bil"].fillna(df["total_assets_bil"] - df["current_liabilities_bil"])
        if "avg_capital_employed_bil" not in df.columns:
            df["avg_capital_employed_bil"] = pd.NA
        df["avg_capital_employed_bil"] = df["avg_capital_employed_bil"].fillna(_avg_current_and_previous(df, "capital_employed_bil"))

    # ROCE source formula: EBIT / Capital Employed. Use core operating profit as EBIT proxy
    # when the normalized data has not supplied a separate EBIT field.
    if {"core_operating_profit_bil", "capital_employed_bil"}.issubset(df.columns):
        if "roce_pct" not in df.columns:
            df["roce_pct"] = pd.NA
        df["roce_pct"] = df["roce_pct"].fillna(
            df["core_operating_profit_bil"] / df["capital_employed_bil"].replace({0: pd.NA}) * 100
        ).where(df["capital_employed_bil"] > 0)

    # MOS_LILU corrected logic for Li Lu-style deployed capital.
    # V15 copied the sheet too literally: average current assets - average AP, but then subtracted
    # ending cash/short-term investments and added ending fixed assets. For companies whose cash or
    # short-term investments change sharply (for example SCS), this asymmetric denominator can be too
    # small and push ROIC to an unrealistic level.
    # V16 computes ending deployed capital first, then averages deployed capital across periods:
    # Deployed Capital = Current Assets - Cash - Short-term Investments - Accounts Payable + Fixed Assets.
    # Average Deployed Capital = (Deployed Capital current + previous) / 2.
    if {"current_assets_bil", "fixed_assets_bil"}.issubset(df.columns):
        cash = df["cash_equivalents_bil"] if "cash_equivalents_bil" in df.columns else 0
        sti = df["short_term_investments_bil"] if "short_term_investments_bil" in df.columns else 0
        if "current_liabilities_bil" in df.columns:
            current_debt = pd.Series(0.0, index=df.index)
            for debt_col in ["short_term_debt_bil", "current_portion_long_term_debt_bil"]:
                if debt_col in df.columns:
                    current_debt = current_debt + pd.to_numeric(df[debt_col], errors="coerce").fillna(0).abs()
            # Li Lu-style deployed capital uses operating working capital, not debt-financed WC.
            op_current_liab = (df["current_liabilities_bil"] - current_debt).clip(lower=0)
        else:
            op_current_liab = df["accounts_payable_bil"] if "accounts_payable_bil" in df.columns else 0
        operating_wc = df["current_assets_bil"] - cash - sti - op_current_liab
        if "roic_working_capital_bil" not in df.columns:
            df["roic_working_capital_bil"] = pd.NA
        # Override older cache values because the formula definition changed in V16/V23.66.
        df["roic_working_capital_bil"] = operating_wc
        deployed_current = operating_wc + df["fixed_assets_bil"]
        if "deployed_capital_bil" not in df.columns:
            df["deployed_capital_bil"] = pd.NA
        df["deployed_capital_bil"] = deployed_current
        if "avg_deployed_capital_bil" not in df.columns:
            df["avg_deployed_capital_bil"] = pd.NA
        df["avg_deployed_capital_bil"] = _avg_current_and_previous(df, "deployed_capital_bil")
    elif {"current_assets_bil", "accounts_payable_bil"}.issubset(df.columns):
        if "roic_working_capital_bil" not in df.columns:
            df["roic_working_capital_bil"] = pd.NA
        df["roic_working_capital_bil"] = df["current_assets_bil"] - df["accounts_payable_bil"]

    if {"nopat_bil", "avg_capital_employed_bil"}.issubset(df.columns):
        roic_std = (df["nopat_bil"] / df["avg_capital_employed_bil"].replace({0: pd.NA}) * 100).where(df["avg_capital_employed_bil"] > 0)
        if "roic_standard_pct" not in df.columns:
            df["roic_standard_pct"] = pd.NA
        df["roic_standard_pct"] = df["roic_standard_pct"].fillna(roic_std)
    if {"core_operating_profit_bil", "avg_deployed_capital_bil"}.issubset(df.columns):
        roic_op = (df["core_operating_profit_bil"] / df["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(df["avg_deployed_capital_bil"] > 0)
        if "roic_operating_profit_pct" not in df.columns:
            df["roic_operating_profit_pct"] = pd.NA
        df["roic_operating_profit_pct"] = df["roic_operating_profit_pct"].fillna(roic_op)
        if "roic_lilu_pct" not in df.columns:
            df["roic_lilu_pct"] = pd.NA
        df["roic_lilu_pct"] = df["roic_operating_profit_pct"].combine_first(df["roic_lilu_pct"])
    if {"owner_earnings_bil", "avg_deployed_capital_bil"}.issubset(df.columns):
        roic_oe = (df["owner_earnings_bil"] / df["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(df["avg_deployed_capital_bil"] > 0)
        if "roic_owner_earnings_pct" not in df.columns:
            df["roic_owner_earnings_pct"] = pd.NA
        df["roic_owner_earnings_pct"] = df["roic_owner_earnings_pct"].fillna(roic_oe)
    if "roic_pct" not in df.columns:
        df["roic_pct"] = pd.NA
    if "roic_standard_pct" in df.columns:
        df["roic_pct"] = df["roic_pct"].fillna(df["roic_standard_pct"])
    if "roic_fireant_pct" in df.columns:
        df["roic_pct"] = df["roic_pct"].fillna(df["roic_fireant_pct"])

    if "expansion_investment_bil" not in df.columns and "capex_bil" in df.columns:
        df["expansion_investment_bil"] = _capex_signed_outflow(df["capex_bil"])
    if "total_investment_bil" not in df.columns:
        df["total_investment_bil"] = pd.NA
    invest_parts = [c for c in ["expansion_investment_bil", "inventory_change_bil", "investment_subsidiary_bil"] if c in df.columns]
    if invest_parts:
        df["total_investment_bil"] = df["total_investment_bil"].fillna(df[invest_parts].sum(axis=1, min_count=1))

    if {"net_profit_bil", "equity_bil"}.issubset(df.columns):
        if "avg_equity_bil" not in df.columns:
            df["avg_equity_bil"] = pd.NA
        df["avg_equity_bil"] = df["avg_equity_bil"].fillna(_avg_current_and_previous(df, "equity_bil"))
        if "roe_actual_pct" not in df.columns:
            df["roe_actual_pct"] = pd.NA
        # ROE tự tính/thực tế = LNST / VCSH bình quân; không dùng VCSH cuối kỳ trừ khi thiếu kỳ trước.
        df["roe_actual_pct"] = df["roe_actual_pct"].fillna(df["net_profit_bil"] / df["avg_equity_bil"].replace({0: pd.NA}) * 100)
        if "roe_pct" in df.columns:
            df["roe_pct"] = df["roe_pct"].fillna(df["roe_actual_pct"])

    if {"net_profit_bil", "shares_outstanding_mil"}.issubset(df.columns):
        if "eps_vnd" not in df.columns:
            df["eps_vnd"] = pd.NA
        df["eps_vnd"] = df["eps_vnd"].fillna(df["net_profit_bil"] * 1000 / df["shares_outstanding_mil"].replace({0: pd.NA}))
    if {"owner_earnings_bil", "shares_outstanding_mil"}.issubset(df.columns):
        if "oeps_vnd" not in df.columns:
            df["oeps_vnd"] = pd.NA
        df["oeps_vnd"] = df["oeps_vnd"].fillna(df["owner_earnings_bil"] * 1000 / df["shares_outstanding_mil"].replace({0: pd.NA}))

    if "net_margin_pct" not in df.columns and {"net_profit_bil", "revenue_bil"}.issubset(df.columns):
        df["net_margin_pct"] = df["net_profit_bil"] / df["revenue_bil"] * 100

    # DuPont dùng tài sản/VCSH bình quân để nhất quán với ROA/ROE tự tính.
    if {"revenue_bil", "total_assets_bil"}.issubset(df.columns):
        if "avg_total_assets_bil" not in df.columns:
            df["avg_total_assets_bil"] = pd.NA
        df["avg_total_assets_bil"] = df["avg_total_assets_bil"].fillna(_avg_current_and_previous(df, "total_assets_bil"))
        if "asset_turnover" not in df.columns:
            df["asset_turnover"] = pd.NA
        df["asset_turnover"] = df["asset_turnover"].fillna(df["revenue_bil"] / df["avg_total_assets_bil"].replace({0: pd.NA}))

    if {"total_assets_bil", "equity_bil"}.issubset(df.columns):
        if "avg_total_assets_bil" not in df.columns:
            df["avg_total_assets_bil"] = pd.NA
        df["avg_total_assets_bil"] = df["avg_total_assets_bil"].fillna(_avg_current_and_previous(df, "total_assets_bil"))
        if "avg_equity_bil" not in df.columns:
            df["avg_equity_bil"] = pd.NA
        df["avg_equity_bil"] = df["avg_equity_bil"].fillna(_avg_current_and_previous(df, "equity_bil"))
        if "equity_multiplier" not in df.columns:
            df["equity_multiplier"] = pd.NA
        df["equity_multiplier"] = df["equity_multiplier"].fillna(df["avg_total_assets_bil"] / df["avg_equity_bil"].replace({0: pd.NA}))

    if {"net_margin_pct", "asset_turnover", "equity_multiplier"}.issubset(df.columns):
        if "roe_dupont_pct" not in df.columns:
            df["roe_dupont_pct"] = pd.NA
        derived = df["net_margin_pct"] / 100 * df["asset_turnover"] * df["equity_multiplier"] * 100
        df["roe_dupont_pct"] = df["roe_dupont_pct"].fillna(derived)

    if {"net_profit_bil", "cfo_bil"}.issubset(df.columns):
        if "cfo_to_net_profit" not in df.columns:
            df["cfo_to_net_profit"] = pd.NA
        df["cfo_to_net_profit"] = df["cfo_to_net_profit"].fillna(df["cfo_bil"] / df["net_profit_bil"].replace({0: pd.NA}))

    if {"net_profit_bil", "free_cash_flow_bil"}.issubset(df.columns):
        if "fcf_to_net_profit" not in df.columns:
            df["fcf_to_net_profit"] = pd.NA
        df["fcf_to_net_profit"] = df["fcf_to_net_profit"].fillna(df["free_cash_flow_bil"] / df["net_profit_bil"].replace({0: pd.NA}))
    if {"pretax_profit_bil", "free_cash_flow_bil"}.issubset(df.columns):
        if "fcf_to_pretax" not in df.columns:
            df["fcf_to_pretax"] = pd.NA
        df["fcf_to_pretax"] = df["fcf_to_pretax"].fillna(df["free_cash_flow_bil"] / df["pretax_profit_bil"].replace({0: pd.NA}))
        if "nibt_to_fcf" not in df.columns:
            df["nibt_to_fcf"] = pd.NA
        df["nibt_to_fcf"] = df["nibt_to_fcf"].fillna(df["pretax_profit_bil"] / df["free_cash_flow_bil"].replace({0: pd.NA}))
    if {"noncash_adjustments_bil", "pretax_profit_bil"}.issubset(df.columns):
        if "noncash_to_pretax" not in df.columns:
            df["noncash_to_pretax"] = pd.NA
        df["noncash_to_pretax"] = df["noncash_to_pretax"].fillna(df["noncash_adjustments_bil"] / df["pretax_profit_bil"].replace({0: pd.NA}))
    if {"working_capital_change_bil", "pretax_profit_bil"}.issubset(df.columns):
        if "wc_to_pretax" not in df.columns:
            df["wc_to_pretax"] = pd.NA
        df["wc_to_pretax"] = df["wc_to_pretax"].fillna(df["working_capital_change_bil"] / df["pretax_profit_bil"].replace({0: pd.NA}))
    if {"capex_bil", "pretax_profit_bil"}.issubset(df.columns):
        if "capex_to_pretax" not in df.columns:
            df["capex_to_pretax"] = pd.NA
        df["capex_to_pretax"] = df["capex_to_pretax"].fillna(_capex_signed_outflow(df["capex_bil"]) / df["pretax_profit_bil"].replace({0: pd.NA}))

    if "owner_earnings_bil" not in df.columns:
        df["owner_earnings_bil"] = pd.NA
    if df["owner_earnings_bil"].isna().any():
        if "capex_bil" in df.columns:
            maintenance_capex = _capex_signed_outflow(df["capex_bil"]).rolling(maintenance_capex_window, min_periods=1).mean()
            if "maintenance_capex_bil" not in df.columns:
                df["maintenance_capex_bil"] = pd.NA
            df["maintenance_capex_bil"] = df["maintenance_capex_bil"].fillna(maintenance_capex)
        if {"cfo_bil", "maintenance_capex_bil"}.issubset(df.columns):
            # OE proxy = CFO - maintenance capex outflow. `maintenance_capex_bil` is stored as a signed outflow.
            oe = df["cfo_bil"] + df["maintenance_capex_bil"]
            df["owner_earnings_bil"] = df["owner_earnings_bil"].fillna(oe)
        elif {"net_profit_bil", "depreciation_bil", "working_capital_change_bil", "maintenance_capex_bil"}.issubset(df.columns):
            oe = df["net_profit_bil"] + df["depreciation_bil"] + df["working_capital_change_bil"] + df["maintenance_capex_bil"]
            df["owner_earnings_bil"] = df["owner_earnings_bil"].fillna(oe)


    # V22 - Phân tích chỉ số tài chính: chuẩn hóa thêm nhóm tăng trưởng, biên lợi nhuận,
    # sinh lời, thanh khoản, đòn bẩy và hiệu quả hoạt động.
    # Triết lý: không dùng một chỉ số đơn lẻ để kết luận; ưu tiên khả năng sinh tiền,
    # lợi nhuận trên vốn, bảng cân đối an toàn và giá mua hợp lý.
    sort_cols = [c for c in ["period_type", "year", "quarter"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    # COGS xấp xỉ để tính vòng quay tồn kho/phải trả nếu không có trực tiếp từ nguồn.
    if {"revenue_bil", "gross_profit_bil"}.issubset(df.columns):
        if "cost_of_goods_sold_bil" not in df.columns:
            df["cost_of_goods_sold_bil"] = pd.NA
        df["cost_of_goods_sold_bil"] = df["cost_of_goods_sold_bil"].fillna(df["revenue_bil"] - df["gross_profit_bil"])

    # Lợi nhuận gộp / hoạt động cốt lõi / LNST trên doanh thu.
    if {"gross_profit_bil", "revenue_bil"}.issubset(df.columns):
        if "gross_margin_pct" not in df.columns:
            df["gross_margin_pct"] = pd.NA
        df["gross_margin_pct"] = df["gross_margin_pct"].fillna(df["gross_profit_bil"] / df["revenue_bil"].replace({0: pd.NA}) * 100)
    if {"core_operating_profit_bil", "revenue_bil"}.issubset(df.columns):
        if "core_operating_margin_pct" not in df.columns:
            df["core_operating_margin_pct"] = pd.NA
        df["core_operating_margin_pct"] = df["core_operating_margin_pct"].fillna(df["core_operating_profit_bil"] / df["revenue_bil"].replace({0: pd.NA}) * 100)
    if {"net_profit_bil", "revenue_bil"}.issubset(df.columns):
        if "net_margin_pct" not in df.columns:
            df["net_margin_pct"] = pd.NA
        df["net_margin_pct"] = df["net_margin_pct"].fillna(df["net_profit_bil"] / df["revenue_bil"].replace({0: pd.NA}) * 100)
    if {"financial_income_bil", "revenue_bil"}.issubset(df.columns):
        if "financial_income_to_revenue_pct" not in df.columns:
            df["financial_income_to_revenue_pct"] = pd.NA
        df["financial_income_to_revenue_pct"] = df["financial_income_to_revenue_pct"].fillna(df["financial_income_bil"] / df["revenue_bil"].replace({0: pd.NA}) * 100)

    # EBITDA chỉ dùng như chỉ số hỗ trợ; không dùng thay thế CFO/FCF.
    if "ebitda_bil" not in df.columns:
        df["ebitda_bil"] = pd.NA
    if {"core_operating_profit_bil", "depreciation_bil"}.issubset(df.columns):
        df["ebitda_bil"] = df["ebitda_bil"].fillna(df["core_operating_profit_bil"] + df["depreciation_bil"].abs())
    if {"ebitda_bil", "revenue_bil"}.issubset(df.columns):
        if "ebitda_margin_pct" not in df.columns:
            df["ebitda_margin_pct"] = pd.NA
        df["ebitda_margin_pct"] = df["ebitda_margin_pct"].fillna(df["ebitda_bil"] / df["revenue_bil"].replace({0: pd.NA}) * 100)

    # ROA dùng tổng tài sản bình quân, không dùng số cuối kỳ khi có đủ dữ liệu.
    if {"net_profit_bil", "total_assets_bil"}.issubset(df.columns):
        if "avg_total_assets_bil" not in df.columns:
            df["avg_total_assets_bil"] = pd.NA
        df["avg_total_assets_bil"] = df["avg_total_assets_bil"].fillna(_avg_current_and_previous(df, "total_assets_bil"))
        if "roa_actual_pct" not in df.columns:
            df["roa_actual_pct"] = pd.NA
        df["roa_actual_pct"] = df["roa_actual_pct"].fillna(df["net_profit_bil"] / df["avg_total_assets_bil"].replace({0: pd.NA}) * 100)
        if "roa_pct" not in df.columns:
            df["roa_pct"] = pd.NA
        df["roa_pct"] = df["roa_pct"].fillna(df["roa_actual_pct"])

    # Tăng trưởng YoY: chỉ tính khi kỳ trước có nền dương/khác 0 để tránh kết luận méo.
    def _yoy(col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series(index=df.index, dtype="float64")
        if "period_type" in df.columns:
            prev = df.groupby("period_type", dropna=False)[col].shift(1)
        else:
            prev = df[col].shift(1)
        return ((df[col] - prev) / prev.replace({0: pd.NA}) * 100).where(prev > 0)

    yoy_map = {
        "revenue_growth_yoy_pct": "revenue_bil",
        "net_profit_growth_yoy_pct": "net_profit_bil",
        "eps_growth_yoy_pct": "eps_vnd",
        "total_assets_growth_yoy_pct": "total_assets_bil",
        "equity_growth_yoy_pct": "equity_bil",
    }
    for out_col, base_col in yoy_map.items():
        if base_col in df.columns:
            if out_col not in df.columns:
                df[out_col] = pd.NA
            df[out_col] = df[out_col].fillna(_yoy(base_col))

    # Thanh khoản & đòn bẩy.
    if {"current_assets_bil", "current_liabilities_bil"}.issubset(df.columns):
        if "current_ratio" not in df.columns:
            df["current_ratio"] = pd.NA
        df["current_ratio"] = df["current_ratio"].fillna(df["current_assets_bil"] / df["current_liabilities_bil"].replace({0: pd.NA}))
    if {"cash_equivalents_bil", "short_term_investments_bil", "current_liabilities_bil"}.issubset(df.columns):
        if "quick_ratio" not in df.columns:
            df["quick_ratio"] = pd.NA
        ar = df["accounts_receivable_bil"] if "accounts_receivable_bil" in df.columns else 0
        df["quick_ratio"] = df["quick_ratio"].fillna((df["cash_equivalents_bil"] + df["short_term_investments_bil"] + ar) / df["current_liabilities_bil"].replace({0: pd.NA}))
        if "net_liquid_assets_bil" not in df.columns:
            df["net_liquid_assets_bil"] = pd.NA
        df["net_liquid_assets_bil"] = df["net_liquid_assets_bil"].fillna(df["cash_equivalents_bil"] + df["short_term_investments_bil"] + ar - df["current_liabilities_bil"])
    if {"total_assets_bil", "equity_bil"}.issubset(df.columns):
        if "liabilities_bil" not in df.columns:
            df["liabilities_bil"] = pd.NA
        df["liabilities_bil"] = df["liabilities_bil"].fillna(df["total_assets_bil"] - df["equity_bil"])
        if "equity_to_assets_pct" not in df.columns:
            df["equity_to_assets_pct"] = pd.NA
        df["equity_to_assets_pct"] = df["equity_to_assets_pct"].fillna(df["equity_bil"] / df["total_assets_bil"].replace({0: pd.NA}) * 100)
        if "liabilities_to_assets_pct" not in df.columns:
            df["liabilities_to_assets_pct"] = pd.NA
        df["liabilities_to_assets_pct"] = df["liabilities_to_assets_pct"].fillna(df["liabilities_bil"] / df["total_assets_bil"].replace({0: pd.NA}) * 100)
        if "liabilities_to_equity" not in df.columns:
            df["liabilities_to_equity"] = pd.NA
        df["liabilities_to_equity"] = df["liabilities_to_equity"].fillna(df["liabilities_bil"] / df["equity_bil"].replace({0: pd.NA}))
    if {"cash_equivalents_bil", "short_term_investments_bil"}.issubset(df.columns):
        if "net_debt_bil" not in df.columns:
            df["net_debt_bil"] = pd.NA
        gross_debt = _interest_bearing_debt_series(df)
        if "interest_bearing_debt_bil" not in df.columns:
            df["interest_bearing_debt_bil"] = pd.NA
        df["interest_bearing_debt_bil"] = df["interest_bearing_debt_bil"].fillna(gross_debt)
        df["net_debt_bil"] = df["net_debt_bil"].fillna(gross_debt - df["cash_equivalents_bil"].fillna(0) - df["short_term_investments_bil"].fillna(0))
        if {"net_debt_bil", "equity_bil"}.issubset(df.columns):
            if "net_debt_to_equity" not in df.columns:
                df["net_debt_to_equity"] = pd.NA
            df["net_debt_to_equity"] = df["net_debt_to_equity"].fillna(df["net_debt_bil"] / df["equity_bil"].replace({0: pd.NA}))
        if {"net_debt_bil", "ebitda_bil"}.issubset(df.columns):
            if "net_debt_to_ebitda" not in df.columns:
                df["net_debt_to_ebitda"] = pd.NA
            df["net_debt_to_ebitda"] = df["net_debt_to_ebitda"].fillna(df["net_debt_bil"] / df["ebitda_bil"].replace({0: pd.NA}))
    if "core_operating_profit_bil" in df.columns:
        if "interest_coverage" not in df.columns:
            df["interest_coverage"] = pd.NA
        interest_cost = None
        for col in ["interest_expense_bil", "interest_paid_bil", "borrowing_cost_bil", "financial_expense_bil"]:
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce").abs()
                interest_cost = vals if interest_cost is None else interest_cost.fillna(vals)
        if interest_cost is not None:
            df["interest_coverage"] = df["interest_coverage"].fillna(df["core_operating_profit_bil"] / interest_cost.replace({0: pd.NA}))

    # Hiệu quả hoạt động. Nếu thiếu phải thu hoặc phải trả thì chỉ tiêu để trống, không suy đoán quá mức.
    if {"accounts_receivable_bil", "revenue_bil"}.issubset(df.columns):
        if "avg_accounts_receivable_bil" not in df.columns:
            df["avg_accounts_receivable_bil"] = pd.NA
        df["avg_accounts_receivable_bil"] = df["avg_accounts_receivable_bil"].fillna(_avg_current_and_previous(df, "accounts_receivable_bil"))
        if "receivables_turnover" not in df.columns:
            df["receivables_turnover"] = pd.NA
        df["receivables_turnover"] = df["receivables_turnover"].fillna(df["revenue_bil"] / df["avg_accounts_receivable_bil"].replace({0: pd.NA}))
        if "dso_days" not in df.columns:
            df["dso_days"] = pd.NA
        df["dso_days"] = df["dso_days"].fillna(365 / df["receivables_turnover"].replace({0: pd.NA}))
    if {"inventory_bil", "cost_of_goods_sold_bil"}.issubset(df.columns):
        if "avg_inventory_bil" not in df.columns:
            df["avg_inventory_bil"] = pd.NA
        df["avg_inventory_bil"] = df["avg_inventory_bil"].fillna(_avg_current_and_previous(df, "inventory_bil"))
        if "inventory_turnover" not in df.columns:
            df["inventory_turnover"] = pd.NA
        df["inventory_turnover"] = df["inventory_turnover"].fillna(df["cost_of_goods_sold_bil"] / df["avg_inventory_bil"].replace({0: pd.NA}))
        if "dio_days" not in df.columns:
            df["dio_days"] = pd.NA
        df["dio_days"] = df["dio_days"].fillna(365 / df["inventory_turnover"].replace({0: pd.NA}))
    if {"accounts_payable_bil", "cost_of_goods_sold_bil"}.issubset(df.columns):
        if "avg_accounts_payable_bil" not in df.columns:
            df["avg_accounts_payable_bil"] = pd.NA
        df["avg_accounts_payable_bil"] = df["avg_accounts_payable_bil"].fillna(_avg_current_and_previous(df, "accounts_payable_bil"))
        if "payables_turnover" not in df.columns:
            df["payables_turnover"] = pd.NA
        df["payables_turnover"] = df["payables_turnover"].fillna(df["cost_of_goods_sold_bil"] / df["avg_accounts_payable_bil"].replace({0: pd.NA}))
        if "dpo_days" not in df.columns:
            df["dpo_days"] = pd.NA
        df["dpo_days"] = df["dpo_days"].fillna(365 / df["payables_turnover"].replace({0: pd.NA}))
    if {"dso_days", "dio_days", "dpo_days"}.issubset(df.columns):
        if "cash_conversion_cycle_days" not in df.columns:
            df["cash_conversion_cycle_days"] = pd.NA
        df["cash_conversion_cycle_days"] = df["cash_conversion_cycle_days"].fillna(df["dso_days"] + df["dio_days"] - df["dpo_days"])

    df = add_company_wacc(df)
    return df



# ===== V23.15: Auditable company-specific WACC engine =====
def _series_or_zero(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index, dtype="float64")


def _first_available_series(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    """Return first non-empty numeric series among candidate columns."""
    out = pd.Series(float("nan"), index=df.index, dtype="float64")
    for col in candidates:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            out = out.fillna(s)
    return out


def _rolling_cv_for_wacc(series: pd.Series, window: int = 5) -> pd.Series:
    """Rolling coefficient of variation used for WACC proxy beta.

    The value is calculated period-by-period, not once for the whole company. This prevents WACC from
    being mechanically identical across all years when no market beta is available.
    """
    s = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], pd.NA)
    s = s.where(s.abs() > 1e-9)
    roll_mean = s.rolling(window, min_periods=3).mean().abs()
    roll_std = s.rolling(window, min_periods=3).std(ddof=0)
    cv = (roll_std / roll_mean.replace({0: pd.NA})).clip(lower=0.0, upper=2.0)
    # For early years with fewer than 3 observations, use expanding CV when possible; otherwise 0.
    exp_mean = s.expanding(min_periods=3).mean().abs()
    exp_std = s.expanding(min_periods=3).std(ddof=0)
    exp_cv = (exp_std / exp_mean.replace({0: pd.NA})).clip(lower=0.0, upper=2.0)
    cv = cv.fillna(exp_cv).fillna(0.0)
    return cv.astype(float)


def _company_beta_proxy(df: pd.DataFrame) -> pd.Series:
    """Estimate beta when no market-regression beta is available.

    Priority:
    1) real beta column from source, if available and reasonable;
    2) period-specific proxy from trailing profit volatility, revenue volatility and leverage.

    V23.16 change: the proxy is now calculated for each period from trailing/rolling data. Earlier builds
    used a single company-level profit/revenue CV, so if a company had little/no mapped debt, WACC could
    appear identical across all years. The formula remains auditable in `wacc_formula_detail`.
    """
    raw_beta = pd.to_numeric(df["beta"], errors="coerce") if "beta" in df.columns else pd.Series(float("nan"), index=df.index)
    # Nếu beta hiện có là beta proxy được tạo ở lần ensure trước, không được hiểu nhầm là beta thị trường.
    if "beta_source" in df.columns:
        prev_src = df["beta_source"].astype(str).str.lower()
        raw_beta = raw_beta.where(~prev_src.str.contains("nội suy|proxy|firm-specific", na=False), float("nan"))

    if "net_profit_bil" in df.columns:
        profit_cv = _rolling_cv_for_wacc(pd.to_numeric(df["net_profit_bil"], errors="coerce"), window=5).clip(upper=1.50)
    else:
        profit_cv = pd.Series(0.0, index=df.index, dtype="float64")

    if "revenue_bil" in df.columns:
        rev_cv = _rolling_cv_for_wacc(pd.to_numeric(df["revenue_bil"], errors="coerce"), window=5).clip(upper=1.00)
    else:
        rev_cv = pd.Series(0.0, index=df.index, dtype="float64")

    debt = pd.to_numeric(df.get("interest_bearing_debt_bil", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0)
    equity = pd.to_numeric(df.get("equity_bil", pd.Series(float("nan"), index=df.index)), errors="coerce")
    leverage = (debt / equity.replace({0: pd.NA})).fillna(0.0).clip(lower=0.0, upper=2.0)

    # Add modest cyclicality from financial leverage and volatility. Bound proxy to avoid one-off distortion.
    proxy = (0.75 + 0.55 * profit_cv + 0.25 * rev_cv + 0.30 * leverage).clip(lower=0.60, upper=2.40)
    return raw_beta.where(raw_beta.between(0.3, 3.5), proxy).clip(lower=0.50, upper=3.00)

def add_company_wacc(df: pd.DataFrame, risk_free_rate_pct: float = 4.5, equity_risk_premium_pct: float = 8.0) -> pd.DataFrame:
    """Calculate auditable company-specific WACC for each period.

    Core formula:
        WACC = We × Ke + Wd × Kd × (1 - Tax Rate)

    Components used by the app:
        E  = market value of equity. Priority: market_cap_bil; if missing, shares × price / 1,000; if still missing, book equity proxy.
        D  = gross interest-bearing debt. Priority: interest_bearing_debt_bil; otherwise short-term debt + long-term debt + bonds + lease liabilities.
        We = E / (E + D); Wd = D / (E + D).
        Kd = interest cost / average gross interest-bearing debt. Priority: interest_paid_bil, interest_expense_bil, then financial_expense_bil as a fallback.
        Ke = risk-free rate + beta × equity risk premium. Beta from source if available; otherwise firm-specific proxy.
        Tax Rate = tax expense / pretax profit, bounded 0-35% for normal periods.

    Important change in V23.15:
        The app ALWAYS recalculates `wacc_pct` from the components above. It no longer keeps an old/source WACC value that may have been stale or inconsistent.
        The detailed formula is saved in `wacc_formula_detail` for checking in Tổng quan doanh nghiệp ROIC & đầu tư.
    """
    if df is None or df.empty:
        return df
    out = df.copy()

    # Gross interest-bearing debt D.
    debt_component_cols = [
        "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil",
        "bonds_payable_bil", "lease_liabilities_bil", "finance_lease_liabilities_bil",
    ]
    component_debt = sum(_series_or_zero(out, c) for c in debt_component_cols)
    existing_debt = pd.to_numeric(out.get("interest_bearing_debt_bil", pd.Series(float("nan"), index=out.index)), errors="coerce")
    # If no component column exists, approximate gross debt from net debt + cash + short investments.
    if component_debt.abs().sum() <= 1e-9 and {"net_debt_bil", "cash_equivalents_bil"}.issubset(out.columns):
        short_inv = _series_or_zero(out, "short_term_investments_bil")
        component_debt = (_series_or_zero(out, "net_debt_bil") + _series_or_zero(out, "cash_equivalents_bil") + short_inv).clip(lower=0.0)
    out["interest_bearing_debt_bil"] = existing_debt.where(existing_debt.notna() & (existing_debt >= 0), component_debt).fillna(0.0)

    # Average gross debt for Kd.
    out["avg_interest_bearing_debt_bil"] = pd.to_numeric(
        out.get("avg_interest_bearing_debt_bil", pd.Series(float("nan"), index=out.index)), errors="coerce"
    ).fillna(_avg_current_and_previous(out, "interest_bearing_debt_bil"))

    # Market value of equity E.
    existing_market_cap = pd.to_numeric(out.get("market_cap_bil", pd.Series(float("nan"), index=out.index)), errors="coerce")
    share_count = _first_available_series(out, ["shares_outstanding_mil", "avg_shares_outstanding_mil"])
    price = _first_available_series(out, ["year_end_price", "current_price", "close_price", "price"])
    market_cap_from_price = share_count * price / 1000.0
    book_equity = pd.to_numeric(out.get("equity_bil", pd.Series(float("nan"), index=out.index)), errors="coerce")
    market_cap = existing_market_cap.where(existing_market_cap.notna() & (existing_market_cap > 0), market_cap_from_price)
    market_cap = market_cap.where(market_cap.notna() & (market_cap > 0), book_equity)
    out["market_cap_bil"] = market_cap

    # Tax rate. Use normal effective tax rate; negative/abnormal pretax falls back to 20%.
    tax_rate = _safe_effective_tax_rate(out).clip(lower=0.0, upper=0.35)
    out["tax_rate_pct"] = tax_rate * 100.0

    # Cost of debt. Use real interest paid/expense first; financial expense only as a conservative fallback.
    interest_cost = _first_available_series(out, ["interest_paid_bil", "interest_expense_bil", "borrowing_cost_bil", "financial_expense_bil"]).abs()
    avg_debt = pd.to_numeric(out["avg_interest_bearing_debt_bil"], errors="coerce")
    kd = (interest_cost / avg_debt.replace({0: pd.NA}) * 100.0)
    kd = kd.where(avg_debt > 1e-6, 0.0).clip(lower=0.0, upper=25.0).fillna(0.0)
    out["cost_of_debt_pct"] = kd

    # Cost of equity by CAPM/proxy.
    beta = _company_beta_proxy(out)
    existing_beta = pd.to_numeric(out.get("beta", pd.Series(float("nan"), index=out.index)), errors="coerce")
    prev_beta_source = out.get("beta_source", pd.Series("", index=out.index)).astype(str).str.lower()
    has_market_beta = existing_beta.between(0.3, 3.5) & ~prev_beta_source.str.contains("nội suy|proxy|firm-specific", na=False)
    out["beta"] = beta
    out["beta_source"] = has_market_beta.map({True: "market/source beta", False: "firm-specific proxy beta"})
    out["risk_free_rate_pct"] = float(risk_free_rate_pct)
    out["equity_risk_premium_pct"] = float(equity_risk_premium_pct)
    ke = (float(risk_free_rate_pct) + beta * float(equity_risk_premium_pct)).clip(lower=6.0, upper=28.0)
    out["cost_of_equity_pct"] = ke

    E = pd.to_numeric(out["market_cap_bil"], errors="coerce").fillna(0.0).clip(lower=0.0)
    D = pd.to_numeric(out["interest_bearing_debt_bil"], errors="coerce").fillna(0.0).clip(lower=0.0)
    total_cap = (E + D).replace({0: pd.NA})
    weight_e = (E / total_cap).fillna(1.0).clip(lower=0.0, upper=1.0)
    weight_d = (D / total_cap).fillna(0.0).clip(lower=0.0, upper=1.0)
    after_tax_kd = kd * (1 - tax_rate)
    wacc_calc = (weight_e * ke + weight_d * after_tax_kd).clip(lower=0.0, upper=35.0)

    # Always overwrite old/source WACC; preserve it for audit if there was a value.
    old_wacc = pd.to_numeric(out.get("wacc_pct", pd.Series(float("nan"), index=out.index)), errors="coerce")
    out["wacc_source_pct"] = old_wacc
    out["wacc_pct"] = wacc_calc
    out["equity_weight_pct"] = weight_e * 100.0
    out["debt_weight_pct"] = weight_d * 100.0
    out["after_tax_cost_of_debt_pct"] = after_tax_kd
    out["wacc_quality"] = "Tốt"
    out.loc[E <= 0, "wacc_quality"] = "Cảnh báo: thiếu market cap/equity"
    out.loc[(D > 0) & (avg_debt <= 0), "wacc_quality"] = "Theo dõi: thiếu nợ vay bình quân"
    out.loc[out["beta_source"].eq("firm-specific proxy beta"), "wacc_quality"] = out.loc[out["beta_source"].eq("firm-specific proxy beta"), "wacc_quality"].replace({"Tốt": "Theo dõi: beta nội suy"})

    details = []
    for idx in out.index:
        details.append(
            "WACC = Tỷ trọng vốn chủ × Chi phí vốn chủ + Tỷ trọng nợ vay × Chi phí nợ vay sau thuế. "
            f"Vốn hóa/giá trị vốn chủ={E.loc[idx]:,.0f} tỷ, nợ vay chịu lãi={D.loc[idx]:,.0f} tỷ, "
            f"We={weight_e.loc[idx]*100:,.1f}%, Wd={weight_d.loc[idx]*100:,.1f}%, "
            f"Ke={ke.loc[idx]:,.1f}%, Kd={kd.loc[idx]:,.1f}%, thuế suất={tax_rate.loc[idx]*100:,.1f}%, "
            f"Kd sau thuế={after_tax_kd.loc[idx]:,.1f}% → WACC={wacc_calc.loc[idx]:,.1f}%. "
            f"hệ số beta={beta.loc[idx]:,.2f} ({out.loc[idx, 'beta_source']})."
        )
    out["wacc_formula_detail"] = details
    out["wacc_note"] = out["wacc_formula_detail"]
    return out

def _safe_divide(num: Any, den: Any) -> Optional[float]:
    n = _to_float(num)
    d = _to_float(den)
    if n is None or d is None or abs(d) < 1e-12:
        return None
    return n / d


def append_ttm_row(annual_df: pd.DataFrame, quarterly_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Append a TTM/T12M row to annual data when at least four quarters are available.

    Flow items (revenue, profit, CFO, FCF, capex, dividends...) are summed over the last
    four quarters. Balance-sheet items (assets, equity, cash, debt, shares...) use the
    latest quarter. Derived ratios are recalculated after the TTM row is appended.
    """
    base = annual_df.copy() if isinstance(annual_df, pd.DataFrame) else pd.DataFrame()
    if base.empty or quarterly_df is None or quarterly_df.empty:
        return ensure_derived_metrics(base) if not base.empty else base
    # Avoid duplicate TTM rows when the function is called more than once.
    if "period" in base.columns:
        base = base[~base["period"].astype(str).str.upper().isin(["TTM", "T12M"])].copy()
    q = ensure_derived_metrics(quarterly_df.copy())
    if len(q) < 4:
        return ensure_derived_metrics(base)
    q4 = q.tail(4).copy()
    latest = q4.iloc[-1]

    flow_cols = [
        "revenue_bil", "gross_profit_bil", "cost_of_goods_sold_bil", "operating_profit_bil", "core_operating_profit_bil", "net_profit_bil", "pretax_profit_bil",
        "financial_income_bil", "financial_expense_bil", "selling_expense_bil", "admin_expense_bil", "tax_expense_bil", "nopat_bil",
        "cfo_bil", "cfi_bil", "cff_bil", "capex_bil", "depreciation_bil", "noncash_adjustments_bil", "operating_cash_before_wc_bil", "working_capital_change_bil",
        "receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil",
        "interest_paid_bil", "interest_expense_bil", "borrowing_cost_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil",
        "equity_issued_bil", "buyback_bil", "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "cash_dividend_bil",
        "cash_and_short_investments_change_bil", "free_cash_flow_bil", "owner_earnings_bil", "maintenance_capex_bil", "investment_subsidiary_bil", "expansion_investment_bil", "total_investment_bil",
    ]
    stock_cols = [
        "current_assets_bil", "current_liabilities_bil", "accounts_receivable_bil", "accounts_payable_bil", "working_capital_bil", "roic_working_capital_bil",
        "operating_working_capital_bil", "fixed_assets_bil", "cash_equivalents_bil", "short_term_investments_bil", "cash_and_short_investments_bil",
        "capital_employed_bil", "deployed_capital_bil",
        "inventory_bil", "total_assets_bil", "liabilities_bil", "equity_bil",
        "shares_outstanding_mil", "year_end_price", "short_term_debt_bil", "long_term_debt_bil", "net_debt_bil",
    ]
    keep_cols = list(dict.fromkeys(list(base.columns) + list(q.columns)))
    ttm: Dict[str, Any] = {c: pd.NA for c in keep_cols}
    ttm["ticker"] = latest.get("ticker") if "ticker" in q.columns else (base.iloc[-1].get("ticker") if not base.empty else "")
    ttm["period"] = "TTM"
    ttm["period_type"] = "Y"
    if "year" in q.columns:
        ttm["year"] = latest.get("year")
    if "quarter" in q.columns:
        ttm["quarter"] = latest.get("quarter")

    for col in flow_cols:
        if col in q4.columns:
            vals = pd.to_numeric(q4[col], errors="coerce")
            if vals.notna().any():
                ttm[col] = float(vals.sum(skipna=True))
    for col in stock_cols:
        if col in q4.columns and pd.notna(latest.get(col)):
            ttm[col] = latest.get(col)

    # V23.67: TTM flow rows should be summed, while TTM balance-sheet denominators
    # should use an average over the trailing quarters.  Do not carry over the latest
    # quarter's avg_* fields, because that would make TTM ROE/ROIC use a one-quarter
    # denominator instead of a trailing-period capital base.
    trailing_average_map = {
        "avg_total_assets_bil": "total_assets_bil",
        "avg_equity_bil": "equity_bil",
        "avg_capital_employed_bil": "capital_employed_bil",
        "avg_deployed_capital_bil": "deployed_capital_bil",
        "avg_interest_bearing_debt_bil": "interest_bearing_debt_bil",
    }
    for avg_col, base_col in trailing_average_map.items():
        if base_col in q4.columns:
            vals = pd.to_numeric(q4[base_col], errors="coerce").dropna()
            if not vals.empty:
                if avg_col not in keep_cols:
                    keep_cols.append(avg_col)
                    ttm[avg_col] = pd.NA
                ttm[avg_col] = float(vals.mean())
    # The latest quarterly market price is a point-in-time input, so it may be carried
    # into the TTM row.  Do NOT carry quarterly/period ratios such as ROE, ROA,
    # ROIC, P/E, P/B or P/S into TTM: they must be recalculated from TTM flow
    # numerators and trailing-period balance-sheet denominators.
    for col in ["current_price", "close_price", "price", "year_end_price"]:
        if col in q4.columns and pd.notna(latest.get(col)):
            if col not in keep_cols:
                keep_cols.append(col)
                ttm[col] = pd.NA
            ttm[col] = latest.get(col)

    add = pd.DataFrame([ttm], columns=keep_cols)
    out = pd.concat([base.reindex(columns=keep_cols), add], ignore_index=True)
    return ensure_derived_metrics(out)


def _latest_row(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    if df is None or df.empty:
        return {}
    src = ensure_derived_metrics(df)
    if "period" in src.columns:
        ttm = src[src["period"].astype(str).str.upper().isin(["TTM", "T12M"])]
        if not ttm.empty:
            return ttm.iloc[-1].to_dict()
    return src.iloc[-1].to_dict()


def _cagr_cap(series: pd.Series, years: int = 5, fallback: float = 0.05, cap: float = 0.15) -> float:
    cagr = _cagr_from_series(series, years)
    if cagr is None or pd.isna(cagr):
        return fallback
    return float(min(max(cagr, 0.0), cap))


def build_mos_valuation_table(company: CompanyOverview, annual_df: pd.DataFrame, mos_rate: float = 0.50, discount_rate: float = 0.15, target_multiple: float = 10.0) -> pd.DataFrame:
    """Build MOS valuation table inspired by sheets MOS and MOS_LILU.

    The table intentionally reports a range rather than a single buy/sell signal:
    - Graham defensive formula: sqrt(22.5 * EPS * BVPS).
    - Phil Town style earnings projection: future EPS/OEPS discounted back at required return.
    - Owner Earnings yield: OEPS / required yield, then MOS.
    - Li Lu/MOS_LILU net-cash-adjusted earnings power: OP/OE * target multiple + net cash.
    """
    if annual_df is None or annual_df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(annual_df).copy()
    if "period" in src.columns:
        ttm_rows = src[src["period"].astype(str).str.upper().isin(["TTM", "T12M"])]
        latest = ttm_rows.iloc[-1] if not ttm_rows.empty else src.iloc[-1]
    else:
        latest = src.iloc[-1]
    shares_mil = _to_float(latest.get("shares_outstanding_mil")) or company.shares_outstanding_mil
    price = company.current_price
    # V23.63: never let a stale overview EPS override fresh financial-statement data.
    # If the latest/TTM row has no EPS/OEPS, derive them from LNST/OE and shares.
    eps = _to_float(latest.get("eps_vnd"))
    if eps is None:
        eps = _per_share_from_bil(_to_float(latest.get("net_profit_bil")), shares_mil)
    if eps is None:
        eps = company.eps
    oeps = _to_float(latest.get("oeps_vnd"))
    if oeps is None:
        oeps = _per_share_from_bil(_to_float(latest.get("owner_earnings_bil")), shares_mil)
    equity = _to_float(latest.get("equity_bil"))
    bvps = _per_share_from_bil(equity, shares_mil)
    net_cash = None
    cash = _to_float(latest.get("cash_equivalents_bil")) or 0.0
    sti = _to_float(latest.get("short_term_investments_bil")) or 0.0
    gross_debt = _to_float(latest.get("interest_bearing_debt_bil"))
    if gross_debt is None:
        gross_debt = sum((_to_float(latest.get(c)) or 0.0) for c in [
            "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil",
            "bonds_payable_bil", "lease_liabilities_bil", "finance_lease_liabilities_bil",
        ])
    if shares_mil not in [None, 0]:
        net_cash = cash + sti - gross_debt
    core_op = _to_float(latest.get("core_operating_profit_bil"))
    oe_bil = _to_float(latest.get("owner_earnings_bil"))
    eps_growth = _cagr_cap(src.get("eps_vnd", pd.Series(dtype="float64")), 5, fallback=0.05, cap=0.15)
    oe_growth = _cagr_cap(src.get("owner_earnings_bil", pd.Series(dtype="float64")), 5, fallback=0.05, cap=0.15)

    rows: List[Dict[str, Any]] = []

    def add(method: str, intrinsic: Optional[float], basis: str, note: str) -> None:
        if intrinsic is None or not pd.notna(intrinsic) or intrinsic <= 0:
            return
        mos_price = intrinsic * (1 - mos_rate)
        margin_now = (intrinsic - price) / intrinsic * 100 if price not in [None, 0] else None
        signal = f"Đạt MOS {mos_rate*100:.0f}%" if price is not None and price <= mos_price else f"Chưa đạt MOS {mos_rate*100:.0f}%" if price is not None else "Thiếu giá"
        rows.append({
            "Phương pháp": method,
            "Giá trị nội tại (đ/cp)": round(float(intrinsic), 0),
            "Mức MOS áp dụng (%)": round(float(mos_rate * 100), 1),
            "Giá MOS chọn (đ/cp)": round(float(mos_price), 0),
            "Giá hiện tại (đ/cp)": round(float(price), 0) if price is not None else None,
            "Biên an toàn hiện tại (%)": round(float(margin_now), 1) if margin_now is not None else None,
            "MOS yêu cầu (%)": round(float(mos_rate * 100), 1),
            "Chênh lệch so với MOS yêu cầu (%)": round(float(margin_now - mos_rate * 100), 1) if margin_now is not None else None,
            "Tín hiệu": signal,
            "Cơ sở tính": basis,
            "Diễn giải": note,
        })

    if eps is not None and bvps is not None and eps > 0 and bvps > 0:
        graham_value = math.sqrt(22.5 * eps * bvps)
        add("Benjamin Graham EPS × BVPS", graham_value, "sqrt(22.5 × EPS × BVPS)", "Công thức phòng thủ, phù hợp khi EPS/BVPS có chất lượng và không bị bóp méo bởi chu kỳ.")
    if eps is not None and eps > 0:
        future_eps = eps * (1 + eps_growth) ** 10
        phil_eps_value = future_eps * target_multiple / (1 + discount_rate) ** 10
        add("Phil Town/EPS chiết khấu", phil_eps_value, f"EPS × (1+{eps_growth:.1%})^10 × P/E {target_multiple:.0f} / (1+{discount_rate:.0%})^10", "Mô hình tăng trưởng đơn giản; chỉ dùng khi tăng trưởng EPS đủ bền vững.")
    if oeps is not None and oeps > 0:
        future_oeps = oeps * (1 + oe_growth) ** 10
        phil_oeps_value = future_oeps * target_multiple / (1 + discount_rate) ** 10
        add("Phil Town/OEPS chiết khấu", phil_oeps_value, f"OEPS × (1+{oe_growth:.1%})^10 × P/E {target_multiple:.0f} / (1+{discount_rate:.0%})^10", "Ưu tiên dòng tiền chủ sở hữu hơn EPS kế toán khi chất lượng lợi nhuận cần kiểm chứng.")
        add("Owner Earnings Yield 10%", oeps * target_multiple, f"OEPS × {target_multiple:.0f}", "Earnings-power không tăng trưởng; yêu cầu lợi suất khoảng 10% trước MOS.")
    if shares_mil not in [None, 0] and net_cash is not None:
        if core_op is not None and core_op > 0:
            value_bil = core_op * target_multiple + net_cash
            add("Li Lu/MOS_LILU Operating Profit + net cash", _per_share_from_bil(value_bil, shares_mil), f"Core OP × {target_multiple:.0f} + net cash", "Tách tiền/đầu tư tài chính dư thừa khỏi hoạt động, sau đó vốn hóa lợi nhuận hoạt động cốt lõi.")
        if oe_bil is not None and oe_bil > 0:
            value_bil = oe_bil * target_multiple + net_cash
            add("Li Lu/MOS_LILU Owner Earnings + net cash", _per_share_from_bil(value_bil, shares_mil), f"Owner Earnings × {target_multiple:.0f} + net cash", "Cách đọc như chủ sở hữu: dòng tiền thuộc cổ đông cộng tiền ròng, rồi áp MOS.")
    return pd.DataFrame(rows)


def build_mos_summary(valuation_df: pd.DataFrame) -> str:
    if valuation_df is None or valuation_df.empty:
        return "Chưa đủ dữ liệu để tính giá MOS. Cần EPS/OEPS, vốn chủ sở hữu, cổ phiếu lưu hành, giá hiện tại và dữ liệu dòng tiền."
    mos_col = "Giá MOS chọn (đ/cp)" if "Giá MOS chọn (đ/cp)" in valuation_df.columns else "Giá MOS 50% (đ/cp)"
    mos_level = _to_float(valuation_df.get("Mức MOS áp dụng (%)", pd.Series([50])).dropna().iloc[0]) if "Mức MOS áp dụng (%)" in valuation_df.columns and not valuation_df.empty else 50
    mos_values = pd.to_numeric(valuation_df.get(mos_col), errors="coerce").dropna()
    intrinsic_values = pd.to_numeric(valuation_df.get("Giá trị nội tại (đ/cp)"), errors="coerce").dropna()
    if mos_values.empty:
        return "Chưa có phương pháp định giá nào đủ dữ liệu để đưa ra giá MOS."
    conservative = float(mos_values.min())
    median_mos = float(mos_values.median())
    median_intrinsic = float(intrinsic_values.median()) if not intrinsic_values.empty else float("nan")
    valid_methods = len(valuation_df)
    achieved = 0
    if "Tín hiệu" in valuation_df.columns:
        # Không dùng contains("Đạt MOS") vì sẽ đếm nhầm cả "Chưa đạt MOS".
        achieved = int(valuation_df["Tín hiệu"].astype(str).str.strip().str.match(r"^Đạt MOS", case=False, na=False).sum())
    current_price = None
    if "Giá hiện tại (đ/cp)" in valuation_df.columns:
        current_series = pd.to_numeric(valuation_df["Giá hiện tại (đ/cp)"], errors="coerce").dropna()
        if not current_series.empty:
            current_price = float(current_series.iloc[0])
    return (
        f"Có {valid_methods} phương pháp đủ dữ liệu. Vùng giá MOS {mos_level:.0f}% thận trọng khoảng {_fmt_num(conservative, ' đ/cp', 0)}, "
        f"trung vị khoảng {_fmt_num(median_mos, ' đ/cp', 0)}; giá trị nội tại trung vị khoảng {_fmt_num(median_intrinsic, ' đ/cp', 0)}. "
        f"Giá hiện tại khoảng {_fmt_num(current_price, ' đ/cp', 0)}. "
        f"Số phương pháp đạt MOS yêu cầu {mos_level:.0f}%: {achieved}/{valid_methods}. "
        f"Cách đọc: chỉ tính là đạt khi giá hiện tại ≤ giá mua theo MOS chọn của từng phương pháp."
    )


def build_mos_detailed_summary(valuation_df: pd.DataFrame, max_methods: int = 6) -> str:
    """Return a markdown detail block for MOS valuation shown in the overview tab."""
    if valuation_df is None or valuation_df.empty:
        return "Chưa đủ dữ liệu để tính MOS. Cần có giá hiện tại, EPS/OEPS, vốn chủ sở hữu, cổ phiếu lưu hành, dòng tiền và dữ liệu tài sản/nợ để kiểm tra nhiều phương pháp."
    lines = [build_mos_summary(valuation_df)]
    df = valuation_df.copy()
    mos_col = "Giá MOS chọn (đ/cp)" if "Giá MOS chọn (đ/cp)" in df.columns else "Giá MOS 50% (đ/cp)"
    mos_level = _to_float(df.get("Mức MOS áp dụng (%)", pd.Series([50])).dropna().iloc[0]) if "Mức MOS áp dụng (%)" in df.columns and not df.empty else 50
    if mos_col in df.columns:
        df["_mos"] = pd.to_numeric(df[mos_col], errors="coerce")
        df = df.sort_values("_mos", ascending=True, na_position="last")
    for _, r in df.head(max_methods).iterrows():
        method = str(r.get("Phương pháp", ""))
        intrinsic = _fmt_num(_to_float(r.get("Giá trị nội tại (đ/cp)")), " đ/cp", 0)
        mos_price = _fmt_num(_to_float(r.get(mos_col)), " đ/cp", 0)
        current = _fmt_num(_to_float(r.get("Giá hiện tại (đ/cp)")), " đ/cp", 0)
        margin = _fmt_pct(_to_float(r.get("Biên an toàn hiện tại (%)")))
        signal = str(r.get("Tín hiệu", "Theo dõi"))
        basis = str(r.get("Cơ sở tính", ""))
        explanation = str(r.get("Diễn giải", ""))
        lines.append(
            f"- **{method}**: giá trị nội tại {intrinsic}; giá MOS {mos_level:.0f}% {mos_price}; giá hiện tại {current}; "
            f"biên an toàn hiện tại {margin}; tín hiệu **{signal}**. Cơ sở: {basis}. {explanation}"
        )
    if len(valuation_df) > max_methods:
        lines.append(f"- Còn {len(valuation_df) - max_methods} phương pháp khác xem tại bảng Kết quả định giá MOS.")
    lines.append("Cách đọc: ưu tiên vùng MOS thận trọng/trung vị và kiểm tra lại giả định tăng trưởng, chất lượng Owner Earnings, bear case và lợi thế cạnh tranh trước khi ra quyết định.")
    return "\n".join(lines)


def build_combined_assessment_table(company: CompanyOverview, annual_df: pd.DataFrame, quarterly_df: Optional[pd.DataFrame] = None, valuation_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Aggregate all automatic evaluations into one overview table."""
    rows: List[Dict[str, Any]] = []

    def add(source: str, level: str, title: str, detail: str) -> None:
        rows.append({"Nguồn đánh giá": source, "Mức độ": level, "Nội dung": title, "Diễn giải": detail})

    for flag in build_flags(company, annual_df=annual_df, quarterly_df=quarterly_df):
        level = {"good": "Tốt", "risk": "Cảnh báo", "watch": "Theo dõi"}.get(flag.get("level", ""), "Theo dõi")
        add("Tổng quan", level, flag.get("title", ""), flag.get("detail", ""))

    if annual_df is not None and not annual_df.empty:
        cf_score = build_cashflow_scorecard(annual_df)
        if not cf_score.empty:
            total = cf_score[cf_score["Nhóm tiêu chí"].astype(str).str.contains("TỔNG", na=False)]
            if not total.empty:
                r = total.iloc[0]
                add("FCF & dòng tiền", str(r.get("Tín hiệu", "Theo dõi")), str(r.get("Nhóm tiêu chí", "Tổng điểm dòng tiền")), f"{r.get('Điểm')}/{r.get('Trọng số')} điểm. {r.get('Nhận xét tự động')}")
            for _, r in cf_score[~cf_score["Nhóm tiêu chí"].astype(str).str.contains("TỔNG", na=False)].iterrows():
                add("FCF & dòng tiền", str(r.get("Tín hiệu", "Theo dõi")), str(r.get("Nhóm tiêu chí", "")), f"{r.get('Điểm')}/{r.get('Trọng số')} điểm. {r.get('Nhận xét tự động')}")
        cf_alerts = build_cashflow_situation_alerts(annual_df)
        for _, r in cf_alerts.iterrows():
            add("Tình huống dòng tiền", str(r.get("Mức độ", "Theo dõi")), str(r.get("Tình huống", "")), str(r.get("Diễn giải", "")))

        ratio_score = build_financial_ratio_scorecard(annual_df)
        if not ratio_score.empty:
            total = ratio_score[ratio_score["Nhóm tiêu chí"].astype(str).str.contains("TỔNG", na=False)]
            if not total.empty:
                r = total.iloc[0]
                add("Chỉ số tài chính", str(r.get("Tín hiệu", "Theo dõi")), str(r.get("Nhóm tiêu chí", "Tổng điểm chỉ số")), f"{r.get('Điểm')}/{r.get('Trọng số')} điểm. {r.get('Nhận xét tự động')}")
            for _, r in ratio_score[~ratio_score["Nhóm tiêu chí"].astype(str).str.contains("TỔNG", na=False)].iterrows():
                add("Chỉ số tài chính", str(r.get("Tín hiệu", "Theo dõi")), str(r.get("Nhóm tiêu chí", "")), f"{r.get('Điểm')}/{r.get('Trọng số')} điểm. {r.get('Nhận xét tự động')}")
        ratio_alerts = build_financial_ratio_alerts(annual_df)
        for _, r in ratio_alerts.iterrows():
            add("Tình huống chỉ số", str(r.get("Mức độ", "Theo dõi")), str(r.get("Tình huống", "")), str(r.get("Diễn giải", "")))

    if valuation_df is not None and not valuation_df.empty:
        for _, r in valuation_df.iterrows():
            mos_col = "Giá MOS chọn (đ/cp)" if "Giá MOS chọn (đ/cp)" in valuation_df.columns else "Giá MOS 50% (đ/cp)"
            _raw_mos_level = _to_float(r.get("Mức MOS áp dụng (%)"))
            mos_level = 50 if _raw_mos_level is None else _raw_mos_level
            add("Định giá MOS", str(r.get("Tín hiệu", "Theo dõi")), str(r.get("Phương pháp", "")), f"Giá MOS {mos_level:.0f}%: {_fmt_num(_to_float(r.get(mos_col)), ' đ/cp', 0)}; giá trị nội tại: {_fmt_num(_to_float(r.get('Giá trị nội tại (đ/cp)')), ' đ/cp', 0)}. {r.get('Diễn giải', '')}")
    if not rows:
        add("Tổng quan", "Theo dõi", "Chưa đủ dữ liệu", "Cần cập nhật đầy đủ dữ liệu năm/quý, dòng tiền và giá thị trường để app đánh giá tự động.")
    return pd.DataFrame(rows)

def build_flags(c: CompanyOverview, annual_df: Optional[pd.DataFrame] = None, quarterly_df: Optional[pd.DataFrame] = None) -> List[Dict[str, str]]:
    """Create rule-based quick alerts for Tổng quan doanh nghiệp + extended historical metrics."""
    flags: List[Dict[str, str]] = []

    if c.roe is not None and c.roic is not None:
        if c.roe >= 15 and c.roic >= 12:
            flags.append({"level": "good", "title": "Hiệu quả sinh lời tốt", "detail": "ROE và ROIC đều ở vùng tích cực."})
        elif c.roe < 8 or c.roic < 6:
            flags.append({"level": "risk", "title": "Hiệu quả sinh lời yếu", "detail": "ROE hoặc ROIC thấp, cần kiểm tra sâu ở phần chỉ số tài chính."})
        else:
            flags.append({"level": "watch", "title": "Hiệu quả ở mức trung bình", "detail": "Cần so sánh thêm với trung vị ngành."})

    if c.pe is not None:
        if c.pe <= 0:
            flags.append({"level": "risk", "title": "P/E không có ý nghĩa", "detail": "EPS âm hoặc gần 0; không nên kết luận rẻ theo P/E."})
        elif c.pe > 25:
            flags.append({"level": "watch", "title": "P/E cao", "detail": "Định giá theo lợi nhuận kế toán đang cao; cần kiểm tra tăng trưởng và dòng tiền."})
        elif c.pe < 8:
            flags.append({"level": "watch", "title": "P/E thấp", "detail": "Có thể hấp dẫn nhưng cần kiểm tra rủi ro chu kỳ, chất lượng lợi nhuận và FCF."})

    hist = annual_df if annual_df is not None and not annual_df.empty else quarterly_df
    if hist is not None and not hist.empty:
        h = ensure_derived_metrics(hist).tail(5)
        if "cfo_bil" in h.columns and "net_profit_bil" in h.columns:
            latest = h.tail(1).iloc[0]
            if pd.notna(latest.get("net_profit_bil")) and latest.get("net_profit_bil") > 0 and pd.notna(latest.get("cfo_bil")) and latest.get("cfo_bil") < 0:
                flags.append({"level": "risk", "title": "LNST dương nhưng CFO âm", "detail": "Chất lượng lợi nhuận cần kiểm tra kỹ; lợi nhuận chưa chuyển hóa thành tiền."})
        if "free_cash_flow_bil" in h.columns:
            fcf_neg = (pd.to_numeric(h["free_cash_flow_bil"], errors="coerce") < 0).sum()
            if fcf_neg >= 2:
                flags.append({"level": "risk", "title": "FCF âm nhiều kỳ", "detail": "Cần bóc tách Capex, vốn lưu động và nhu cầu đầu tư duy trì."})
        if "owner_earnings_bil" in h.columns and "free_cash_flow_bil" in h.columns:
            latest = h.tail(1).iloc[0]
            if pd.notna(latest.get("free_cash_flow_bil")) and pd.notna(latest.get("owner_earnings_bil")):
                gap = abs(latest["owner_earnings_bil"] - latest["free_cash_flow_bil"])
                base = max(abs(latest["free_cash_flow_bil"]), 1)
                if gap / base > 0.35:
                    flags.append({"level": "watch", "title": "OE lệch đáng kể so với FCF", "detail": "Owner Earnings khác FCF, nên xem lại Maintenance Capex và các khoản phi tiền mặt."})
        if "cfo_to_net_profit" in h.columns:
            latest_ratio = pd.to_numeric(h["cfo_to_net_profit"], errors="coerce").dropna()
            if not latest_ratio.empty and latest_ratio.iloc[-1] < 0.8:
                flags.append({"level": "watch", "title": "CFO/LNST thấp", "detail": "Lợi nhuận chưa chuyển hóa tốt thành tiền; cần kiểm tra phải thu, tồn kho, phải trả."})

    if not flags:
        flags.append({"level": "watch", "title": "Chưa đủ dữ liệu đánh giá", "detail": "Cần cập nhật đầy đủ chỉ số và dữ liệu ngành."})
    return flags


def build_quick_summary(c: CompanyOverview, annual_df: Optional[pd.DataFrame] = None) -> str:
    """Generate a concise Vietnamese business overview summary."""
    parts = [
        f"{c.ticker} - {c.company_name} đang niêm yết trên {c.exchange}, thuộc ngành {c.industry} / {c.sub_industry}.",
        f"Quy mô vốn hóa khoảng {_fmt_money_bil(c.market_cap_bil)}, số lượng cổ phiếu lưu hành khoảng {_fmt_num(c.shares_outstanding_mil, ' triệu cp', 2)}.",
        f"Giá hiện tại {_fmt_num(c.current_price, ' đồng/cp', 0)}, EPS {_fmt_num(c.eps, ' đồng/cp', 0)}; P/E {_fmt_ratio(c.pe)}, P/B {_fmt_ratio(c.pb)}, P/S {_fmt_ratio(c.ps)}.",
        f"Hiệu quả sinh lời: ROE {_fmt_pct(c.roe)}, ROA {_fmt_pct(c.roa)}, ROIC {_fmt_pct(c.roic)}.",
    ]
    if annual_df is not None and not annual_df.empty:
        df = ensure_derived_metrics(annual_df)
        if "period" in df.columns:
            ttm_rows = df[df["period"].astype(str).str.upper().isin(["TTM", "T12M"])]
            latest = ttm_rows.iloc[-1] if not ttm_rows.empty else df.tail(1).iloc[0]
        else:
            latest = df.tail(1).iloc[0]
        df = df.tail(10)
        if "revenue_bil" in df.columns and "net_profit_bil" in df.columns:
            parts.append(f"Năm/kỳ gần nhất: doanh thu {_fmt_money_bil(latest.get('revenue_bil'))}, LNST {_fmt_money_bil(latest.get('net_profit_bil'))}.")
        if "free_cash_flow_bil" in df.columns and "owner_earnings_bil" in df.columns:
            parts.append(f"Dòng tiền: FCF {_fmt_money_bil(latest.get('free_cash_flow_bil'))}, Owner Earnings {_fmt_money_bil(latest.get('owner_earnings_bil'))}.")
    flags = build_flags(c, annual_df=annual_df)
    risk = [f["title"] for f in flags if f["level"] == "risk"]
    good = [f["title"] for f in flags if f["level"] == "good"]
    if risk:
        parts.append("Nhận xét nhanh: cần thận trọng, trọng tâm kiểm tra là " + "; ".join(risk[:2]) + ".")
    elif good:
        parts.append("Nhận xét nhanh: nền tảng sinh lời tích cực; cần xác nhận thêm chất lượng CFO, FCF và Owner Earnings.")
    else:
        parts.append("Nhận xét nhanh: cần theo dõi thêm khi so sánh với trung vị ngành và dữ liệu dòng tiền.")
    return " ".join(parts)


def build_metric_dict(c: CompanyOverview) -> Dict[str, str]:
    return {
        "Mã cổ phiếu": c.ticker,
        "Tên công ty": c.company_name,
        "Sàn": c.exchange,
        "Ngành": c.industry,
        "Phân ngành": c.sub_industry,
        "Vốn hóa": _fmt_money_bil(c.market_cap_bil),
        "Cổ phiếu lưu hành": _fmt_num(c.shares_outstanding_mil, " triệu cp", 2),
        "Giá hiện tại": _fmt_num(c.current_price, " đồng/cp", 0),
        "EPS": _fmt_num(c.eps, " đồng/cp", 0),
        "P/E": _fmt_ratio(c.pe),
        "P/B": _fmt_ratio(c.pb),
        "P/S": _fmt_ratio(c.ps),
        "ROE": _fmt_pct(c.roe),
        "ROA": _fmt_pct(c.roa),
        "ROIC": _fmt_pct(c.roic),
        "Cập nhật": c.updated_at or "N/A",
    }


def latest_metric_cards(df: pd.DataFrame) -> Dict[str, str]:
    if df.empty:
        return {}
    df = ensure_derived_metrics(df)
    if "period" in df.columns:
        ttm = df[df["period"].astype(str).str.upper().isin(["TTM", "T12M"])]
        latest = ttm.iloc[-1] if not ttm.empty else df.tail(1).iloc[0]
    else:
        latest = df.tail(1).iloc[0]
    return {
        "Kỳ dữ liệu": str(latest.get("period", "")),
        "Doanh thu": _fmt_money_bil(latest.get("revenue_bil")),
        "LNST": _fmt_money_bil(latest.get("net_profit_bil")),
        "CFO": _fmt_money_bil(latest.get("cfo_bil")),
        "FCF": _fmt_money_bil(latest.get("free_cash_flow_bil")),
        "Owner Earnings": _fmt_money_bil(latest.get("owner_earnings_bil")),
        "ROE": _fmt_pct(latest.get("roe_pct")),
        "ROE thực tế": _fmt_pct(latest.get("roe_actual_pct")),
        "ROIC": _fmt_pct(latest.get("roic_pct")),
        "ROIC Operating Profit": _fmt_pct(latest.get("roic_operating_profit_pct")),
        "ROIC Owner Earnings": _fmt_pct(latest.get("roic_owner_earnings_pct")),
        "ROIC Li Lu/Deployed": _fmt_pct(latest.get("roic_lilu_pct")),
        "Capital Employed": _fmt_money_bil(latest.get("capital_employed_bil")),
        "Deployed Capital": _fmt_money_bil(latest.get("deployed_capital_bil")),
        "Core Operating Profit": _fmt_money_bil(latest.get("core_operating_profit_bil")),
        "EPS": _fmt_num(latest.get("eps_vnd"), " đồng/cp", 0),
        "OEPS": _fmt_num(latest.get("oeps_vnd"), " đồng/cp", 0),
        "Tỷ suất cổ tức": _fmt_pct(latest.get("cash_dividend_yield_pct")),
    }


def chart_frame(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    if df.empty:
        return df
    keep = ["period"] + [c for c in columns if c in df.columns]
    out = df[keep].copy()
    # Force text labels so Streamlit charts do not display year values as 2024.0.
    out["period"] = out["period"].astype(str).str.replace(r"\.0$", "", regex=True)
    out = out.drop_duplicates("period", keep="last")
    out = out.set_index("period")
    return out.apply(pd.to_numeric, errors="coerce")



def _format_fcf_value(value: Any, kind: str) -> str:
    num = _to_float(value)
    if num is None:
        return ""
    if kind == "pct":
        return f"{num * 100:,.1f}%"
    if kind == "ratio":
        return f"{num:,.1f} lần"
    if kind == "vnd":
        return f"{num:,.0f}"
    # money in tỷ đồng: no decimals; other numeric values: one decimal.
    if kind == "money":
        return f"{num:,.0f}"
    return f"{num:,.1f}"


def build_fcf_analysis_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build a transposed FCF analysis table inspired by FCF-Years and FCF-Quaters.

    Rows follow the user's Excel model:
    - Business model: NIBT -> non-cash adjustments -> change in working capital -> capex -> FCF.
    - Use of cash: FCF -> debt repayment/borrowing, dividends, capex, investments, buyback, cash+STI.
    - Owner earnings: FCF versus owner earnings and OEPS/EPS.
    """
    if df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(df).copy()
    src["period"] = src["period"].astype(str).str.replace(r"\.0$", "", regex=True)
    specs = [
        ("(I) PHÂN TÍCH BUSINESS MODEL", None, "section"),
        ("(1) Net Income Before Tax - NIBT", "pretax_profit_bil", "money"),
        ("(2) Điều chỉnh phi tiền mặt/D&A", "noncash_adjustments_bil", "money"),
        ("% D&A / NIBT", "noncash_to_pretax", "pct"),
        ("(3) Chênh lệch vốn lưu động - Change in WC", "working_capital_change_bil", "money"),
        ("% WC / NIBT", "wc_to_pretax", "pct"),
        ("(4) Capex", "capex_bil", "money"),
        ("% Capex / NIBT", "capex_to_pretax", "pct"),
        ("Free Cash Flow - FCF", "free_cash_flow_bil", "money"),
        ("% FCF / NIBT", "fcf_to_pretax", "pct"),
        ("% FCF / NIAT - FCF Conversion", "fcf_to_net_profit", "pct"),
        ("", None, "blank"),
        ("(II) PHÂN TÍCH SINH TIỀN - DỤNG TIỀN", None, "section"),
        ("Free Cash Flow - FCF", "free_cash_flow_bil", "money"),
        ("Trả/vay nợ ròng", "net_debt_cashflow_bil", "money"),
        ("Cổ tức đã trả", "cash_dividend_bil", "money"),
        ("Capex (đã trừ khi tính FCF)", "capex_bil", "money"),
        ("Đầu tư vào công ty con/liên kết", "investment_subsidiary_bil", "money"),
        ("Mua cổ phiếu quỹ", "buyback_bil", "money"),
        ("Tăng/giảm tiền & đầu tư tài chính ngắn hạn trong kỳ", "cash_and_short_investments_change_bil", "money"),
        ("", None, "blank"),
        ("(III) PHÂN TÍCH OWNER EARNINGS", None, "section"),
        ("Owner Earnings", "owner_earnings_bil", "money"),
        ("Free Cash Flow - FCF", "free_cash_flow_bil", "money"),
        ("Maintenance Capex ước tính", "maintenance_capex_bil", "money"),
        ("OEPS", "oeps_vnd", "vnd"),
        ("EPS", "eps_vnd", "vnd"),
        ("CFO/LNST", "cfo_to_net_profit", "pct"),
        ("FCF/LNST", "fcf_to_net_profit", "pct"),
    ]
    rows: list[dict[str, Any]] = []
    periods = src["period"].tolist()
    for label, col, kind in specs:
        row: dict[str, Any] = {"Nhóm / chỉ tiêu": label}
        if kind in {"section", "blank"}:
            for period in periods:
                row[period] = ""
        else:
            for _, rec in src.iterrows():
                period = str(rec.get("period", ""))
                row[period] = _format_fcf_value(rec.get(col) if col in src.columns else None, kind)
        rows.append(row)
    return pd.DataFrame(rows)



def _num_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _score_pct(value: float, full: float, partial: float, weight: float, reverse: bool = False) -> float:
    if value is None or pd.isna(value):
        return 0.0
    if not reverse:
        if value >= full:
            return weight
        if value >= partial:
            return weight * 0.5
    else:
        if value <= full:
            return weight
        if value <= partial:
            return weight * 0.5
    return 0.0


def build_cashflow_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    """Automatic FCF/cash-flow quality scorecard.

    The scorecard follows the criteria agreed with the user:
    CFO quality, FCF quality, Owner Earnings, working capital, capex intensity, and use of cash.
    It is intentionally rule-based and transparent so each result can be inspected and adjusted.
    """
    if df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(df).copy()
    if src.empty:
        return pd.DataFrame()
    src = src.tail(min(len(src), 10)).copy()
    latest = src.iloc[-1]
    rows: list[dict[str, Any]] = []

    def add(group: str, weight: float, score: float, signal: str, note: str) -> None:
        rows.append({
            "Nhóm tiêu chí": group,
            "Trọng số": weight,
            "Điểm": round(max(0.0, min(weight, score)), 1),
            "Tỷ lệ đạt": round(max(0.0, min(weight, score)) / weight * 100, 1) if weight else None,
            "Tín hiệu": signal,
            "Nhận xét tự động": note,
        })

    cfo = _num_series(src, "cfo_bil")
    ni = _num_series(src, "net_profit_bil")
    fcf = _num_series(src, "free_cash_flow_bil")
    oe = _num_series(src, "owner_earnings_bil")
    wc = _num_series(src, "working_capital_change_bil")
    nibt = _num_series(src, "pretax_profit_bil")
    capex = _num_series(src, "capex_bil")
    net_debt_cf = _num_series(src, "net_debt_cashflow_bil")
    div = _num_series(src, "cash_dividend_bil")
    cash_change = _num_series(src, "cash_and_short_investments_change_bil")

    cfo_positive_rate = float((cfo > 0).mean()) if cfo.notna().any() else float("nan")
    latest_cfo_to_ni = _to_float(latest.get("cfo_to_net_profit"))
    median_cfo_to_ni = float((cfo / ni.where(ni != 0)).replace([math.inf, -math.inf], pd.NA).median(skipna=True)) if ni.notna().any() else float("nan")
    score = 0
    score += _score_pct(cfo_positive_rate, 0.8, 0.6, 8)
    score += _score_pct(latest_cfo_to_ni, 1.0, 0.8, 7)
    score += _score_pct(median_cfo_to_ni, 0.8, 0.5, 5)
    add("1. Chất lượng CFO", 20, score,
        "Tốt" if score >= 15 else "Theo dõi" if score >= 8 else "Cảnh báo",
        f"CFO dương {cfo_positive_rate:.0%} số kỳ; CFO/LNST kỳ gần nhất {latest_cfo_to_ni:.2f} lần." if pd.notna(latest_cfo_to_ni) else "Thiếu dữ liệu CFO/LNST để đánh giá đầy đủ.")

    fcf_positive_rate = float((fcf > 0).mean()) if fcf.notna().any() else float("nan")
    latest_fcf_to_ni = _to_float(latest.get("fcf_to_net_profit"))
    score = 0
    score += _score_pct(fcf_positive_rate, 0.7, 0.5, 8)
    score += _score_pct(latest_fcf_to_ni, 0.8, 0.5, 7)
    score += 5 if _to_float(latest.get("free_cash_flow_bil")) is not None and _to_float(latest.get("free_cash_flow_bil")) > 0 else 0
    add("2. Chất lượng FCF", 20, score,
        "Tốt" if score >= 15 else "Theo dõi" if score >= 8 else "Cảnh báo",
        f"FCF dương {fcf_positive_rate:.0%} số kỳ; FCF/LNST kỳ gần nhất {latest_fcf_to_ni:.2f} lần." if pd.notna(latest_fcf_to_ni) else "Thiếu dữ liệu FCF/LNST để đánh giá đầy đủ.")

    oe_positive_rate = float((oe > 0).mean()) if oe.notna().any() else float("nan")
    oe_to_ni = (oe / ni.where(ni != 0)).replace([math.inf, -math.inf], pd.NA)
    latest_oe_to_ni = float(oe_to_ni.iloc[-1]) if len(oe_to_ni) and pd.notna(oe_to_ni.iloc[-1]) else float("nan")
    score = 0
    score += _score_pct(oe_positive_rate, 0.7, 0.5, 8)
    score += _score_pct(latest_oe_to_ni, 0.8, 0.5, 7)
    score += 5 if _to_float(latest.get("owner_earnings_bil")) is not None and _to_float(latest.get("owner_earnings_bil")) > 0 else 0
    add("3. Owner Earnings", 20, score,
        "Tốt" if score >= 15 else "Theo dõi" if score >= 8 else "Cảnh báo",
        f"Owner Earnings dương {oe_positive_rate:.0%} số kỳ; OE/LNST kỳ gần nhất {latest_oe_to_ni:.2f} lần." if pd.notna(latest_oe_to_ni) else "Thiếu dữ liệu Owner Earnings/LNST để đánh giá đầy đủ.")

    wc_abs_to_nibt = (wc.abs() / nibt.abs().where(nibt != 0)).replace([math.inf, -math.inf], pd.NA)
    latest_wc_ratio = float(wc_abs_to_nibt.iloc[-1]) if len(wc_abs_to_nibt) and pd.notna(wc_abs_to_nibt.iloc[-1]) else float("nan")
    median_wc_ratio = float(wc_abs_to_nibt.median(skipna=True)) if wc_abs_to_nibt.notna().any() else float("nan")
    score = 0
    score += _score_pct(latest_wc_ratio, 0.3, 0.5, 8, reverse=True)
    score += _score_pct(median_wc_ratio, 0.3, 0.5, 7, reverse=True)
    add("4. Vốn lưu động", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        f"|ΔWC|/LNTT kỳ gần nhất {latest_wc_ratio:.1%}; trung vị {median_wc_ratio:.1%}." if pd.notna(latest_wc_ratio) else "Thiếu dữ liệu thay đổi vốn lưu động.")

    capex_to_cfo = (capex.abs() / cfo.abs().where(cfo != 0)).replace([math.inf, -math.inf], pd.NA)
    latest_capex_ratio = float(capex_to_cfo.iloc[-1]) if len(capex_to_cfo) and pd.notna(capex_to_cfo.iloc[-1]) else float("nan")
    score = _score_pct(latest_capex_ratio, 0.5, 0.8, 10, reverse=True)
    add("5. Capex & cường độ đầu tư", 10, score,
        "Tốt" if score >= 8 else "Theo dõi" if score >= 5 else "Cảnh báo",
        f"ABS(Capex)/CFO kỳ gần nhất {latest_capex_ratio:.1%}." if pd.notna(latest_capex_ratio) else "Thiếu dữ liệu Capex/CFO.")

    latest_fcf = _to_float(latest.get("free_cash_flow_bil"))
    latest_debt = _to_float(latest.get("net_debt_cashflow_bil"))
    latest_div = _to_float(latest.get("cash_dividend_bil"))
    latest_cash_change = _to_float(latest.get("cash_and_short_investments_change_bil"))
    score = 0
    if latest_fcf is not None and latest_fcf > 0:
        score += 5
        if latest_debt is not None and latest_debt < 0:
            score += 4
        if latest_cash_change is not None and latest_cash_change >= 0:
            score += 3
        if latest_div is None or abs(latest_div) <= abs(latest_fcf):
            score += 3
    else:
        if latest_debt is not None and latest_debt > 0:
            score += 0
        elif latest_cash_change is not None and latest_cash_change >= 0:
            score += 3
    add("6. Sử dụng dòng tiền", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        "Đánh giá FCF so với vay/trả nợ ròng, cổ tức và tăng/giảm tiền + ĐTTC trong kỳ.")

    total_weight = sum(r["Trọng số"] for r in rows)
    total_score = sum(r["Điểm"] for r in rows)
    rows.append({
        "Nhóm tiêu chí": "TỔNG ĐIỂM DÒNG TIỀN",
        "Trọng số": total_weight,
        "Điểm": round(total_score, 1),
        "Tỷ lệ đạt": round(total_score / total_weight * 100, 1) if total_weight else None,
        "Tín hiệu": "Tốt" if total_score >= 75 else "Theo dõi" if total_score >= 50 else "Cảnh báo",
        "Nhận xét tự động": "Điểm tổng hợp theo bộ tiêu chí CFO, FCF, Owner Earnings, vốn lưu động, capex và sử dụng dòng tiền.",
    })
    return pd.DataFrame(rows)


def build_cashflow_situation_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Return automatic cash-flow situation labels and warnings."""
    if df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(df).copy()
    if src.empty:
        return pd.DataFrame()
    latest = src.iloc[-1]
    alerts: list[dict[str, Any]] = []

    def add(situation: str, level: str, detail: str) -> None:
        alerts.append({"Tình huống": situation, "Mức độ": level, "Diễn giải": detail})

    fcf = _to_float(latest.get("free_cash_flow_bil"))
    cfo = _to_float(latest.get("cfo_bil"))
    ni = _to_float(latest.get("net_profit_bil"))
    wc_ratio = _to_float(latest.get("wc_to_pretax"))
    capex = _to_float(latest.get("capex_bil"))
    net_debt_cf = _to_float(latest.get("net_debt_cashflow_bil"))
    cash_change = _to_float(latest.get("cash_and_short_investments_change_bil"))
    div = _to_float(latest.get("cash_dividend_bil"))
    cfo_to_ni = _to_float(latest.get("cfo_to_net_profit"))
    fcf_to_ni = _to_float(latest.get("fcf_to_net_profit"))

    if ni and ni > 0 and cfo and cfo > ni and fcf and fcf > 0 and cfo_to_ni and cfo_to_ni >= 1 and fcf_to_ni and fcf_to_ni >= 0.8:
        add("Dòng tiền mạnh", "Tốt", "LNST chuyển hóa tốt thành CFO và FCF; doanh nghiệp có khả năng tự tài trợ tốt.")
    if ni and ni > 0 and ((cfo is not None and cfo < 0) or (cfo_to_ni is not None and cfo_to_ni < 0.5) or (fcf is not None and fcf < 0)):
        add("Lợi nhuận tăng nhưng dòng tiền yếu", "Cảnh báo", "Cần kiểm tra phải thu, tồn kho, chính sách ghi nhận doanh thu và chất lượng lợi nhuận.")
    if wc_ratio is not None and pd.notna(wc_ratio) and abs(wc_ratio) > 0.3:
        add("Bị hút tiền vào vốn lưu động", "Cảnh báo" if abs(wc_ratio) > 0.5 else "Theo dõi", "Thay đổi vốn lưu động lớn so với LNTT; cần kiểm tra phải thu, tồn kho, phải trả.")
    if cfo not in [None, 0] and capex is not None and abs(capex) / abs(cfo) > 0.8:
        add("Capex nặng", "Cảnh báo" if abs(capex) > abs(cfo) else "Theo dõi", "Capex tiêu thụ phần lớn CFO; cần phân biệt growth capex và maintenance capex.")
    if cfo and cfo > 0 and fcf and fcf < 0:
        add("FCF âm do đầu tư", "Theo dõi", "Nếu capex phục vụ mở rộng và tăng trưởng sau đầu tư tốt thì chưa nhất thiết xấu.")
    if fcf is not None and div is not None and div < 0 and (fcf <= 0 or abs(div) > abs(fcf) * 0.8):
        add("Cổ tức vượt khả năng FCF", "Cảnh báo", "Cần kiểm tra doanh nghiệp dùng FCF, tiền tích lũy hay vay nợ để trả cổ tức.")
    if fcf is not None and fcf < 0 and net_debt_cf is not None and net_debt_cf > 0:
        add("Vay nợ để bù dòng tiền", "Cảnh báo", "FCF âm trong khi vay ròng dương; cần kiểm tra rủi ro tài chính.")
    if fcf is not None and fcf > 0 and net_debt_cf is not None and net_debt_cf < 0 and (cash_change is None or cash_change >= 0):
        add("Tự tài trợ và trả nợ lành mạnh", "Tốt", "Doanh nghiệp tạo FCF đủ để trả nợ và vẫn duy trì/tăng thanh khoản.")
    if fcf is not None and fcf > 0 and cash_change is not None and cash_change > 0:
        add("Tích lũy tiền/ĐTTC ngắn hạn", "Theo dõi", "Cần đánh giá hiệu quả sử dụng tiền: tái đầu tư, cổ tức, mua cổ phiếu quỹ hay giữ tiền quá nhiều.")
    if not alerts:
        add("Chưa phát hiện tín hiệu nổi bật", "Trung tính", "Dữ liệu kỳ gần nhất chưa kích hoạt các tình huống cảnh báo/tích cực đã thiết lập.")
    return pd.DataFrame(alerts)




def _safe_latest(src: pd.DataFrame, col: str) -> Optional[float]:
    if col not in src.columns or src.empty:
        return None
    val = pd.to_numeric(src[col], errors="coerce").dropna()
    if val.empty:
        return None
    return float(val.iloc[-1])


def _safe_median_recent(src: pd.DataFrame, col: str, n: int = 5) -> Optional[float]:
    if col not in src.columns or src.empty:
        return None
    val = pd.to_numeric(src.tail(n)[col], errors="coerce").dropna()
    if val.empty:
        return None
    return float(val.median())


def _cagr_from_series(series: pd.Series, years: int = 5) -> Optional[float]:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if len(vals) < 2:
        return None
    vals = vals.tail(min(len(vals), years + 1))
    start, end = float(vals.iloc[0]), float(vals.iloc[-1])
    periods = len(vals) - 1
    if periods <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / periods) - 1


def build_financial_ratio_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build the PHÂN TÍCH CHỈ SỐ TC table for the app.

    The table is generated from normalized financial data instead of copying Excel formulas blindly.
    It emphasizes durable growth, profitability on capital, liquidity/leverage, working-capital efficiency and valuation.
    """
    if df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(df).copy()
    src["period"] = src["period"].astype(str).str.replace(r"\.0$", "", regex=True)
    periods = src["period"].tolist()
    specs = [
        ("(I) TĂNG TRƯỞNG", None, "section"),
        ("Tăng trưởng doanh thu YoY", "revenue_growth_yoy_pct", "pct_points"),
        ("Tăng trưởng LNST YoY", "net_profit_growth_yoy_pct", "pct_points"),
        ("Tăng trưởng EPS YoY", "eps_growth_yoy_pct", "pct_points"),
        ("Tăng trưởng tổng tài sản YoY", "total_assets_growth_yoy_pct", "pct_points"),
        ("Tăng trưởng VCSH YoY", "equity_growth_yoy_pct", "pct_points"),
        ("", None, "blank"),
        ("(II) BIÊN LỢI NHUẬN", None, "section"),
        ("Gross Margin", "gross_margin_pct", "pct_points"),
        ("Core Operating Margin", "core_operating_margin_pct", "pct_points"),
        ("Net Profit Margin", "net_margin_pct", "pct_points"),
        ("EBITDA Margin hỗ trợ", "ebitda_margin_pct", "pct_points"),
        ("Thu nhập tài chính/Doanh thu", "financial_income_to_revenue_pct", "pct_points"),
        ("", None, "blank"),
        ("(III) SINH LỜI TRÊN VỐN", None, "section"),
        ("ROE tự tính", "roe_actual_pct", "pct_points"),
        ("ROA tự tính", "roa_actual_pct", "pct_points"),
        ("ROIC chuẩn", "roic_standard_pct", "pct_points"),
        ("ROIC Operating Profit Li Lu", "roic_operating_profit_pct", "pct_points"),
        ("ROIC Owner Earnings Li Lu", "roic_owner_earnings_pct", "pct_points"),
        ("Asset Turnover", "asset_turnover", "ratio"),
        ("Equity Multiplier", "equity_multiplier", "ratio"),
        ("", None, "blank"),
        ("(IV) HIỆU QUẢ HOẠT ĐỘNG & VỐN LƯU ĐỘNG", None, "section"),
        ("Vòng quay phải thu", "receivables_turnover", "ratio"),
        ("DSO - Số ngày phải thu", "dso_days", "days"),
        ("Vòng quay tồn kho", "inventory_turnover", "ratio"),
        ("DIO - Số ngày tồn kho", "dio_days", "days"),
        ("Vòng quay phải trả", "payables_turnover", "ratio"),
        ("DPO - Số ngày phải trả", "dpo_days", "days"),
        ("CCC - Chu kỳ chuyển đổi tiền", "cash_conversion_cycle_days", "days"),
        ("CFO/LNST", "cfo_to_net_profit", "ratio"),
        ("FCF/LNST", "fcf_to_net_profit", "ratio"),
        ("", None, "blank"),
        ("(V) THANH KHOẢN & ĐÒN BẨY", None, "section"),
        ("Current Ratio", "current_ratio", "ratio"),
        ("Quick Ratio", "quick_ratio", "ratio"),
        ("Net Liquid Assets", "net_liquid_assets_bil", "money"),
        ("VCSH/Tổng tài sản", "equity_to_assets_pct", "pct_points"),
        ("Nợ phải trả/Tổng tài sản", "liabilities_to_assets_pct", "pct_points"),
        ("Nợ phải trả/VCSH", "liabilities_to_equity", "ratio"),
        ("Nợ vay ròng/VCSH", "net_debt_to_equity", "ratio"),
        ("Interest Coverage", "interest_coverage", "ratio"),
        ("Net Debt/EBITDA", "net_debt_to_ebitda", "ratio"),
        ("", None, "blank"),
        ("(VI) ĐỊNH GIÁ & DÒNG TIỀN", None, "section"),
        ("EPS", "eps_vnd", "vnd"),
        ("OEPS", "oeps_vnd", "vnd"),
        ("Tỷ suất cổ tức tiền mặt thực tế", "cash_dividend_yield_pct", "pct_points"),
        ("Free Cash Flow", "free_cash_flow_bil", "money"),
        ("Owner Earnings", "owner_earnings_bil", "money"),
    ]
    rows: list[dict[str, Any]] = []
    for label, col, kind in specs:
        row: dict[str, Any] = {"Nhóm / chỉ tiêu": label}
        if kind in {"section", "blank"}:
            for p in periods:
                row[p] = ""
        else:
            for _, rec in src.iterrows():
                p = str(rec.get("period", ""))
                val = rec.get(col) if col in src.columns else None
                row[p] = _format_ratio_value_for_table(val, kind)
        rows.append(row)
    return pd.DataFrame(rows)


def _format_ratio_value_for_table(value: Any, kind: str) -> str:
    num = _to_float(value)
    if num is None:
        return ""
    if kind == "pct_points":
        return f"{num:,.1f}%"
    if kind == "ratio":
        return f"{num:,.1f}"
    if kind == "days":
        return f"{num:,.0f}"
    if kind == "vnd":
        return f"{num:,.0f}"
    if kind == "money":
        return f"{num:,.0f}"
    return f"{num:,.1f}"


def build_financial_ratio_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    """Automatic 100-point financial-ratio scorecard.

    It translates the agreed PHÂN TÍCH CHỈ SỐ TC logic into transparent rules. The score is not a buy/sell
    recommendation; it is a checklist to help apply value-investing discipline and avoid value traps.
    """
    if df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(df).tail(min(len(df), 10)).copy()
    rows: list[dict[str, Any]] = []

    def add(group: str, weight: float, score: float, signal: str, note: str) -> None:
        rows.append({
            "Nhóm tiêu chí": group,
            "Trọng số": weight,
            "Điểm": round(max(0.0, min(weight, score)), 1),
            "Tỷ lệ đạt": round(max(0.0, min(weight, score)) / weight * 100, 1) if weight else None,
            "Tín hiệu": signal,
            "Nhận xét tự động": note,
        })

    rev_cagr = _cagr_from_series(src.get("revenue_bil", pd.Series(dtype="float64")), 5)
    ni_cagr = _cagr_from_series(src.get("net_profit_bil", pd.Series(dtype="float64")), 5)
    eps_cagr = _cagr_from_series(src.get("eps_vnd", pd.Series(dtype="float64")), 5)
    score = 0
    for val, w in [(rev_cagr, 5), (ni_cagr, 5), (eps_cagr, 5)]:
        score += _score_pct(val if val is not None else float("nan"), 0.10, 0.05, w)
    add("1. Tăng trưởng", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        f"CAGR 5 năm: doanh thu {rev_cagr:.1%}, LNST {ni_cagr:.1%}, EPS {eps_cagr:.1%}." if all(v is not None for v in [rev_cagr, ni_cagr, eps_cagr]) else "Không tính CAGR khi dữ liệu đầu kỳ âm/bằng 0 hoặc thiếu dữ liệu.")

    gm = _safe_median_recent(src, "gross_margin_pct")
    nm = _safe_median_recent(src, "net_margin_pct")
    com = _safe_median_recent(src, "core_operating_margin_pct")
    fin_inc = _safe_latest(src, "financial_income_to_revenue_pct")
    score = 0
    score += _score_pct(gm if gm is not None else float("nan"), 30, 20, 5)
    score += _score_pct(nm if nm is not None else float("nan"), 10, 5, 4)
    score += _score_pct(com if com is not None else float("nan"), 10, 5, 4)
    score += _score_pct(fin_inc if fin_inc is not None else float("nan"), 10, 20, 2, reverse=True)
    add("2. Biên lợi nhuận & chất lượng lợi nhuận", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        "Ưu tiên biên lợi nhuận cốt lõi bền vững; cảnh báo nếu lợi nhuận phụ thuộc nhiều vào thu nhập tài chính/bất thường.")

    roe = _safe_median_recent(src, "roe_actual_pct") or _safe_median_recent(src, "roe_pct")
    roa = _safe_median_recent(src, "roa_actual_pct") or _safe_median_recent(src, "roa_pct")
    roic = _safe_median_recent(src, "roic_standard_pct") or _safe_median_recent(src, "roic_pct")
    roic_oe = _safe_median_recent(src, "roic_owner_earnings_pct")
    score = 0
    score += _score_pct(roe if roe is not None else float("nan"), 15, 10, 7)
    score += _score_pct(roa if roa is not None else float("nan"), 8, 5, 5)
    score += _score_pct(roic if roic is not None else float("nan"), 12, 8, 8)
    score += _score_pct(roic_oe if roic_oe is not None else float("nan"), 12, 8, 5)
    add("3. Sinh lời trên vốn", 25, score,
        "Tốt" if score >= 19 else "Theo dõi" if score >= 11 else "Cảnh báo",
        "Trọng tâm Buffett/Li Lu: vốn bỏ vào doanh nghiệp phải tạo lợi nhuận và dòng tiền tốt; ROIC/OE quan trọng hơn chỉ nhìn EPS.")

    cfo_to_ni = _safe_latest(src, "cfo_to_net_profit")
    fcf_to_ni = _safe_latest(src, "fcf_to_net_profit")
    ccc = _safe_latest(src, "cash_conversion_cycle_days")
    dso = _safe_latest(src, "dso_days")
    dio = _safe_latest(src, "dio_days")
    score = 0
    score += _score_pct(cfo_to_ni if cfo_to_ni is not None else float("nan"), 1.0, 0.8, 5)
    score += _score_pct(fcf_to_ni if fcf_to_ni is not None else float("nan"), 0.8, 0.5, 4)
    score += _score_pct(ccc if ccc is not None else float("nan"), 60, 120, 3, reverse=True)
    score += _score_pct(dso if dso is not None else float("nan"), 60, 90, 1.5, reverse=True)
    score += _score_pct(dio if dio is not None else float("nan"), 90, 150, 1.5, reverse=True)
    add("4. Hiệu quả hoạt động & vốn lưu động", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        "Đọc cùng CFO/LNST, FCF/LNST, DSO, DIO, DPO và CCC; không kết luận tốt chỉ vì doanh thu tăng.")

    current_ratio = _safe_latest(src, "current_ratio")
    quick_ratio = _safe_latest(src, "quick_ratio")
    net_debt_to_equity = _safe_latest(src, "net_debt_to_equity")
    interest_coverage = _safe_latest(src, "interest_coverage")
    equity_to_assets = _safe_latest(src, "equity_to_assets_pct")
    score = 0
    score += _score_pct(current_ratio if current_ratio is not None else float("nan"), 1.5, 1.0, 3)
    score += _score_pct(quick_ratio if quick_ratio is not None else float("nan"), 1.0, 0.7, 3)
    score += _score_pct(net_debt_to_equity if net_debt_to_equity is not None else float("nan"), 0.5, 1.0, 3, reverse=True)
    score += _score_pct(interest_coverage if interest_coverage is not None else float("nan"), 5, 3, 3)
    score += _score_pct(equity_to_assets if equity_to_assets is not None else float("nan"), 50, 35, 3)
    add("5. Thanh khoản & đòn bẩy", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        "Ưu tiên bảng cân đối an toàn; đòn bẩy cao có thể làm ROE đẹp nhưng tăng rủi ro suy giảm vốn.")

    latest = src.iloc[-1]
    pe = _to_float(latest.get("pe"))
    fcf = _to_float(latest.get("free_cash_flow_bil"))
    oe = _to_float(latest.get("owner_earnings_bil"))
    div_yield = _to_float(latest.get("cash_dividend_yield_pct"))
    roic_latest = _to_float(latest.get("roic_standard_pct")) or _to_float(latest.get("roic_pct"))
    score = 0
    if fcf is not None and fcf > 0:
        score += 5
    if oe is not None and oe > 0:
        score += 5
    if roic_latest is not None and roic_latest >= 12:
        score += 3
    if div_yield is not None and div_yield > 0:
        score += 2
    add("6. Định giá & biên an toàn sơ bộ", 15, score,
        "Tốt" if score >= 11 else "Theo dõi" if score >= 6 else "Cảnh báo",
        "Không tự động kết luận rẻ/đắt nếu chưa có MOS; P/E thấp nhưng FCF/OE yếu có thể là value trap.")

    total_weight = sum(r["Trọng số"] for r in rows)
    total_score = sum(r["Điểm"] for r in rows)
    rows.append({
        "Nhóm tiêu chí": "TỔNG ĐIỂM CHỈ SỐ TÀI CHÍNH",
        "Trọng số": total_weight,
        "Điểm": round(total_score, 1),
        "Tỷ lệ đạt": round(total_score / total_weight * 100, 1) if total_weight else None,
        "Tín hiệu": "Tốt" if total_score >= 75 else "Theo dõi" if total_score >= 50 else "Cảnh báo",
        "Nhận xét tự động": "Điểm tổng hợp theo triết lý: sở hữu doanh nghiệp chất lượng, bảng cân đối an toàn, dòng tiền thật và biên an toàn khi mua.",
    })
    return pd.DataFrame(rows)


def build_financial_ratio_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Generate value-investing oriented ratio alerts."""
    if df.empty:
        return pd.DataFrame()
    src = ensure_derived_metrics(df).copy()
    if src.empty:
        return pd.DataFrame()
    latest = src.iloc[-1]
    alerts: list[dict[str, Any]] = []

    def add(situation: str, level: str, detail: str) -> None:
        alerts.append({"Tình huống": situation, "Mức độ": level, "Diễn giải": detail})

    roe = _to_float(latest.get("roe_actual_pct")) or _to_float(latest.get("roe_pct"))
    roic = _to_float(latest.get("roic_standard_pct")) or _to_float(latest.get("roic_pct"))
    cfo_to_ni = _to_float(latest.get("cfo_to_net_profit"))
    fcf_to_ni = _to_float(latest.get("fcf_to_net_profit"))
    fcf = _to_float(latest.get("free_cash_flow_bil"))
    ni = _to_float(latest.get("net_profit_bil"))
    gm = _to_float(latest.get("gross_margin_pct"))
    net_debt_to_eq = _to_float(latest.get("net_debt_to_equity"))
    interest_coverage = _to_float(latest.get("interest_coverage"))
    fin_income_ratio = _to_float(latest.get("financial_income_to_revenue_pct"))
    eps_growth = _to_float(latest.get("eps_growth_yoy_pct"))
    ni_growth = _to_float(latest.get("net_profit_growth_yoy_pct"))

    if roe is not None and roic is not None and roe >= 15 and roic >= 12:
        add("Sinh lời trên vốn tốt", "Tốt", "ROE và ROIC đều ở vùng tích cực; cần xác nhận tính bền vững qua CFO, FCF và lợi thế cạnh tranh.")
    if roe is not None and roic is not None and roe >= 15 and roic < 8:
        add("ROE cao nhưng ROIC thấp", "Cảnh báo", "ROE có thể được khuếch đại bởi đòn bẩy hoặc yếu tố kế toán; cần kiểm tra vốn sử dụng và nợ.")
    if ni is not None and ni > 0 and (cfo_to_ni is not None and cfo_to_ni < 0.8 or fcf is not None and fcf < 0):
        add("Lợi nhuận chưa chuyển hóa thành tiền", "Cảnh báo", "Theo Graham/Buffett, lợi nhuận kế toán cần được kiểm chứng bằng dòng tiền; CFO/LNST hoặc FCF đang yếu.")
    if fcf_to_ni is not None and fcf_to_ni >= 0.8 and cfo_to_ni is not None and cfo_to_ni >= 1.0:
        add("Chất lượng lợi nhuận tốt", "Tốt", "CFO và FCF chuyển hóa tốt so với LNST, giảm rủi ro lợi nhuận giấy.")
    if gm is not None and gm < 15:
        add("Biên lợi nhuận gộp mỏng", "Theo dõi", "Biên gộp thấp có thể cho thấy cạnh tranh cao hoặc ít quyền định giá; cần so sánh với ngành.")
    if fin_income_ratio is not None and fin_income_ratio > 20:
        add("Lợi nhuận phụ thuộc tài chính", "Theo dõi", "Thu nhập tài chính/doanh thu cao; cần tách hoạt động cốt lõi khỏi tiền nhàn rỗi/đầu tư tài chính.")
    if net_debt_to_eq is not None and net_debt_to_eq > 1:
        add("Đòn bẩy tài chính cao", "Cảnh báo", "Nợ vay ròng/VCSH cao; cần kiểm tra khả năng chịu đựng chu kỳ xấu.")
    if interest_coverage is not None and interest_coverage < 3:
        add("Khả năng trả lãi yếu", "Cảnh báo", "Interest coverage dưới 3 lần; cần kiểm tra rủi ro lãi vay và thanh khoản.")
    if eps_growth is not None and ni_growth is not None and ni_growth > 10 and eps_growth < ni_growth * 0.5:
        add("Có thể pha loãng EPS", "Theo dõi", "LNST tăng nhanh hơn EPS; cần kiểm tra phát hành thêm/cổ phiếu lưu hành.")
    if not alerts:
        add("Chưa phát hiện tín hiệu nổi bật", "Trung tính", "Các chỉ tiêu chưa kích hoạt cảnh báo/tích cực; cần đọc cùng ngành, chu kỳ và định giá MOS.")
    return pd.DataFrame(alerts)


def build_value_investing_assessment(company: CompanyOverview, annual_df: pd.DataFrame, ratio_scorecard: Optional[pd.DataFrame] = None) -> str:
    """Generate a concise assessment aligned with Graham/Buffett/Li Lu/Howard Marks.

    The wording avoids buy/sell recommendations and emphasizes business ownership, risk control, cash flow,
    capital allocation and margin of safety.
    """
    df = ensure_derived_metrics(annual_df).copy() if annual_df is not None and not annual_df.empty else pd.DataFrame()
    score = None
    signal = "Theo dõi"
    if isinstance(ratio_scorecard, pd.DataFrame) and not ratio_scorecard.empty:
        total = ratio_scorecard[ratio_scorecard["Nhóm tiêu chí"].astype(str).str.contains("TỔNG", na=False)]
        if not total.empty:
            score = _to_float(total.iloc[0].get("Điểm"))
            signal = str(total.iloc[0].get("Tín hiệu", signal))
    latest = df.iloc[-1] if not df.empty else {}
    roe = _to_float(latest.get("roe_actual_pct")) if hasattr(latest, "get") else company.roe
    roic = _to_float(latest.get("roic_standard_pct")) if hasattr(latest, "get") else company.roic
    cfo_to_ni = _to_float(latest.get("cfo_to_net_profit")) if hasattr(latest, "get") else None
    fcf = _to_float(latest.get("free_cash_flow_bil")) if hasattr(latest, "get") else None
    oe = _to_float(latest.get("owner_earnings_bil")) if hasattr(latest, "get") else None
    net_debt_to_eq = _to_float(latest.get("net_debt_to_equity")) if hasattr(latest, "get") else None
    parts = []
    if score is not None:
        parts.append(f"Bộ chỉ số tài chính V22 chấm **{score:.1f}/100 điểm**, tín hiệu **{signal}**. ")
    if roe is not None and roic is not None:
        if roe >= 15 and roic >= 12:
            parts.append("Hiệu quả sinh lời trên vốn đang tích cực, phù hợp tiêu chí doanh nghiệp có khả năng tạo lợi nhuận tốt trên vốn triển khai. ")
        elif roe >= 15 and roic < 8:
            parts.append("ROE nhìn tốt nhưng ROIC chưa tương xứng; cần tránh bẫy ROE đẹp do đòn bẩy hoặc vốn sử dụng bị tính chưa đúng. ")
        else:
            parts.append("Hiệu quả sinh lời chưa đủ nổi bật; nên so sánh thêm với trung vị ngành và chu kỳ kinh doanh. ")
    if cfo_to_ni is not None:
        if cfo_to_ni >= 1:
            parts.append("Chất lượng lợi nhuận được hỗ trợ bởi CFO/LNST tốt, đây là điểm cộng theo góc nhìn dòng tiền thật. ")
        elif cfo_to_ni < 0.8:
            parts.append("CFO/LNST thấp, cần kiểm tra phải thu, tồn kho và các khoản điều chỉnh vốn lưu động trước khi tin vào lợi nhuận kế toán. ")
    if fcf is not None and oe is not None:
        if fcf > 0 and oe > 0:
            parts.append("FCF và Owner Earnings dương, cho thấy doanh nghiệp có khả năng tạo tiền cho chủ sở hữu sau nhu cầu đầu tư duy trì/Capex. ")
        elif fcf < 0:
            parts.append("FCF âm; cần phân biệt FCF âm do đầu tư mở rộng có hiệu quả với FCF âm do mô hình kinh doanh hút tiền. ")
    if net_debt_to_eq is not None:
        if net_debt_to_eq <= 0:
            parts.append("Bảng cân đối có vị thế tiền ròng/ít nợ, giúp doanh nghiệp chống chịu tốt hơn khi chu kỳ xấu. ")
        elif net_debt_to_eq > 1:
            parts.append("Đòn bẩy cao làm tăng rủi ro suy giảm vốn; theo tinh thần Howard Marks, ưu tiên kiểm soát rủi ro trước khi tìm lợi nhuận. ")
    parts.append("Kết luận của app không phải khuyến nghị mua/bán: cần định giá MOS riêng, hiểu bear case và chỉ hành động khi giá trả đủ hấp dẫn so với giá trị nội tại.")
    return "".join(parts)


def format_table_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = [
        "period", "revenue_bil", "gross_profit_bil", "operating_profit_bil", "core_operating_profit_bil", "net_profit_bil",
        "cash_dividend_bil", "cash_dividend_yield_pct", "year_end_price", "cfo_bil", "free_cash_flow_bil", "owner_earnings_bil", "maintenance_capex_bil",
        "noncash_adjustments_bil", "working_capital_change_bil", "receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "tax_paid_bil",
        "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "buyback_bil", "cash_and_short_investments_change_bil",
        "working_capital_bil", "roic_working_capital_bil", "operating_working_capital_bil", "fixed_assets_bil", "cash_equivalents_bil", "short_term_investments_bil", "capital_employed_bil", "avg_capital_employed_bil", "deployed_capital_bil", "avg_deployed_capital_bil",
        "expansion_investment_bil", "investment_subsidiary_bil", "total_investment_bil", "wacc_pct", "nopat_bil",
        "gross_margin_pct", "core_operating_margin_pct", "net_margin_pct", "ebitda_margin_pct", "financial_income_to_revenue_pct",
        "revenue_growth_yoy_pct", "net_profit_growth_yoy_pct", "eps_growth_yoy_pct", "total_assets_growth_yoy_pct", "equity_growth_yoy_pct",
        "roe_pct", "roe_actual_pct", "roa_pct", "roa_actual_pct", "roic_pct", "roic_operating_profit_pct", "roic_owner_earnings_pct", "roic_standard_pct", "roic_lilu_pct", "roic_fireant_pct", "roe_dupont_pct", "eps_vnd", "oeps_vnd",
        "current_ratio", "quick_ratio", "net_liquid_assets_bil", "equity_to_assets_pct", "liabilities_to_assets_pct", "liabilities_to_equity", "net_debt_to_equity", "interest_coverage", "net_debt_to_ebitda",
        "receivables_turnover", "dso_days", "inventory_turnover", "dio_days", "payables_turnover", "dpo_days", "cash_conversion_cycle_days",
        "cfo_to_net_profit", "fcf_to_net_profit", "fcf_to_pretax",
    ]
    cols = [c for c in cols if c in df.columns]
    renamed = {
        "period": "Kỳ", "revenue_bil": "Doanh thu (tỷ)", "gross_profit_bil": "Lợi nhuận gộp (tỷ)", "operating_profit_bil": "Lợi nhuận thuần HĐKD (tỷ)", "net_profit_bil": "LNST (tỷ)",
        "cash_dividend_bil": "Cổ tức tiền mặt đã trả (tỷ)", "cash_dividend_yield_pct": "Tỷ suất cổ tức (%)", "year_end_price": "Giá cuối năm", "cfo_bil": "CFO (tỷ)",
        "free_cash_flow_bil": "FCF (tỷ)", "owner_earnings_bil": "Owner Earnings (tỷ)", "maintenance_capex_bil": "Maintenance Capex ước tính (tỷ)", "nopat_bil": "NOPAT (tỷ)",
        "noncash_adjustments_bil": "Điều chỉnh phi tiền mặt/D&A (tỷ)", "working_capital_change_bil": "Thay đổi VLĐ (tỷ)", "receivables_change_bil": "Tăng/giảm phải thu (tỷ)", "inventory_change_bil": "Tăng/giảm tồn kho (tỷ)", "payables_change_bil": "Tăng/giảm phải trả (tỷ)", "prepaid_change_bil": "Tăng/giảm trả trước (tỷ)", "tax_paid_bil": "Thuế TNDN đã nộp (tỷ)",
        "debt_raised_bil": "Vay nhận được (tỷ)", "debt_repaid_bil": "Trả nợ gốc vay (tỷ)", "net_debt_cashflow_bil": "Vay/trả nợ ròng (tỷ)", "buyback_bil": "Mua cổ phiếu quỹ (tỷ)", "cash_and_short_investments_change_bil": "Tăng/giảm tiền + ĐTTC ngắn hạn trong kỳ (tỷ)",
        "working_capital_bil": "Working Capital kế toán (tỷ)", "operating_working_capital_bil": "Operating Working Capital (tỷ)", "fixed_assets_bil": "Fixed Assets/Capital Assets (tỷ)", "cash_equivalents_bil": "Tiền & tương đương tiền (tỷ)", "short_term_investments_bil": "ĐTTC ngắn hạn (tỷ)",
        "core_operating_profit_bil": "Operating Profit MOS/Li Lu (tỷ)", "roic_working_capital_bil": "Working Capital ROIC MOS/Li Lu (tỷ)", "capital_employed_bil": "Capital Employed chuẩn (tỷ)", "avg_capital_employed_bil": "Capital Employed bình quân (tỷ)", "deployed_capital_bil": "Deployed Capital MOS/Li Lu (tỷ)", "avg_deployed_capital_bil": "Deployed Capital bình quân MOS/Li Lu (tỷ)",
        "expansion_investment_bil": "Đầu tư mở rộng (tỷ)", "investment_subsidiary_bil": "Đầu tư công ty con/liên kết (tỷ)", "total_investment_bil": "Tổng đầu tư (tỷ)", "wacc_pct": "WACC DN tự tính (%)",
        "roe_pct": "ROE dữ liệu/tự tính (%)", "roe_actual_pct": "ROE tự tính (%)", "roic_pct": "ROIC chính - Operating Profit (%)", "roic_operating_profit_pct": "ROIC Operating Profit (%)", "roic_owner_earnings_pct": "ROIC Owner Earnings (%)", "roic_standard_pct": "ROIC NOPAT/Capital Employed (%)", "roic_lilu_pct": "ROIC Li Lu/Deployed (%)", "roe_dupont_pct": "ROE DuPont (%)", "eps_vnd": "EPS (đ/cp)", "oeps_vnd": "OEPS (đ/cp)",
        "gross_margin_pct": "Gross Margin (%)", "core_operating_margin_pct": "Core Operating Margin (%)", "net_margin_pct": "Net Margin (%)", "ebitda_margin_pct": "EBITDA Margin (%)", "financial_income_to_revenue_pct": "Thu nhập tài chính/Doanh thu (%)",
        "revenue_growth_yoy_pct": "Tăng trưởng doanh thu YoY (%)", "net_profit_growth_yoy_pct": "Tăng trưởng LNST YoY (%)", "eps_growth_yoy_pct": "Tăng trưởng EPS YoY (%)", "total_assets_growth_yoy_pct": "Tăng trưởng tổng tài sản YoY (%)", "equity_growth_yoy_pct": "Tăng trưởng VCSH YoY (%)",
        "roa_pct": "ROA dữ liệu/tự tính (%)", "roa_actual_pct": "ROA tự tính (%)",
        "current_ratio": "Current Ratio", "quick_ratio": "Quick Ratio", "net_liquid_assets_bil": "Net Liquid Assets (tỷ)", "equity_to_assets_pct": "VCSH/Tổng tài sản (%)", "liabilities_to_assets_pct": "Nợ phải trả/Tổng tài sản (%)", "liabilities_to_equity": "Nợ phải trả/VCSH", "net_debt_to_equity": "Nợ vay ròng/VCSH", "interest_coverage": "Interest Coverage", "net_debt_to_ebitda": "Net Debt/EBITDA",
        "receivables_turnover": "Vòng quay phải thu", "dso_days": "DSO (ngày)", "inventory_turnover": "Vòng quay tồn kho", "dio_days": "DIO (ngày)", "payables_turnover": "Vòng quay phải trả", "dpo_days": "DPO (ngày)", "cash_conversion_cycle_days": "CCC (ngày)",
        "cfo_to_net_profit": "CFO/LNST", "fcf_to_net_profit": "FCF/LNST", "fcf_to_pretax": "FCF/LNTT",
    }
    out = df[cols].rename(columns=renamed)
    # Streamlit/pyarrow fails if display column names are duplicated. Enforce unique names defensively.
    seen = {}
    unique_cols = []
    for name in out.columns:
        if name not in seen:
            seen[name] = 0
            unique_cols.append(name)
        else:
            seen[name] += 1
            unique_cols.append(f"{name} ({seen[name] + 1})")
    out.columns = unique_cols
    return out
