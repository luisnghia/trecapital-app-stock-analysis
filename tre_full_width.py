from __future__ import annotations

import streamlit as st

def apply_full_width() -> None:
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
