from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st


def infer_numeric_kind(column: str) -> str:
    name = str(column or '').strip()
    low = name.casefold()
    if '(tỷ)' in low or ' tỷ' in low or low.endswith('tỷ'):
        return 'amount_bil'
    if '(ngày)' in low or ' ngày' in low or low in {'dso', 'dio', 'dpo', 'ccc'} or low.startswith(('dso ', 'dio ', 'dpo ', 'ccc ')):
        return 'days'
    if '(x)' in low or '/ebit' in low or '/interest' in low or 'current ratio' in low or 'turnover' in low or 'turns' in low:
        return 'ratio'
    if any(token in low for token in ('%', 'margin', 'roic', 'yield', 'growth', 'tăng trưởng', 'revenue share', 'market share', 'retention rate', 'churn rate')):
        return 'percent'
    return 'text'


def format_numeric(value: Any, kind: str) -> str:
    try:
        if value is None or pd.isna(value):
            return '—'
        number = float(value)
    except Exception:
        return escape(str(value or ''))
    if kind == 'amount_bil':
        return f'{number:,.0f}'
    if kind == 'percent':
        return f'{number:,.1f}%'
    if kind == 'ratio':
        return f'{number:,.1f}x'
    if kind == 'days':
        return f'{number:,.1f}'
    return escape(str(value))


def _heat_eligible(column: str) -> bool:
    low = str(column or '').casefold()
    return any(token.casefold() in low for token in (
        'tăng trưởng', 'growth', 'change', 'delta', 'Δ', 'margin', 'roic',
        'cfo', 'fcf', 'ebit', 'profit', 'lợi nhuận', 'cash flow', 'dòng tiền',
        'headroom', 'impact',
    ))


def _heat_style(value: Any, max_abs: float) -> str:
    try:
        number = float(value)
    except Exception:
        return ''
    if pd.isna(number) or number == 0:
        return ''
    scale = min(1.0, abs(number) / max_abs) if max_abs > 0 else 0.0
    alpha = 0.07 + 0.23 * scale
    if number < 0:
        return f'color:#991B1B;font-weight:700;background:rgba(185,28,28,{alpha:.3f});'
    return f'color:#047857;font-weight:700;background:rgba(4,120,87,{alpha:.3f});'


def _coerce_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    data = getattr(value, 'data', None)
    if isinstance(data, pd.DataFrame):
        return data.copy()
    try:
        return pd.DataFrame(value)
    except Exception:
        return pd.DataFrame()


def static_table_html(value: Any, *, height: int | None = None) -> str:
    frame = _coerce_frame(value)
    if frame.empty:
        return ''
    cols = list(frame.columns)
    max_abs: dict[str, float] = {}
    for column in cols:
        kind = infer_numeric_kind(column)
        if kind == 'text' or not _heat_eligible(column):
            continue
        numeric = pd.to_numeric(frame[column], errors='coerce').abs().dropna()
        max_abs[column] = float(numeric.max()) if not numeric.empty else 0.0

    head = ''.join(f'<th>{escape(str(column))}</th>' for column in cols)
    body: list[str] = []
    for _, row in frame.iterrows():
        cells: list[str] = []
        for column in cols:
            kind = infer_numeric_kind(column)
            raw = row.get(column)
            if kind == 'text':
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    text = '—'
                else:
                    text = escape(str(raw))
                cells.append(f'<td>{text}</td>')
            else:
                style = _heat_style(raw, max_abs.get(column, 0.0)) if _heat_eligible(column) else ''
                cells.append(f'<td class="num" style="{style}">{format_numeric(raw, kind)}</td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')

    max_height = f'max-height:{int(height)}px;' if height else ''
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


def render_static_table(value: Any, **kwargs: Any) -> None:
    frame = _coerce_frame(value)
    if frame.empty:
        st.caption('Chưa có dữ liệu.')
        return
    height = kwargs.get('height')
    st.html(static_table_html(frame, height=int(height) if height else None))


__all__ = ['format_numeric', 'infer_numeric_kind', 'render_static_table', 'static_table_html']
