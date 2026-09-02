from __future__ import annotations

import streamlit as st


def render_tre_sidebar_nav() -> None:
    """Shared navigation contract for Trecapital pages."""
    st.markdown("### Điều hướng")
    st.page_link("app.py", label="Tổng quan doanh nghiệp", icon="📊")
    st.page_link("pages/02_Dinh_gia_Porter_Moat.py", label="Định giá chuyên sâu", icon="🧠")
    st.page_link("pages/03_So_sanh_doanh_nghiep.py", label="So sánh doanh nghiệp", icon="⚖️")
    st.page_link("pages/04_Bao_cao_tong_hop.py", label="Báo cáo tổng hợp toàn bộ nội dung", icon="📄")
    st.page_link("pages/05_Investment_Checklist.py", label="Investment Checklist", icon="📋")
    st.page_link("pages/06_Phan_tich_TopDown_Nganh.py", label="Fisher Top-Down theo ngành", icon="🧭")
    st.page_link("pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py", label="Phân tích chuyên sâu doanh nghiệp", icon="🔬")
    st.divider()