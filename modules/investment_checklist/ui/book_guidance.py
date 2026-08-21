from __future__ import annotations

import html
from typing import Iterable

import streamlit as st

from ..book_guidance import BOOK_TITLE, guidance_for


def _guidance_html(rows: list[dict]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td><b>{html.escape(str(row['metric']))}</b></td>"
            f"<td>{html.escape(str(row['read']))}</td>"
            f"<td>{html.escape(str(row['check']))}</td>"
            f"<td>{html.escape(str(row.get('caution') or '—'))}</td>"
            "</tr>"
        )
    return (
        "<style>"
        ".shearn-guide-wrap{width:100%;overflow-x:auto;margin:.35rem 0 .6rem}"
        ".shearn-guide{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.82rem;line-height:1.38}"
        ".shearn-guide th{background:#F6F2E8;color:#173F38;font-weight:800;padding:.52rem;border:1px solid #DDD4C2;"
        "white-space:normal!important;overflow-wrap:anywhere;vertical-align:top}"
        ".shearn-guide td{padding:.5rem;border:1px solid #E5DED0;white-space:normal!important;overflow-wrap:anywhere;"
        "vertical-align:top;max-width:0}"
        ".shearn-guide tr:nth-child(even) td{background:#FCFBF7}"
        "</style>"
        "<div class='shearn-guide-wrap'><table class='shearn-guide'>"
        "<thead><tr><th>Chỉ tiêu</th><th>Cách đọc</th><th>Điều cần kiểm tra</th><th>Cảnh báo / giới hạn</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def render_book_guidance(
    table_key: str,
    columns: Iterable[str] | None = None,
    *,
    expanded: bool = False,
    title: str = "📚 Hướng dẫn phân tích từ sách",
) -> None:
    """Render source-grounded, paraphrased guidance for only the currently visible table.

    Static guidance does not query PostgreSQL or external services, so it preserves the fast fragment
    path. The card is intentionally collapsed by default to keep analytical tables compact.
    """
    spec = guidance_for(table_key, columns)
    if not spec:
        return
    with st.expander(title, expanded=expanded):
        st.markdown(f"**Mục tiêu:** {spec['purpose']}")
        principles = spec.get("principles") or ()
        if principles:
            st.markdown("**Cách Shearn đề nghị suy nghĩ về bảng này:**")
            for principle in principles:
                st.markdown(f"- {principle}")
        rows = list(spec.get("metric_rows") or [])
        if rows:
            markup = _guidance_html(rows)
            if hasattr(st, "html"):
                st.html(markup)
            else:
                st.markdown(markup, unsafe_allow_html=True)
        st.caption(f"Nguồn hướng dẫn: {BOOK_TITLE} · {spec['source']}. Nội dung trong app là diễn giải/paraphrase để hỗ trợ analyst, không phải chép lại nguyên văn sách.")


__all__ = ["render_book_guidance"]
