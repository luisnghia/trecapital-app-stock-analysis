from __future__ import annotations

import streamlit as st

def apply_full_width() -> None:
    st.markdown(
        """
        <style>
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            width: 100% !important;
            max-width: none !important;
        }

        .main .block-container,
        section.main > div,
        div[data-testid="stAppViewContainer"] .block-container,
        div[data-testid="stMainBlockContainer"] {
            max-width: none !important;
            width: 100% !important;
            padding-left: 1.0rem !important;
            padding-right: 1.0rem !important;
            padding-top: 0.8rem !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="column"],
        div[data-testid="stElementContainer"] {
            max-width: none !important;
        }

        .page-brand-shell,
        .page-hero-card,
        .hero-card,
        .workflow-card,
        .source-card,
        .note-card,
        .ok-card,
        .warn-card,
        .big-warning-card {
            max-width: none !important;
            width: 100% !important;
        }

        .hero-card p {
            max-width: none !important;
        }

        iframe {
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )