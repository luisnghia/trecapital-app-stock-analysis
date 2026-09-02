from __future__ import annotations

import streamlit as st

from modules.deep_company_analysis.chapter1 import render_chapter1
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
st.caption("Khung phân tích chi tiết doanh nghiệp theo The Investment Checklist — triển khai từng chương, bắt đầu từ Chương 1.")

default_ticker = str(
    st.session_state.get("active_ticker")
    or st.session_state.get("shared_ticker")
    or st.session_state.get("module2_ticker")
    or "DCM"
)

render_chapter1(default_ticker=default_ticker)
apply_full_width()
