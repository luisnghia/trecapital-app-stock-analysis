from __future__ import annotations

"""Chapter 8 Phase 8B — structured data bridge.

This module connects the Chapter 8 source-locked workspace to two existing sources:
1) Chapter 7 manager identity/background records (manager master), and
2) Trecapital canonical normalized financial rows (financial single source of truth).

It deliberately does not perform web research, does not write analyst assessments, and does not
produce a management score or investment recommendation. Missing fields remain missing/Unknown.
"""

from typing import Any, Iterable, Optional
import math

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8


CANONICAL_SOURCE_LABEL = "Trecapital canonical financial data / Module 1"
CANONICAL_DATA_ORIGIN = "Canonical Trecapital normalized statements"
MANAGER_SOURCE_LABEL = "Chapter 7 manager master"


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
    return str(row.get("period") or row.get("year") or "").strip()


def _metric(row: dict[str, Any], name: str) -> Optional[float]:
    aliases: dict[str, tuple[str, ...]] = {
        "revenue": ("revenue_bil", "net_revenue_bil", "gross_revenue_bil"),
        "gross_profit": ("gross_profit_bil",),
        "ebit": ("core_operating_profit_bil", "operating_profit_bil", "ebit_bil"),
        "cfo": ("cfo_bil", "operating_cash_flow_bil"),
        "capex": ("capex_bil", "capital_expenditure_bil"),
        "fcf": ("free_cash_flow_bil", "fcf_bil"),
        "cash": ("cash_and_cash_equivalents_bil", "cash_bil", "cash_equivalents_bil"),
        "dividend_cash": ("cash_dividend_bil", "dividends_paid_bil", "dividend_paid_bil", "cash_dividends_paid_bil"),
        "acquisition_cash": ("acquisition_cash_bil", "cash_paid_for_acquisitions_bil", "acquisitions_bil"),
        "buyback_cash": ("share_buyback_cash_bil", "stock_repurchases_bil", "share_repurchases_bil", "treasury_share_purchase_bil"),
        "buyback_shares": ("shares_repurchased", "share_repurchases", "treasury_shares_purchased"),
        "shares": ("shares_outstanding", "shares_outstanding_mil", "weighted_avg_shares_mil", "shares_mil"),
        "sga": ("sga_expense_bil", "selling_general_admin_expense_bil", "selling_admin_expense_bil"),
        "admin": ("admin_expense_bil", "general_admin_expense_bil"),
        "selling": ("selling_expense_bil",),
        "roic": ("roic_pct", "roic_standard_pct", "return_on_invested_capital_pct"),
    }
    return _pick(row, *aliases.get(name, (name,)))


def _annual_rows(df: pd.DataFrame, years: int = 10, include_ttm: bool = True) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    work = df.copy()
    if "period_type" in work.columns:
        annual = work[work["period_type"].astype(str).str.upper().eq("Y")].copy()
        if not annual.empty:
            work = annual
    ttm_rows = pd.DataFrame()
    if "period" in work.columns:
        mask = work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        ttm_rows = work[mask].copy()
        work = work[~mask].copy()
    if "year" in work.columns:
        work["_sort_year"] = pd.to_numeric(work["year"], errors="coerce")
    elif "period" in work.columns:
        work["_sort_year"] = pd.to_numeric(work["period"].astype(str).str.extract(r"(\d{4})", expand=False), errors="coerce")
    else:
        work["_sort_year"] = range(len(work))
    work = work.sort_values("_sort_year").drop(columns=["_sort_year"], errors="ignore").tail(max(1, int(years)))
    rows = [r.to_dict() for _, r in work.iterrows()]
    if include_ttm and not ttm_rows.empty:
        rows.append(ttm_rows.iloc[-1].to_dict())
    return rows


def build_manager_reference(chapter7_payload: dict[str, Any] | None) -> pd.DataFrame:
    """Reference Chapter 7 manager IDs; never creates a second manager master."""
    profiles = (chapter7_payload or {}).get("management_profiles", [])
    out: list[dict[str, Any]] = []
    for row in profiles if isinstance(profiles, list) else []:
        if not isinstance(row, dict):
            continue
        manager_id = str(row.get("Manager ID") or "").strip()
        manager = str(row.get("Manager") or "").strip()
        if not manager_id and not manager:
            continue
        out.append({
            "Manager ID": manager_id,
            "Manager": manager,
            "Current Role": str(row.get("Current Role") or "").strip(),
            "Analyst Classification": str(row.get("Analyst Classification") or "Unknown").strip() or "Unknown",
            "Chapter 7 Confidence": str(row.get("Confidence") or "Unknown").strip() or "Unknown",
            "Source": MANAGER_SOURCE_LABEL,
        })
    return pd.DataFrame(out, columns=[
        "Manager ID", "Manager", "Current Role", "Analyst Classification", "Chapter 7 Confidence", "Source"
    ])


def normalize_guidance_rows(rows: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    """Normalize disclosed guidance and calculate only arithmetic range outcome.

    The function does not infer intent, conservatism, sandbagging, manipulation or management quality.
    """
    out: list[dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        low = _safe_float(item.get("Guidance Low"))
        high = _safe_float(item.get("Guidance High"))
        point = _safe_float(item.get("Guidance Point"))
        actual = _safe_float(item.get("Actual"))
        event = str(item.get("Guidance Event") or "Unknown").strip()
        if event not in ch8.GUIDANCE_EVENT_OPTIONS:
            event = "Unknown"
        outcome = "Unknown"
        if event == "Withdrawn":
            outcome = "N/A"
        elif actual is not None:
            if low is not None and high is not None:
                lo, hi = min(low, high), max(low, high)
                outcome = "Beat" if actual > hi else "Miss" if actual < lo else "Meet"
            elif point is not None:
                outcome = "Beat" if actual > point else "Miss" if actual < point else "Meet"
        out.append({
            "Issued Date": str(item.get("Issued Date") or "").strip(),
            "Metric": str(item.get("Metric") or "").strip(),
            "Horizon": str(item.get("Horizon") or "").strip(),
            "Guidance Low": low,
            "Guidance High": high,
            "Guidance Point": point,
            "Guidance Event": event,
            "Actual": actual,
            "Outcome": outcome,
            "Source": str(item.get("Source") or "").strip(),
            "Analyst Note": str(item.get("Analyst Note") or "").strip(),
        })
    return pd.DataFrame(out, columns=ch8.GUIDANCE_HISTORY_COLUMNS)


def build_q45_cost_context(annual_df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    """Canonical cost context only; no automatic conclusion that lower cost is better."""
    out: list[dict[str, Any]] = []
    for row in _annual_rows(annual_df, years=years, include_ttm=True):
        revenue = _metric(row, "revenue")
        gross_profit = _metric(row, "gross_profit")
        cogs = (revenue - gross_profit) if revenue is not None and gross_profit is not None else None
        sga = _metric(row, "sga")
        if sga is None:
            selling = _metric(row, "selling")
            admin = _metric(row, "admin")
            if selling is not None or admin is not None:
                sga = float(selling or 0.0) + float(admin or 0.0)
        ebit = _metric(row, "ebit")
        out.append({
            "Kỳ": _period(row),
            "Doanh thu (tỷ)": revenue,
            "COGS canonical/derived (tỷ)": cogs,
            "COGS/Doanh thu %": (cogs / revenue * 100.0) if cogs is not None and revenue not in {None, 0} else None,
            "SG&A explicit (tỷ)": sga,
            "SG&A/Doanh thu %": (abs(sga) / revenue * 100.0) if sga is not None and revenue not in {None, 0} else None,
            "EBIT (tỷ)": ebit,
            "EBIT Margin %": (ebit / revenue * 100.0) if ebit is not None and revenue not in {None, 0} else None,
            "CFO (tỷ)": _metric(row, "cfo"),
            "FCF (tỷ)": _metric(row, "fcf"),
            "Source": CANONICAL_SOURCE_LABEL,
            "Data Origin": CANONICAL_DATA_ORIGIN,
            "Boundary": "Cost context only — analyst determines whether cuts are unnecessary, harmful, or value creating.",
        })
    return pd.DataFrame(out)


def build_q46_capital_allocation_context(annual_df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    """Map canonical data to Shearn's five excess-FCF allocation buckets without scoring discipline."""
    out: list[dict[str, Any]] = []
    for row in _annual_rows(annual_df, years=years, include_ttm=True):
        capex = _metric(row, "capex")
        out.append({
            "Kỳ": _period(row),
            "FCF (tỷ)": _metric(row, "fcf"),
            "1. Reinvest — CAPEX proxy (tỷ)": abs(capex) if capex is not None else None,
            "2. Hold cash — Ending cash stock (tỷ)": _metric(row, "cash"),
            "3. Dividends explicit (tỷ)": abs(_metric(row, "dividend_cash")) if _metric(row, "dividend_cash") is not None else None,
            "4. Buybacks explicit (tỷ)": abs(_metric(row, "buyback_cash")) if _metric(row, "buyback_cash") is not None else None,
            "5. Acquisitions explicit (tỷ)": abs(_metric(row, "acquisition_cash")) if _metric(row, "acquisition_cash") is not None else None,
            "ROIC canonical %": _metric(row, "roic"),
            "Source": CANONICAL_SOURCE_LABEL,
            "Data Origin": CANONICAL_DATA_ORIGIN,
            "Boundary": "Cash is a stock, CAPEX is only a reinvestment proxy; rows must not be summed into a fabricated allocation total.",
        })
    return pd.DataFrame(out)


def build_q47_buyback_context(annual_df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    """Buyback context. Share-count changes alone are never relabelled as repurchases."""
    out: list[dict[str, Any]] = []
    previous_shares: Optional[float] = None
    for row in _annual_rows(annual_df, years=years, include_ttm=True):
        buyback_cash = _metric(row, "buyback_cash")
        buyback_shares = _metric(row, "buyback_shares")
        shares = _metric(row, "shares")
        change = (shares - previous_shares) if shares is not None and previous_shares is not None else None
        explicit = buyback_cash is not None or buyback_shares is not None
        out.append({
            "Kỳ": _period(row),
            "Buyback cash explicit (tỷ)": abs(buyback_cash) if buyback_cash is not None else None,
            "Shares repurchased explicit": abs(buyback_shares) if buyback_shares is not None else None,
            "Shares outstanding / avg shares": shares,
            "Share-count change": change,
            "Explicit buyback field available?": "Yes" if explicit else "No",
            "Source": CANONICAL_SOURCE_LABEL,
            "Data Origin": CANONICAL_DATA_ORIGIN,
            "Boundary": "Share-count decline is context only and is not proof of buyback; opportunism/valuation remains analyst judgment.",
        })
        if shares is not None:
            previous_shares = shares
    return pd.DataFrame(out)


def build_phase8b_context(
    ticker: str,
    annual_df: pd.DataFrame,
    chapter7_payload: dict[str, Any] | None = None,
    guidance_rows: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the structured Phase 8B package without modifying analyst fields."""
    symbol = str(ticker or "").strip().upper()
    managers = build_manager_reference(chapter7_payload)
    guidance = normalize_guidance_rows(guidance_rows)
    cost = build_q45_cost_context(annual_df)
    allocation = build_q46_capital_allocation_context(annual_df)
    buyback = build_q47_buyback_context(annual_df)
    warnings: list[str] = []
    if managers.empty:
        warnings.append("Chapter 7 manager master is empty/unavailable; Chapter 8 does not create replacement manager IDs.")
    if guidance.empty:
        warnings.append("Q41 guidance disclosure is not supplied; remains a research gap until structured disclosure evidence is added.")
    if allocation.empty:
        warnings.append("Canonical financial history unavailable for Q45-Q47 context.")
    elif allocation["4. Buybacks explicit (tỷ)"].isna().all():
        warnings.append("Q47 explicit buyback cash is unavailable in canonical rows; share-count changes are not treated as buybacks.")
    return {
        "ticker": symbol,
        "manager_reference": managers,
        "q41_guidance_history": guidance,
        "q45_cost_context": cost,
        "q46_capital_allocation_context": allocation,
        "q47_buyback_context": buyback,
        "warnings": warnings,
        "financial_ssot": CANONICAL_SOURCE_LABEL,
        "manager_ssot": MANAGER_SOURCE_LABEL,
        "analyst_boundary": "Research/structured context only — no management score, no BUY/HOLD/SELL, no MOS/Research Gate changes.",
    }
