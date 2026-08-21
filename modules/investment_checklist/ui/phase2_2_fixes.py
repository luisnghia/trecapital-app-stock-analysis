from __future__ import annotations

from textwrap import dedent
from typing import Iterable

import pandas as pd
import streamlit as st

from . import portfolio_extensions as _pe


def render_wrapped_table_fixed(df: pd.DataFrame, *, css_class: str = "checklist-wrapped-table") -> None:
    """Render formula/assumption tables as real HTML with wrapped, fully visible cell content.

    The previous indented triple-quoted Markdown block could be interpreted as a code block by
    Streamlit/Markdown, which exposed raw <div>/<table> markup. Building a dedented HTML fragment
    removes that ambiguity while retaining responsive wrapping.
    """
    if df is None or df.empty:
        st.caption("Chưa có dữ liệu.")
        return
    html = df.to_html(index=False, escape=True, border=0, classes=[css_class])
    fragment = dedent(
        f"""
        <style>
        .{css_class}-wrap {{ width:100%; overflow-x:auto; margin:.35rem 0 1rem; }}
        table.{css_class} {{ width:100%; table-layout:fixed; border-collapse:collapse; font-size:.86rem; }}
        table.{css_class} th {{ background:#F6F2E8; color:#173F38; font-weight:800; padding:.55rem;
            border:1px solid #DDD4C2; white-space:normal !important; word-break:break-word; overflow-wrap:anywhere; }}
        table.{css_class} td {{ padding:.52rem; vertical-align:top; border:1px solid #E5DED0;
            white-space:normal !important; word-break:break-word; overflow-wrap:anywhere; line-height:1.38; }}
        table.{css_class} th:nth-child(1), table.{css_class} td:nth-child(1) {{ width:17%; }}
        table.{css_class} th:nth-child(2), table.{css_class} td:nth-child(2) {{ width:18%; }}
        table.{css_class} th:nth-child(3), table.{css_class} td:nth-child(3) {{ width:31%; }}
        table.{css_class} th:nth-child(4), table.{css_class} td:nth-child(4) {{ width:22%; }}
        table.{css_class} th:nth-child(5), table.{css_class} td:nth-child(5) {{ width:12%; }}
        </style>
        <div class="{css_class}-wrap">{html}</div>
        """
    ).strip()
    st.markdown(fragment, unsafe_allow_html=True)


def metric_candidates_fixed(df: pd.DataFrame, excluded: Iterable[str]) -> list[str]:
    """Expose numeric metrics even when the whole column is currently empty.

    Empty line-items (Provision, charge-off, etc.) are exactly the fields an analyst may need to
    populate manually. Pandas gives all-None columns dtype=object, so a numeric-dtype-only filter
    incorrectly hid them from the correction editor.
    """
    excluded = set(excluded)
    out: list[str] = []
    for col in df.columns:
        if col in excluded:
            continue
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            out.append(str(col))
            continue
        if s.isna().all():
            out.append(str(col))
            continue
        non_null = s.dropna()
        if not non_null.empty:
            coerced = pd.to_numeric(non_null, errors="coerce")
            if coerced.notna().all():
                out.append(str(col))
    return out


# Install the fixes before integration_preview imports render_wrapped_table and before the
# analytical context managers execute their dynamically-resolved helper functions.
_pe.render_wrapped_table = render_wrapped_table_fixed
_pe._metric_candidates = metric_candidates_fixed

__all__ = ["render_wrapped_table_fixed", "metric_candidates_fixed"]
