from __future__ import annotations

import streamlit as st


def inject_oaktree_theme() -> None:
    """Oaktree-inspired institutional UI layer.

    This overrides only visual Streamlit styles. It does not change data, valuation,
    crawler, or scoring logic.
    """
    st.markdown(
        """
        <style>
        :root {
            --oak-pine:#12362F;
            --oak-pine-2:#0B2A25;
            --oak-pine-3:#1F4A42;
            --oak-gold:#B68A3A;
            --oak-gold-soft:#E9D9B8;
            --oak-cream:#F5F1E8;
            --oak-paper:#FFFDF8;
            --oak-ink:#17231F;
            --oak-muted:#5E6A64;
            --oak-line:#D7CFBE;
            --oak-red:#A43A2F;
            --oak-green:#16624F;
        }

        /* Overall shell: institutional, calm, white/cream like an asset-manager website */
        .stApp {
            background:
                linear-gradient(90deg, rgba(18,54,47,.030) 0 1px, transparent 1px) 0 0 / 72px 72px,
                linear-gradient(180deg, var(--oak-cream) 0%, #FAF8F2 18%, #FFFFFF 72%) !important;
            color: var(--oak-ink) !important;
        }
        .main .block-container {
            max-width: 1480px !important;
            padding-top: 1.05rem !important;
            padding-bottom: 2.6rem !important;
        }
        h1, h2, h3, h4 {
            color: var(--oak-pine-2) !important;
            letter-spacing: -.015em !important;
        }
        h1, .hero-card h1 {
            font-family: Georgia, 'Times New Roman', serif !important;
            font-weight: 500 !important;
        }
        p, li, label, .stMarkdown, .stCaptionContainer {
            color: var(--oak-ink) !important;
        }
        .small-muted, div[data-testid="stMetricLabel"] p, .stCaptionContainer p {
            color: var(--oak-muted) !important;
        }

        /* Sidebar = calm navigation rail, not a colorful dashboard panel */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #F3EFE4 0%, #FBF8F0 100%) !important;
            border-right: 1px solid var(--oak-line) !important;
            box-shadow: 12px 0 28px rgba(18,54,47,.045) !important;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
            color: var(--oak-pine-2) !important;
        }
        section[data-testid="stSidebar"] hr,
        section[data-testid="stSidebar"] [data-testid="stDivider"] {
            border-color: rgba(18,54,47,.18) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {display:none !important;}
        div[data-testid="stPageLink"] a {
            border: 1px solid transparent !important;
            border-left: 4px solid transparent !important;
            border-radius: 6px !important;
            margin: 5px 0 !important;
            padding: 11px 12px !important;
            background: transparent !important;
            color: var(--oak-pine-2) !important;
            font-weight: 760 !important;
            box-shadow: none !important;
            text-decoration: none !important;
            transition: all .16s ease-in-out !important;
        }
        div[data-testid="stPageLink"] a:hover {
            border-color: rgba(182,138,58,.38) !important;
            border-left-color: var(--oak-gold) !important;
            background: rgba(255,255,255,.68) !important;
            color: var(--oak-pine-2) !important;
            box-shadow: 0 8px 18px rgba(18,54,47,.07) !important;
            transform: translateX(2px) !important;
        }

        /* Header: Oaktree-style mission block: dark field, gold rule, restrained typography */
        .page-brand-shell {
            display: grid !important;
            grid-template-columns: 134px minmax(0, 1fr) !important;
            gap: 18px !important;
            align-items: stretch !important;
            margin: 8px 0 24px 0 !important;
        }
        .page-logo-wrap {
            height: auto !important;
            min-height: 124px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 18px !important;
            background: linear-gradient(135deg,#FFF7E6 0%,#EAF7F1 100%) !important;
            border: 2.6px solid #0B7F75 !important;
            border-bottom: 4px solid rgba(6,78,71,.38) !important;
            box-shadow: 0 12px 30px rgba(11,127,117,.16) !important;
            transition: all .16s ease-in-out !important;
        }
        .page-logo-wrap:hover {
            background: linear-gradient(135deg,#FFE8A3 0%,#D8F3E4 100%) !important;
            border-color: #F5B21B !important;
            box-shadow: 0 16px 36px rgba(245,178,27,.20), 0 10px 22px rgba(11,127,117,.16) !important;
            transform: translateY(-1px) !important;
        }
        .page-logo-img {
            max-height: 104px !important;
            max-width: 108px !important;
            object-fit: contain !important;
            filter: saturate(.78) contrast(.98) !important;
        }
        .hero-card {
            position: relative !important;
            padding: 28px 34px !important;
            border-radius: 4px !important;
            background: linear-gradient(135deg, var(--oak-pine-2) 0%, var(--oak-pine) 70%, #294E44 100%) !important;
            border: 1px solid rgba(255,255,255,.12) !important;
            border-left: 6px solid var(--oak-gold) !important;
            color: #FFFFFF !important;
            box-shadow: 0 20px 48px rgba(18,54,47,.22) !important;
            overflow: hidden !important;
        }
        .hero-card:after {
            content: "";
            position: absolute;
            inset: auto 0 0 0;
            height: 3px;
            background: linear-gradient(90deg, var(--oak-gold), rgba(255,255,255,0));
        }
        .page-hero-card {
            margin-bottom: 0 !important;
            min-height: 124px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
        }
        .hero-card h1 {
            color: #FFFFFF !important;
            font-size: 2.08rem !important;
            line-height: 1.15 !important;
            margin: 0 0 8px 0 !important;
        }
        .hero-card p {
            color: rgba(255,255,255,.86) !important;
            font-size: 1.00rem !important;
            line-height: 1.55 !important;
            margin: 0 !important;
            max-width: 1060px !important;
        }

        /* Cards and callouts */
        .workflow-card, .source-card, .note-card, .ok-card, .warn-card,
        div[data-testid="stMetric"], div[data-testid="stAlert"] {
            border-radius: 5px !important;
            background: rgba(255,253,248,.96) !important;
            border: 1px solid var(--oak-line) !important;
            box-shadow: 0 10px 22px rgba(18,54,47,.055) !important;
        }
        .workflow-card, .source-card, .note-card, .ok-card, .warn-card {
            border-left: 4px solid var(--oak-gold) !important;
            padding: 14px 16px !important;
            margin-bottom: 13px !important;
            color: var(--oak-ink) !important;
        }
        .ok-card {border-left-color: var(--oak-green) !important;}
        .warn-card, .note-card {background: #FFF9EA !important;}
        .big-warning-card {
            border-radius: 5px !important;
            border: 1px solid rgba(182,138,58,.48) !important;
            border-left: 6px solid var(--oak-gold) !important;
            background: linear-gradient(180deg, #FFF8E6 0%, #FFFFFF 100%) !important;
            box-shadow: 0 12px 28px rgba(182,138,58,.13) !important;
        }
        .big-warning-title {color: var(--oak-pine-2) !important;}
        .big-warning-text {color: #5A431B !important;}
        .important-red {
            border-radius: 5px !important;
            background: linear-gradient(180deg, #FFF7F3 0%, #FFFFFF 100%) !important;
            border: 1px solid rgba(164,58,47,.34) !important;
            border-left: 6px solid var(--oak-red) !important;
            box-shadow: 0 10px 24px rgba(164,58,47,.08) !important;
        }
        .important-red, .important-red * {color: #6F2D27 !important;}
        .important-red-title {color: var(--oak-red) !important;}

        /* Metrics */
        div[data-testid="stMetric"] {
            padding: 16px 18px !important;
            min-height: 82px !important;
        }
        div[data-testid="stMetricValue"] {
            color: var(--oak-pine-2) !important;
            font-size: 1.34rem !important;
            font-weight: 780 !important;
        }
        div[data-testid="stMetricDelta"] svg {display:none !important;}

        /* Buttons: rectangular CTA similar to institutional web pages */
        div.stButton > button,
        div[data-testid="stDownloadButton"] > button,
        button[kind="primary"], button[kind="secondary"] {
            border-radius: 4px !important;
            border: 1px solid var(--oak-pine-2) !important;
            background: var(--oak-pine-2) !important;
            color: #FFFFFF !important;
            font-weight: 780 !important;
            letter-spacing: .01em !important;
            box-shadow: none !important;
            transition: all .16s ease-in-out !important;
        }
        div.stButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        button[kind="primary"]:hover, button[kind="secondary"]:hover {
            background: #FFFFFF !important;
            color: var(--oak-pine-2) !important;
            border-color: var(--oak-gold) !important;
            box-shadow: inset 0 -3px 0 var(--oak-gold) !important;
        }


        /* Robust button text contrast: prevent BaseWeb inner spans/paragraphs from inheriting same color as background */
        div.stButton > button *,
        div[data-testid="stDownloadButton"] > button *,
        button[kind="primary"] *,
        button[kind="secondary"] *,
        div.stButton > button p,
        div[data-testid="stDownloadButton"] > button p {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }
        div.stButton > button:hover *,
        div[data-testid="stDownloadButton"] > button:hover *,
        button[kind="primary"]:hover *,
        button[kind="secondary"]:hover *,
        div.stButton > button:hover p,
        div[data-testid="stDownloadButton"] > button:hover p {
            color: var(--oak-pine-2) !important;
            fill: var(--oak-pine-2) !important;
        }
        div.stButton > button:disabled,
        div[data-testid="stDownloadButton"] > button:disabled,
        button:disabled {
            background: #E7E0D0 !important;
            border-color: #CFC4AE !important;
            color: #6D746F !important;
            opacity: 1 !important;
        }
        div.stButton > button:disabled *,
        div[data-testid="stDownloadButton"] > button:disabled *,
        button:disabled * {
            color: #6D746F !important;
            fill: #6D746F !important;
        }

        /* Inputs */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea,
        input {
            border-radius: 4px !important;
            border-color: var(--oak-line) !important;
            background: #FFFFFF !important;
        }
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="input"] > div:focus-within,
        textarea:focus,
        input:focus {
            border-color: var(--oak-gold) !important;
            box-shadow: 0 0 0 3px rgba(182,138,58,.14) !important;
        }

        /* Tabs: navigation strip like Insights/Strategies sections */
        div[data-testid="stTabs"] {margin-top: 14px !important; margin-bottom: 18px !important;}
        div[data-testid="stTabs"] div[data-baseweb="tab-list"],
        div[data-testid="stTabs"] div[role="tablist"],
        div[data-baseweb="tab-list"],
        div[role="tablist"] {
            gap: 6px !important;
            min-height: 58px !important;
            padding: 8px !important;
            margin: 12px 0 22px 0 !important;
            background: #FFFFFF !important;
            border: 1px solid var(--oak-line) !important;
            border-radius: 5px !important;
            box-shadow: 0 10px 22px rgba(18,54,47,.055) !important;
        }
        div[data-testid="stTabs"] button[data-baseweb="tab"],
        div[data-testid="stTabs"] button[role="tab"],
        button[data-baseweb="tab"],
        button[role="tab"],
        div[data-testid="stTabs"] div[role="tab"] {
            min-height: 44px !important;
            height: 44px !important;
            padding: 0 18px !important;
            border-radius: 3px !important;
            border: 1.8px solid rgba(182,138,58,.42) !important;
            border-bottom: 4px solid rgba(18,54,47,.32) !important;
            background: linear-gradient(135deg, #FFF6D8 0%, #EAF5EC 100%) !important;
            color: var(--oak-pine-2) !important;
            font-size: 15px !important;
            font-weight: 760 !important;
            box-shadow: 0 5px 13px rgba(18,54,47,.07) !important;
        }
        button[data-baseweb="tab"] p, button[role="tab"] p,
        button[data-baseweb="tab"] span, button[role="tab"] span {
            color: inherit !important;
            font-size: 15px !important;
            font-weight: 760 !important;
        }

        div[data-testid="stTabs"] button[data-baseweb="tab"]:hover,
        div[data-testid="stTabs"] button[role="tab"]:hover,
        button[data-baseweb="tab"]:hover,
        button[role="tab"]:hover,
        div[data-testid="stTabs"] div[role="tab"]:hover {
            background: linear-gradient(135deg, #FFE8A3 0%, #D8F3E4 100%) !important;
            border-color: var(--oak-gold) !important;
            color: var(--oak-pine-2) !important;
            transform: translateY(-1px) !important;
        }
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        button[data-baseweb="tab"][aria-selected="true"],
        button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] div[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, var(--oak-pine-2) 0%, var(--oak-green) 72%, var(--oak-gold) 132%) !important;
            color: #FFFFFF !important;
            border-color: var(--oak-gold) !important;
            border-bottom-color: var(--oak-gold) !important;
            box-shadow: 0 9px 22px rgba(18,54,47,.18) !important;
            transform: translateY(-1px) !important;
        }

        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] p,
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p,
        button[data-baseweb="tab"][aria-selected="true"] p,
        button[role="tab"][aria-selected="true"] p,
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] span,
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] span,
        button[data-baseweb="tab"][aria-selected="true"] span,
        button[role="tab"][aria-selected="true"] span {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            font-weight: 850 !important;
        }
        div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {display:none !important;}

        /* Tables */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border-radius: 5px !important;
            overflow: hidden !important;
            border: 1px solid var(--oak-line) !important;
            box-shadow: 0 10px 22px rgba(18,54,47,.05) !important;
        }
        div[data-testid="stDataFrame"] [role="columnheader"],
        div[data-testid="stDataEditor"] [role="columnheader"] {
            background: #F3EFE4 !important;
            color: var(--oak-pine-2) !important;
            font-weight: 820 !important;
            border-bottom: 1px solid var(--oak-line) !important;
        }
        .peer-compare-table th, .type-fit-table th {
            background: #F3EFE4 !important;
            color: var(--oak-pine-2) !important;
            border-color: var(--oak-line) !important;
        }
        .peer-compare-table tr:hover td,
        .type-fit-table tr:hover td {
            background: #FBF8F0 !important;
        }

        /* Plotly/chart containers */
        div[data-testid="stPlotlyChart"] {
            border-radius: 5px !important;
            border: 1px solid var(--oak-line) !important;
            background: #FFFFFF !important;
            padding: 6px !important;
            box-shadow: 0 10px 22px rgba(18,54,47,.045) !important;
        }

        /* Mobile */
        @media (max-width: 900px) {
            .page-brand-shell {grid-template-columns: 1fr !important;}
            .page-logo-wrap {min-height: 92px !important;}
            .hero-card h1 {font-size: 1.55rem !important;}
            .hero-card {padding: 22px 24px !important;}
            div[data-testid="stTabs"] button[role="tab"] {width: 100% !important; justify-content: flex-start !important;}
        }


        /* Final contrast guard: cover Streamlit sidebar buttons, BaseWeb buttons,
           download buttons and nested p/span/svg labels after all legacy CSS. */
        section[data-testid="stSidebar"] div[data-testid="stButton"] button,
        section[data-testid="stSidebar"] div.stButton button,
        section[data-testid="stSidebar"] button[data-testid^="baseButton"],
        div[data-testid="stButton"] button,
        div.stButton button,
        div[data-testid="stDownloadButton"] button,
        button[data-testid^="baseButton"],
        button[kind="primary"], button[kind="secondary"], button[kind="formSubmit"] {
            background: var(--oak-pine-2) !important;
            background-color: var(--oak-pine-2) !important;
            border: 1px solid var(--oak-pine-2) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            text-shadow: none !important;
            font-weight: 820 !important;
            opacity: 1 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button *,
        section[data-testid="stSidebar"] div.stButton button *,
        section[data-testid="stSidebar"] button[data-testid^="baseButton"] *,
        div[data-testid="stButton"] button *,
        div.stButton button *,
        div[data-testid="stDownloadButton"] button *,
        button[data-testid^="baseButton"] *,
        button[kind="primary"] *, button[kind="secondary"] *, button[kind="formSubmit"] *,
        div[data-testid="stButton"] button p,
        div.stButton button p,
        div[data-testid="stDownloadButton"] button p,
        button[data-testid^="baseButton"] p,
        button[kind="primary"] p, button[kind="secondary"] p, button[kind="formSubmit"] p,
        div[data-testid="stButton"] button span,
        div.stButton button span,
        div[data-testid="stDownloadButton"] button span,
        button[data-testid^="baseButton"] span,
        button[kind="primary"] span, button[kind="secondary"] span, button[kind="formSubmit"] span,
        div[data-testid="stButton"] button svg,
        div.stButton button svg,
        div[data-testid="stDownloadButton"] button svg,
        button[data-testid^="baseButton"] svg {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
            stroke: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            opacity: 1 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover,
        section[data-testid="stSidebar"] div.stButton button:hover,
        section[data-testid="stSidebar"] button[data-testid^="baseButton"]:hover,
        div[data-testid="stButton"] button:hover,
        div.stButton button:hover,
        div[data-testid="stDownloadButton"] button:hover,
        button[data-testid^="baseButton"]:hover,
        button[kind="primary"]:hover, button[kind="secondary"]:hover, button[kind="formSubmit"]:hover {
            background: #FFFFFF !important;
            background-color: #FFFFFF !important;
            border-color: var(--oak-gold) !important;
            color: var(--oak-pine-2) !important;
            -webkit-text-fill-color: var(--oak-pine-2) !important;
            box-shadow: inset 0 -3px 0 var(--oak-gold), 0 8px 18px rgba(18,54,47,.08) !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover *,
        section[data-testid="stSidebar"] div.stButton button:hover *,
        section[data-testid="stSidebar"] button[data-testid^="baseButton"]:hover *,
        div[data-testid="stButton"] button:hover *,
        div.stButton button:hover *,
        div[data-testid="stDownloadButton"] button:hover *,
        button[data-testid^="baseButton"]:hover *,
        button[kind="primary"]:hover *, button[kind="secondary"]:hover *, button[kind="formSubmit"]:hover *,
        div[data-testid="stButton"] button:hover p,
        div.stButton button:hover p,
        div[data-testid="stDownloadButton"] button:hover p,
        button[data-testid^="baseButton"]:hover p,
        div[data-testid="stButton"] button:hover span,
        div.stButton button:hover span,
        div[data-testid="stDownloadButton"] button:hover span,
        button[data-testid^="baseButton"]:hover span,
        div[data-testid="stButton"] button:hover svg,
        div.stButton button:hover svg,
        div[data-testid="stDownloadButton"] button:hover svg,
        button[data-testid^="baseButton"]:hover svg {
            color: var(--oak-pine-2) !important;
            fill: var(--oak-pine-2) !important;
            stroke: var(--oak-pine-2) !important;
            -webkit-text-fill-color: var(--oak-pine-2) !important;
            opacity: 1 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button:disabled,
        div[data-testid="stButton"] button:disabled,
        div.stButton button:disabled,
        div[data-testid="stDownloadButton"] button:disabled,
        button[data-testid^="baseButton"]:disabled,
        button:disabled {
            background: #E7E0D0 !important;
            background-color: #E7E0D0 !important;
            border-color: #CFC4AE !important;
            color: #5E6A64 !important;
            -webkit-text-fill-color: #5E6A64 !important;
            opacity: 1 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button:disabled *,
        div[data-testid="stButton"] button:disabled *,
        div.stButton button:disabled *,
        div[data-testid="stDownloadButton"] button:disabled *,
        button[data-testid^="baseButton"]:disabled *,
        button:disabled * {
            color: #5E6A64 !important;
            fill: #5E6A64 !important;
            stroke: #5E6A64 !important;
            -webkit-text-fill-color: #5E6A64 !important;
        }

        /* V23.55 final tab color override: all Streamlit tabs on all pages show visible colors by default. */
        div[data-testid="stTabs"] button[role="tab"],
        div[data-testid="stTabs"] button[data-baseweb="tab"],
        div[data-testid="stTabs"] div[role="tab"],
        button[role="tab"], button[data-baseweb="tab"] {
            background: linear-gradient(135deg, #FFF6D8 0%, #EAF5EC 100%) !important;
            border: 1.8px solid rgba(182,138,58,.50) !important;
            border-bottom: 4px solid rgba(18,54,47,.35) !important;
            color: var(--oak-pine-2) !important;
            -webkit-text-fill-color: var(--oak-pine-2) !important;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
        div[data-testid="stTabs"] div[role="tab"][aria-selected="true"],
        button[role="tab"][aria-selected="true"], button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, var(--oak-pine-2) 0%, var(--oak-green) 72%, var(--oak-gold) 132%) !important;
            border-color: var(--oak-gold) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }
        div[data-testid="stTabs"] button[role="tab"] p,
        div[data-testid="stTabs"] button[data-baseweb="tab"] p,
        div[data-testid="stTabs"] button[role="tab"] span,
        div[data-testid="stTabs"] button[data-baseweb="tab"] span,
        button[role="tab"] p, button[data-baseweb="tab"] p,
        button[role="tab"] span, button[data-baseweb="tab"] span {
            color: inherit !important;
            -webkit-text-fill-color: inherit !important;
            font-weight: 820 !important;
        }


        /* V23.56: Sidebar navigation uses the same visual language as tabs.
           This covers both manual st.page_link navigation and Streamlit's built-in nav if it appears. */
        section[data-testid="stSidebar"] div[data-testid="stPageLink"] a,
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
        section[data-testid="stSidebar"] nav a {
            min-height: 48px !important;
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
            border-radius: 999px !important;
            margin: 7px 2px !important;
            padding: 10px 16px !important;
            border: 2.4px solid var(--oak-green) !important;
            border-bottom: 4px solid rgba(18,54,47,.36) !important;
            background: linear-gradient(135deg, #FFF7E6 0%, #EAF7F1 100%) !important;
            color: var(--oak-pine-2) !important;
            -webkit-text-fill-color: var(--oak-pine-2) !important;
            font-weight: 900 !important;
            text-decoration: none !important;
            box-shadow: 0 8px 18px rgba(18,54,47,.12) !important;
            transition: all .16s ease-in-out !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stPageLink"] a *,
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] *,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a *,
        section[data-testid="stSidebar"] nav a * {
            color: var(--oak-pine-2) !important;
            -webkit-text-fill-color: var(--oak-pine-2) !important;
            font-weight: 900 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover,
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover,
        section[data-testid="stSidebar"] nav a:hover {
            background: linear-gradient(135deg, #FFE8A3 0%, #D8F3E4 100%) !important;
            border-color: var(--oak-gold) !important;
            border-bottom-color: var(--oak-gold) !important;
            color: var(--oak-pine-2) !important;
            -webkit-text-fill-color: var(--oak-pine-2) !important;
            box-shadow: 0 12px 24px rgba(18,54,47,.18) !important;
            transform: translateX(2px) !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stPageLink"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] nav a[aria-current="page"] {
            background: linear-gradient(135deg, var(--oak-pine-2) 0%, var(--oak-green) 72%, var(--oak-gold) 132%) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            border-color: var(--oak-gold) !important;
            border-bottom-color: var(--oak-gold) !important;
            box-shadow: 0 12px 26px rgba(18,54,47,.30) !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stPageLink"] a[aria-current="page"] *,
        section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] *,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] *,
        section[data-testid="stSidebar"] nav a[aria-current="page"] * {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        /* V23.56: sticky headers for every Streamlit dataframe/data editor.
           HTML click-note tables already use sticky <th>; this adds the same behavior for st.dataframe. */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            overflow: auto !important;
        }
        div[data-testid="stDataFrame"] [role="columnheader"],
        div[data-testid="stDataEditor"] [role="columnheader"],
        div[data-testid="stDataFrame"] [data-testid="stHeaderCell"],
        div[data-testid="stDataEditor"] [data-testid="stHeaderCell"] {
            position: sticky !important;
            top: 0 !important;
            z-index: 50 !important;
            background: #EAF7F1 !important;
            color: var(--oak-pine-2) !important;
            font-weight: 950 !important;
            box-shadow: 0 2px 0 rgba(18,54,47,.20) !important;
        }
        div[data-testid="stDataFrame"] [role="rowgroup"] [role="row"]:first-child,
        div[data-testid="stDataEditor"] [role="rowgroup"] [role="row"]:first-child {
            position: sticky !important;
            top: 0 !important;
            z-index: 49 !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )
