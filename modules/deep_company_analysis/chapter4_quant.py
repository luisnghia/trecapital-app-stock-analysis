from __future__ import annotations

"""Phase 4B quantitative bridge for Shearn Chapter 4.

This module consumes Trecapital's normalized/canonical financial rows. It does not
create a parallel data source and it does not classify moat, pricing power,
industry quality, competition intensity, or supplier quality.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Optional
import math

import pandas as pd


NUMERIC_PEER_COLUMNS = (
    "ROIC Latest",
    "ROIC 5Y Median",
    "ROIC 10Y Median",
    "ROIC Min",
    "ROIC Max",
    "EBIT Margin",
    "CCC",
)


@dataclass(frozen=True)
class QuantProvenance:
    ticker: str
    company_name: str
    source_label: str
    data_period: str
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


def _pick(row: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _period(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year") or "")


def _is_ttm(row: dict[str, Any]) -> bool:
    p = _period(row).upper()
    return "TTM" in p or "T12M" in p


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


def _current_row(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    rows = [row.to_dict() for _, row in df.iterrows()]
    ttm = [row for row in rows if _is_ttm(row)]
    if ttm:
        return ttm[-1]
    annual = _annual_rows(df)
    return annual[-1] if annual else rows[-1]


def _metric(row: dict[str, Any], metric: str) -> Optional[float]:
    if metric == "roic_pct":
        return _pick(row, "roic_pct", "roic_standard_pct", "roic_fireant_pct")
    if metric == "gross_margin_pct":
        value = _pick(row, "gross_margin_pct")
        if value is not None:
            return value
        revenue = _pick(row, "revenue_bil")
        gross_profit = _pick(row, "gross_profit_bil")
        return gross_profit / revenue * 100 if revenue and gross_profit is not None else None
    if metric == "ebit_margin_pct":
        value = _pick(row, "core_operating_margin_pct", "operating_margin_pct")
        if value is not None:
            return value
        revenue = _pick(row, "revenue_bil")
        ebit = _pick(row, "core_operating_profit_bil", "operating_profit_bil")
        return ebit / revenue * 100 if revenue and ebit is not None else None
    if metric == "fcf_margin_pct":
        revenue = _pick(row, "revenue_bil")
        fcf = _pick(row, "free_cash_flow_bil")
        return fcf / revenue * 100 if revenue and fcf is not None else None
    if metric == "revenue_growth_pct":
        return _pick(row, "revenue_growth_yoy_pct")
    if metric == "ccc_days":
        return _pick(row, "cash_conversion_cycle_days")
    if metric == "inventory_turnover":
        return _pick(row, "inventory_turnover")
    if metric == "dso_days":
        return _pick(row, "dso_days")
    if metric == "dio_days":
        return _pick(row, "dio_days")
    if metric == "dpo_days":
        return _pick(row, "dpo_days")
    return _pick(row, metric)


def _series(rows: Iterable[dict[str, Any]], metric: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _metric(row, metric)
        if value is not None:
            values.append(value)
    return values


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return float(pd.Series(values, dtype="float64").median())


def build_company_snapshot(
    ticker: str,
    company_name: str,
    annual_df: pd.DataFrame,
    source_label: str = "Trecapital canonical data",
) -> dict[str, Any]:
    """Build auditable Chapter 4 quantitative context from canonical rows.

    Historical medians use annual rows only. Latest operating context may use the
    appended TTM row when available. No qualitative Chapter 4 conclusion is emitted.
    """
    annual_rows = _annual_rows(annual_df)
    current = _current_row(annual_df)
    if not current and not annual_rows:
        return {}

    roic_all = _series(annual_rows, "roic_pct")
    roic_5 = roic_all[-5:]
    roic_10 = roic_all[-10:]
    latest_period = _period(current) or (_period(annual_rows[-1]) if annual_rows else "")

    history: list[dict[str, Any]] = []
    display_rows = annual_rows[-10:]
    if current and _is_ttm(current):
        display_rows = display_rows + [current]
    for row in display_rows:
        history.append({
            "Kỳ": _period(row),
            "Tăng trưởng DT %": _metric(row, "revenue_growth_pct"),
            "Gross Margin %": _metric(row, "gross_margin_pct"),
            "EBIT Margin %": _metric(row, "ebit_margin_pct"),
            "FCF Margin %": _metric(row, "fcf_margin_pct"),
            "ROIC %": _metric(row, "roic_pct"),
            "CCC ngày": _metric(row, "ccc_days"),
            "Vòng quay tồn kho": _metric(row, "inventory_turnover"),
            "DSO ngày": _metric(row, "dso_days"),
            "DIO ngày": _metric(row, "dio_days"),
            "DPO ngày": _metric(row, "dpo_days"),
        })

    provenance = QuantProvenance(
        ticker=str(ticker).upper().strip(),
        company_name=company_name or "",
        source_label=source_label or "Trecapital canonical data",
        data_period=latest_period,
    )

    return {
        "ticker": provenance.ticker,
        "company_name": provenance.company_name,
        "latest_period": latest_period,
        "roic_latest": _metric(current, "roic_pct"),
        "roic_5y_median": _median(roic_5),
        "roic_10y_median": _median(roic_10),
        "roic_min": min(roic_10) if roic_10 else None,
        "roic_max": max(roic_10) if roic_10 else None,
        "gross_margin_latest": _metric(current, "gross_margin_pct"),
        "ebit_margin_latest": _metric(current, "ebit_margin_pct"),
        "fcf_margin_latest": _metric(current, "fcf_margin_pct"),
        "ccc_latest": _metric(current, "ccc_days"),
        "inventory_turnover_latest": _metric(current, "inventory_turnover"),
        "dso_latest": _metric(current, "dso_days"),
        "dio_latest": _metric(current, "dio_days"),
        "dpo_latest": _metric(current, "dpo_days"),
        "history": history,
        "provenance": {
            "source_label": provenance.source_label,
            "source_module": provenance.source_module,
            "data_origin": provenance.data_origin,
            "data_period": provenance.data_period,
        },
        # Guardrails are explicit so tests/UI can verify the bridge never becomes a classifier.
        "guardrails": {
            "auto_moat_conclusion": False,
            "auto_pricing_power_conclusion": False,
            "auto_industry_quality_conclusion": False,
            "auto_competition_intensity_conclusion": False,
            "auto_supplier_quality_conclusion": False,
        },
    }


def build_peer_table(snapshots: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        if not isinstance(snap, dict) or not snap.get("ticker"):
            continue
        rows.append({
            "Company": snap.get("ticker"),
            "Company Name": snap.get("company_name") or "",
            "ROIC Latest": snap.get("roic_latest"),
            "ROIC 5Y Median": snap.get("roic_5y_median"),
            "ROIC 10Y Median": snap.get("roic_10y_median"),
            "ROIC Min": snap.get("roic_min"),
            "ROIC Max": snap.get("roic_max"),
            "Gross Margin": snap.get("gross_margin_latest"),
            "EBIT Margin": snap.get("ebit_margin_latest"),
            "FCF Margin": snap.get("fcf_margin_latest"),
            "CCC": snap.get("ccc_latest"),
            "Inventory Turns": snap.get("inventory_turnover_latest"),
            "Data Period": snap.get("latest_period") or "",
            "Data Origin": (snap.get("provenance") or {}).get("data_origin") or "",
        })
    return pd.DataFrame(rows)


def build_industry_distribution(peer_df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(peer_df, pd.DataFrame) or peer_df.empty or "ROIC Latest" not in peer_df.columns:
        return {}
    values = pd.to_numeric(peer_df["ROIC Latest"], errors="coerce").dropna()
    if values.empty:
        return {}
    return {
        "peer_count": int(values.count()),
        "median_roic": float(values.median()),
        "p25_roic": float(values.quantile(0.25)),
        "p75_roic": float(values.quantile(0.75)),
        "min_roic": float(values.min()),
        "max_roic": float(values.max()),
        "spread_roic": float(values.max() - values.min()),
        "positive_roic_pct": float((values > 0).mean() * 100.0),
        "industry_quality": None,  # Analyst only.
    }


def build_peer_benchmark(peer_df: pd.DataFrame, target_ticker: str) -> pd.DataFrame:
    """Table 4.2 quantitative context; Max/Min are descriptive, not 'ideal'."""
    if not isinstance(peer_df, pd.DataFrame) or peer_df.empty:
        return pd.DataFrame()
    metrics = [
        ("ROIC %", "ROIC Latest"),
        ("Gross Margin %", "Gross Margin"),
        ("EBIT Margin %", "EBIT Margin"),
        ("FCF Margin %", "FCF Margin"),
        ("CCC ngày", "CCC"),
        ("Vòng quay tồn kho", "Inventory Turns"),
    ]
    target = peer_df[peer_df["Company"].astype(str).str.upper().eq(str(target_ticker).upper())]
    rows: list[dict[str, Any]] = []
    for label, col in metrics:
        if col not in peer_df.columns:
            continue
        series = pd.to_numeric(peer_df[col], errors="coerce").dropna()
        target_value = None
        if not target.empty:
            target_series = pd.to_numeric(target[col], errors="coerce").dropna()
            if not target_series.empty:
                target_value = float(target_series.iloc[0])
        rows.append({
            "Metric": label,
            "Target": target_value,
            "Peer Median": float(series.median()) if not series.empty else None,
            "Peer Min": float(series.min()) if not series.empty else None,
            "Peer Max": float(series.max()) if not series.empty else None,
            "Analyst Note": "",
        })
    return pd.DataFrame(rows)


def pricing_context(snapshot: dict[str, Any]) -> pd.DataFrame:
    """Return margin history only; never infer price increases or pricing power."""
    history = snapshot.get("history") if isinstance(snapshot, dict) else None
    if not isinstance(history, list):
        return pd.DataFrame()
    cols = ["Kỳ", "Tăng trưởng DT %", "Gross Margin %", "EBIT Margin %", "FCF Margin %"]
    df = pd.DataFrame(history)
    return df[[c for c in cols if c in df.columns]] if not df.empty else pd.DataFrame(columns=cols)


def supply_chain_context(snapshot: dict[str, Any]) -> pd.DataFrame:
    history = snapshot.get("history") if isinstance(snapshot, dict) else None
    if not isinstance(history, list):
        return pd.DataFrame()
    cols = ["Kỳ", "Vòng quay tồn kho", "CCC ngày", "DSO ngày", "DIO ngày", "DPO ngày"]
    df = pd.DataFrame(history)
    return df[[c for c in cols if c in df.columns]] if not df.empty else pd.DataFrame(columns=cols)
