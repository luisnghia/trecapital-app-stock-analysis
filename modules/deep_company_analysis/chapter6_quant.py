from __future__ import annotations

"""Chapter 6 Phase 6B — quantitative bridge from Trecapital canonical data.

The bridge is evidence-only. It consumes normalized Trecapital rows and never creates a
parallel financial source, never overwrites analyst answers, and never emits an investment
recommendation or a mechanical earnings-distribution score.
"""

from dataclasses import dataclass
from typing import Any, Optional
import math

import pandas as pd


FINANCIAL_INDUSTRY_TOKENS = (
    "bank",
    "ngân hàng",
    "securities",
    "chứng khoán",
    "insurance",
    "bảo hiểm",
    "financial services",
    "dịch vụ tài chính",
    "finance",
    "tài chính",
)


@dataclass(frozen=True)
class QuantProvenance:
    ticker: str
    company_name: str
    industry: str
    sub_industry: str
    source_label: str
    latest_period: str
    source_module: str = "Trecapital canonical financial data / Module 1"
    data_origin: str = "Canonical Trecapital normalized statements"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _pick_with_field(row: dict[str, Any], *keys: str) -> tuple[Optional[float], str]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value, key
    return None, ""


def _pick(row: dict[str, Any], *keys: str) -> Optional[float]:
    return _pick_with_field(row, *keys)[0]


def _period(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year") or "")


def _is_ttm(row: dict[str, Any]) -> bool:
    text = _period(row).upper()
    return "TTM" in text or "T12M" in text


def _annual_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    work = df.copy()
    if "period_type" in work.columns:
        annual = work[work["period_type"].astype(str).str.upper().eq("Y")].copy()
        if not annual.empty:
            work = annual
    if "period" in work.columns:
        work = work[~work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)].copy()
    if work.empty:
        return []
    if "year" in work.columns:
        work["_year"] = pd.to_numeric(work["year"], errors="coerce")
    elif "period" in work.columns:
        work["_year"] = pd.to_numeric(work["period"].astype(str).str.extract(r"(\d{4})", expand=False), errors="coerce")
    else:
        work["_year"] = range(len(work))
    work = work.sort_values("_year").drop(columns=["_year"], errors="ignore")
    return [row.to_dict() for _, row in work.iterrows()]


def _ttm_row(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty or "period" not in df.columns:
        return {}
    mask = df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
    return df[mask].iloc[-1].to_dict() if mask.any() else {}


def _ratio(num: Optional[float], den: Optional[float], multiplier: float = 1.0) -> Optional[float]:
    if num is None or den is None or abs(den) < 1e-12:
        return None
    return num / den * multiplier


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous <= 0:
        return None
    return (current / previous - 1.0) * 100.0


def _revenue(row: dict[str, Any]) -> Optional[float]:
    return _pick(row, "revenue_bil", "net_revenue_bil", "gross_revenue_bil")


def _ebit(row: dict[str, Any]) -> Optional[float]:
    return _pick(row, "core_operating_profit_bil", "operating_profit_bil", "ebit_bil")


def _net_income(row: dict[str, Any]) -> Optional[float]:
    return _pick(row, "net_profit_bil", "net_income_bil")


def _cfo(row: dict[str, Any]) -> Optional[float]:
    return _pick(row, "cfo_bil", "operating_cash_flow_bil")


def _gross_margin(row: dict[str, Any]) -> Optional[float]:
    explicit = _pick(row, "gross_margin_pct")
    if explicit is not None:
        return explicit
    revenue = _revenue(row)
    gross_profit = _pick(row, "gross_profit_bil")
    return _ratio(gross_profit, revenue, 100.0)


def _ebit_margin(row: dict[str, Any]) -> Optional[float]:
    explicit = _pick(row, "core_operating_margin_pct", "operating_margin_pct", "ebit_margin_pct")
    if explicit is not None:
        return explicit
    return _ratio(_ebit(row), _revenue(row), 100.0)


def _financial_company(industry: str, sub_industry: str) -> bool:
    text = f"{industry} {sub_industry}".casefold()
    return any(token.casefold() in text for token in FINANCIAL_INDUSTRY_TOKENS)


def _history_rows(df: pd.DataFrame, years: int = 10, include_ttm: bool = True) -> list[dict[str, Any]]:
    rows = _annual_rows(df)[-max(1, int(years)):]
    if include_ttm:
        ttm = _ttm_row(df)
        if ttm:
            rows = rows + [ttm]
    return rows


def build_q27_accounting_quality(df: pd.DataFrame, years: int = 10) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = _history_rows(df, years=years, include_ttm=True)
    out: list[dict[str, Any]] = []
    cumulative_cfo = 0.0
    cumulative_ni = 0.0
    cumulative_count = 0
    tax_available = False
    current_tax_fields: set[str] = set()

    for row in rows:
        ni = _net_income(row)
        cfo = _cfo(row)
        ratio = _ratio(cfo, ni) if ni is not None and ni > 0 else None
        gap = (cfo - ni) if cfo is not None and ni is not None else None
        overlapping_ttm = _is_ttm(row)
        if cfo is not None and ni is not None and not overlapping_ttm:
            cumulative_cfo += cfo
            cumulative_ni += ni
            cumulative_count += 1
        cumulative_ratio = _ratio(cumulative_cfo, cumulative_ni) if cumulative_count and cumulative_ni > 0 and not overlapping_ttm else None

        provision, provision_field = _pick_with_field(row, "tax_expense_bil", "income_tax_expense_bil")
        current_tax, current_tax_field = _pick_with_field(
            row,
            "current_tax_expense_bil",
            "current_income_tax_expense_bil",
            "current_income_tax_bil",
            "current_tax_bil",
        )
        tax_gap_pct = None
        if provision is not None and current_tax is not None and abs(provision) > 1e-12:
            tax_available = True
            current_tax_fields.add(current_tax_field)
            tax_gap_pct = abs(abs(current_tax) - abs(provision)) / abs(provision) * 100.0

        out.append({
            "Kỳ": _period(row),
            "LNST (tỷ)": ni,
            "CFO (tỷ)": cfo,
            "CFO/NI (x)": ratio,
            "CFO - NI (tỷ)": gap,
            "Cumulative CFO (tỷ)": cumulative_cfo if cumulative_count and not overlapping_ttm else None,
            "Cumulative NI (tỷ)": cumulative_ni if cumulative_count and not overlapping_ttm else None,
            "Cumulative CFO/NI (x)": cumulative_ratio,
            "Tax Provision (tỷ)": abs(provision) if provision is not None else None,
            "Current Tax (tỷ)": abs(current_tax) if current_tax is not None else None,
            "Current Tax vs Provision Gap (%)": tax_gap_pct,
            "Tax Data Status": (
                f"Available: {current_tax_field} vs {provision_field}"
                if tax_gap_pct is not None
                else "N/A — current tax expense not separately available"
            ),
        })

    annual = pd.DataFrame([r for r in out if "TTM" not in str(r.get("Kỳ", "")).upper() and "T12M" not in str(r.get("Kỳ", "")).upper()])
    summary = {
        "annual_periods": int(len(annual)),
        "cumulative_cfo_bil": cumulative_cfo if cumulative_count else None,
        "cumulative_net_income_bil": cumulative_ni if cumulative_count else None,
        "cumulative_cfo_to_ni": _ratio(cumulative_cfo, cumulative_ni) if cumulative_ni > 0 else None,
        "tax_comparison_available": tax_available,
        "current_tax_source_fields": sorted(current_tax_fields),
        "tax_guardrail": "tax_paid_bil is NOT treated as current-tax expense",
    }
    return pd.DataFrame(out), summary


def build_q28_disclosed_recurring(df: pd.DataFrame) -> pd.DataFrame:
    """Expose only explicit canonical recurring-revenue fields; never infer a share."""
    candidates = (
        ("recurring_revenue_pct", "Recurring revenue"),
        ("contracted_revenue_pct", "Contracted revenue"),
        ("subscription_revenue_pct", "Subscription revenue"),
        ("recurring_revenue_share_pct", "Recurring revenue"),
    )
    rows: list[dict[str, Any]] = []
    for row in _history_rows(df, years=10, include_ttm=True):
        for field, label in candidates:
            value = _safe_float(row.get(field))
            if value is None:
                continue
            rows.append({
                "Kỳ": _period(row),
                "Disclosed Metric": label,
                "Disclosed Share (%)": value,
                "Source Field": field,
                "Boundary": "Explicit canonical disclosure only — no inference",
            })
    return pd.DataFrame(rows)


def build_q29_cycle_history(df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    rows = _history_rows(df, years=years, include_ttm=True)
    out: list[dict[str, Any]] = []
    prev_revenue: Optional[float] = None
    prev_ebit: Optional[float] = None
    revenue_peak: Optional[float] = None
    ebit_peak: Optional[float] = None

    for row in rows:
        revenue = _revenue(row)
        ebit = _ebit(row)
        revenue_growth = _pct_change(revenue, prev_revenue)
        ebit_growth = _pct_change(ebit, prev_ebit)
        if revenue is not None:
            revenue_peak = revenue if revenue_peak is None else max(revenue_peak, revenue)
        if ebit is not None:
            ebit_peak = ebit if ebit_peak is None else max(ebit_peak, ebit)
        revenue_drawdown = _ratio(revenue - revenue_peak, revenue_peak, 100.0) if revenue is not None and revenue_peak and revenue_peak > 0 else None
        ebit_drawdown = _ratio(ebit - ebit_peak, ebit_peak, 100.0) if ebit is not None and ebit_peak and ebit_peak > 0 else None
        out.append({
            "Kỳ": _period(row),
            "Doanh thu (tỷ)": revenue,
            "Tăng trưởng DT (%)": revenue_growth,
            "EBIT (tỷ)": ebit,
            "Tăng trưởng EBIT (%)": ebit_growth,
            "Gross Margin (%)": _gross_margin(row),
            "EBIT Margin (%)": _ebit_margin(row),
            "Revenue Drawdown from Peak (%)": revenue_drawdown,
            "EBIT Drawdown from Peak (%)": ebit_drawdown,
        })
        if not _is_ttm(row):
            prev_revenue = revenue
            prev_ebit = ebit
    return pd.DataFrame(out)


def build_q30_dol(df: pd.DataFrame, years: int = 10, min_revenue_change_pct: float = 1.0) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = _annual_rows(df)[-max(2, int(years)):]
    out: list[dict[str, Any]] = []
    valid_values: list[float] = []
    downside: list[float] = []
    upside: list[float] = []

    previous: Optional[dict[str, Any]] = None
    for row in rows:
        period = _period(row)
        revenue = _revenue(row)
        ebit = _ebit(row)
        if previous is None:
            out.append({
                "Kỳ": period,
                "Δ Revenue (%)": None,
                "Δ EBIT (%)": None,
                "Historical DOL (x)": None,
                "Observation": "Base period",
                "Validity": "N/A",
                "Invalid Reason": "No prior annual period",
            })
            previous = row
            continue

        prev_revenue = _revenue(previous)
        prev_ebit = _ebit(previous)
        rev_change = _pct_change(revenue, prev_revenue)
        ebit_change = _pct_change(ebit, prev_ebit)
        reason = ""
        valid = True
        if rev_change is None:
            valid = False
            reason = "Revenue growth undefined"
        elif abs(rev_change) < float(min_revenue_change_pct):
            valid = False
            reason = f"|Revenue change| < {min_revenue_change_pct:.1f}% — DOL unstable"
        elif prev_ebit is None or ebit is None or prev_ebit <= 0 or ebit <= 0:
            valid = False
            reason = "EBIT non-positive/sign-shift — percentage leverage not economically stable"
        elif ebit_change is None:
            valid = False
            reason = "EBIT growth undefined"

        dol = _ratio(ebit_change, rev_change) if valid else None
        observation = "Flat"
        if rev_change is not None and rev_change < 0:
            observation = "Downside"
        elif rev_change is not None and rev_change > 0:
            observation = "Upside"

        if dol is not None and math.isfinite(dol):
            valid_values.append(dol)
            if observation == "Downside":
                downside.append(dol)
            elif observation == "Upside":
                upside.append(dol)

        out.append({
            "Kỳ": period,
            "Δ Revenue (%)": rev_change,
            "Δ EBIT (%)": ebit_change,
            "Historical DOL (x)": dol,
            "Observation": observation,
            "Validity": "Valid" if dol is not None else "Invalid",
            "Invalid Reason": reason,
        })
        previous = row

    ttm = _ttm_row(df)
    if ttm:
        out.append({
            "Kỳ": _period(ttm),
            "Δ Revenue (%)": None,
            "Δ EBIT (%)": None,
            "Historical DOL (x)": None,
            "Observation": "TTM current context",
            "Validity": "N/A",
            "Invalid Reason": "TTM displayed; comparable prior TTM is required for DOL. No FY-vs-TTM sensitivity is fabricated.",
        })

    def median(values: list[float]) -> Optional[float]:
        return float(pd.Series(values, dtype="float64").median()) if values else None

    return pd.DataFrame(out), {
        "valid_observations": len(valid_values),
        "median_dol": median(valid_values),
        "downside_median_dol": median(downside),
        "upside_median_dol": median(upside),
        "invalid_observations": sum(1 for item in out if item.get("Validity") == "Invalid"),
        "guardrail": "Invalid rows remain visible and are excluded from medians; no automatic operating-leverage conclusion.",
    }


def _operating_working_capital(row: dict[str, Any]) -> tuple[Optional[float], str]:
    explicit, field = _pick_with_field(row, "operating_working_capital_bil", "roic_working_capital_bil")
    if explicit is not None:
        return explicit, field
    current_assets = _pick(row, "current_assets_bil")
    current_liabilities = _pick(row, "current_liabilities_bil")
    if current_assets is None or current_liabilities is None:
        return None, ""
    cash = _pick(row, "cash_equivalents_bil", "cash_bil") or 0.0
    short_investments = _pick(row, "short_term_investments_bil") or 0.0
    short_debt = _pick(row, "short_term_debt_bil") or 0.0
    current_ltd = _pick(row, "current_portion_long_term_debt_bil") or 0.0
    operating_assets = current_assets - cash - short_investments
    operating_liabilities = max(0.0, current_liabilities - abs(short_debt) - abs(current_ltd))
    return operating_assets - operating_liabilities, "Derived: CA - cash - STI - (CL - current debt)"


def _days_metric(
    current_balance: Optional[float],
    previous_balance: Optional[float],
    flow: Optional[float],
    canonical_value: Optional[float],
) -> tuple[Optional[float], str]:
    if current_balance is not None and previous_balance is not None and flow is not None and flow > 0:
        average = (current_balance + previous_balance) / 2.0
        if average >= 0:
            return average / flow * 365.0, "Average current/prior balance"
    if canonical_value is not None:
        return canonical_value, "Canonical metric fallback"
    return None, "Insufficient average-balance inputs"


def build_q31_working_capital(
    df: pd.DataFrame,
    years: int = 10,
    *,
    industry: str = "",
    sub_industry: str = "",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if _financial_company(industry, sub_industry):
        return pd.DataFrame(), {
            "applicable": False,
            "status": "N/A — not economically applicable",
            "reason": "CCC/operating working-capital mechanics are not decision-useful in the same way for banks/insurers/securities/financial services.",
        }

    rows = _history_rows(df, years=years, include_ttm=True)
    out: list[dict[str, Any]] = []
    previous: Optional[dict[str, Any]] = None
    previous_owc: Optional[float] = None

    for row in rows:
        revenue = _revenue(row)
        cogs = _pick(row, "cost_of_goods_sold_bil", "cogs_bil")
        ar = _pick(row, "accounts_receivable_bil", "receivables_bil")
        inventory = _pick(row, "inventory_bil")
        ap = _pick(row, "accounts_payable_bil", "payables_bil")
        prev_ar = _pick(previous, "accounts_receivable_bil", "receivables_bil") if previous else None
        prev_inventory = _pick(previous, "inventory_bil") if previous else None
        prev_ap = _pick(previous, "accounts_payable_bil", "payables_bil") if previous else None

        dso, dso_basis = _days_metric(ar, prev_ar, revenue, _pick(row, "dso_days"))
        dio, dio_basis = _days_metric(inventory, prev_inventory, cogs, _pick(row, "dio_days"))
        dpo, dpo_basis = _days_metric(ap, prev_ap, cogs, _pick(row, "dpo_days"))
        ccc = (dso + dio - dpo) if dso is not None and dio is not None and dpo is not None else _pick(row, "cash_conversion_cycle_days")
        owc, owc_basis = _operating_working_capital(row)
        delta_owc = (owc - previous_owc) if owc is not None and previous_owc is not None else None
        cash_impact = -delta_owc if delta_owc is not None else None
        canonical_cfs_wc = _pick(row, "working_capital_change_bil")
        reconciliation_gap = (cash_impact - canonical_cfs_wc) if cash_impact is not None and canonical_cfs_wc is not None else None
        basis = "; ".join(sorted({dso_basis, dio_basis, dpo_basis, owc_basis} - {""}))

        out.append({
            "Kỳ": _period(row),
            "AR (tỷ)": ar,
            "Inventory (tỷ)": inventory,
            "AP (tỷ)": ap,
            "DSO (ngày)": dso,
            "DIO (ngày)": dio,
            "DPO (ngày)": dpo,
            "CCC (ngày)": ccc,
            "OWC (tỷ)": owc,
            "Δ OWC (tỷ)": delta_owc,
            "Cash Impact from ΔOWC (tỷ)": cash_impact,
            "Canonical CFS WC Change (tỷ)": canonical_cfs_wc,
            "Reconciliation Gap (tỷ)": reconciliation_gap,
            "Metric Basis": basis,
        })
        previous = row
        previous_owc = owc

    valid_ccc = pd.to_numeric(pd.DataFrame(out).get("CCC (ngày)", pd.Series(dtype=float)), errors="coerce").dropna()
    return pd.DataFrame(out), {
        "applicable": True,
        "status": "Applicable",
        "valid_ccc_periods": int(valid_ccc.count()),
        "cash_sign_convention": "Cash impact = -ΔOWC; positive means cash released, negative means cash absorbed.",
        "reconciliation_note": "Balance-sheet ΔOWC may differ from canonical CFS WC change because of classification, FX, M&A or other statement mapping effects.",
    }


def build_q32_capex(
    df: pd.DataFrame,
    years: int = 10,
    *,
    industry: str = "",
    sub_industry: str = "",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = _history_rows(df, years=years, include_ttm=True)
    out: list[dict[str, Any]] = []
    for row in rows:
        revenue = _revenue(row)
        cfo = _cfo(row)
        raw_capex, capex_field = _pick_with_field(row, "capex_bil", "capital_expenditure_bil")
        capex = abs(raw_capex) if raw_capex is not None else None
        depreciation = _pick(row, "depreciation_bil", "depreciation_amortization_bil", "d_and_a_bil")
        depreciation = abs(depreciation) if depreciation is not None else None
        fcf = _pick(row, "free_cash_flow_bil", "fcf_bil")
        if fcf is None and cfo is not None and capex is not None:
            fcf = cfo - capex
        net_ppe = _pick(row, "net_ppe_bil", "ppe_net_bil", "property_plant_equipment_net_bil", "fixed_assets_bil")
        gross_ppe = _pick(row, "gross_ppe_bil", "ppe_gross_bil", "property_plant_equipment_gross_bil")
        out.append({
            "Kỳ": _period(row),
            "Doanh thu (tỷ)": revenue,
            "CFO (tỷ)": cfo,
            "Total Capex (tỷ)": capex,
            "D&A (tỷ)": depreciation,
            "Capex/Revenue (%)": _ratio(capex, revenue, 100.0),
            "Capex/D&A (x)": _ratio(capex, depreciation),
            "FCF (tỷ)": fcf,
            "FCF Margin (%)": _ratio(fcf, revenue, 100.0),
            "Net PP&E (tỷ)": net_ppe,
            "Gross PP&E (tỷ)": gross_ppe,
            "Net/Gross PP&E (%)": _ratio(net_ppe, gross_ppe, 100.0),
            "Capex Source Field": capex_field,
        })

    frame = pd.DataFrame(out)
    capex_intensity = pd.to_numeric(frame.get("Capex/Revenue (%)", pd.Series(dtype=float)), errors="coerce").dropna()
    capex_da = pd.to_numeric(frame.get("Capex/D&A (x)", pd.Series(dtype=float)), errors="coerce").dropna()
    financial = _financial_company(industry, sub_industry)
    return frame, {
        "applicable": True,
        "relevance": "Limited / interpret with financial-sector economics" if financial else "Normal operating-business relevance",
        "median_capex_to_revenue_pct": float(capex_intensity.median()) if not capex_intensity.empty else None,
        "median_capex_to_da": float(capex_da.median()) if not capex_da.empty else None,
        "maintenance_capex_guardrail": (
            "Phase 6B deliberately does NOT import Module-1 maintenance_capex_bil because that field may be a generic Owner-Earnings proxy. "
            "Chapter 6 maintenance capex remains company-disclosed / analyst-estimated / explicitly selected D&A rough proxy / Unknown."
        ),
    }


def _provenance_table(prov: QuantProvenance) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Question": "Q27",
            "Metrics": "CFO/NI; CFO-NI; cumulative cash conversion; current-tax vs provision when separately disclosed",
            "Source Field(s)": "cfo_bil; net_profit_bil; tax_expense_bil; current_tax_* only",
            "Formula / Boundary": "tax_paid_bil is never substituted for current-tax expense",
            "Source Module": prov.source_module,
            "Data Origin": prov.data_origin,
        },
        {
            "Question": "Q28",
            "Metrics": "Explicit recurring/contracted/subscription revenue share only",
            "Source Field(s)": "recurring_revenue_pct / contracted_revenue_pct / subscription_revenue_pct if present",
            "Formula / Boundary": "No inferred recurring share",
            "Source Module": prov.source_module,
            "Data Origin": prov.data_origin,
        },
        {
            "Question": "Q29",
            "Metrics": "Revenue/EBIT growth, margins, peak drawdowns",
            "Source Field(s)": "revenue_bil; core_operating_profit_bil/operating_profit_bil; gross_profit_bil",
            "Formula / Boundary": "Historical variability only; no automatic causal/cycle label",
            "Source Module": prov.source_module,
            "Data Origin": prov.data_origin,
        },
        {
            "Question": "Q30",
            "Metrics": "Historical DOL",
            "Source Field(s)": "revenue_bil; core_operating_profit_bil/operating_profit_bil",
            "Formula / Boundary": "%ΔEBIT / %ΔRevenue; invalid rows visible, excluded from medians",
            "Source Module": prov.source_module,
            "Data Origin": prov.data_origin,
        },
        {
            "Question": "Q31",
            "Metrics": "DSO/DIO/DPO/CCC; OWC; ΔOWC cash impact; CFS reconciliation",
            "Source Field(s)": "AR; inventory; AP; revenue; COGS; operating_working_capital_bil; working_capital_change_bil",
            "Formula / Boundary": "Average balances; cash impact = -ΔOWC; financial-sector N/A guardrail",
            "Source Module": prov.source_module,
            "Data Origin": prov.data_origin,
        },
        {
            "Question": "Q32",
            "Metrics": "Total Capex intensity; Capex/D&A; FCF; Net/Gross PP&E",
            "Source Field(s)": "capex_bil; depreciation_bil; cfo_bil; free_cash_flow_bil; PP&E fields",
            "Formula / Boundary": "No silent maintenance-capex import or inference",
            "Source Module": prov.source_module,
            "Data Origin": prov.data_origin,
        },
    ])


def build_chapter6_quant_context(
    ticker: str,
    company_name: str,
    annual_and_ttm_df: pd.DataFrame,
    *,
    industry: str = "",
    sub_industry: str = "",
    source_label: str = "Trecapital canonical data",
    years: int = 10,
) -> dict[str, Any]:
    if not isinstance(annual_and_ttm_df, pd.DataFrame) or annual_and_ttm_df.empty:
        return {}
    annual = _annual_rows(annual_and_ttm_df)
    ttm = _ttm_row(annual_and_ttm_df)
    latest = _period(ttm) if ttm else (_period(annual[-1]) if annual else "")
    prov = QuantProvenance(
        ticker=str(ticker).upper().strip(),
        company_name=company_name or "",
        industry=industry or "",
        sub_industry=sub_industry or "",
        source_label=source_label or "Trecapital canonical data",
        latest_period=latest,
    )

    q27, q27_summary = build_q27_accounting_quality(annual_and_ttm_df, years=years)
    q28 = build_q28_disclosed_recurring(annual_and_ttm_df)
    q29 = build_q29_cycle_history(annual_and_ttm_df, years=years)
    q30, q30_summary = build_q30_dol(annual_and_ttm_df, years=years)
    q31, q31_summary = build_q31_working_capital(
        annual_and_ttm_df,
        years=years,
        industry=industry,
        sub_industry=sub_industry,
    )
    q32, q32_summary = build_q32_capex(
        annual_and_ttm_df,
        years=years,
        industry=industry,
        sub_industry=sub_industry,
    )

    warnings: list[str] = []
    if not q27_summary.get("tax_comparison_available"):
        warnings.append("Q27: current-tax expense is not separately available; Tax vs Book diagnostic remains N/A. tax_paid_bil is not substituted.")
    if q28.empty:
        warnings.append("Q28: canonical dataset has no explicit recurring/contracted revenue share; Phase 6B does not infer one.")
    if not q31_summary.get("applicable", True):
        warnings.append("Q31: CCC/OWC diagnostic marked N/A for the identified financial-sector business model.")
    if int(q30_summary.get("valid_observations") or 0) < 3:
        warnings.append("Q30: fewer than 3 valid historical DOL observations; do not rely on a summary DOL.")
    if q32.empty:
        warnings.append("Q32: canonical data does not contain usable capex history.")
    elif "Gross PP&E (tỷ)" in q32.columns and pd.to_numeric(q32["Gross PP&E (tỷ)"], errors="coerce").notna().sum() == 0:
        warnings.append("Q32: Gross PP&E unavailable; asset-age Net/Gross PP&E diagnostic remains N/A.")

    return {
        "ticker": prov.ticker,
        "company_name": prov.company_name,
        "industry": prov.industry,
        "sub_industry": prov.sub_industry,
        "latest_period": prov.latest_period,
        "q27_accounting_quality": q27,
        "q27_summary": q27_summary,
        "q28_disclosed_recurring": q28,
        "q29_cycle_history": q29,
        "q30_dol_history": q30,
        "q30_summary": q30_summary,
        "q31_working_capital": q31,
        "q31_summary": q31_summary,
        "q32_capex_history": q32,
        "q32_summary": q32_summary,
        "coverage_warnings": warnings,
        "provenance_table": _provenance_table(prov),
        "provenance": {
            "source_label": prov.source_label,
            "source_module": prov.source_module,
            "source_period": prov.latest_period,
            "data_origin": prov.data_origin,
            "industry": prov.industry,
            "sub_industry": prov.sub_industry,
        },
        "guardrails": {
            "auto_accounting_quality_conclusion": False,
            "auto_recurring_revenue_share": False,
            "auto_cycle_classification": False,
            "auto_operating_leverage_conclusion": False,
            "auto_working_capital_quality_conclusion": False,
            "auto_maintenance_capex": False,
            "auto_distribution_width": False,
            "auto_mos_change": False,
            "auto_buy_hold_sell": False,
        },
    }


__all__ = [
    "build_chapter6_quant_context",
    "build_q27_accounting_quality",
    "build_q28_disclosed_recurring",
    "build_q29_cycle_history",
    "build_q30_dol",
    "build_q31_working_capital",
    "build_q32_capex",
]
