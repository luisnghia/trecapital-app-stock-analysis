from __future__ import annotations

"""Enrich normalized Trecapital frames with debt line items from the latest FireAnt raw audit file.

This is a transitional compatibility layer for Phase 1C. It does not call an external source:
it reads the FireAnt raw response already downloaded by Trecapital and restores debt-specific
balance-sheet facts that the current canonical mapper can omit. Once these aliases are mapped
upstream in Trecapital Data Layer, Checklist can remove this layer.
"""

from pathlib import Path
from typing import Any, Iterable
import json
import math
import re
import unicodedata

import pandas as pd


_DEBT_LABELS = {
    "short_term_debt_bil": (
        "vay va no thue tai chinh ngan han",
        "short term borrowings",
        "short term debt",
        "current borrowings",
    ),
    "long_term_debt_bil": (
        "vay va no thue tai chinh dai han",
        "long term borrowings",
        "long term debt",
        "non current borrowings",
    ),
    "bonds_payable_bil": (
        "trai phieu phat hanh",
        "trai phieu chuyen doi",
        "bonds payable",
        "convertible bonds",
    ),
}


def _norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace("Đ", "D").replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        return None if math.isnan(v) else v
    except Exception:
        text = str(value or "").strip().replace(",", "")
        try:
            return float(text)
        except Exception:
            return None


def _field_for_label(label: Any) -> str | None:
    n = _norm(label)
    if not n:
        return None
    for field, aliases in _DEBT_LABELS.items():
        for alias in aliases:
            a = _norm(alias)
            if n == a or n.startswith(a + " "):
                return field
    return None


def _latest_manifest(raw_dir: str | Path, ticker: str) -> Path | None:
    root = Path(raw_dir)
    files = sorted(root.glob(f"fireant_excel_vba_{ticker.upper()}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _iter_period_values(obj: Any) -> Iterable[dict[str, Any]]:
    """Yield nested FireAnt {Year, Quarter, Value} records from any wrapper shape."""
    if isinstance(obj, dict):
        keys = {str(k).lower(): k for k in obj.keys()}
        if "year" in keys and "value" in keys:
            yield obj
        for value in obj.values():
            if isinstance(value, (dict, list)):
                yield from _iter_period_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_period_values(item)


def _walk_report_items(obj: Any) -> Iterable[dict[str, Any]]:
    """Yield every nested report item that has a recognizable debt label.

    FireAnt responses are not guaranteed to be a top-level list. Some deployments wrap the
    rows under data/items/result. The previous implementation stopped on those payloads and
    therefore returned Debt/TEV as unknown even though the raw audit contained the line items.
    """
    if isinstance(obj, dict):
        label = obj.get("Name") or obj.get("name") or obj.get("Title") or obj.get("title") or obj.get("DisplayName") or obj.get("displayName")
        if _field_for_label(label):
            yield obj
        for value in obj.values():
            if isinstance(value, (dict, list)):
                yield from _walk_report_items(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_report_items(item)


def _to_bil(value: float) -> float:
    """FireAnt LastestFinancialReports normally returns raw VND; tolerate already-scaled values."""
    av = abs(value)
    if av >= 1_000_000_000:
        return value / 1_000_000_000.0
    if av >= 1_000_000:
        return value / 1_000.0
    return value


def _extract_rows(manifest: Path, ticker: str) -> dict[tuple[str, int, int | None], dict[str, float]]:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return {}

    rows: dict[tuple[str, int, int | None], dict[str, float]] = {}
    for response in payload.get("responses", []) or []:
        if not isinstance(response, dict):
            continue
        url = str(response.get("url") or "")
        if "LastestFinancialReports" not in url or not re.search(r"[?&]type=1(?:&|$)", url):
            continue
        body = response.get("body")
        if not body:
            continue
        try:
            decoded = json.loads(body) if isinstance(body, str) else body
        except Exception:
            continue

        for item in _walk_report_items(decoded):
            label = item.get("Name") or item.get("name") or item.get("Title") or item.get("title") or item.get("DisplayName") or item.get("displayName")
            field = _field_for_label(label)
            if not field:
                continue
            for pv in _iter_period_values(item):
                year = _float(pv.get("Year") if "Year" in pv else pv.get("year"))
                q = _float(pv.get("Quarter") if "Quarter" in pv else pv.get("quarter"))
                value = _float(pv.get("Value") if "Value" in pv else pv.get("value"))
                if year is None or value is None:
                    continue
                quarter = int(q) if q is not None and 1 <= int(q) <= 4 else None
                period_type = "Q" if quarter else "Y"
                key = (period_type, int(year), quarter)
                rows.setdefault(key, {})[field] = _to_bil(value)

    # Aggregate short-term and long-term borrowing rows are authoritative. Do not add bonds on top
    # when those aggregate lines are present, otherwise bonds can be double counted.
    for values in rows.values():
        short = values.get("short_term_debt_bil")
        long = values.get("long_term_debt_bil")
        if short is not None or long is not None:
            values["interest_bearing_debt_bil"] = abs(short or 0.0) + abs(long or 0.0)
        elif values.get("bonds_payable_bil") is not None:
            values["interest_bearing_debt_bil"] = abs(values["bonds_payable_bil"])
    return rows


def _merge_frame(df: pd.DataFrame, rows: dict[tuple[str, int, int | None], dict[str, float]], period_type: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or not rows:
        return df
    out = df.copy()
    for field in ["short_term_debt_bil", "long_term_debt_bil", "bonds_payable_bil", "interest_bearing_debt_bil"]:
        if field not in out.columns:
            out[field] = pd.NA
    for idx, row in out.iterrows():
        try:
            year = int(float(row.get("year")))
        except Exception:
            continue
        quarter = None
        if period_type == "Q":
            try:
                quarter = int(float(row.get("quarter")))
            except Exception:
                continue
        values = rows.get((period_type, year, quarter))
        if not values:
            continue
        for field, value in values.items():
            if field in out.columns:
                out.at[idx, field] = value
    return out


def augment_debt_from_latest_fireant_raw(
    annual: pd.DataFrame,
    quarterly: pd.DataFrame,
    ticker: str,
    raw_dir: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Return debt-enriched Trecapital frames plus an audit note; never invent debt."""
    manifest = _latest_manifest(raw_dir, ticker)
    if manifest is None:
        return annual, quarterly, "Không tìm thấy FireAnt raw audit gần nhất để bổ sung nợ vay."
    rows = _extract_rows(manifest, ticker)
    if not rows:
        return annual, quarterly, "FireAnt raw audit chưa tách được dòng Vay & nợ thuê tài chính; Debt giữ trạng thái chưa xác định."
    annual_out = _merge_frame(annual, rows, "Y")
    quarterly_out = _merge_frame(quarterly, rows, "Q")
    return annual_out, quarterly_out, f"Debt được bổ sung từ Trecapital FireAnt raw audit (không gọi nguồn riêng): {manifest.name}."
