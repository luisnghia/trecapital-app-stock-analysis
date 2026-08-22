from __future__ import annotations

"""Phase 2 quantitative analytical tools based on Michael Shearn's source tables.

Design rules:
- consume Trecapital's normalized financial Data Layer; do not fetch a parallel source;
- never convert missing data into zero;
- keep Shearn analytical variants visibly separate from Trecapital standardized metrics;
- preserve negative/weak economics as warnings instead of manufacturing a positive score;
- tools support analyst judgment; they do not write checklist assessments automatically.
"""

from dataclasses import dataclass
from typing import Any, Iterable
import math

import pandas as pd

from financial_sign_policy import positive_base_growth


@dataclass(frozen=True)
class ToolResult:
    name: str
    checklist_questions: tuple[str, ...]
    source_tables: tuple[str, ...]
    rows: list[dict[str, Any]]
    notes: tuple[str, ...] = ()


def _f(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return None if math.isnan(out) else out
    except Exception:
        return None


def _n(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in row:
            value = _f(row.get(key))
            if value is not None:
                return value
    return None


def _period(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year") or "—")


def _is_ttm(row: dict[str, Any]) -> bool:
    p = _period(row).upper()
    return "TTM" in p or "T12M" in p


def _annual_and_ttm_rows(df: pd.DataFrame, limit_years: int = 10) -> list[dict[str, Any]]:
    """Return oldest→newest annual rows plus TTM last so change formulas use the right prior period."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        d = r.to_dict()
        pt = str(d.get("period_type") or "").upper()
        if pt == "Y" or _is_ttm(d) or not pt:
            rows.append(d)
    annual = [r for r in rows if not _is_ttm(r)]
    ttm = [r for r in rows if _is_ttm(r)]

    def year_key(r: dict[str, Any]) -> int:
        y = _f(r.get("year"))
        if y is not None:
            return int(y)
        p = _period(r)
        return int(p[:4]) if len(p) >= 4 and p[:4].isdigit() else 0

    annual.sort(key=year_key)
    return annual[-limit_years:] + (ttm[-1:] if ttm else [])


def _pct_change(current: float | None, previous: float | None) -> float | None:
    return positive_base_growth(current, previous)


def _safe_ratio(numerator: float | None, denominator: float | None, *, positive_denominator: bool = False) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    if positive_denominator and denominator <= 0:
        return None
    return numerator / denominator


def _interest(row: dict[str, Any]) -> float | None:
    value = _n(row, "interest_expense_bil", "interest_paid_bil", "borrowing_cost_bil")
    return abs(value) if value is not None else None


def _ebit(row: dict[str, Any]) -> float | None:
    direct = _n(row, "ebit_bil", "core_operating_profit_bil", "operating_profit_bil")
    if direct is not None:
        return direct
    gross = _n(row, "gross_profit_bil")
    selling = _n(row, "selling_expense_bil")
    admin = _n(row, "admin_expense_bil")
    if gross is not None and (selling is not None or admin is not None):
        return gross - abs(selling or 0.0) - abs(admin or 0.0)
    pretax = _n(row, "pretax_profit_bil")
    interest = _interest(row)
    return pretax + interest if pretax is not None and interest is not None else None


def _ebitda(row: dict[str, Any]) -> float | None:
    direct = _n(row, "ebitda_bil")
    if direct is not None:
        return direct
    ebit = _ebit(row)
    da = _n(row, "depreciation_bil", "depreciation_amortization_bil", "depreciation_and_amortization_bil", "da_bil")
    return ebit + abs(da) if ebit is not None and da is not None else None


def _debt(row: dict[str, Any]) -> float | None:
    """Use interest-bearing debt without double-counting current portion or bond detail."""
    direct = _n(row, "interest_bearing_debt_bil")
    if direct is not None and direct > 0:
        return abs(direct)
    short = _n(row, "short_term_debt_bil")
    current_portion = _n(row, "current_portion_long_term_debt_bil")
    long = _n(row, "long_term_debt_bil")
    bonds = _n(row, "bonds_payable_bil")
    leases = _n(row, "finance_lease_liabilities_bil", "lease_liabilities_bil")
    current_bucket = short if short is not None else current_portion
    noncurrent_bucket = long if long is not None else bonds
    if current_bucket is not None or noncurrent_bucket is not None:
        return abs(current_bucket or 0.0) + abs(noncurrent_bucket or 0.0)
    if leases is not None:
        return abs(leases)
    generic = _n(row, "total_debt_bil", "borrowings_bil")
    return abs(generic) if generic is not None and generic > 0 else None


def _cash(row: dict[str, Any]) -> float | None:
    direct = _n(row, "cash_and_short_investments_bil")
    if direct is not None:
        return max(direct, 0.0)
    cash = _n(row, "cash_equivalents_bil", "cash_bil")
    sti = _n(row, "short_term_investments_bil")
    if cash is None and sti is None:
        return None
    return max(cash or 0.0, 0.0) + max(sti or 0.0, 0.0)


def _eps(row: dict[str, Any]) -> tuple[float | None, str]:
    direct = _n(row, "eps_vnd", "basic_eps_vnd", "eps")
    if direct is not None:
        return direct, "reported/Trecapital"
    ni = _n(row, "net_profit_bil", "net_income_bil")
    shares = _n(row, "weighted_avg_shares_mil", "shares_outstanding_mil")
    if ni is None or shares is None or shares <= 0:
        return None, "missing"
    return ni * 1000.0 / shares, "derived Net income/shares"


def balance_sheet_leverage(df: pd.DataFrame) -> ToolResult:
    out: list[dict[str, Any]] = []
    for row in _annual_and_ttm_rows(df):
        debt = _debt(row)
        cash = _cash(row)
        ebitda = _ebitda(row)
        ebit = _ebit(row)
        interest = _interest(row)
        current_assets = _n(row, "current_assets_bil")
        current_liabilities = _n(row, "current_liabilities_bil")
        out.append({
            "Kỳ": _period(row), "Total Debt": debt, "Cash + STI": cash,
            "Net Debt": None if debt is None or cash is None else debt - cash,
            "EBITDA": ebitda, "Debt/EBITDA": _safe_ratio(debt, ebitda, positive_denominator=True),
            "EBIT": ebit, "Interest": interest, "EBIT/Interest": _safe_ratio(ebit, interest, positive_denominator=True),
            "Current Assets": current_assets, "Current Liabilities": current_liabilities,
            "Current Ratio": _safe_ratio(current_assets, current_liabilities, positive_denominator=True),
        })
    return ToolResult(
        "Balance Sheet & Leverage Analyzer", ("Q25",), ("5.1", "5.2"), out,
        ("Theo dõi nhiều kỳ thay vì kết luận từ một snapshot.",
         "Debt là interest-bearing debt; thiếu cấu phần nợ thì để trống, không giả định bằng 0."),
    )


def _tax_rate(row: dict[str, Any]) -> float | None:
    pretax = _n(row, "pretax_profit_bil")
    tax = _n(row, "income_tax_expense_bil", "tax_expense_bil")
    if pretax is None or pretax <= 0 or tax is None:
        return None
    return min(max(abs(tax) / pretax, 0.0), 0.5)


def _nopat(row: dict[str, Any]) -> float | None:
    direct = _n(row, "nopat_bil")
    if direct is not None:
        return direct
    ebit = _ebit(row)
    rate = _tax_rate(row)
    return ebit * (1.0 - rate) if ebit is not None and rate is not None else None


def _capital_employed(row: dict[str, Any]) -> float | None:
    """Match Trecapital standardized ROIC denominator methodology.

    Module 1 defines capital employed as Total Assets − Current Liabilities and then uses the
    average capital-employed base for roic_standard_pct. Do not silently substitute a second
    Equity + Debt − Cash methodology here.
    """
    direct = _n(row, "capital_employed_bil")
    if direct is not None:
        return direct
    assets = _n(row, "total_assets_bil")
    current_liabilities = _n(row, "current_liabilities_bil")
    if assets is None or current_liabilities is None:
        return None
    return assets - current_liabilities


def roic_quality(df: pd.DataFrame) -> ToolResult:
    """Tables 5.3–5.4: preserve Trecapital ROIC and show transparent Shearn cash/goodwill views."""
    rows = _annual_and_ttm_rows(df)
    out: list[dict[str, Any]] = []
    prior_incl_cash = prior_ex_cash = prior_ex_goodwill = None
    for row in rows:
        nopat = _nopat(row)
        capital_employed = _capital_employed(row)
        cash = _cash(row)
        goodwill = _n(row, "goodwill_bil", "goodwill_intangibles_bil")

        # Trecapital's capital-employed base (Total Assets − Current Liabilities) includes cash.
        base_incl_cash = capital_employed
        base_ex_cash = None if capital_employed is None or cash is None else capital_employed - cash
        base_ex_goodwill = None if capital_employed is None or goodwill is None else capital_employed - goodwill

        avg_incl_cash = None if base_incl_cash is None else (base_incl_cash if prior_incl_cash is None else (base_incl_cash + prior_incl_cash) / 2.0)
        avg_ex_cash = None if base_ex_cash is None else (base_ex_cash if prior_ex_cash is None else (base_ex_cash + prior_ex_cash) / 2.0)
        avg_ex_goodwill = None if base_ex_goodwill is None else (base_ex_goodwill if prior_ex_goodwill is None else (base_ex_goodwill + prior_ex_goodwill) / 2.0)

        standardized = _n(row, "roic_standard_pct", "roic_pct", "roic_standardized_pct", "roic")
        if standardized is not None and abs(standardized) <= 2.0:
            standardized *= 100.0

        out.append({
            "Kỳ": _period(row),
            "ROIC Trecapital": standardized,
            "NOPAT": nopat,
            "Avg Capital Employed (incl cash)": avg_incl_cash,
            "ROIC Shearn – Incl Cash": None if nopat is None or avg_incl_cash is None or avg_incl_cash <= 0 else nopat / avg_incl_cash * 100.0,
            "ROIC Shearn – Ex Cash": None if nopat is None or avg_ex_cash is None or avg_ex_cash <= 0 else nopat / avg_ex_cash * 100.0,
            "ROIC Shearn – Ex Goodwill": None if nopat is None or avg_ex_goodwill is None or avg_ex_goodwill <= 0 else nopat / avg_ex_goodwill * 100.0,
            "Cash + STI": cash,
            "Goodwill/Intangibles": goodwill,
        })
        if base_incl_cash is not None:
            prior_incl_cash = base_incl_cash
        if base_ex_cash is not None:
            prior_ex_cash = base_ex_cash
        if base_ex_goodwill is not None:
            prior_ex_goodwill = base_ex_goodwill

    return ToolResult(
        "ROIC Quality Analyzer", ("Q26",), ("5.3", "5.4"), out,
        ("ROIC Trecapital (roic_standard_pct) là Single Source of Truth cho metric chuẩn hóa hiện hành.",
         "Trecapital Capital Employed = Total Assets − Current Liabilities; base này bao gồm cash. Shearn Ex Cash trừ Cash + ST investments khỏi đúng base đó.",
         "Các ROIC Shearn là analytical variants để nhìn distortion do excess cash/goodwill; không âm thầm thay ROIC chuẩn.",
         "Investment base của analytical variants dùng bình quân hai kỳ khi có dữ liệu.",
         "Gross-asset/off-balance-sheet variant chỉ được thêm khi Data Layer có accumulated depreciation/contractual obligations đáng tin cậy; không giả lập số thiếu."),
    )


def operating_leverage(df: pd.DataFrame) -> ToolResult:
    rows = [r for r in _annual_and_ttm_rows(df) if not _is_ttm(r)]
    out: list[dict[str, Any]] = []
    prev_rev = prev_ebit = None
    for row in rows:
        rev = _n(row, "revenue_bil")
        ebit = _ebit(row)
        rev_g = _pct_change(rev, prev_rev)
        ebit_g = _pct_change(ebit, prev_ebit) if prev_ebit is not None and prev_ebit > 0 and ebit is not None else None
        dol = None if rev_g is None or abs(rev_g) < 0.01 or ebit_g is None else _safe_ratio(ebit_g, rev_g)
        total_assets = _n(row, "total_assets_bil")
        ppe = _n(row, "net_ppe_bil", "property_plant_equipment_bil", "fixed_assets_bil")
        selling = _n(row, "selling_expense_bil")
        admin = _n(row, "admin_expense_bil")
        sga = _n(row, "sga_bil", "selling_admin_expense_bil")
        if sga is None and (selling is not None or admin is not None):
            sga = abs(selling or 0.0) + abs(admin or 0.0)
        da = _n(row, "depreciation_bil", "depreciation_amortization_bil")
        out.append({
            "Kỳ": _period(row), "Revenue": rev,
            "Revenue growth": None if rev_g is None else rev_g * 100.0,
            "EBIT": ebit, "EBIT growth": None if ebit_g is None else ebit_g * 100.0, "DOL": dol,
            "PP&E / Assets": None if ppe is None or total_assets is None or total_assets <= 0 else ppe / total_assets * 100.0,
            "SG&A / Revenue": None if sga is None or rev is None or rev <= 0 else abs(sga) / rev * 100.0,
            "D&A / Revenue": None if da is None or rev is None or rev <= 0 else abs(da) / rev * 100.0,
        })
        if rev is not None:
            prev_rev = rev
        if ebit is not None:
            prev_ebit = ebit
    return ToolResult(
        "Operating Leverage & Cost Structure Analyzer", ("Q29", "Q30"), ("6.3", "6.4", "6.5"), out,
        ("DOL = %Δ EBIT / %Δ Revenue theo Shearn. Sales change dưới 1% hoặc prior EBIT ≤ 0 bị loại để tránh ratio méo.",
         "PP&E/Assets, SG&A/Revenue và D&A/Revenue chỉ là evidence; fixed/variable/semi-variable cuối cùng cần analyst đọc MD&A."),
    )


def operating_leverage_stress(df: pd.DataFrame, revenue_changes: Iterable[float] = (-0.05, -0.10, -0.20)) -> list[dict[str, Any]]:
    hist = operating_leverage(df).rows
    valid = [float(r["DOL"]) for r in hist if _f(r.get("DOL")) is not None and 0 <= float(r["DOL"]) <= 20]
    if not valid:
        return []
    dol = float(pd.Series(valid[-5:]).median())
    base_rows = _annual_and_ttm_rows(df)
    if not base_rows:
        return []
    base = base_rows[-1]
    revenue, ebit = _n(base, "revenue_bil"), _ebit(base)
    if revenue is None or ebit is None:
        return []
    return [{
        "Revenue shock": float(change) * 100.0, "DOL used": dol,
        "Revenue stressed": revenue * (1.0 + float(change)),
        "EBIT change": dol * float(change) * 100.0,
        "EBIT stressed": ebit * (1.0 + dol * float(change)),
    } for change in revenue_changes]


def working_capital(df: pd.DataFrame) -> ToolResult:
    rows = _annual_and_ttm_rows(df)
    out: list[dict[str, Any]] = []
    prev = None
    prev_owc = None
    for row in rows:
        rev = _n(row, "revenue_bil")
        cogs = _n(row, "cost_of_goods_sold_bil")
        if cogs is None:
            gross = _n(row, "gross_profit_bil")
            cogs = None if rev is None or gross is None else rev - gross
        if cogs is not None:
            cogs = abs(cogs)
        ar = _n(row, "accounts_receivable_bil", "receivables_bil")
        inv = _n(row, "inventory_bil")
        ap = _n(row, "accounts_payable_bil", "payables_bil")
        dso = dio = dpo = ccc = None
        if prev is not None and rev is not None and rev > 0 and cogs is not None and cogs > 0:
            p_ar = _n(prev, "accounts_receivable_bil", "receivables_bil")
            p_inv = _n(prev, "inventory_bil")
            p_ap = _n(prev, "accounts_payable_bil", "payables_bil")
            if ar is not None and p_ar is not None:
                dso = ((ar + p_ar) / 2.0) / rev * 365.0
            if inv is not None and p_inv is not None:
                dio = ((inv + p_inv) / 2.0) / cogs * 365.0
            if ap is not None and p_ap is not None:
                dpo = ((ap + p_ap) / 2.0) / cogs * 365.0
            if dso is not None and dio is not None and dpo is not None:
                ccc = dso + dio - dpo
        direct_dso = _n(row, "dso_days")
        direct_dio = _n(row, "dio_days")
        direct_dpo = _n(row, "dpo_days")
        direct_ccc = _n(row, "ccc_days", "cash_conversion_cycle_days")
        if direct_dso is not None:
            dso = direct_dso
        if direct_dio is not None:
            dio = direct_dio
        if direct_dpo is not None:
            dpo = direct_dpo
        if direct_ccc is not None:
            ccc = direct_ccc
        owc = None if ar is None or inv is None or ap is None else ar + inv - ap
        delta = None if owc is None or prev_owc is None else owc - prev_owc
        out.append({
            "Kỳ": _period(row), "DSO": dso, "DIO": dio, "DPO": dpo, "CCC": ccc,
            "Operating WC": owc, "Δ Operating WC": delta,
            "ΔWC / Revenue": None if delta is None or rev is None or rev <= 0 else delta / rev * 100.0,
            "Cash released/(absorbed)": None if delta is None else -delta,
        })
        prev = row
        if owc is not None:
            prev_owc = owc
    return ToolResult(
        "Working Capital / CCC Analyzer", ("Q31",), ("6.6",), out,
        ("CCC = DIO + DSO − DPO; proxy dùng Inventory/AR/AP bình quân hai kỳ.",
         "CCC giảm không tự động đồng nghĩa tốt hơn: cần xem DPO có tăng do kéo dài thanh toán supplier hay không."),
    )


def maintenance_capex_context(df: pd.DataFrame) -> ToolResult:
    out: list[dict[str, Any]] = []
    for row in _annual_and_ttm_rows(df):
        revenue = _n(row, "revenue_bil")
        capex = _n(row, "capex_bil", "capital_expenditure_bil", "capital_expenditures_bil")
        da = _n(row, "depreciation_bil", "depreciation_amortization_bil", "depreciation_and_amortization_bil")
        maintenance = _n(row, "maintenance_capex_bil")
        cfo = _n(row, "cfo_bil", "operating_cash_flow_bil")
        fcf = _n(row, "free_cash_flow_bil", "fcf_bil")
        if fcf is None and cfo is not None and capex is not None:
            fcf = cfo - abs(capex)
        out.append({
            "Kỳ": _period(row), "Capex": None if capex is None else abs(capex),
            "Maintenance Capex Trecapital (ước tính)": None if maintenance is None else abs(maintenance),
            "D&A rough proxy": None if da is None else abs(da),
            "Capex / Revenue": None if capex is None or revenue is None or revenue <= 0 else abs(capex) / revenue * 100.0,
            "Capex / D&A": None if capex is None or da is None or abs(da) <= 0 else abs(capex) / abs(da),
            "CFO": cfo, "FCF": fcf,
        })
    return ToolResult(
        "Maintenance Capex Context", ("Q32",), ("Key Points — Chapter 6",), out,
        ("Nếu Trecapital đã có maintenance_capex_bil thì hiển thị riêng và ghi rõ đây là ước tính của Trecapital.",
         "Shearn: khi không thể tính maintenance capex, depreciation có thể dùng như rough approximation — không phải maintenance capex thực tế.",
         "App không tự tách growth capex/maintenance capex nếu nguồn chưa đủ bằng chứng."),
    )


def buyback_dilution(df: pd.DataFrame) -> ToolResult:
    rows = _annual_and_ttm_rows(df)
    out: list[dict[str, Any]] = []
    prev_shares = None
    for row in rows:
        shares = _n(row, "shares_outstanding_mil", "weighted_avg_shares_mil")
        net_income = _n(row, "net_profit_bil", "net_income_bil")
        eps, eps_source = _eps(row)
        gross_buyback = _n(row, "shares_repurchased_mil", "buyback_shares_mil")
        buyback_amount = _n(row, "buyback_bil")
        issued = _n(row, "shares_issued_mil", "esop_options_shares_mil", "stock_comp_shares_mil")
        net_reduction = None if shares is None or prev_shares is None else prev_shares - shares
        eps_without = net_income * 1000.0 / prev_shares if net_income is not None and prev_shares is not None and prev_shares > 0 else None
        eps_uplift = (
            (eps / eps_without - 1.0) * 100.0
            if net_income is not None and net_income > 0 and eps is not None and eps > 0
            and eps_without is not None and eps_without > 0 else None
        )
        out.append({
            "Kỳ": _period(row), "Shares outstanding": shares, "Net share reduction": net_reduction,
            "Share count change vs prior displayed period": None if shares is None or prev_shares is None or prev_shares == 0 else (shares / prev_shares - 1.0) * 100.0,
            "Buyback amount": None if buyback_amount is None else abs(buyback_amount),
            "Gross buyback shares": gross_buyback, "Shares issued / ESOP / options": issued,
            "Net buyback after dilution": None if gross_buyback is None or issued is None else gross_buyback - issued,
            "EPS reported/derived": eps, "EPS source": eps_source,
            "EPS without share-count change": eps_without,
            "EPS uplift from share-count change": eps_uplift,
        })
        if shares is not None and shares > 0:
            prev_shares = shares
    return ToolResult(
        "Buyback & Dilution Analyzer", ("Q46", "Q47"), ("8.2", "8.3"), out,
        ("Net share reduction theo dõi hiệu ứng thực lên số cổ phiếu lưu hành; gross buyback phải trừ shares issued/ESOP/options khi nguồn có dữ liệu.",
         "EPS reported/derived ghi rõ nguồn; fallback Net income/shares chỉ là derived proxy, không được gọi là reported EPS.",
         "EPS without share-count change là analytical proxy dùng prior-period shares; không phải reported EPS. EPS uplift chỉ tính khi LNST và cả hai nền EPS đều dương."),
    )


def operating_driver_eps(df: pd.DataFrame, driver_field: str = "revenue_bil", driver_label: str = "Revenue") -> ToolResult:
    rows = _annual_and_ttm_rows(df)
    out: list[dict[str, Any]] = []
    prev_driver = prev_eps = None
    for row in rows:
        driver = _n(row, driver_field)
        eps, eps_source = _eps(row)
        # A single current TTM row is not directly comparable with the preceding FY row as a YoY
        # growth observation. Display TTM levels but leave growth/divergence blank until a prior TTM
        # comparable period exists.
        if _is_ttm(row):
            dg = eg = None
        else:
            dg, eg = _pct_change(driver, prev_driver), _pct_change(eps, prev_eps)
        divergence = None
        if dg is not None and eg is not None:
            if dg < 0 < eg:
                divergence = "EPS ↑ trong khi driver ↓ — cần kiểm tra nguồn tăng earnings khác"
            elif dg > 0 > eg:
                divergence = "Driver ↑ nhưng EPS ↓ — cần kiểm tra margin/cost/dilution"
            else:
                divergence = "Cùng hướng"
        elif not _is_ttm(row) and prev_eps is not None and eps is not None:
            if prev_eps <= 0 < eps:
                divergence = "EPS chuyển từ lỗ sang lãi — báo chuyển trạng thái, không tính % tăng trưởng"
            elif prev_eps > 0 >= eps:
                divergence = "EPS chuyển từ lãi sang lỗ — cảnh báo, không diễn giải như % tăng trưởng"
        out.append({
            "Kỳ": _period(row), driver_label: driver,
            f"{driver_label} growth": None if dg is None else dg * 100.0,
            "EPS reported/derived": eps, "EPS source": eps_source,
            "EPS growth": None if eg is None else eg * 100.0, "Signal": divergence,
        })
        if not _is_ttm(row):
            if driver is not None:
                prev_driver = driver
            if eps is not None:
                prev_eps = eps
    return ToolResult(
        "Operating Driver → EPS Analyzer", ("Q53", "Q54", "Q55", "Q56", "Q57"), ("10.1",), out,
        ("Đặt EPS cạnh operating metric phù hợp để phát hiện earnings tăng từ nguồn kém bền vững.",
         "Một TTM hiện tại không được so tăng trưởng trực tiếp với FY trước; TTM vẫn hiển thị level nhưng growth/signal để trống nếu không có prior-TTM comparable.",
         "EPS từ lỗ sang lãi hoặc lãi sang lỗ được gắn nhãn chuyển trạng thái; không tính phần trăm tăng trưởng trên nền EPS âm/bằng 0.",
         "Revenue chỉ là driver mặc định; industry-specific driver được mở rộng ở Phase 3 Industry Overlay."),
    )


def accounting_quality_proxy(df: pd.DataFrame) -> ToolResult:
    rows = _annual_and_ttm_rows(df)
    out: list[dict[str, Any]] = []
    prev_revenue = prev_ar = prev_inventory = None
    for row in rows:
        ni = _n(row, "net_profit_bil", "net_income_bil")
        cfo = _n(row, "cfo_bil", "operating_cash_flow_bil")
        revenue = _n(row, "revenue_bil")
        ar = _n(row, "accounts_receivable_bil", "receivables_bil")
        inventory = _n(row, "inventory_bil")
        provision = _n(row, "bad_debt_provision_bil", "credit_loss_provision_bil", "provision_bil")
        charge_off = _n(row, "charge_off_bil", "write_off_bil")
        if _is_ttm(row):
            rev_growth = ar_growth = inv_growth = None
        else:
            rev_growth = _pct_change(revenue, prev_revenue)
            ar_growth = _pct_change(ar, prev_ar)
            inv_growth = _pct_change(inventory, prev_inventory)
        out.append({
            "Kỳ": _period(row), "Net income": ni, "CFO": cfo,
            "CFO / Net income": _safe_ratio(cfo, ni, positive_denominator=True),
            "Provision": provision, "Actual charge-off/write-off": charge_off,
            "Provision / charge-off": _safe_ratio(provision, charge_off, positive_denominator=True),
            "Revenue growth": None if rev_growth is None else rev_growth * 100.0,
            "AR growth": None if ar_growth is None else ar_growth * 100.0,
            "Inventory growth": None if inv_growth is None else inv_growth * 100.0,
        })
        if not _is_ttm(row):
            if revenue is not None:
                prev_revenue = revenue
            if ar is not None:
                prev_ar = ar
            if inventory is not None:
                prev_inventory = inventory
    return ToolResult(
        "Accounting Reserve Quality Analyzer", ("Q27",), ("6.1", "6.2"), out,
        ("Không tính Beneish lần thứ hai; Module Manipulation vẫn là nguồn chính cho manipulation tests.",
         "Provision vs actual charge-off chỉ hiện khi Data Layer có line-item; thiếu dữ liệu thì để trống.",
         "CFO/NI và tăng AR/Inventory nhanh hơn revenue là evidence để analyst điều tra, không phải kết luận tự động gian lận.",
         "TTM hiện tại không được so growth trực tiếp với FY trước khi thiếu prior-TTM comparable."),
    )
