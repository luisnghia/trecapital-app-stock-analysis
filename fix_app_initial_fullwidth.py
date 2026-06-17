from pathlib import Path

p = Path("app.py")

new_content = r'''from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Trecapital Stock Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        width: 100% !important;
        max-width: none !important;
    }

    .main .block-container,
    section.main > div,
    div[data-testid="stAppViewContainer"] .block-container {
        max-width: none !important;
        width: 100% !important;
        padding-left: 1.0rem !important;
        padding-right: 1.0rem !important;
        padding-top: 0.8rem !important;
    }

    div[data-testid="stVerticalBlock"],
    div[data-testid="stHorizontalBlock"] {
        max-width: none !important;
        width: 100% !important;
    }

    iframe {
        max-width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

from module1_dashboard import render_dashboard

render_dashboard()
'''

p.write_text(new_content, encoding="utf-8")
print("Updated app.py with initial full-width CSS")
