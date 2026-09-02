from __future__ import annotations

import streamlit as st

from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme


st.set_page_config(
    page_title="Phân tích chuyên sâu doanh nghiệp | Trecapital",
    page_icon="🔬",
    layout="wide",
)

inject_oaktree_theme()

with st.sidebar:
    render_tre_sidebar_nav()

st.title("Phân tích chuyên sâu doanh nghiệp")
st.caption("Khung phân tích chuyên sâu theo The Investment Checklist — đang chuẩn bị thiết kế chi tiết.")

st.info(
    "Trang này mới được tạo ở mức khung (scaffold). Chưa triển khai các nội dung phân tích, "
    "công thức, dữ liệu, AI hay checklist chi tiết.",
    icon="ℹ️",
)

apply_full_width()
