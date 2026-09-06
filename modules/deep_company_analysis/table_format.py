from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
import hashlib
import inspect

import pandas as pd
import streamlit as st

ORIGINAL_ORDER_LABEL = "Giữ thứ tự gốc"
ASC_LABEL = "Tăng dần"
DESC_LABEL = "Giảm dần"


def infer_numeric_kind(column: str) -> str:
    """Infer only explicit/known Trecapital display units.

    Unknown labels stay text so the renderer never invents a financial unit.
    """
    name = str(column or "").strip()
    low = name.casefold()
    if "(tỷ)" in low or " tỷ" in low or low.endswith("tỷ"):
        return "amount_bil"
    if "(ngày)" in low or " ngày" in low or low in {"dso", "dio", "dpo", "ccc"} or low.startswith(("dso ", "dio ", "dpo ", "ccc ")):
        return "days"
    if "(x)" in low or "/ebit" in low or "/interest" in low or "current ratio" in low or "turnover" in low or "turns" in low:
        return "ratio"
    pct_tokens = (
        "%", "margin", "roic", "yield", "growth", "tăng trưởng", "revenue share",
        "market share", "retention rate", "churn rate", "drawdown", "percentile",
    )
    if any(token in low for token in pct_tokens):
        return "percent"
    return "text"


def format_numeric(value: Any, kind: str) -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        number = float(value)
    except Exception:
        return escape(str(value or ""))
    if kind == "amount_bil":
        return f"{number:,.0f}"
    if kind == "percent":
        return f"{number:,.1f}%"
    if kind == "ratio":
        return f"{number:,.1f}x"
    if kind == "days":
        return f"{number:,.1f}"
    return escape(str(value))


def _heat_eligible(column: str) -> bool:
    low = str(column or "").casefold()
    tokens = (
        "tăng trưởng", "growth", "change", "delta", "Δ", "margin", "roic",
        "cfo", "fcf", "ebit", "profit", "lợi nhuận", "cash flow", "dòng tiền",
        "headroom", "impact", "drawdown",
    )
    return any(token.casefold() in low for token in tokens)


def _heat_style(value: Any, max_abs: float) -> str:
    try:
        number = float(value)
    except Exception:
        return ""
    if pd.isna(number) or number == 0:
        return ""
    scale = min(1.0, abs(number) / max_abs) if max_abs > 0 else 0.0
    alpha = 0.07 + 0.23 * scale
    if number < 0:
        return f"color:#991B1B;font-weight:700;background:rgba(185,28,28,{alpha:.3f});"
    return f"color:#047857;font-weight:700;background:rgba(4,120,87,{alpha:.3f});"


def _coerce_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    data = getattr(value, "data", None)
    if isinstance(data, pd.DataFrame):
        return data.copy()
    try:
        return pd.DataFrame(value)
    except Exception:
        return pd.DataFrame()


def sort_frame(value: Any, sort_by: str | None, ascending: bool = True) -> pd.DataFrame:
    """Stable sort on raw values. The input frame is never mutated."""
    frame = _coerce_frame(value)
    if frame.empty or not sort_by or sort_by not in frame.columns:
        return frame
    work = frame.copy()
    series = work[sort_by]
    non_null = int(series.notna().sum())
    numeric = pd.to_numeric(series, errors="coerce")
    numeric_count = int(numeric.notna().sum())
    temp = "__tre_sort_key__"
    while temp in work.columns:
        temp += "_"
    if non_null > 0 and numeric_count >= max(1, int(non_null * 0.70)):
        work[temp] = numeric
    else:
        work[temp] = series.fillna("").astype(str).str.casefold()
    work = work.sort_values(temp, ascending=bool(ascending), na_position="last", kind="mergesort")
    return work.drop(columns=[temp]).reset_index(drop=True)


def _stable_widget_key(frame: pd.DataFrame, explicit: str | None, prefix: str) -> str:
    if explicit:
        seed = str(explicit)
    else:
        caller = "unknown"
        for info in inspect.stack()[2:]:
            if Path(info.filename).resolve() != Path(__file__).resolve():
                caller = f"{info.filename}:{info.lineno}"
                break
        sample = ""
        if not frame.empty:
            try:
                sample = "|".join(str(x) for x in frame.iloc[0].tolist()[:3])
            except Exception:
                sample = ""
        seed = f"{caller}|{list(frame.columns)}|{frame.shape}|{sample}"
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:14]
    return f"tre_{prefix}_{digest}"


def prefer_ttm_latest(value: Any) -> pd.DataFrame:
    """Keep a valid TTM row as the latest/default period without fabricating one.

    The relative order of all non-TTM rows is preserved. This is a display/default-order helper;
    it never creates or recalculates TTM data.
    """
    frame = _coerce_frame(value)
    if frame.empty:
        return frame
    period_col = next((c for c in ("Kỳ", "Period", "period", "Kỳ dữ liệu") if c in frame.columns), None)
    if period_col is None:
        return frame
    labels = frame[period_col].fillna("").astype(str).str.strip().str.upper()
    is_ttm = labels.eq("TTM")
    if not bool(is_ttm.any()):
        return frame
    return pd.concat([frame.loc[~is_ttm], frame.loc[is_ttm]], ignore_index=True)


def interactive_sort_frame(value: Any, *, key: str | None = None) -> pd.DataFrame:
    """Legacy compatibility shim. No visible sort controls are rendered.

    Sorting is handled natively by clicking a table column header. New production callers should use
    render_static_table / sortable_data_editor directly.
    """
    del key
    return prefer_ttm_latest(value)


def static_table_html(value: Any, *, height: int | None = None) -> str:
    frame = _coerce_frame(value)
    if frame.empty:
        return ""
    cols = list(frame.columns)
    max_abs: dict[str, float] = {}
    for column in cols:
        kind = infer_numeric_kind(column)
        if kind == "text" or not _heat_eligible(column):
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()
        max_abs[column] = float(numeric.max()) if not numeric.empty else 0.0

    head = "".join(f"<th>{escape(str(column))}</th>" for column in cols)
    body: list[str] = []
    for _, row in frame.iterrows():
        cells: list[str] = []
        for column in cols:
            kind = infer_numeric_kind(column)
            raw = row.get(column)
            if kind == "text":
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    text = "—"
                else:
                    text = escape(str(raw))
                cells.append(f"<td>{text}</td>")
            else:
                style = _heat_style(raw, max_abs.get(column, 0.0)) if _heat_eligible(column) else ""
                cells.append(f'<td class="num" style="{style}">{format_numeric(raw, kind)}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

    max_height = f"max-height:{int(height)}px;" if height else ""
    return (
        '<div class="tre-dca-static-table"><style>'
        '.tre-dca-static-table{overflow:auto;width:100%;' + max_height + '}'
        '.tre-dca-static-table table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.92rem;}'
        '.tre-dca-static-table th,.tre-dca-static-table td{border:1px solid rgba(148,163,184,.35);padding:7px 8px;'
        'white-space:normal;overflow-wrap:anywhere;vertical-align:top;}'
        '.tre-dca-static-table th{position:sticky;top:0;z-index:1;background:#F0FDF4;color:#065F46;font-weight:800;}'
        '.tre-dca-static-table td.num{text-align:right;font-variant-numeric:tabular-nums;}'
        '</style><table><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
    )


def _default_editor_column_config(frame: pd.DataFrame) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for column in frame.columns:
        kind = infer_numeric_kind(str(column))
        if kind == "amount_bil":
            config[column] = st.column_config.NumberColumn(str(column), format="%.0f", help="Đơn vị: tỷ đồng; 0 số lẻ.")
        elif kind == "percent":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f%%", help="Đơn vị: %; 1 số lẻ.")
        elif kind == "ratio":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Hệ số; 1 số lẻ.")
        elif kind == "days":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Số ngày; 1 số lẻ.")
    return config


def sortable_data_editor(value: Any, **kwargs: Any):
    """Editable table using Streamlit's native click-on-header sorting.

    No separate sort selector is rendered. Dynamic-row editors retain their edit/add/delete behavior;
    native sorting availability follows Streamlit's editor capabilities.
    """
    frame = prefer_ttm_latest(value)
    defaults = _default_editor_column_config(frame)
    provided = kwargs.get("column_config")
    if isinstance(provided, dict):
        defaults.update(provided)
    if defaults:
        kwargs["column_config"] = defaults
    return st.data_editor(frame, **kwargs)


def _native_table_styler(frame: pd.DataFrame):
    styler = frame.style
    for column in frame.columns:
        if not _heat_eligible(str(column)):
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()
        max_abs = float(numeric.max()) if not numeric.empty else 0.0
        styler = styler.map(lambda value, m=max_abs: _heat_style(value, m), subset=[column])
    return styler


def render_static_table(value: Any, **kwargs: Any) -> None:
    """Read-only native grid: click a column header to sort ascending/descending.

    The old separate 'Sort theo cột / Thứ tự' controls are intentionally removed.
    """
    frame = prefer_ttm_latest(value)
    if frame.empty:
        st.caption("Chưa có dữ liệu.")
        return
    kwargs.pop("sort_key", None)
    kwargs.pop("key", None)
    height = kwargs.pop("height", None)
    hide_index = kwargs.pop("hide_index", True)
    use_container_width = kwargs.pop("use_container_width", True)
    provided = kwargs.pop("column_config", None)
    column_config = _default_editor_column_config(frame)
    if isinstance(provided, dict):
        column_config.update(provided)
    st.dataframe(
        _native_table_styler(frame),
        use_container_width=use_container_width,
        hide_index=hide_index,
        height=int(height) if height else None,
        column_config=column_config or None,
        row_height=42,
        **kwargs,
    )


__all__ = [
    "format_numeric", "infer_numeric_kind", "interactive_sort_frame", "prefer_ttm_latest", "render_static_table",
    "sort_frame", "sortable_data_editor", "static_table_html",
]
