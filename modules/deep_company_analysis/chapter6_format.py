from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd


def infer_numeric_kind(column: str) -> str:
    name = str(column or "")
    if "(tỷ)" in name:
        return "amount_bil"
    if "(%)" in name:
        return "percent"
    if "(x)" in name:
        return "ratio"
    if "(ngày)" in name or name in {"DSO", "DIO", "DPO", "CCC"}:
        return "days"
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
    return f"{number:,.1f}"


def has_financial_numeric_columns(columns: list[str]) -> bool:
    return any(infer_numeric_kind(column) != "text" for column in columns)


def _heat_style(value: Any, max_abs: float) -> str:
    try:
        number = float(value)
    except Exception:
        return ""
    if pd.isna(number) or number == 0:
        return ""
    scale = min(1.0, abs(number) / max_abs) if max_abs > 0 else 0.0
    alpha = 0.08 + 0.24 * scale
    if number < 0:
        return f"color:#991B1B;font-weight:700;background:rgba(185,28,28,{alpha:.3f});"
    return f"color:#047857;font-weight:700;background:rgba(4,120,87,{alpha:.3f});"


def financial_table_html(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    """Render a read-only Chapter-6 financial table using project display rules.

    Amounts labelled ``(tỷ)`` use zero decimals. Percentages and ratios use one
    decimal. Signed values use red/emerald heat intensity by absolute magnitude.
    Text is escaped and wrapped inside a fixed-layout table.
    """
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return ""
    cols = list(columns or frame.columns)
    work = frame.copy()
    for column in cols:
        if column not in work.columns:
            work[column] = None
    work = work[cols]

    max_abs: dict[str, float] = {}
    for column in cols:
        kind = infer_numeric_kind(column)
        if kind == "text":
            continue
        numeric = pd.to_numeric(work[column], errors="coerce").abs().dropna()
        max_abs[column] = float(numeric.max()) if not numeric.empty else 0.0

    head = "".join(f"<th>{escape(str(column))}</th>" for column in cols)
    rows_html: list[str] = []
    for _, row in work.iterrows():
        cells: list[str] = []
        for column in cols:
            kind = infer_numeric_kind(column)
            value = row.get(column)
            if kind == "text":
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    text = "—"
                else:
                    text = escape(str(value))
                cells.append(f"<td>{text}</td>")
            else:
                style = _heat_style(value, max_abs.get(column, 0.0))
                cells.append(
                    f'<td class="num" style="{style}">{format_numeric(value, kind)}</td>'
                )
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    return (
        '<div class="tre-ch6-table"><style>'
        '.tre-ch6-table{overflow-x:auto;width:100%;}'
        '.tre-ch6-table table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.92rem;}'
        '.tre-ch6-table th,.tre-ch6-table td{border:1px solid rgba(148,163,184,.35);padding:7px 8px;'
        'white-space:normal;overflow-wrap:anywhere;vertical-align:top;}'
        '.tre-ch6-table th{background:#F0FDF4;color:#065F46;font-weight:800;}'
        '.tre-ch6-table td.num{text-align:right;font-variant-numeric:tabular-nums;}'
        '</style><table><thead><tr>'
        + head
        + '</tr></thead><tbody>'
        + "".join(rows_html)
        + '</tbody></table></div>'
    )


__all__ = [
    "financial_table_html",
    "format_numeric",
    "has_financial_numeric_columns",
    "infer_numeric_kind",
]
