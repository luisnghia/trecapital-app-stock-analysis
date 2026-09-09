from __future__ import annotations

"""Deep Company Analysis V100 — read-only cyclical normalization.

Consumes the existing Trecapital canonical financial dataframe. It does not fetch, persist,
or replace financial statement data and it does not produce valuation or investment actions.
The purpose is to make 5–10 year cycle context explicit for analyst review.
"""

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional
import math

import pandas as pd

from modules.deep_company_analysis.financial_semantics import period_display


@dataclass(frozen=True)
class NormalizedMetric:
    metric: str
    label: str
    unit: str
    observations: int
    median: Optional[float]
    trimmed_mean: Optional[float]
    p25: Optional[float]
    p75: Optional[float]
    trough: Optional[float]
    peak: Optional[float]
    latest_annual: Optional[float]
    latest_ttm: Optional[float]
    latest_vs_median_pct: Optional[float]
    source_field: str
    source_module: str
    source_period: str
    data_origin: str


METRICS = (
    ("revenue", "Doanh thu", "tỷ đồng", ("revenue_bil", "net_revenue_bil", "gross_revenue_bil")),
    ("gross_margin", "Biên lợi nhuận gộp", "%", ("gross_margin_pct",)),
    ("ebit_margin", "Biên EBIT/HĐKD", "%", ("core_operating_margin_pct", "operating_margin_pct", "ebit_margin_pct")),
    ("roic", "ROIC", "%", ("roic_pct", "roic")),
    ("net_income", "LNST canonical", "tỷ đồng", ("net_profit_bil", "net_income_bil")),
)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _pick(row: dict[str, Any], fields: Iterable[str]) -> tuple[Optional[float], str]:
    for field in fields:
        value = _safe_float(row.get(field))
        if value is not None:
            return value, field
    return None, ""


def _is_ttm(row: dict[str, Any]) -> bool:
    text = f"{row.get('period', '')} {row.get('period_display', '')}".upper()
    return "TTM" in text or "T12M" in text


def _year(row: dict[str, Any]) -> Optional[int]:
    value = _safe_float(row.get("year"))
    if value is not None:
        return int(value)
    text = str(row.get("period") or "")
    for token in text.replace("/", " ").replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None


def _annual_rows(df: pd.DataFrame, years: int) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    rows = [row.to_dict() for _, row in df.iterrows()]
    rows = [row for row in rows if not _is_ttm(row)]
    annual_tagged = [row for row in rows if str(row.get("period_type") or "").upper() == "Y"]
    if annual_tagged:
        rows = annual_tagged
    rows.sort(key=lambda row: (_year(row) is None, _year(row) or 0))
    return rows[-max(1, min(int(years), 10)):]


def _latest_ttm(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    candidates = [row.to_dict() for _, row in df.iterrows() if _is_ttm(row.to_dict())]
    return candidates[-1] if candidates else {}


def _derived_metric(row: dict[str, Any], metric: str, fields: tuple[str, ...]) -> tuple[Optional[float], str]:
    explicit, field = _pick(row, fields)
    if explicit is not None:
        return explicit, field
    revenue, revenue_field = _pick(row, ("revenue_bil", "net_revenue_bil", "gross_revenue_bil"))
    if revenue is None or abs(revenue) < 1e-12:
        return None, ""
    if metric == "gross_margin":
        gp, gp_field = _pick(row, ("gross_profit_bil",))
        return ((gp / revenue * 100.0), f"{gp_field}/{revenue_field}") if gp is not None else (None, "")
    if metric == "ebit_margin":
        ebit, ebit_field = _pick(row, ("core_operating_profit_bil", "operating_profit_bil", "ebit_bil"))
        return ((ebit / revenue * 100.0), f"{ebit_field}/{revenue_field}") if ebit is not None else (None, "")
    return None, ""


def _trimmed_mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    trim = 1 if len(ordered) >= 7 else 0
    core = ordered[trim:len(ordered) - trim] if trim else ordered
    return float(sum(core) / len(core)) if core else None


def _pct_delta(value: Optional[float], base: Optional[float]) -> Optional[float]:
    if value is None or base is None or abs(base) < 1e-12:
        return None
    return (value / base - 1.0) * 100.0


def comparability_breaks(df: pd.DataFrame, years: int = 10) -> pd.DataFrame:
    rows = []
    for row in _annual_rows(df, years):
        status = str(row.get("comparability_status") or "").strip()
        note = str(row.get("comparability_note") or "").strip()
        normalized = status.casefold()
        comparable = not status or normalized in {"comparable", "ok", "yes", "normal", "same basis"}
        if not comparable or note:
            rows.append({
                "Period": period_display(row),
                "Comparability Status": status or "Unknown",
                "Comparability Note": note,
            })
    return pd.DataFrame(rows, columns=["Period", "Comparability Status", "Comparability Note"])


def normalization_table(
    df: pd.DataFrame,
    *,
    years: int = 10,
    source_label: str = "Trecapital canonical data",
    source_module: str = "Trecapital canonical financial data / Module 1",
) -> pd.DataFrame:
    annual = _annual_rows(df, years)
    ttm = _latest_ttm(df)
    latest_annual_period = period_display(annual[-1]) if annual else ""
    source_period = period_display(ttm) if ttm else latest_annual_period
    records: list[dict[str, Any]] = []

    for metric, label, unit, fields in METRICS:
        values: list[float] = []
        used_fields: list[str] = []
        latest_annual = None
        for row in annual:
            value, source_field = _derived_metric(row, metric, fields)
            if value is not None:
                values.append(value)
                if source_field:
                    used_fields.append(source_field)
                latest_annual = value
        latest_ttm, ttm_field = _derived_metric(ttm, metric, fields) if ttm else (None, "")
        if ttm_field:
            used_fields.append(ttm_field)
        series = pd.Series(values, dtype="float64")
        median = float(series.median()) if not series.empty else None
        p25 = float(series.quantile(0.25)) if not series.empty else None
        p75 = float(series.quantile(0.75)) if not series.empty else None
        item = NormalizedMetric(
            metric=metric,
            label=label,
            unit=unit,
            observations=len(values),
            median=median,
            trimmed_mean=_trimmed_mean(values),
            p25=p25,
            p75=p75,
            trough=min(values) if values else None,
            peak=max(values) if values else None,
            latest_annual=latest_annual,
            latest_ttm=latest_ttm,
            latest_vs_median_pct=_pct_delta(latest_ttm if latest_ttm is not None else latest_annual, median),
            source_field=" | ".join(dict.fromkeys(used_fields)),
            source_module=source_module,
            source_period=source_period,
            data_origin=source_label or "Trecapital canonical data",
        )
        records.append(asdict(item))
    return pd.DataFrame(records)


def historical_cycle_table(df: pd.DataFrame, *, years: int = 10) -> pd.DataFrame:
    annual = _annual_rows(df, years)
    metrics = normalization_table(df, years=years)
    thresholds = {
        row["metric"]: (row["p25"], row["p75"])
        for _, row in metrics.iterrows()
    }
    out: list[dict[str, Any]] = []
    for row in annual:
        record: dict[str, Any] = {"Period": period_display(row)}
        flags: list[str] = []
        for metric, label, _unit, fields in METRICS:
            value, _field = _derived_metric(row, metric, fields)
            record[label] = value
            low, high = thresholds.get(metric, (None, None))
            if value is not None and low is not None and high is not None:
                if value <= low:
                    flags.append(f"{label}: trough-zone")
                elif value >= high:
                    flags.append(f"{label}: peak-zone")
        record["Cycle Flags"] = "; ".join(flags)
        status = str(row.get("comparability_status") or "Unknown")
        note = str(row.get("comparability_note") or "")
        record["Comparability"] = status
        record["Comparability Note"] = note
        out.append(record)
    return pd.DataFrame(out)


def normalization_guardrails(df: pd.DataFrame, *, years: int = 10) -> list[str]:
    annual = _annual_rows(df, years)
    warnings: list[str] = []
    if len(annual) < 5:
        warnings.append("Fewer than 5 annual observations: cycle normalization is low-confidence and must remain analyst-reviewed.")
    breaks = comparability_breaks(df, years=years)
    if not breaks.empty:
        warnings.append("Comparability breaks exist inside the normalization window; normalized values are descriptive, not mechanically decision-grade.")
    table = normalization_table(df, years=years)
    sparse = table[table["observations"] < 5] if not table.empty else table
    if not sparse.empty:
        warnings.append("One or more metrics have fewer than 5 valid observations and should not be treated as a stable cycle baseline.")
    if _latest_ttm(df):
        warnings.append("TTM is shown as a current overlay only and is excluded from annual median/trimmed-mean baselines to avoid overlap double-counting.")
    warnings.append("Normalization is evidence context only: it does not change intrinsic value, MOS, Research Gate, or BUY/HOLD/SELL status.")
    return warnings


__all__ = [
    "METRICS",
    "NormalizedMetric",
    "comparability_breaks",
    "historical_cycle_table",
    "normalization_guardrails",
    "normalization_table",
]
