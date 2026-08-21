from __future__ import annotations

from copy import copy
from inspect import Parameter, signature
from typing import Any, Optional

import pandas as pd

from .contracts import InventorySourceData
from .services.formulas import inventory_metrics


MATERIAL_MISMATCH = 0.30
PRICE_GROSS_MISMATCH = 2.0
DEBT_COMPONENT_FIELDS = (
    "short_term_debt_bil",
    "current_portion_long_term_debt_bil",
    "long_term_debt_bil",
    "bonds_payable_bil",
    "lease_liabilities_bil",
    "finance_lease_liabilities_bil",
)


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


def _period(row: dict) -> str:
    return str(row.get("period") or row.get("year") or "kỳ gần nhất")


def _preferred_rows(df: pd.DataFrame) -> list[dict]:
    """Return TTM first, then newest-to-oldest rows."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    rows: list[dict] = []
    if "period" in df.columns:
        ttm = df[df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        for _, row in ttm.iloc[::-1].iterrows():
            rows.append(row.to_dict())
    for _, row in df.iloc[::-1].iterrows():
        d = row.to_dict()
        p = str(d.get("period") or "").upper()
        if "TTM" in p or "T12M" in p:
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
            return value, _period(row)
    return None, None


def _row_interest_expense(row: dict) -> Optional[float]:
    value = _number(row, "interest_expense_bil", "interest_paid_bil", "borrowing_cost_bil")
    return None if value is None else abs(value)


def _row_ebit(row: dict) -> tuple[Optional[float], str]:
    """Resolve EBIT only from Trecapital facts, with an auditable proxy as last resort."""
    direct = _number(row, "ebit_bil", "core_operating_profit_bil", "operating_profit_bil")
    if direct is not None:
        return direct, "direct"
    gross = _number(row, "gross_profit_bil")
    selling = _number(row, "selling_expense_bil")
    admin = _number(row, "admin_expense_bil")
    if gross is not None and (selling is not None or admin is not None):
        return gross - abs(selling or 0.0) - abs(admin or 0.0), "gross_less_sga"
    pretax = _number(row, "pretax_profit_bil")
    interest = _row_interest_expense(row)
    if pretax is not None and interest is not None:
        return pretax + interest, "pretax_plus_interest_proxy"
    return None, "missing"


def _row_ebitda(row: dict) -> tuple[Optional[float], str, str]:
    direct = _number(row, "ebitda_bil")
    if direct is not None:
        return direct, "direct", "direct"
    ebit, ebit_method = _row_ebit(row)
    da = _number(row, "depreciation_bil", "depreciation_amortization_bil", "depreciation_and_amortization_bil", "da_bil")
    if ebit is not None and da is not None:
        return ebit + abs(da), "ebit_plus_da", ebit_method
    return None, "missing", ebit_method


def _row_fcf(row: dict) -> tuple[Optional[float], str]:
    direct = _number(row, "free_cash_flow_bil")
    if direct is not None:
        return direct, "direct"
    cfo = _number(row, "cfo_bil")
    capex = _number(row, "capex_bil")
    if cfo is not None and capex is not None:
        return cfo - abs(capex), "cfo_minus_capex"
    return None, "missing"


def _best_ebit(df: pd.DataFrame) -> tuple[Optional[float], Optional[str], str]:
    for row in _preferred_rows(df):
        value, method = _row_ebit(row)
        if value is not None:
            return value, _period(row), method
    return None, None, "missing"


def _best_ebitda(df: pd.DataFrame) -> tuple[Optional[float], Optional[str], str, str]:
    for row in _preferred_rows(df):
        value, method, ebit_method = _row_ebitda(row)
        if value is not None:
            return value, _period(row), method, ebit_method
    return None, None, "missing", "missing"


def _best_fcf(df: pd.DataFrame) -> tuple[Optional[float], Optional[str], str]:
    for row in _preferred_rows(df):
        value, method = _row_fcf(row)
        if value is not None:
            return value, _period(row), method
    return None, None, "missing"


def _row_debt(row: dict) -> tuple[Optional[float], str]:
    """Return actual interest-bearing debt, never a synthetic zero produced by derived-metric fill.

    A zero `interest_bearing_debt_bil` is accepted only if at least one underlying debt component
    is explicitly present. If no component exists, zero is treated as unknown rather than debt-free.
    """
    direct = _number(row, "interest_bearing_debt_bil")
    parts = [_safe_float(row.get(k)) for k in DEBT_COMPONENT_FIELDS]
    has_parts = any(v is not None for v in parts)
    component_total = sum(abs(v or 0.0) for v in parts) if has_parts else None
    if direct is not None and direct > 0:
        return abs(direct), "direct"
    if has_parts:
        return component_total, "components"
    # Some providers expose total debt under a generic but debt-specific alias.
    generic = _number(row, "total_debt_bil", "borrowings_bil")
    if generic is not None and generic >= 0:
        return abs(generic), "generic_debt_alias"
    return None, "missing"


def _best_total_debt(df: pd.DataFrame) -> tuple[Optional[float], Optional[str], str]:
    for row in _preferred_rows(df):
        debt, method = _row_debt(row)
        if debt is not None:
            return debt, _period(row), method
    return None, None, "missing"


def _cash_and_investments(row: dict) -> Optional[float]:
    direct = _number(row, "cash_and_short_investments_bil")
    if direct is not None:
        return max(direct, 0.0)
    cash = _number(row, "cash_equivalents_bil")
    sti = _number(row, "short_term_investments_bil")
    if cash is None and sti is None:
        return None
    return max(cash or 0.0, 0.0) + max(sti or 0.0, 0.0)


def _relative_gap(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or a == 0 or b == 0:
        return None
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _materially_different(a: Optional[float], b: Optional[float], threshold: float = MATERIAL_MISMATCH) -> bool:
    gap = _relative_gap(a, b)
    return gap is not None and gap > threshold


def _infer_shares_row(row: dict) -> Optional[float]:
    direct = _number(row, "shares_outstanding_mil")
    net_profit = _number(row, "net_profit_bil")
    eps = _number(row, "eps_vnd", "basic_eps_vnd")
    inferred = net_profit * 1000.0 / eps if net_profit is not None and eps is not None and eps > 0 else None
    if direct is not None and direct > 0 and inferred is not None and inferred > 0 and _materially_different(direct, inferred):
        return inferred
    if direct is not None and direct > 0:
        return direct
    return inferred if inferred is not None and inferred > 0 else None


def _infer_shares_from_financials(df: pd.DataFrame) -> tuple[Optional[float], Optional[str]]:
    for row in _preferred_rows(df):
        shares = _infer_shares_row(row)
        if shares is not None:
            return shares, _period(row)
    return None, None


def _best_shares_mil(company, df: pd.DataFrame, notes: list[str]) -> Optional[float]:
    direct, direct_period = _metric(df, "shares_outstanding_mil")
    overview = _safe_float(getattr(company, "shares_outstanding_mil", None))
    inferred, inferred_period = _infer_shares_from_financials(df)
    if inferred is not None and direct is not None and _materially_different(direct, inferred):
        notes.append(f"Số CP lưu hành TTM ({direct:,.1f} triệu) lệch >30% so với LNST/EPS nội bộ ({inferred:,.1f} triệu); dùng giá trị suy ra từ {inferred_period}.")
        return inferred
    if direct is not None and direct > 0:
        if overview is not None and _materially_different(direct, overview):
            notes.append(f"Số CP ở Tổng quan ({overview:,.1f} triệu) không khớp BCTC {direct_period} ({direct:,.1f} triệu); ưu tiên BCTC Trecapital.")
        return direct
    if inferred is not None:
        notes.append(f"Số CP lưu hành được suy ra từ LNST/EPS Trecapital kỳ {inferred_period}: {inferred:,.1f} triệu.")
        return inferred
    return overview if overview is not None and overview > 0 else None


def _best_price(company, df: pd.DataFrame, notes: list[str]) -> Optional[float]:
    overview = _safe_float(getattr(company, "current_price", None))
    internal, internal_period = _metric(df, "current_price", "market_price_vnd", "year_end_price")
    if overview is not None and overview > 0 and internal is not None and internal > 0:
        ratio = overview / internal
        if ratio > PRICE_GROSS_MISMATCH or ratio < 1.0 / PRICE_GROSS_MISMATCH:
            notes.append(f"Giá Tổng quan {overview:,.0f} đ/cp lệch >2x giá nội bộ gần nhất {internal:,.0f} đ/cp ({internal_period}); dùng giá nội bộ Trecapital để tránh sai đơn vị/mismatch nguồn.")
            return internal
    if overview is not None and overview > 0:
        return overview
    if internal is not None and internal > 0:
        notes.append(f"Không có giá hợp lệ ở Tổng quan; dùng giá nội bộ Trecapital {internal_period}: {internal:,.0f} đ/cp.")
        return internal
    return None


def _best_market_cap(company, price: Optional[float], shares_mil: Optional[float], notes: list[str]) -> Optional[float]:
    direct = _safe_float(getattr(company, "market_cap_bil", None))
    computed = price * shares_mil / 1000.0 if price is not None and shares_mil is not None and price > 0 and shares_mil > 0 else None
    if computed is not None and direct is not None and direct > 0 and _materially_different(direct, computed):
        notes.append(f"Vốn hóa Tổng quan {direct:,.0f} tỷ lệch >30% so với Giá×CPLH nội bộ {computed:,.0f} tỷ; dùng {computed:,.0f} tỷ.")
        return computed
    if direct is not None and direct > 0:
        return direct
    if computed is not None:
        notes.append(f"Vốn hóa được tính từ giá và CPLH Trecapital: {computed:,.0f} tỷ đồng.")
        return computed
    return None


def _row_ccc(row: dict, prev_row: Optional[dict] = None) -> tuple[Optional[float], str]:
    direct = _number(row, "cash_conversion_cycle_days", "ccc_days")
    if direct is not None:
        return direct, "direct"
    dso = _number(row, "dso_days")
    dio = _number(row, "dio_days")
    dpo = _number(row, "dpo_days")
    if dso is not None and dio is not None and dpo is not None:
        return dio + dso - dpo, "dio_dso_dpo"
    revenue = _number(row, "revenue_bil")
    gross_profit = _number(row, "gross_profit_bil")
    if revenue is None or revenue <= 0 or gross_profit is None:
        return None, "missing"
    cogs = revenue - gross_profit
    if cogs <= 0:
        return None, "missing"
    inv = _number(row, "inventory_bil")
    ar = _number(row, "accounts_receivable_bil")
    ap = _number(row, "accounts_payable_bil")
    if inv is None or ar is None or ap is None:
        return None, "missing"
    if prev_row is None:
        return None, "missing_average_balance"
    p_inv = _number(prev_row, "inventory_bil")
    p_ar = _number(prev_row, "accounts_receivable_bil")
    p_ap = _number(prev_row, "accounts_payable_bil")
    if p_inv is None or p_ar is None or p_ap is None:
        return None, "missing_average_balance"
    avg_inv = (inv + p_inv) / 2.0
    avg_ar = (ar + p_ar) / 2.0
    avg_ap = (ap + p_ap) / 2.0
    dio = avg_inv / cogs * 365.0
    dso = avg_ar / revenue * 365.0
    dpo = avg_ap / cogs * 365.0
    return dio + dso - dpo, "shearn_avg_balance_proxy"


def _chronological_rows(df: pd.DataFrame) -> list[dict]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    work = df.copy()
    # Keep annual rows plus the appended TTM row; quarterly rows should not appear in the 10-year proxy.
    if "period_type" in work.columns:
        is_ttm = work.get("period", pd.Series(index=work.index, dtype="object")).astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        work = work[work["period_type"].astype(str).eq("Y") | is_ttm]
    def key(row):
        p = str(row.get("period") or "").upper()
        if "TTM" in p or "T12M" in p:
            return (9999, 1)
        y = _safe_float(row.get("year"))
        return (int(y) if y is not None else 0, 0)
    rows = [r.to_dict() for _, r in work.iterrows()]
    rows.sort(key=key)
    return rows


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
    """Bridge normalized Trecapital facts into Shearn Table 1.2 and its historical proxy."""

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
            pass
        return fn()

    def _current_ccc(self) -> tuple[Optional[float], Optional[str], str]:
        rows = _chronological_rows(self.annual_df)
        if not rows:
            return None, None, "missing"
        row = rows[-1]
        prev = rows[-2] if len(rows) > 1 else None
        value, method = _row_ccc(row, prev)
        return value, _period(row), method

    def get_inventory_source_data(self, company_context):
        notes: list[str] = []
        latest = _latest_row(self.annual_df)
        as_of = _period(latest) if latest else str(pd.Timestamp.today().date())
        ticker = str(getattr(self.company, "ticker", "") or "").upper()
        if "ticker" in self.annual_df.columns and not self.annual_df.empty:
            financial_tickers = {str(x).upper() for x in self.annual_df["ticker"].dropna().unique()}
            if financial_tickers and ticker and ticker not in financial_tickers:
                notes.append(f"CẢNH BÁO: Tổng quan là {ticker} nhưng BCTC đang mang mã {', '.join(sorted(financial_tickers))}.")

        shares_mil = _best_shares_mil(self.company, self.annual_df, notes)
        price = _best_price(self.company, self.annual_df, notes)
        market_cap = _best_market_cap(self.company, price, shares_mil, notes)

        debt, debt_period, debt_method = _best_total_debt(self.annual_df)
        if debt is None:
            notes.append("CẢNH BÁO: Chưa có cấu phần nợ vay đủ tin cậy; không coi interest_bearing_debt_bil=0 tổng hợp là doanh nghiệp không có nợ.")
        elif debt_period and debt_period.upper() != as_of.upper():
            notes.append(f"Total debt TTM chưa đủ cấu phần; dùng nợ vay kỳ gần nhất có dữ liệu: {debt_period} ({debt_method}).")

        cash, _ = _metric(self.annual_df, "cash_and_short_investments_bil")
        if cash is None:
            cash_eq, _ = _metric(self.annual_df, "cash_equivalents_bil")
            sti, _ = _metric(self.annual_df, "short_term_investments_bil")
            if cash_eq is not None or sti is not None:
                cash = max(cash_eq or 0.0, 0.0) + max(sti or 0.0, 0.0)
        net_debt = (debt - (cash or 0.0)) if debt is not None else None
        tev = market_cap + net_debt if market_cap is not None and net_debt is not None else None

        ebit, ebit_period, ebit_method = _best_ebit(self.annual_df)
        if ebit is not None and ebit_period and ebit_period.upper() != as_of.upper():
            notes.append(f"EBIT TTM trống; dùng EBIT kỳ gần nhất có dữ liệu: {ebit_period}.")
        if ebit is not None and ebit_period:
            if ebit_method == "gross_less_sga":
                notes.append(f"EBIT {ebit_period} = Lợi nhuận gộp - |CP bán hàng| - |CP QLDN| từ Trecapital.")
            elif ebit_method == "pretax_plus_interest_proxy":
                notes.append(f"EBIT proxy {ebit_period} = LNTT + |chi phí lãi vay| từ Trecapital; cần kiểm tra lãi/lỗ ngoài hoạt động.")

        ebitda, ebitda_period, ebitda_method, ebitda_ebit_method = _best_ebitda(self.annual_df)
        if ebitda is not None and ebitda_period and ebitda_period.upper() != as_of.upper():
            notes.append(f"EBITDA TTM trống; dùng EBITDA kỳ gần nhất có dữ liệu: {ebitda_period}.")
        if ebitda is not None and ebitda_period and ebitda_method == "ebit_plus_da":
            suffix = " (EBIT là proxy LNTT + lãi vay)" if ebitda_ebit_method == "pretax_plus_interest_proxy" else ""
            notes.append(f"EBITDA {ebitda_period} = EBIT + |Khấu hao/D&A| từ Trecapital{suffix}.")

        pretax, _ = _metric(self.annual_df, "pretax_profit_bil")
        interest_expense, _ = _metric(self.annual_df, "interest_expense_bil", "interest_paid_bil", "borrowing_cost_bil")
        interest_expense = abs(interest_expense) if interest_expense is not None else None
        fcf, fcf_period, fcf_method = _best_fcf(self.annual_df)
        if fcf is not None and fcf_period and fcf_period.upper() != as_of.upper():
            notes.append(f"FCF TTM trống; dùng FCF kỳ gần nhất có dữ liệu: {fcf_period}.")
        if fcf is not None and fcf_period and fcf_method == "cfo_minus_capex":
            notes.append(f"FCF {fcf_period} = CFO - |Capex| từ dữ liệu Trecapital.")

        ccc, ccc_period, ccc_method = self._current_ccc()
        if ccc is not None and ccc_method == "shearn_avg_balance_proxy":
            notes.append(f"CCC {ccc_period} proxy theo Shearn = DIO + DSO - DPO, dùng tồn kho/AR/AP bình quân và COGS/Revenue Trecapital.")

        dps, _ = _metric(self.annual_df, "dividend_per_share", "cash_dividend_per_share", "cash_dividend_per_share_vnd", "dps_vnd")
        if dps is None and shares_mil is not None and shares_mil > 0:
            cash_dividend, dividend_period = _metric(self.annual_df, "cash_dividend_bil")
            if cash_dividend is not None:
                dps = abs(cash_dividend) * 1000.0 / shares_mil
                notes.append(f"Dividend/share được suy ra từ cổ tức tiền mặt/CPLH Trecapital kỳ {dividend_period}: {dps:,.0f} đ/cp.")

        fcf_estimate, fcf_estimate_period = _metric(self.annual_df, "fcf_estimate_per_share_vnd", "fcf_per_share_vnd", "fcf_estimate_vnd")
        if fcf_estimate is None and fcf is not None and shares_mil is not None and shares_mil > 0:
            fcf_estimate = fcf * 1000.0 / shares_mil
            notes.append(f"FCF estimate/share tự động = FCF {fcf_period or as_of} / CPLH = {fcf_estimate:,.0f} đ/cp; baseline TTM, analyst có thể override forward estimate.")
        elif fcf_estimate is not None and fcf_estimate_period:
            notes.append(f"FCF estimate/share lấy trực tiếp từ Trecapital kỳ {fcf_estimate_period}: {fcf_estimate:,.0f} đ/cp.")

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
            as_of_date=as_of, tev=tev, ebit=ebit, ebitda=ebitda, normalized_earnings=pretax,
            total_debt=debt, interest_expense=interest_expense, fcf_current=fcf, market_cap=market_cap,
            dividend_per_share=dps, market_price=price, fcf_estimate=fcf_estimate, target_price=target_price,
            mos=mos, shares_outstanding_mil=shares_mil, ccc_days=ccc,
            source_module=source_module, source_notes=tuple(notes),
        )

    def get_inventory_proxy_history(self, years: int = 10) -> list[dict[str, Any]]:
        """Build a source-only 10-year + TTM Table 1.2 proxy from Trecapital history.

        Historical Target/MOS are intentionally left blank because a current valuation must not be
        backfilled into the past. Saved analyst reviews are overlaid separately by the UI.
        """
        rows = _chronological_rows(self.annual_df)
        if not rows:
            return []
        annual_idx = [i for i, r in enumerate(rows) if "TTM" not in _period(r).upper() and "T12M" not in _period(r).upper()]
        keep_annual = set(annual_idx[-max(int(years), 1):])
        keep_idx = [i for i in range(len(rows)) if i in keep_annual or "TTM" in _period(rows[i]).upper() or "T12M" in _period(rows[i]).upper()]
        current = self.get_inventory_source_data(None)
        out: list[dict[str, Any]] = []
        for i in keep_idx:
            row = rows[i]
            prev = rows[i - 1] if i > 0 else None
            period = _period(row)
            is_ttm = "TTM" in period.upper() or "T12M" in period.upper()
            if is_ttm:
                shares = current.shares_outstanding_mil
                price = current.market_price
                market_cap = current.market_cap
                debt = current.total_debt
                tev = current.tev
                target = current.target_price
                mos = current.mos
                ccc = current.ccc_days
            else:
                shares = _infer_shares_row(row)
                price = _number(row, "year_end_price", "market_price_vnd")
                market_cap = price * shares / 1000.0 if price is not None and price > 0 and shares is not None and shares > 0 else None
                debt, _ = _row_debt(row)
                cash = _cash_and_investments(row)
                net_debt = debt - (cash or 0.0) if debt is not None else None
                tev = market_cap + net_debt if market_cap is not None and net_debt is not None else None
                target = None
                mos = None
                ccc, _ = _row_ccc(row, prev)
            ebit, _ = _row_ebit(row)
            ebitda, _, _ = _row_ebitda(row)
            norm = _number(row, "pretax_profit_bil")
            interest = _row_interest_expense(row)
            fcf, _ = _row_fcf(row)
            if is_ttm:
                fcf = current.fcf_current
                ebit = current.ebit
                ebitda = current.ebitda
                norm = current.normalized_earnings
                interest = current.interest_expense
            cash_dividend = _number(row, "cash_dividend_bil")
            dps = abs(cash_dividend) * 1000.0 / shares if cash_dividend is not None and shares is not None and shares > 0 else None
            if is_ttm:
                dps = current.dividend_per_share
            fcf_ps = fcf * 1000.0 / shares if fcf is not None and shares is not None and shares > 0 else None
            metrics = inventory_metrics(
                tev=tev, ebit=ebit, ebitda=ebitda, normalized_earnings=norm, total_debt=debt,
                interest_expense=interest, fcf_current=fcf, market_cap=market_cap,
                dividend_per_share=dps, market_price=price, target_price=target,
            )
            out.append({
                "period": period, "source_type": "TTM" if is_ttm else "10Y proxy", "tev": tev,
                "ebit": ebit, "ebitda": ebitda, "normalized_earnings": norm, "total_debt": debt,
                "interest_expense": interest, "fcf_current": fcf, "market_cap": market_cap,
                "market_price": price, "dividend_per_share": dps, "fcf_estimate": fcf_ps,
                "target_price": target, "mos": mos, "ccc_days": ccc, **metrics,
            })
        return out
