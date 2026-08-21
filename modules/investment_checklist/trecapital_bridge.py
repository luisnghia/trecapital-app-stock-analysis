from __future__ import annotations

from copy import copy
from inspect import Parameter, signature
from typing import Any, Optional

import pandas as pd

from .contracts import InventorySourceData


MATERIAL_MISMATCH = 0.30
PRICE_GROSS_MISMATCH = 2.0


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _number(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _preferred_rows(df: pd.DataFrame) -> list[dict]:
    """Return TTM first, then newest-to-oldest rows.

    TTM is preferred for flow metrics. If a TTM cell is blank, the bridge may use the
    closest Trecapital period that actually contains that metric instead of returning a
    misleading blank. No external data are introduced here.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    rows: list[dict] = []
    if "period" in df.columns:
        ttm = df[df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        for _, row in ttm.iloc[::-1].iterrows():
            rows.append(row.to_dict())
    for _, row in df.iloc[::-1].iterrows():
        d = row.to_dict()
        period = str(d.get("period") or "").upper()
        if "TTM" in period or "T12M" in period:
            continue
        rows.append(d)
    return rows


def _latest_row(df: pd.DataFrame) -> dict:
    rows = _preferred_rows(df)
    return rows[0] if rows else {}


def _metric(df: pd.DataFrame, *keys: str) -> tuple[Optional[float], Optional[str]]:
    for row in _preferred_rows(df):
        value = _number(row, *keys)
        if value is not None:
            period = str(row.get("period") or row.get("year") or "kỳ gần nhất")
            return value, period
    return None, None


def _row_ebit(row: dict) -> Optional[float]:
    direct = _number(row, "ebit_bil", "core_operating_profit_bil", "operating_profit_bil")
    if direct is not None:
        return direct
    gross = _number(row, "gross_profit_bil")
    selling = _number(row, "selling_expense_bil")
    admin = _number(row, "admin_expense_bil")
    if gross is not None and (selling is not None or admin is not None):
        return gross - abs(selling or 0.0) - abs(admin or 0.0)
    return None


def _best_ebit(df: pd.DataFrame) -> tuple[Optional[float], Optional[str], bool]:
    for row in _preferred_rows(df):
        direct = _number(row, "ebit_bil", "core_operating_profit_bil", "operating_profit_bil")
        period = str(row.get("period") or row.get("year") or "kỳ gần nhất")
        if direct is not None:
            return direct, period, False
        derived = _row_ebit(row)
        if derived is not None:
            return derived, period, True
    return None, None, False


def _best_ebitda(df: pd.DataFrame) -> tuple[Optional[float], Optional[str], bool]:
    for row in _preferred_rows(df):
        period = str(row.get("period") or row.get("year") or "kỳ gần nhất")
        direct = _number(row, "ebitda_bil")
        if direct is not None:
            return direct, period, False
        ebit = _row_ebit(row)
        da = _number(
            row,
            "depreciation_bil",
            "depreciation_amortization_bil",
            "depreciation_and_amortization_bil",
            "da_bil",
        )
        if ebit is not None and da is not None:
            return ebit + abs(da), period, True
    return None, None, False


def _relative_gap(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or a == 0 or b == 0:
        return None
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _materially_different(a: Optional[float], b: Optional[float], threshold: float = MATERIAL_MISMATCH) -> bool:
    gap = _relative_gap(a, b)
    return gap is not None and gap > threshold


def _infer_shares_from_financials(df: pd.DataFrame) -> tuple[Optional[float], Optional[str]]:
    for row in _preferred_rows(df):
        net_profit = _number(row, "net_profit_bil")
        eps = _number(row, "eps_vnd", "basic_eps_vnd")
        if net_profit is not None and eps is not None and eps > 0:
            shares = net_profit * 1000.0 / eps
            if shares > 0:
                return shares, str(row.get("period") or row.get("year") or "kỳ gần nhất")
    return None, None


def _best_shares_mil(company, df: pd.DataFrame, notes: list[str]) -> Optional[float]:
    direct, direct_period = _metric(df, "shares_outstanding_mil")
    overview = _safe_float(getattr(company, "shares_outstanding_mil", None))
    inferred, inferred_period = _infer_shares_from_financials(df)

    if inferred is not None and direct is not None and _materially_different(direct, inferred):
        notes.append(
            f"Số CP lưu hành TTM ({direct:,.1f} triệu) lệch >30% so với LNST/EPS nội bộ ({inferred:,.1f} triệu); dùng giá trị suy ra từ {inferred_period}."
        )
        return inferred
    if direct is not None and direct > 0:
        if overview is not None and _materially_different(direct, overview):
            notes.append(
                f"Số CP ở Tổng quan ({overview:,.1f} triệu) không khớp BCTC {direct_period} ({direct:,.1f} triệu); ưu tiên BCTC Trecapital."
            )
        return direct
    if inferred is not None:
        notes.append(f"Số CP lưu hành được suy ra từ LNST/EPS Trecapital kỳ {inferred_period}: {inferred:,.1f} triệu.")
        return inferred
    if overview is not None and overview > 0:
        return overview
    return None


def _best_price(company, df: pd.DataFrame, notes: list[str]) -> Optional[float]:
    overview = _safe_float(getattr(company, "current_price", None))
    internal, internal_period = _metric(df, "current_price", "market_price_vnd", "year_end_price")
    if overview is not None and overview > 0 and internal is not None and internal > 0:
        ratio = overview / internal
        if ratio > PRICE_GROSS_MISMATCH or ratio < 1.0 / PRICE_GROSS_MISMATCH:
            notes.append(
                f"Giá Tổng quan {overview:,.0f} đ/cp lệch >2x giá nội bộ gần nhất {internal:,.0f} đ/cp ({internal_period}); dùng giá nội bộ Trecapital để tránh sai đơn vị/mismatch nguồn."
            )
            return internal
    if overview is not None and overview > 0:
        return overview
    if internal is not None and internal > 0:
        notes.append(f"Không có giá hợp lệ ở Tổng quan; dùng giá nội bộ Trecapital {internal_period}: {internal:,.0f} đ/cp.")
        return internal
    return None


def _best_market_cap(company, price: Optional[float], shares_mil: Optional[float], notes: list[str]) -> Optional[float]:
    direct = _safe_float(getattr(company, "market_cap_bil", None))
    computed = None
    if price is not None and shares_mil is not None and price > 0 and shares_mil > 0:
        # VND/share × million shares / 1,000 = billion VND.
        computed = price * shares_mil / 1000.0
    if computed is not None and direct is not None and direct > 0 and _materially_different(direct, computed):
        notes.append(
            f"Vốn hóa Tổng quan {direct:,.0f} tỷ lệch >30% so với Giá×CPLH nội bộ {computed:,.0f} tỷ; dùng {computed:,.0f} tỷ."
        )
        return computed
    if direct is not None and direct > 0:
        return direct
    if computed is not None:
        notes.append(f"Vốn hóa được tính từ giá và CPLH Trecapital: {computed:,.0f} tỷ đồng.")
        return computed
    return None


def _sanitize_company(company, *, price: Optional[float], market_cap: Optional[float], shares_mil: Optional[float]):
    safe = copy(company)
    for name, value in (("current_price", price), ("market_cap_bil", market_cap), ("shares_outstanding_mil", shares_mil)):
        if value is None:
            continue
        try:
            setattr(safe, name, value)
        except Exception:
            pass
    return safe


def _sanitize_annual(df: pd.DataFrame, shares_mil: Optional[float], price: Optional[float]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    idx = out.index[-1]
    if "period" in out.columns:
        mask = out["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        if mask.any():
            idx = out.index[mask][-1]
    if shares_mil is not None:
        if "shares_outstanding_mil" not in out.columns:
            out["shares_outstanding_mil"] = pd.NA
        out.at[idx, "shares_outstanding_mil"] = shares_mil
    if price is not None:
        if "year_end_price" not in out.columns:
            out["year_end_price"] = pd.NA
        out.at[idx, "year_end_price"] = price
    return out


class CurrentRepoDataProvider:
    """Use Trecapital's normalized Module 1 facts and Module 2 valuation as the single source.

    The bridge reconciles obvious unit/source inconsistencies *within Trecapital itself* before
    Table 1.2 is calculated. It never fabricates a missing financial fact and never substitutes a
    generic web value for the app's data layer.
    """

    def __init__(self, company, annual_df: pd.DataFrame, valuation_range=None):
        self.company = company
        self.annual_df = annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame()
        self.valuation_range = valuation_range

    def _resolve_valuation_range(self, safe_company, safe_annual):
        if not callable(self.valuation_range):
            return self.valuation_range
        fn = self.valuation_range
        try:
            params = list(signature(fn).parameters.values())
            positional = [p for p in params if p.kind in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD}]
            has_varargs = any(p.kind == Parameter.VAR_POSITIONAL for p in params)
            if has_varargs or len(positional) >= 2:
                return fn(safe_company, safe_annual)
            if len(positional) == 1:
                return fn(safe_company)
        except Exception:
            # Some callables do not expose a signature. Preserve Phase 1B zero-argument behavior.
            pass
        return fn()

    def get_inventory_source_data(self, company_context):
        notes: list[str] = []
        latest = _latest_row(self.annual_df)
        as_of = str(latest.get("period") or latest.get("year") or pd.Timestamp.today().date())

        ticker = str(getattr(self.company, "ticker", "") or "").upper()
        if "ticker" in self.annual_df.columns and not self.annual_df.empty:
            financial_tickers = {str(x).upper() for x in self.annual_df["ticker"].dropna().unique()}
            if financial_tickers and ticker and ticker not in financial_tickers:
                notes.append(f"CẢNH BÁO: Tổng quan là {ticker} nhưng BCTC đang mang mã {', '.join(sorted(financial_tickers))}.")

        shares_mil = _best_shares_mil(self.company, self.annual_df, notes)
        price = _best_price(self.company, self.annual_df, notes)
        market_cap = _best_market_cap(self.company, price, shares_mil, notes)

        net_debt, _ = _metric(self.annual_df, "net_debt_bil")
        tev = None if market_cap is None else market_cap + (net_debt or 0.0)

        ebit, ebit_period, ebit_derived = _best_ebit(self.annual_df)
        if ebit is not None and ebit_period and ebit_period.upper() not in {as_of.upper()}:
            notes.append(f"EBIT TTM trống; dùng EBIT kỳ gần nhất có dữ liệu: {ebit_period}.")
        if ebit_derived and ebit_period:
            notes.append(f"EBIT {ebit_period} được Trecapital suy ra từ Lợi nhuận gộp - CP bán hàng - CP QLDN.")

        ebitda, ebitda_period, ebitda_derived = _best_ebitda(self.annual_df)
        if ebitda is not None and ebitda_period and ebitda_period.upper() not in {as_of.upper()}:
            notes.append(f"EBITDA TTM trống; dùng EBITDA kỳ gần nhất có dữ liệu: {ebitda_period}.")
        if ebitda_derived and ebitda_period:
            notes.append(f"EBITDA {ebitda_period} = EBIT + |Khấu hao| từ dữ liệu Trecapital.")

        pretax, _ = _metric(self.annual_df, "pretax_profit_bil")
        debt, _ = _metric(self.annual_df, "interest_bearing_debt_bil")
        if debt is None:
            parts = []
            for key in (
                "short_term_debt_bil",
                "current_portion_long_term_debt_bil",
                "long_term_debt_bil",
                "bonds_payable_bil",
                "lease_liabilities_bil",
                "finance_lease_liabilities_bil",
            ):
                value, _ = _metric(self.annual_df, key)
                parts.append(value)
            if any(v is not None for v in parts):
                debt = sum(v or 0.0 for v in parts)

        interest_expense, _ = _metric(self.annual_df, "interest_expense_bil", "interest_paid_bil", "borrowing_cost_bil")
        if interest_expense is not None:
            # Coverage ratios use the magnitude of financing cost; accounting/cash-flow feeds may store outflows as negative.
            interest_expense = abs(interest_expense)
        fcf, _ = _metric(self.annual_df, "free_cash_flow_bil")

        dps, _ = _metric(
            self.annual_df,
            "dividend_per_share",
            "cash_dividend_per_share",
            "cash_dividend_per_share_vnd",
            "dps_vnd",
        )
        if dps is None and shares_mil is not None and shares_mil > 0:
            cash_dividend, dividend_period = _metric(self.annual_df, "cash_dividend_bil")
            if cash_dividend is not None:
                dps = abs(cash_dividend) * 1000.0 / shares_mil
                notes.append(f"Dividend/share được suy ra từ cổ tức tiền mặt/CPLH Trecapital kỳ {dividend_period}: {dps:,.0f} đ/cp.")

        fcf_estimate, _ = _metric(self.annual_df, "fcf_estimate_bil", "normalized_fcf_bil")

        safe_company = _sanitize_company(self.company, price=price, market_cap=market_cap, shares_mil=shares_mil)
        safe_annual = _sanitize_annual(self.annual_df, shares_mil, price)
        valuation_range = self._resolve_valuation_range(safe_company, safe_annual)
        target_price = None
        mos = None
        source_module = "module1_normalized_cache"
        if valuation_range is not None:
            target_price = _safe_float(getattr(valuation_range, "weighted_vnd", None))
            mos_pct = _safe_float(getattr(valuation_range, "mos_to_weighted_pct", None))
            mos = None if mos_pct is None else mos_pct / 100.0
            source_module += "+module2_valuation"
        if notes:
            source_module += "+reconciled_internal_data"

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
            shares_outstanding_mil=shares_mil,
            source_module=source_module,
            source_notes=tuple(notes),
        )
