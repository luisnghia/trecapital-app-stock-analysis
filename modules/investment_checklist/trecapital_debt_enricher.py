from __future__ import annotations

"""Enrich normalized Trecapital frames with debt line items from the latest FireAnt raw audit file.

The main FireAnt exact parser historically mapped assets/liabilities but did not map the Vietnamese
borrowing rows, which made derived `interest_bearing_debt_bil` look like zero. This module reads the
raw response already downloaded by Trecapital (no extra network request), extracts only debt-specific
balance-sheet labels, and merges them back into the normalized annual/quarterly frames.
"""

from pathlib import Path
from typing import Any
import json
import math
import re
import unicodedata

import pandas as pd


_DEBT_LABELS = {
    "short_term_debt_bil": (
        "vay va no thue tai chinh ngan han",
        "vay va no thue tai chinh ngắn hạn",
        "short term borrowings",
        "short term debt",
    ),
    "long_term_debt_bil": (
        "vay va no thue tai chinh dai han",
        "vay va no thue tai chinh dài hạn",
        "long term borrowings",
        "long term debt",
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
    # Prefer the aggregate borrowing rows. Avoid detail lines that merely contain a shorter token.
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
        # Only balance-sheet LastestFinancialReports (type=1).
        if "LastestFinancialReports" not in url or not re.search(r"[?&]type=1(?:&|$)", url):
            continue
        body = response.get("body")
        if not body:
            continue
        try:
            items = json.loads(body)
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            field = _field_for_label(item.get("Name") or item.get("name"))
            if not field:
                continue
            values = item.get("Values") or item.get("values") or []
            if not isinstance(values, list):
                continue
            for pv in values:
                if not isinstance(pv, dict):
                    continue
                year = _float(pv.get("Year") if "Year" in pv else pv.get("year"))
                q = _float(pv.get("Quarter") if "Quarter" in pv else pv.get("quarter"))
                value = _float(pv.get("Value") if "Value" in pv else pv.get("value"))
                if year is None or value is None:
                    continue
                quarter = int(q) if q is not None and 1 <= int(q) <= 4 else None
                period_type = "Q" if quarter else "Y"
                key = (period_type, int(year), quarter)
                # FireAnt statement values are raw VND.
                rows.setdefault(key, {})[field] = value / 1_000_000_000.0
    for values in rows.values():
        debt_parts = [values.get("short_term_debt_bil"), values.get("long_term_debt_bil"), values.get("bonds_payable_bil")]
        known = [abs(v) for v in debt_parts if v is not None]
        if known:
            values["interest_bearing_debt_bil"] = sum(known)
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
    """Return debt-enriched frames plus an audit note; never invent debt when raw lines are absent."""
    manifest = _latest_manifest(raw_dir, ticker)
    if manifest is None:
        return annual, quarterly, "Không tìm thấy FireAnt raw audit gần nhất để bổ sung nợ vay."
    rows = _extract_rows(manifest, ticker)
    if not rows:
        return annual, quarterly, "FireAnt raw audit chưa tách được dòng Vay & nợ thuê tài chính; Debt giữ trạng thái chưa xác định."
    annual_out = _merge_frame(annual, rows, "Y")
    quarterly_out = _merge_frame(quarterly, rows, "Q")
    return annual_out, quarterly_out, f"Debt được bổ sung từ các dòng Vay & nợ thuê tài chính trong FireAnt raw audit: {manifest.name}."
