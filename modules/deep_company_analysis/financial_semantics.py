from __future__ import annotations

"""Read-only financial semantics/provenance helpers for Deep Company Analysis V99.

This module consumes the existing Trecapital canonical financial dataframe. It does not fetch,
store or calculate an alternative financial dataset. Its job is to make period/scope semantics
visible so research code cannot silently confuse consolidated PAT, parent-attributable PAT, EPS,
or an undated TTM label.
"""

from dataclasses import dataclass
from typing import Any, Optional
import math

import pandas as pd


@dataclass(frozen=True)
class MetricSemantics:
    metric: str
    label: str
    value: Optional[float]
    unit: str
    profit_scope: str
    source_field: str
    source_module: str
    source_period: str
    data_origin: str
    comparability_status: str
    comparability_note: str


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _clean(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def period_display(row: dict[str, Any]) -> str:
    explicit = _clean(row.get("period_display"))
    if explicit:
        return explicit
    period = _clean(row.get("period") or row.get("year"))
    upper = period.upper()
    if "TTM" not in upper and "T12M" not in upper:
        return period
    end_period = _clean(row.get("ttm_end_period"))
    if end_period:
        return f"TTM đến {end_period}"
    year = _safe_float(row.get("year"))
    quarter = _safe_float(row.get("quarter"))
    if year is not None and quarter is not None and 1 <= int(quarter) <= 4:
        return f"TTM đến Q{int(quarter)}/{int(year)}"
    return "TTM"


def _preferred_latest(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    work = df.copy()
    if "period" in work.columns:
        mask = work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        if mask.any():
            return work[mask].iloc[-1].to_dict()
    return work.iloc[-1].to_dict()


def _profit_scope(row: dict[str, Any]) -> str:
    explicit = _clean(row.get("net_profit_scope"))
    if explicit:
        return explicit
    if _safe_float(row.get("net_profit_parent_bil")) is not None:
        return "parent_attributable"
    if _safe_float(row.get("net_profit_consolidated_bil")) is not None:
        return "consolidated"
    if _safe_float(row.get("net_profit_bil")) is not None:
        return "unspecified"
    return "unknown"


def _legacy_profit_source_field(row: dict[str, Any]) -> str:
    if _safe_float(row.get("net_profit_parent_bil")) is not None:
        return "net_profit_parent_bil → net_profit_bil"
    if _safe_float(row.get("net_profit_consolidated_bil")) is not None:
        return "net_profit_consolidated_bil → net_profit_bil"
    return "net_profit_bil"


def latest_metric_semantics(
    df: pd.DataFrame,
    *,
    source_label: str = "Trecapital canonical data",
    source_module: str = "Trecapital canonical financial data / Module 1",
) -> list[MetricSemantics]:
    row = _preferred_latest(df)
    if not row:
        return []
    source_period = period_display(row)
    comparability_status = _clean(row.get("comparability_status")) or "Unknown / not provided"
    comparability_note = _clean(row.get("comparability_note"))
    scope = _profit_scope(row)
    specs = (
        ("net_profit_consolidated_bil", "LNST hợp nhất", "tỷ đồng", "consolidated", "net_profit_consolidated_bil"),
        ("net_profit_parent_bil", "LNST thuộc CĐ công ty mẹ", "tỷ đồng", "parent_attributable", "net_profit_parent_bil"),
        ("net_profit_bil", "LNST canonical/legacy", "tỷ đồng", scope, _legacy_profit_source_field(row)),
        ("eps_vnd", "EPS", "đồng/cp", "per_share", "eps_vnd"),
    )
    out: list[MetricSemantics] = []
    for metric, label, unit, metric_scope, source_field in specs:
        out.append(
            MetricSemantics(
                metric=metric,
                label=label,
                value=_safe_float(row.get(metric)),
                unit=unit,
                profit_scope=metric_scope,
                source_field=source_field,
                source_module=source_module,
                source_period=source_period,
                data_origin=source_label or "Trecapital canonical data",
                comparability_status=comparability_status,
                comparability_note=comparability_note,
            )
        )
    return out


def semantics_table(
    df: pd.DataFrame,
    *,
    source_label: str = "Trecapital canonical data",
    source_module: str = "Trecapital canonical financial data / Module 1",
) -> pd.DataFrame:
    rows = latest_metric_semantics(df, source_label=source_label, source_module=source_module)
    return pd.DataFrame(
        [
            {
                "Metric": item.label,
                "Value": item.value,
                "Unit": item.unit,
                "Profit Scope": item.profit_scope,
                "Source Field": item.source_field,
                "Source Module": item.source_module,
                "Source Period": item.source_period,
                "Data Origin": item.data_origin,
                "Comparability": item.comparability_status,
                "Comparability Note": item.comparability_note,
            }
            for item in rows
        ]
    )


def semantic_warnings(df: pd.DataFrame) -> list[str]:
    row = _preferred_latest(df)
    if not row:
        return ["Canonical financial data is empty; financial semantics remain Unknown."]
    warnings: list[str] = []
    period = period_display(row)
    raw_period = _clean(row.get("period")).upper()
    if ("TTM" in raw_period or "T12M" in raw_period) and "Q" not in period:
        warnings.append("TTM period has no explicit ending quarter; UI must not present it as FY data.")
    scope = _profit_scope(row)
    if _safe_float(row.get("net_profit_bil")) is not None and scope == "unspecified":
        warnings.append("Canonical net_profit_bil is present but its consolidated/parent-attributable scope is unspecified.")
    parent = _safe_float(row.get("net_profit_parent_bil"))
    consolidated = _safe_float(row.get("net_profit_consolidated_bil"))
    legacy = _safe_float(row.get("net_profit_bil"))
    if parent is not None and legacy is not None and not math.isclose(parent, legacy, rel_tol=1e-9, abs_tol=1e-9):
        warnings.append("Legacy net_profit_bil does not match explicit parent-attributable profit; canonical alias requires review.")
    if consolidated is not None and parent is None and _safe_float(row.get("eps_vnd")) is None:
        warnings.append("Only consolidated PAT is explicit; parent-attributable PAT/EPS must remain Unknown unless separately sourced.")
    return warnings


__all__ = [
    "MetricSemantics",
    "latest_metric_semantics",
    "period_display",
    "semantic_warnings",
    "semantics_table",
]
