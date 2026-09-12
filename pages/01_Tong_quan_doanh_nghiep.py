import streamlit as st
from module1_dashboard import render_dashboard
from tre_full_width import apply_full_width

render_dashboard()
with st.sidebar:
    st.page_link("pages/05_Investment_Checklist.py", label="Investment Checklist", icon="📋")
apply_full_width()
