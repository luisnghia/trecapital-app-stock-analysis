from __future__ import annotations

import html
from collections.abc import Iterable

import streamlit as st

from ..source_table_guidance import (
    CHAPTER_9_NOTE,
    SOURCE_TABLE_GUIDANCE,
    SOURCE_TABLE_ORDER,
    guidance_for_source_table,
)


def _render_one(table_id: str) -> None:
    spec = guidance_for_source_table(table_id)
    if not spec:
        return
    st.markdown(f"#### {html.escape(str(spec['title']))}")
    st.markdown(f"**Mục tiêu phân tích:** {spec['objective']}")
    st.markdown("**Cách đọc bảng:**")
    for item in spec.get("how_to_read", ()):  # static source guidance
        st.markdown(f"- {item}")
    st.markdown("**Điều cần kiểm tra:**")
    for item in spec.get("checks", ()):  # static source guidance
        st.markdown(f"- {item}")
    st.warning(f"Cảnh báo / giới hạn: {spec['caution']}")
    st.caption(f"Liên kết trong app: {spec['mapping']}")


def render_source_table_guidance(table_ids: Iterable[str], *, title: str = "📚 Hướng dẫn theo từng bảng gốc của sách") -> None:
    ids = [str(x) for x in table_ids if str(x) in SOURCE_TABLE_GUIDANCE]
    if not ids:
        return
    with st.expander(title, expanded=False):
        st.caption(
            "Diễn giải/paraphrase từ Michael Shearn, The Investment Checklist. Đây là hướng dẫn để analyst đọc bảng; "
            "không phải ngưỡng chấm BUY/SELL và không ghi đè Analyst Assessment."
        )
        for idx, table_id in enumerate(ids):
            if idx:
                st.divider()
            _render_one(table_id)


def render_full_chapter_5_to_10_guide() -> None:
    """Fast lookup for every numbered source table from Chapters 5–10 used by the module."""
    with st.expander("📚 Tra cứu đầy đủ các bảng Chương 5–10", expanded=False):
        table_id = st.selectbox(
            "Bảng gốc trong sách",
            SOURCE_TABLE_ORDER,
            format_func=lambda x: SOURCE_TABLE_GUIDANCE[x]["title"],
            key="checklist_shearn_source_table_lookup",
        )
        _render_one(table_id)
        st.info(CHAPTER_9_NOTE)
        st.caption(
            "Danh mục hiện phủ Table 5.1–5.4, 6.1–6.6, 7.1, 8.1–8.3 và 10.1. "
            "Không tạo Table 9.x giả khi sách không có bảng đánh số tương ứng trong bộ nguồn này."
        )


__all__ = ["render_source_table_guidance", "render_full_chapter_5_to_10_guide"]
