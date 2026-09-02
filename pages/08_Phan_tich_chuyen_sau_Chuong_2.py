from __future__ import annotations

import streamlit as st

from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme

st.set_page_config(page_title="Chương 2 đã chuyển tab | Trecapital", page_icon="🔬", layout="wide")
inject_oaktree_theme()
with st.sidebar:
    render_tre_sidebar_nav()

st.title("Phân tích chuyên sâu doanh nghiệp")
st.info("Chương 2 đã được hợp nhất thành một tab trong trang Phân tích chuyên sâu doanh nghiệp để các chương dùng chung một workspace.")
st.page_link("pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py", label="🔬 Mở Phân tích chuyên sâu doanh nghiệp")
apply_full_width()
