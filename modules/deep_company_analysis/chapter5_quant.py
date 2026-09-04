from __future__ import annotations

"""Chapter 5 Phase 5B — quantitative bridge.

This module consumes normalized Trecapital financial rows. It never creates a parallel financial
source and never emits a qualitative investment conclusion. Canonical ROIC stays canonical;
Shearn-style analytical variants are explicitly labelled and are computed only when their required
inputs are available. Missing inputs remain Unknown rather than being guessed.
"""

from typing import Any, Iterable, Optional
import math

import pandas as pd


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _pick(row: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _period(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year") or "")


def _annual_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    work = df.copy()
    if "period_type" in work.columns:
        annual = work[work["period_type"].astype(str).str.upper().eq("Y")].copy()
        if not annual.empty:
            work = annual
    if "period" in work.columns:
        work = work[~work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
    if work.empty:
        return []
    if "year" in work.columns:
        work["_year"] = pd.to_numeric(work["year"], errors="coerce")
    else:
        work["_year"] = pd.to_numeric(work.get("period", "").astype(str).str.extract(r"(\d{4})", expand=False), errors="coerce")
    work = work.sort_values("_year").drop(columns=["_year"], errors="ignore")
    return [row.to_dict() for _, row in work.iterrows()]


def _current_row(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    if "period" in df.columns:
        mask = df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        if mask.any():
            return df[mask].iloc[-1].to_dict()
    annual = _annual_rows(df)
    return annual[-1] if annual else df.iloc[-1].to_dict()


def _ratio(num: Optional[float], den: Optional[float], multiplier: float = 1.0) -> Optional[float]:
    if num is None or den is None or abs(den) < 1e-12:
        return None
    return num / den * multiplier


def _metric(row: dict[str, Any], name: str) -> Optional[float]:
    aliases: dict[str, tuple[str, ...]] = {
        "revenue": ("revenue_bil", "net_revenue_bil", "gross_revenue_bil"),
        "revenue_growth": ("revenue_growth_yoy_pct",),
        "gross_margin": ("gross_margin_pct",),
        "ebit_margin": ("core_operating_margin_pct", "operating_margin_pct", "ebit_margin_pct"),
        "roic": ("roic_pct", "roic_standard_pct", "return_on_invested_capital_pct"),
        "cfo": ("cfo_bil", "operating_cash_flow_bil"),
        "capex": ("capex_bil", "capital_expenditure_bil"),
        "fcf": ("free_cash_flow_bil", "fcf_bil"),
        "ebit": ("core_operating_profit_bil", "operating_profit_bil", "ebit_bil"),
        "ebitda": ("ebitda_bil", "core_ebitda_bil"),
        "interest": ("interest_expense_bil", "finance_interest_expense_bil", "interest_cost_bil"),
        "cash": ("cash_and_cash_equivalents_bil", "cash_bil", "cash_equivalents_bil"),
        "debt": ("total_debt_bil", "interest_bearing_debt_bil", "debt_bil"),
        "short_debt": ("short_term_debt_bil", "short_debt_bil", "current_borrowings_bil"),
        "long_debt": ("long_term_debt_bil", "long_debt_bil", "noncurrent_borrowings_bil"),
        "current_assets": ("current_assets_bil",),
        "current_liabilities": ("current_liabilities_bil",),
        "equity": ("equity_bil", "total_equity_bil"),
        "assets": ("total_assets_bil",),
        "goodwill": ("goodwill_bil",),
        "net_ppe": ("net_ppe_bil", "ppe_net_bil", "property_plant_equipment_net_bil"),
        "gross_ppe": ("gross_ppe_bil", "ppe_gross_bil", "property_plant_equipment_gross_bil"),
        "nopat": ("nopat_bil",),
        "invested_capital": ("invested_capital_bil", "average_invested_capital_bil"),
        "pretax": ("pretax_profit_bil", "profit_before_tax_bil"),
        "tax": ("tax_expense_bil", "income_tax_expense_bil"),
        "net_profit": ("net_profit_bil",),
    }
    value = _pick(row, *aliases.get(name, (name,)))
    if value is not None:
        return value
    if name == "gross_margin":
        return _ratio(_pick(row, "gross_profit_bil"), _metric(row, "revenue"), 100.0)
    if name == "ebit_margin":
        return _ratio(_metric(row, "ebit"), _metric(row, "revenue"), 100.0)
    if name == "revenue_growth":
        return None
    return None


def _nopat_proxy(row: dict[str, Any]) -> tuple[Optional[float], str]:
    explicit = _metric(row, "nopat")
    if explicit is not None:
        return explicit, "Canonical/normalized NOPAT"
    ebit = _metric(row, "ebit")
    tax = _metric(row, "tax")
    pretax = _metric(row, "pretax")
    if ebit is not None and tax is not None and pretax is not None and pretax > 0:
        tax_rate = min(max(abs(tax) / pretax, 0.0), 0.60)
        return ebit * (1.0 - tax_rate), "Analytical NOPAT proxy = EBIT × (1 − effective tax rate)"
    return None, "NOPAT unavailable — no tax-rate guess"


def _debt(row: dict[str, Any]) -> Optional[float]:
    total = _metric(row, "debt")
    if total is not None:
        return total
    short = _metric(row, "short_debt")
    long = _metric(row, "long_debt")
    if short is None and long is None:
        return None
    return float(short or 0.0) + float(long or 0.0)


def _total_financing_capital(row: dict[str, Any]) -> Optional[float]:
    equity = _metric(row, "equity")
    debt = _debt(row)
    if equity is None or debt is None:
        return None
    return equity + debt


def _operating_ic_proxy(row: dict[str, Any]) -> Optional[float]:
    explicit = _metric(row, "invested_capital")
    if explicit is not None:
        return explicit
    total = _total_financing_capital(row)
    cash = _metric(row, "cash")
    if total is None or cash is None:
        return None
    return total - cash


def _average(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None:
        return None
    if previous is None:
        return current
    return (current + previous) / 2.0


def build_q22_context(annual_df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    """Financial/operating context only; it does not choose Shearn's critical operating KPIs."""
    rows = _annual_rows(annual_df)[-max(1, int(years)):]
    out: list[dict[str, Any]] = []
    previous_revenue: Optional[float] = None
    for row in rows:
        revenue = _metric(row, "revenue")
        growth = _metric(row, "revenue_growth")
        if growth is None and previous_revenue not in {None, 0} and revenue is not None:
            growth = (revenue / previous_revenue - 1.0) * 100.0
        out.append({
            "Kỳ": _period(row),
            "Doanh thu (tỷ)": revenue,
            "Tăng trưởng DT %": growth,
            "Gross Margin %": _metric(row, "gross_margin"),
            "EBIT Margin %": _metric(row, "ebit_margin"),
            "CFO (tỷ)": _metric(row, "cfo"),
            "CAPEX (tỷ)": _metric(row, "capex"),
            "FCF (tỷ)": _metric(row, "fcf"),
            "ROIC canonical %": _metric(row, "roic"),
        })
        previous_revenue = revenue
    return pd.DataFrame(out)


def build_balance_sheet_context(annual_df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    rows = _annual_rows(annual_df)[-max(1, int(years)):]
    out: list[dict[str, Any]] = []
    for row in rows:
        cash = _metric(row, "cash")
        debt = _debt(row)
        ebit = _metric(row, "ebit")
        ebitda = _metric(row, "ebitda")
        interest = _metric(row, "interest")
        if interest is not None:
            interest = abs(interest)
        out.append({
            "Kỳ": _period(row),
            "Tiền (tỷ)": cash,
            "Nợ vay (tỷ)": debt,
            "Nợ vay ròng (tỷ)": (debt - cash) if debt is not None and cash is not None else None,
            "Debt/EBITDA (x)": _ratio(debt, ebitda),
            "EBIT/Interest (x)": _ratio(ebit, interest),
            "CFO/Interest (x)": _ratio(_metric(row, "cfo"), interest),
            "Current Ratio (x)": _ratio(_metric(row, "current_assets"), _metric(row, "current_liabilities")),
            "Tổng tài sản (tỷ)": _metric(row, "assets"),
            "Vốn CSH (tỷ)": _metric(row, "equity"),
        })
    return pd.DataFrame(out)


def _adjustment_amount(adjustments: Iterable[dict[str, Any]] | None, needles: tuple[str, ...]) -> Optional[float]:
    for row in adjustments or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Adjustment") or "").casefold()
        included = str(row.get("Included?") or "").strip().casefold()
        if included not in {"1", "true", "yes", "y", "x", "✓", "included", "có"}:
            continue
        if any(needle.casefold() in name for needle in needles):
            value = _safe_float(row.get("Amount"))
            if value is not None:
                return abs(value)
    return None


def build_roic_variants(
    annual_df: pd.DataFrame,
    adjustments: Iterable[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Build auditable ROIC views. No analytical variant replaces canonical ROIC.

    Excess-cash and off-BS variants require analyst-confirmed adjustments. The engine deliberately
    does not assume all cash is excess cash.
    """
    rows = _annual_rows(annual_df)
    current = rows[-1] if rows else _current_row(annual_df)
    previous = rows[-2] if len(rows) >= 2 else {}
    if not current:
        return pd.DataFrame()

    canonical = _metric(current, "roic")
    nopat, nopat_source = _nopat_proxy(current)
    cap_cur = _total_financing_capital(current)
    cap_prev = _total_financing_capital(previous) if previous else None
    avg_total_cap = _average(cap_cur, cap_prev)
    roic_with_cash = _ratio(nopat, avg_total_cap, 100.0)

    excess_cash = _adjustment_amount(adjustments, ("excess cash", "tiền dư thừa"))
    off_bs = _adjustment_amount(adjustments, ("off-bs", "off balance", "ngoài bảng"))
    base_excess_den = (avg_total_cap - excess_cash) if avg_total_cap is not None and excess_cash is not None else None
    roic_ex_excess = _ratio(nopat, base_excess_den, 100.0)

    goodwill_cur = _metric(current, "goodwill")
    goodwill_prev = _metric(previous, "goodwill") if previous else None
    avg_goodwill = _average(goodwill_cur, goodwill_prev)
    roic_incl_goodwill = roic_ex_excess
    ex_goodwill_den = (base_excess_den - avg_goodwill) if base_excess_den is not None and avg_goodwill is not None else None
    roic_ex_goodwill = _ratio(nopat, ex_goodwill_den, 100.0)

    gross_cur, net_cur = _metric(current, "gross_ppe"), _metric(current, "net_ppe")
    gross_prev = _metric(previous, "gross_ppe") if previous else None
    net_prev = _metric(previous, "net_ppe") if previous else None
    avg_gross = _average(gross_cur, gross_prev)
    avg_net = _average(net_cur, net_prev)
    gross_den = None
    if base_excess_den is not None and avg_gross is not None and avg_net is not None:
        gross_den = base_excess_den + max(0.0, avg_gross - avg_net)
    roic_gross = _ratio(nopat, gross_den, 100.0)

    off_den = (base_excess_den + off_bs) if base_excess_den is not None and off_bs is not None else None
    roic_off = _ratio(nopat, off_den, 100.0)

    period = _period(current)
    return pd.DataFrame([
        {"ROIC View": "Trecapital Canonical ROIC", "Origin": "Trecapital canonical", "Value %": canonical, "Denominator (tỷ)": None, "Status / Requirement": "Single Source of Truth", "Formula / Note": "Read directly from canonical normalized data."},
        {"ROIC View": "ROIC with cash", "Origin": "Shearn analytical", "Value %": roic_with_cash, "Denominator (tỷ)": avg_total_cap, "Status / Requirement": "Computed" if roic_with_cash is not None else "Missing debt/equity/NOPAT", "Formula / Note": f"NOPAT / average (Equity + interest-bearing debt). {nopat_source}."},
        {"ROIC View": "ROIC ex excess cash", "Origin": "Shearn analytical", "Value %": roic_ex_excess, "Denominator (tỷ)": base_excess_den, "Status / Requirement": "Computed from analyst-confirmed excess cash" if roic_ex_excess is not None else "Requires analyst-confirmed Excess Cash adjustment", "Formula / Note": "NOPAT / [average total financing capital − analyst-confirmed excess cash]. App never assumes all cash is excess."},
        {"ROIC View": "ROIC including goodwill", "Origin": "Shearn analytical", "Value %": roic_incl_goodwill, "Denominator (tỷ)": base_excess_den, "Status / Requirement": "Computed" if roic_incl_goodwill is not None else "Requires excess-cash base", "Formula / Note": "Uses the ex-excess-cash capital base without removing goodwill."},
        {"ROIC View": "ROIC ex goodwill", "Origin": "Shearn analytical", "Value %": roic_ex_goodwill, "Denominator (tỷ)": ex_goodwill_den, "Status / Requirement": "Computed" if roic_ex_goodwill is not None else "Requires goodwill + excess-cash base", "Formula / Note": "NOPAT / [capital base − average goodwill]."},
        {"ROIC View": "ROIC gross-asset adjusted", "Origin": "Shearn analytical", "Value %": roic_gross, "Denominator (tỷ)": gross_den, "Status / Requirement": "Computed" if roic_gross is not None else "Requires gross PP&E + net PP&E + excess-cash base", "Formula / Note": "Adds accumulated PP&E write-down proxy (gross PP&E − net PP&E) to the capital base."},
        {"ROIC View": "ROIC off-BS adjusted", "Origin": "Shearn analytical", "Value %": roic_off, "Denominator (tỷ)": off_den, "Status / Requirement": "Computed from analyst-confirmed off-BS adjustment" if roic_off is not None else "Requires analyst-confirmed off-BS obligation adjustment", "Formula / Note": "Adds analyst-confirmed material off-balance-sheet obligations to the capital base."},
    ]).assign(**{"Kỳ": period})


def build_roic_distortion_diagnostics(annual_df: pd.DataFrame) -> pd.DataFrame:
    rows = _annual_rows(annual_df)
    if not rows:
        return pd.DataFrame()
    current = rows[-1]
    cash, assets = _metric(current, "cash"), _metric(current, "assets")
    goodwill = _metric(current, "goodwill")
    diagnostics = [
        {
            "Diagnostic": "Cash materiality / excess-cash review",
            "Observed": _ratio(cash, assets, 100.0),
            "Unit": "% assets",
            "Status": "Review operating cash vs excess cash" if cash is not None else "Unknown",
            "Auto conclusion?": "No",
        },
        {
            "Diagnostic": "Goodwill / acquisition-capital review",
            "Observed": _ratio(goodwill, assets, 100.0),
            "Unit": "% assets",
            "Status": "Compare incl/ex goodwill when material" if goodwill is not None else "Unknown",
            "Auto conclusion?": "No",
        },
    ]
    if len(rows) >= 3:
        first, last = rows[-3], rows[-1]
        roic0, roic1 = _metric(first, "roic"), _metric(last, "roic")
        ebit0, ebit1 = _metric(first, "ebit"), _metric(last, "ebit")
        ppe0, ppe1 = _metric(first, "net_ppe"), _metric(last, "net_ppe")
        candidate = False
        if None not in {roic0, roic1, ebit0, ebit1, ppe0, ppe1} and abs(float(ebit0)) > 1e-9 and float(ppe0) > 0:
            ebit_change = abs(float(ebit1) / float(ebit0) - 1.0) * 100.0
            ppe_change = (float(ppe1) / float(ppe0) - 1.0) * 100.0
            candidate = float(roic1) - float(roic0) >= 3.0 and ebit_change <= 15.0 and ppe_change <= -10.0
        diagnostics.append({
            "Diagnostic": "Depreciation / aging-asset distortion candidate",
            "Observed": (float(roic1) - float(roic0)) if roic0 is not None and roic1 is not None else None,
            "Unit": "ROIC Δ ppt / 3Y",
            "Status": "Candidate — analyst review" if candidate else "No mechanical flag / insufficient inputs",
            "Auto conclusion?": "No",
        })
    return pd.DataFrame(diagnostics)


def build_reinvestment_context(annual_df: pd.DataFrame, years: int = 6) -> pd.DataFrame:
    """Trecapital extension: descriptive incremental-return context, never a compounder score."""
    rows = _annual_rows(annual_df)[-max(2, int(years)):]
    out: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for row in rows:
        if previous is None:
            previous = row
            continue
        nopat_now, src_now = _nopat_proxy(row)
        nopat_prev, _ = _nopat_proxy(previous)
        ic_now = _operating_ic_proxy(row)
        ic_prev = _operating_ic_proxy(previous)
        delta_nopat = (nopat_now - nopat_prev) if nopat_now is not None and nopat_prev is not None else None
        delta_ic = (ic_now - ic_prev) if ic_now is not None and ic_prev is not None else None
        inc_roic = _ratio(delta_nopat, delta_ic, 100.0) if delta_ic is not None and delta_ic > 0 else None
        out.append({
            "Kỳ": _period(row),
            "ΔNOPAT (tỷ)": delta_nopat,
            "ΔInvested Capital proxy (tỷ)": delta_ic,
            "Incremental ROIC %": inc_roic,
            "NOPAT Source": src_now,
            "Interpretation": "Analyst only — cyclical/base effects must be reviewed",
        })
        previous = row
    return pd.DataFrame(out)


def build_chapter5_quant_context(
    ticker: str,
    company_name: str,
    annual_df: pd.DataFrame,
    source_label: str = "Trecapital canonical data",
    adjustments: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = _current_row(annual_df)
    if not current:
        return {}
    q22 = build_q22_context(annual_df)
    q25 = build_balance_sheet_context(annual_df)
    q26 = build_roic_variants(annual_df, adjustments=adjustments)
    return {
        "ticker": str(ticker or "").upper().strip(),
        "company_name": company_name or "",
        "latest_period": _period(current),
        "q22_context": q22,
        "q25_context": q25,
        "q26_variants": q26,
        "q26_distortions": build_roic_distortion_diagnostics(annual_df),
        "reinvestment_context": build_reinvestment_context(annual_df),
        "canonical_roic_latest": _metric(current, "roic"),
        "provenance": {
            "source_label": source_label or "Trecapital canonical data",
            "source_module": "Trecapital canonical financial data / Module 1",
            "data_origin": "Canonical Trecapital normalized statements",
            "data_period": _period(current),
        },
        "guardrails": {
            "auto_operating_metric_criticality": False,
            "auto_balance_sheet_conclusion": False,
            "auto_roic_quality_conclusion": False,
            "auto_compounder_conclusion": False,
            "assume_all_cash_is_excess": False,
            "invent_off_bs_obligation": False,
        },
    }
