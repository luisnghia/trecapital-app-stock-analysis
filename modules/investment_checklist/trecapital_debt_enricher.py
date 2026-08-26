from __future__ import annotations

"""Recover interest-bearing debt from FireAnt raw audit payloads already fetched by Trecapital.

The canonical FireAnt mapper uses a deliberately small exact-ID map. Debt IDs exist in FireAnt's
balance sheet but were not part of that map, so DCM and similar companies could show a synthetic
``interest_bearing_debt_bil = 0`` even though the raw statement contained real borrowings.

This compatibility layer reads only the FireAnt raw audit already downloaded by Trecapital. It does
not call another data source and it never converts a missing debt structure into zero.

FireAnt balance-sheet IDs confirmed against the live DCM endpoint on 2026-08-21:
- 3010101 = Vay và nợ thuê tài chính ngắn hạn
- 3010102 = Vay và nợ dài hạn đến hạn phải trả
- 3010206 = Vay và nợ thuê tài chính dài hạn

For short-term interest-bearing debt, 3010102 is a separate line and must be ADDED to 3010101.
Detailed borrowing/lease sub-lines are used only when the corresponding aggregate line is absent.
"""

from pathlib import Path
from typing import Any, Iterable
import json
import math
import re
import unicodedata

import pandas as pd


# FireAnt IDs are the strongest signal when available. Keep labels as a resilient fallback for
# wrapper/API shape changes and for historical raw files that omit IDs.
_FIREANT_DEBT_ID_KIND: dict[int, str] = {
    3010101: "short_core",
    3010102: "current_portion",
    3010206: "long_core",
}

_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "short_core": (
        "vay va no thue tai chinh ngan han",
        "short term borrowings and finance lease liabilities",
        "short term borrowings and lease liabilities",
        "short term debt and finance lease liabilities",
    ),
    "current_portion": (
        "vay va no dai han den han phai tra",
        "vay va no dai han den han tra",
        "no dai han den han phai tra",
        "no dai han den han tra",
        "no dai han toi han tra",
        "current portion of long term debt",
        "current portion of long term borrowings",
        "long term debt due within one year",
    ),
    "short_borrowing": (
        "vay ngan han",
        "short term borrowings",
        "short term borrowing",
        "short term loans",
        "current borrowings",
    ),
    "short_lease": (
        "no thue tai chinh ngan han",
        "finance lease liabilities current",
        "current finance lease liabilities",
        "short term finance lease liabilities",
        "current lease liabilities",
    ),
    "long_core": (
        "vay va no thue tai chinh dai han",
        "long term borrowings and finance lease liabilities",
        "long term borrowings and lease liabilities",
        "long term debt and finance lease liabilities",
    ),
    "long_borrowing": (
        "vay dai han",
        "long term borrowings",
        "long term borrowing",
        "long term loans",
        "non current borrowings",
    ),
    "long_lease": (
        "no thue tai chinh dai han",
        "finance lease liabilities non current",
        "non current finance lease liabilities",
        "long term finance lease liabilities",
        "non current lease liabilities",
    ),
    "bonds": (
        "trai phieu phat hanh",
        "trai phieu chuyen doi",
        "bonds payable",
        "convertible bonds",
        "bond liabilities",
    ),
    "total_debt": (
        "tong vay va no thue tai chinh",
        "tong no vay",
        "total interest bearing debt",
        "total borrowings",
    ),
}

_DIRECT_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "short_core": (
        "shorttermdebt", "shorttermborrowings", "currentborrowings", "shorttermloans",
        "short_term_debt", "short_term_borrowings",
    ),
    "long_core": (
        "longtermdebt", "longtermborrowings", "noncurrentborrowings", "longtermloans",
        "long_term_debt", "long_term_borrowings",
    ),
    "current_portion": (
        "currentportionlongtermdebt", "currentportionoflongtermdebt",
        "current_portion_long_term_debt",
    ),
    "total_debt": (
        "interestbearingdebt", "totaldebt", "totalborrowings", "borrowings",
        "interest_bearing_debt", "total_debt",
    ),
}


def _norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace("Đ", "D").replace("_", " ").replace("-", " ")
    text = re.sub(r"[^0-9a-zA-Z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(value))


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


def _int(value: Any) -> int | None:
    v = _float(value)
    return None if v is None else int(v)


def _kind_for_item(item: dict[str, Any]) -> str | None:
    rid = _int(item.get("ID") if "ID" in item else item.get("id"))
    if rid in _FIREANT_DEBT_ID_KIND:
        return _FIREANT_DEBT_ID_KIND[rid]

    label = (
        item.get("Name") or item.get("name") or item.get("Title") or item.get("title")
        or item.get("DisplayName") or item.get("displayName") or item.get("ItemName") or item.get("itemName")
        or item.get("Label") or item.get("label")
    )
    n = _norm(label)
    if not n:
        return None
    candidates: list[tuple[int, str, str]] = []
    for kind, aliases in _LABEL_ALIASES.items():
        for alias in aliases:
            a = _norm(alias)
            if a:
                candidates.append((len(a), a, kind))
    # Numbered FireAnt labels such as "1. Vay ..." normalize to "1 vay ...". A bounded
    # substring match handles those while the longest-first rule prevents broad aliases winning.
    padded = f" {n} "
    for _, alias, kind in sorted(candidates, reverse=True):
        if n == alias or f" {alias} " in padded or n.startswith(alias + " ") or n.endswith(" " + alias):
            return kind
    return None


def _latest_manifest(raw_dir: str | Path, ticker: str) -> Path | None:
    root = Path(raw_dir)
    files = sorted(root.glob(f"fireant_excel_vba_{ticker.upper()}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _iter_period_values(obj: Any) -> Iterable[dict[str, Any]]:
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


def _walk_dicts(obj: Any) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            if isinstance(value, (dict, list)):
                yield from _walk_dicts(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_dicts(item)


def _to_bil(value: float) -> float:
    av = abs(value)
    if av >= 1_000_000_000:  # raw VND
        return value / 1_000_000_000.0
    if av >= 1_000_000:  # million VND
        return value / 1_000.0
    return value  # already billion VND


def _period_key(pv: dict[str, Any]) -> tuple[str, int, int | None] | None:
    lower = {str(k).lower(): k for k in pv.keys()}
    year = _float(pv.get(lower.get("year"))) if "year" in lower else None
    if year is None:
        return None
    q = _float(pv.get(lower.get("quarter"))) if "quarter" in lower else None
    quarter = int(q) if q is not None and 1 <= int(q) <= 4 else None
    return ("Q" if quarter else "Y", int(year), quarter)


def _value_from_period(pv: dict[str, Any]) -> float | None:
    lower = {str(k).lower(): k for k in pv.keys()}
    key = lower.get("value")
    return _float(pv.get(key)) if key is not None else None


def _add_candidate(
    candidates: dict[tuple[str, int, int | None], dict[str, list[float]]],
    key: tuple[str, int, int | None],
    kind: str,
    value: float,
) -> None:
    candidates.setdefault(key, {}).setdefault(kind, []).append(abs(_to_bil(value)))


def _extract_candidates_from_payload(
    payload: Any,
    candidates: dict[tuple[str, int, int | None], dict[str, list[float]]],
) -> None:
    for item in _walk_dicts(payload):
        kind = _kind_for_item(item)
        if kind:
            for pv in _iter_period_values(item):
                key = _period_key(pv)
                value = _value_from_period(pv)
                if key is not None and value is not None:
                    _add_candidate(candidates, key, kind, value)

        # Some normalized/public payloads are one record per period with direct debt keys.
        key = _period_key(item)
        if key is not None:
            key_lookup = {_clean_key(k): k for k in item.keys()}
            for kind2, aliases in _DIRECT_KEY_ALIASES.items():
                for alias in aliases:
                    raw_key = key_lookup.get(_clean_key(alias))
                    if raw_key is None:
                        continue
                    value = _float(item.get(raw_key))
                    if value is not None:
                        _add_candidate(candidates, key, kind2, value)
                        break


def _latest_json_payloads(raw_dir: Path, ticker: str, limit: int = 80) -> list[tuple[Path, Any]]:
    files = sorted(raw_dir.glob(f"fireant_{ticker.upper()}_json_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out: list[tuple[Path, Any]] = []
    for path in files:
        try:
            out.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return out


def _collapse_candidates(
    candidates: dict[tuple[str, int, int | None], dict[str, list[float]]]
) -> dict[tuple[str, int, int | None], dict[str, float]]:
    rows: dict[tuple[str, int, int | None], dict[str, float]] = {}

    def preferred(values: dict[str, list[float]], kind: str) -> float | None:
        xs = values.get(kind) or []
        # Multiple endpoint probes repeat the same statement row. Do not sum duplicates.
        return xs[-1] if xs else None

    for key, values in candidates.items():
        short_core = preferred(values, "short_core")
        current_portion = preferred(values, "current_portion")
        long_core = preferred(values, "long_core")
        explicit_total = preferred(values, "total_debt")

        if short_core is None:
            parts = [preferred(values, "short_borrowing"), preferred(values, "short_lease")]
            short_core = sum(x for x in parts if x is not None) if any(x is not None for x in parts) else None
        # FireAnt 3010102 is separate from 3010101 and therefore added exactly once.
        short = (
            (short_core or 0.0) + (current_portion or 0.0)
            if short_core is not None or current_portion is not None
            else None
        )

        if long_core is None:
            parts = [preferred(values, "long_borrowing"), preferred(values, "long_lease")]
            long_core = sum(x for x in parts if x is not None) if any(x is not None for x in parts) else None
        long = long_core

        row: dict[str, float] = {}
        if short is not None:
            row["short_term_debt_bil"] = abs(short)
        if current_portion is not None:
            row["current_portion_long_term_debt_bil"] = abs(current_portion)
        if long is not None:
            row["long_term_debt_bil"] = abs(long)

        if explicit_total is not None and explicit_total > 0:
            total = abs(explicit_total)
        elif short is not None or long is not None:
            total = abs(short or 0.0) + abs(long or 0.0)
        else:
            bonds = preferred(values, "bonds")
            total = abs(bonds) if bonds is not None else None
            if bonds is not None:
                row["bonds_payable_bil"] = abs(bonds)

        if total is not None:
            row["interest_bearing_debt_bil"] = total
        if row:
            rows[key] = row
    return rows


def _extract_rows(manifest: Path, ticker: str, raw_dir: Path) -> tuple[dict[tuple[str, int, int | None], dict[str, float]], list[str]]:
    candidates: dict[tuple[str, int, int | None], dict[str, list[float]]] = {}
    sources: list[str] = []

    try:
        manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        manifest_payload = None

    if isinstance(manifest_payload, dict):
        before = 0
        for response in manifest_payload.get("responses", []) or []:
            if not isinstance(response, dict):
                continue
            body = response.get("body")
            if not body:
                continue
            try:
                decoded = json.loads(body) if isinstance(body, str) else body
            except Exception:
                continue
            _extract_candidates_from_payload(decoded, candidates)
        after = sum(len(xs) for by_kind in candidates.values() for xs in by_kind.values())
        if after > before:
            sources.append(manifest.name)

    before = sum(len(xs) for by_kind in candidates.values() for xs in by_kind.values())
    for path, payload in _latest_json_payloads(raw_dir, ticker):
        _extract_candidates_from_payload(payload, candidates)
        after = sum(len(xs) for by_kind in candidates.values() for xs in by_kind.values())
        if after > before:
            sources.append(path.name)
            before = after

    return _collapse_candidates(candidates), list(dict.fromkeys(sources))


def _merge_frame(df: pd.DataFrame, rows: dict[tuple[str, int, int | None], dict[str, float]], period_type: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or not rows:
        return df
    out = df.copy()
    for field in [
        "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil",
        "bonds_payable_bil", "interest_bearing_debt_bil",
    ]:
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
    root = Path(raw_dir)
    manifest = _latest_manifest(root, ticker)
    if manifest is None:
        return annual, quarterly, "Không tìm thấy FireAnt raw audit gần nhất để bổ sung nợ vay."
    rows, sources = _extract_rows(manifest, ticker, root)
    if not rows:
        return annual, quarterly, (
            "FireAnt raw audit chưa tách được cấu phần Vay & nợ thuê tài chính; "
            "Debt/TEV giữ trạng thái chưa xác định thay vì gán 0."
        )
    annual_out = _merge_frame(annual, rows, "Y")
    quarterly_out = _merge_frame(quarterly, rows, "Q")
    periods = sorted(
        [f"Q{k[2]}/{k[1]}" if k[0] == "Q" and k[2] else str(k[1]) for k in rows],
        reverse=True,
    )
    source_text = ", ".join(sources[:3]) if sources else manifest.name
    period_text = ", ".join(periods[:6])
    # Keep the legacy phrase "Debt được bổ sung" for audit/test compatibility.
    return annual_out, quarterly_out, (
        "Debt được bổ sung/phục hồi từ chính Trecapital FireAnt raw audit (không gọi nguồn ngoài): "
        f"{source_text}; kỳ nhận diện: {period_text}."
    )
