from __future__ import annotations

import streamlit as st

from modules.deep_company_analysis.chapter10_page_support import render_chapter10_tab
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme

st.set_page_config(page_title="Chương 10 — Growth Opportunities | Trecapital", page_icon="🌱", layout="wide")
inject_oaktree_theme()
with st.sidebar:
    render_tre_sidebar_nav()

st.title("Chương 10 — Evaluating Growth Opportunities")
st.caption("Deep Company Analysis | The Investment Checklist | Q53–Q57")
default_ticker = str(st.session_state.get("dca_ch10_ticker") or st.session_state.get("active_ticker") or st.session_state.get("shared_ticker") or "DGC")
render_chapter10_tab(default_ticker)
apply_full_width()
