from __future__ import annotations

import streamlit as st

from modules.deep_company_analysis.chapter2 import render_chapter2
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme

st.set_page_config(
    page_title="Chương 2 - Hiểu doanh nghiệp | Trecapital",
    page_icon="🔎",
    layout="wide",
)

inject_oaktree_theme()
with st.sidebar:
    render_tre_sidebar_nav()

st.title("Phân tích chuyên sâu doanh nghiệp")
st.caption("Chương 2 — Understanding the Business: The Basics | Michael Shearn, The Investment Checklist")

# Reuse the shared ticker selected elsewhere in Trecapital when available.
default_ticker = str(
    st.session_state.get("dca_ch2_ticker")
    or st.session_state.get("dca_ch1_ticker")
    or st.session_state.get("active_ticker")
    or st.session_state.get("shared_ticker")
    or st.session_state.get("module2_ticker")
    or "DGC"
).upper().strip()

default_company = str(st.session_state.get("active_company_name") or "")

render_chapter2(default_ticker=default_ticker, company_name=default_company)
apply_full_width()
