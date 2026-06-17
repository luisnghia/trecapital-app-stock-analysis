from __future__ import annotations

from pathlib import Path
from typing import Callable
import warnings
import html
import json
import re
import base64


import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*DrawingML support.*")
warnings.filterwarnings("ignore", message=".*Sparkline Group extension.*")
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

from module1_engine import (
    load_overview_from_csv,
    load_timeseries_from_csv,
    ensure_derived_metrics,
    build_flags,
    build_quick_summary,
    build_metric_dict,
    latest_metric_cards,
    format_table_for_display,
    build_fcf_analysis_table,
    build_cashflow_scorecard,
    build_cashflow_situation_alerts,
    build_financial_ratio_table,
    build_financial_ratio_scorecard,
    build_financial_ratio_alerts,
    build_value_investing_assessment,
    append_ttm_row,
    build_mos_valuation_table,
    build_mos_summary,
    build_mos_detailed_summary,
    build_combined_assessment_table,
)
from module1_charts import make_line_fig, make_metric_bar, make_dupont_profitability_fig, make_dupont_driver_fig, make_roic_investment_fig, make_fcf_generation_fig, make_fcf_usage_fig, make_fcf_conversion_fig
from adapters.base import ProviderResult, MODULE1_OVERVIEW_COLUMNS, MODULE1_TIMESERIES_COLUMNS, normalize_columns
from adapters.excel_financial_provider import ExcelFinancialProvider
from adapters.vn_public_crawler import PublicFireAntCrawler, PublicVietstockCrawler
from adapters.module2_web_research import WebEvidenceAgent
from report_exporter import render_full_report_export_box

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "trecapital_logo.png"
DEFAULT_OVERVIEW_CSV = APP_DIR / "sample_data" / "company_overview_sample.csv"
DEFAULT_YEAR_CSV = APP_DIR / "sample_data" / "financial_timeseries_year.csv"
DEFAULT_QUARTER_CSV = APP_DIR / "sample_data" / "financial_timeseries_quarter.csv"
BUNDLED_XLSM = APP_DIR / "data_sources" / "Financial-v1.3.0.xlsm"
RAW_DIR = APP_DIR / "raw_data"
DATA_CACHE_DIR = APP_DIR / "data_cache"

ICB_CODE_NAME_MAP = {
    "2353": "XÃ¢y dá»±ng & Váº­t liá»‡u",
    "2350": "XÃ¢y dá»±ng & Váº­t liá»‡u",
    "2357": "Váº­t liá»‡u xÃ¢y dá»±ng",
    "1353": "HÃ³a cháº¥t",
    "1357": "HÃ³a cháº¥t cÆ¡ báº£n/PhÃ¢n bÃ³n",
    "1753": "Dá»‹ch vá»¥ váº­n táº£i",
    "2777": "Háº¡ táº§ng giao thÃ´ng & dá»‹ch vá»¥ sÃ¢n bay",
    "8355": "NgÃ¢n hÃ ng",
    "8532": "Báº£o hiá»ƒm",
    "9533": "Báº¥t Ä‘á»™ng sáº£n",
}


def _display_industry_value(value: object) -> str:
    """Convert raw numeric industry codes to readable names so Tá»•ng quan doanh nghiá»‡p never shows only codes like 2353."""
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return "N/A"
    # Some data sources return ICB/industry code as 2353. Show the sector name, not the raw code alone.
    code_text = text[:-2] if re.fullmatch(r"\d{3,6}\.0", text) else text
    if re.fullmatch(r"\d{3,6}", code_text):
        return ICB_CODE_NAME_MAP.get(code_text, f"ChÆ°a nháº­n diá»‡n tÃªn ngÃ nh (mÃ£ {code_text})")
    return text


def _logo_data_uri() -> str:
    try:
        if LOGO_PATH.exists():
            return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    except Exception:
        pass
    return ""


def _render_brand_page_header(title: str, subtitle: str) -> None:
    logo_uri = _logo_data_uri()
    logo_html = f"<img src='{logo_uri}' alt='Trecapital' class='page-logo-img'>" if logo_uri else ""
    st.markdown(
        f"""
        <div class="page-brand-shell">
          <div class="page-logo-wrap">{logo_html}</div>
          <div class="hero-card page-hero-card">
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

SOURCE_DISPLAY_TO_INTERNAL = {
    "Tá»± Ä‘á»™ng": "FireAnt + Vietstock",
    "Dá»¯ liá»‡u Æ°u tiÃªn 1": "FireAnt",
    "Dá»¯ liá»‡u Æ°u tiÃªn 2": "Vietstock",
    "Dá»¯ liá»‡u tÃ­ch há»£p": "Financial tÃ­ch há»£p",
}
SOURCE_OPTIONS = list(SOURCE_DISPLAY_TO_INTERNAL.keys())
SOURCE_INTERNAL_TO_DISPLAY = {v: k for k, v in SOURCE_DISPLAY_TO_INTERNAL.items()}


def _to_internal_source(display_value: str) -> str:
    return SOURCE_DISPLAY_TO_INTERNAL.get(str(display_value), str(display_value))


def _safe_source_label(value: object) -> str:
    text = str(value or "")
    for raw, public in SOURCE_INTERNAL_TO_DISPLAY.items():
        text = text.replace(raw, public)
    replacements = {
        "FireAnt": "Dá»¯ liá»‡u Æ°u tiÃªn 1",
        "Vietstock": "Dá»¯ liá»‡u Æ°u tiÃªn 2",
        "Simplize": "Danh sÃ¡ch cÃ¹ng ngÃ nh",
        "vnstock": "Dá»¯ liá»‡u trá»±c tuyáº¿n",
        "KBS": "nhÃ³m dá»¯ liá»‡u trá»±c tuyáº¿n",
        "VCI": "nhÃ³m dá»¯ liá»‡u trá»±c tuyáº¿n",
        "Financial tÃ­ch há»£p": "Dá»¯ liá»‡u tÃ­ch há»£p",
        "CSV máº«u tÃ­ch há»£p": "Dá»¯ liá»‡u máº«u",
        "raw_data": "nháº­t kÃ½ ná»™i bá»™",
        "data_cache": "bá»™ nhá»› dá»¯ liá»‡u",
    }
    for raw, public in replacements.items():
        text = text.replace(raw, public)
    text = re.sub(r"/?[^\s<>]*\.(?:csv|json|html|txt|xlsm|xlsx)", "file ná»™i bá»™", text, flags=re.I)
    text = re.sub(r"[A-Za-z]:\\[^\s<>]+", "Ä‘Æ°á»ng dáº«n ná»™i bá»™", text)
    text = re.sub(r"/(?:mnt|home|Users|raw_data|data_cache)[^\s<>]+", "Ä‘Æ°á»ng dáº«n ná»™i bá»™", text)
    return text

st.set_page_config(
    page_title="Tá»•ng quan doanh nghiá»‡p tÃ­ch há»£p V23.36",
    page_icon="ðŸ“Š",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: none; width: 100%;}
    .stApp {background: radial-gradient(circle at 10% 0%, rgba(11,127,117,.08), transparent 28%), linear-gradient(180deg, #F7FBF8 0%, #FFFFFF 60%);} 
    section[data-testid="stSidebar"] {background: linear-gradient(180deg, #EAF7F1 0%, #FFFFFF 72%); border-right: 1px solid rgba(11,127,117,.14);}
    /* V23.25: hide Streamlit built-in multipage nav; app provides branded page links manually. */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {display:none !important;}
    div[data-testid="stPageLink"] a {
        border: 1.7px solid rgba(11,127,117,.28) !important;
        border-radius: 17px !important;
        margin: 6px 0 !important;
        padding: 11px 14px !important;
        background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(248,255,251,.88)) !important;
        color: #064E47 !important;
        font-weight: 900 !important;
        box-shadow: 0 7px 17px rgba(11,127,117,.08) !important;
        text-decoration: none !important;
    }
    div[data-testid="stPageLink"] a:hover {
        border-color:#F5B21B !important;
        background: linear-gradient(135deg, #F8FFFB 0%, #FFF7E6 100%) !important;
        color:#0B5F58 !important;
        box-shadow: 0 10px 22px rgba(11,127,117,.16) !important;
    }
 
    .hero-card {
        padding: 20px 23px; border-radius: 24px;
        background: linear-gradient(135deg, #0B7F75 0%, #128C7E 56%, #F5B21B 135%);
        color: white; margin-bottom: 18px; box-shadow: 0 14px 34px rgba(11,127,117,.20);
        border: 1px solid rgba(255,255,255,.28);
    }
    .hero-card h1 {font-size: 1.85rem; margin: 0 0 6px 0; color: white; letter-spacing: -.02em;}
    .hero-card p {font-size: .88rem; margin: 0; opacity: .95;}
    .logo-card {display:flex; align-items:center; justify-content:center; padding: 10px 6px; border-radius:22px; background: transparent; border:1px solid rgba(11,127,117,.10); box-shadow: 0 10px 24px rgba(11,127,117,.10); margin-bottom: 16px;}
    .page-brand-shell {display:grid; grid-template-columns: 152px minmax(0,1fr); gap:18px; align-items:center; margin:8px 0 20px 0;}
    .page-logo-wrap {height:150px; display:flex; align-items:center; justify-content:center; border-radius:26px; background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%); border:1.8px solid rgba(11,127,117,.18); box-shadow:0 12px 30px rgba(11,127,117,.10);}
    .page-logo-img {max-height:132px; max-width:132px; object-fit:contain;}
    .page-hero-card {margin-bottom:0 !important; min-height:112px; display:flex; flex-direction:column; justify-content:center;}
    div[data-testid="stDataFrame"] [role="columnheader"], div[data-testid="stDataEditor"] [role="columnheader"] {font-weight:950 !important; color:#064E47 !important;}
    .workflow-card {
        border: 1px solid rgba(11,127,117,.28); border-radius: 18px; padding: 14px 16px;
        background: linear-gradient(180deg, rgba(234,247,241,.96), rgba(255,255,255,.88)); margin-bottom: 14px;
    }
    .source-card {
        border: 1px solid rgba(11,127,117,.28); border-radius: 16px; padding: 12px 14px;
        background: rgba(234,247,241,.72); margin-top: 8px; margin-bottom: 12px;
    }
    .note-card {
        border: 1px solid rgba(11,127,117,.22); border-radius: 16px; padding: 13px 16px;
        background: rgba(255,251,235,.75); margin-bottom: 10px;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,.84); border: 1px solid rgba(148,163,184,.25);
        border-radius: 16px; padding: 12px 14px; box-shadow: 0 4px 16px rgba(15,23,42,.04);
    }
    div[data-testid="stMetricLabel"] p {font-size: .88rem; color: #475569;}
    div[data-testid="stMetricValue"] {font-size: 1.22rem;}
    .stTabs [data-baseweb="tab-list"], div[data-testid="stTabs"] [role="tablist"] {gap: 14px !important; background: rgba(234,247,241,.96) !important; padding: 14px 16px !important; border-radius: 26px !important; border:2px solid rgba(11,127,117,.30) !important; box-shadow:0 10px 26px rgba(11,127,117,.12) !important;}
    .stTabs [data-baseweb="tab"], div[data-testid="stTabs"] button[role="tab"] {min-height: 58px !important; height: 58px !important; border-radius: 999px !important; padding: 0 28px !important; border: 2.5px solid rgba(11,127,117,.40) !important; background: #FFFFFF !important; color:#0B5F58 !important; font-size: 1.08rem !important; font-weight: 900 !important; box-shadow:0 6px 16px rgba(11,127,117,.10) !important;}
    .stTabs [aria-selected="true"], div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {background: linear-gradient(135deg, #0B7F75, #128C7E) !important; color: #FFFFFF !important; border-color:#F5B21B !important; box-shadow:0 10px 24px rgba(11,127,117,.28) !important; transform: translateY(-1px);}
    .stTabs [data-baseweb="tab"] p, div[data-testid="stTabs"] button[role="tab"] p {font-size: 1.08rem !important; font-weight: 900 !important;}
    .important-red {color:#B91C1C !important; font-size:1.26rem !important; line-height:1.66 !important; font-weight:900 !important; background:rgba(254,242,242,.92) !important; border:2px solid rgba(239,68,68,.28) !important; border-left:10px solid #DC2626 !important; padding:16px 18px !important; border-radius:16px !important; margin:12px 0 16px 0 !important; box-shadow:0 8px 22px rgba(185,28,28,.08) !important;}
    .small-muted {font-size: .88rem; color: #64748b;}
    div.stButton > button {border-radius: 999px; border: 1px solid rgba(11,127,117,.35); background: linear-gradient(135deg, #0B7F75, #139486); color: white; font-weight: 700;}
    div.stButton > button:hover {border-color:#F5B21B; color:white; box-shadow: 0 0 0 3px rgba(245,178,27,.16);}
    
    /* V23.20: robust global Streamlit tab styling for Tá»•ng quan doanh nghiá»‡p + Äá»‹nh giÃ¡ chuyÃªn sÃ¢u */
    div[data-testid="stTabs"] {margin-top: 12px !important;}
    div[data-testid="stTabs"] div[role="tablist"],
    div[role="tablist"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 14px !important;
        min-height: 72px !important;
        padding: 14px 16px !important;
        margin: 10px 0 18px 0 !important;
        background: linear-gradient(180deg, #EAF7F1 0%, #F8FFFB 100%) !important;
        border: 2px solid rgba(11,127,117,.36) !important;
        border-radius: 26px !important;
        box-shadow: 0 10px 26px rgba(11,127,117,.14) !important;
        visibility: visible !important;
        opacity: 1 !important;
        overflow: visible !important;
    }
    div[data-testid="stTabs"] button[role="tab"],
    div[data-testid="stTabs"] div[role="tab"],
    div[role="tablist"] button,
    button[role="tab"],
    div[role="tab"] {
        min-height: 56px !important;
        height: 56px !important;
        padding: 0 26px !important;
        border-radius: 999px !important;
        border: 2px solid rgba(11,127,117,.42) !important;
        background: #FFFFFF !important;
        color: #0B5F58 !important;
        font-size: 16px !important;
        font-weight: 900 !important;
        box-shadow: 0 6px 16px rgba(11,127,117,.12) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    button[role="tab"] p, div[role="tab"] p,
    button[role="tab"] span, div[role="tab"] span,
    div[data-testid="stTabs"] p, div[data-testid="stTabs"] span {
        font-size: 16px !important;
        font-weight: 900 !important;
        color: inherit !important;
        line-height: 1.2 !important;
    }
    button[role="tab"][aria-selected="true"],
    div[role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #0B7F75 0%, #128C7E 100%) !important;
        color: #FFFFFF !important;
        border-color: #F5B21B !important;
        box-shadow: 0 10px 24px rgba(11,127,117,.28) !important;
        transform: translateY(-1px) !important;
    }
    button[role="tab"][aria-selected="true"] p, div[role="tab"][aria-selected="true"] p,
    button[role="tab"][aria-selected="true"] span, div[role="tab"][aria-selected="true"] span {
        color: #FFFFFF !important;
    }
    .important-red, .important-red * {
        color:#B91C1C !important;
        font-size:1.08rem !important;
        line-height:1.65 !important;
        font-weight:850 !important;
    }
    .important-red-title {
        color:#991B1B !important;
        font-size:1.22rem !important;
        font-weight:950 !important;
        margin-bottom:8px !important;
    }
    .important-red {
        background:linear-gradient(180deg, #FFF1F2 0%, #FEF2F2 100%) !important;
        border:2px solid rgba(220,38,38,.34) !important;
        border-left:10px solid #DC2626 !important;
        padding:16px 18px !important;
        border-radius:16px !important;
        margin:12px 0 16px 0 !important;
        box-shadow:0 8px 22px rgba(185,28,28,.10) !important;
    }
    .ticker-title-card {border:3px solid rgba(11,127,117,.38); border-left:12px solid #F5B21B; border-radius:20px; padding:14px 18px; background:linear-gradient(135deg, rgba(234,247,241,.98) 0%, rgba(255,255,255,.98) 100%); margin:14px 0 16px 0; box-shadow:0 12px 30px rgba(11,127,117,.14);}
    .ticker-title-code {font-size:2.45rem !important; font-weight:1000; color:#0B7F75; letter-spacing:-.03em;}
    .ticker-title-name {font-size:1.55rem !important; font-weight:950; color:#9A6600;}
    .ticker-title-meta {font-size:1.22rem; color:#0B5F58; margin-top:8px; font-weight:700;}
    /* V23.20: thu nhá» cÃ¡c tháº» thá»‘ng kÃª tá»•ng quan xuá»‘ng khoáº£ng 40% Ä‘á»ƒ gá»n dashboard */
    div[data-testid="stMetric"] {padding:6px 9px !important; border-radius:12px !important; min-height:53px !important; box-shadow:0 3px 10px rgba(15,23,42,.045) !important;}
    div[data-testid="stMetricLabel"] p {font-size:.66rem !important; line-height:1.10 !important; color:#475569 !important;}
    div[data-testid="stMetricValue"] {font-size:.88rem !important; line-height:1.18 !important; color:#064E47 !important; font-weight:900 !important;}
    div[data-testid="stMetricDelta"] {font-size:.60rem !important;}
    
    /* V23.33 extra CSS */

        section[data-testid="stSidebar"] img {display:none !important;}
        div[data-testid="stDataFrame"] [role="columnheader"], div[data-testid="stDataEditor"] [role="columnheader"],
        div[data-testid="stDataFrame"] [data-testid="stHeader"], div[data-testid="stDataEditor"] [data-testid="stHeader"],
        .stDataFrame th, .stDataEditor th {font-weight:950 !important; color:#064E47 !important;}
        .page-brand-shell {display:grid; grid-template-columns: 176px minmax(0,1fr); gap:22px; align-items:center; margin:6px 0 22px 0;}
        .page-logo-wrap {height:166px; display:flex; align-items:center; justify-content:center; border-radius:30px; background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%); border:2px solid rgba(11,127,117,.20); box-shadow:0 14px 34px rgba(11,127,117,.12);}
        .page-logo-img {max-height:146px; max-width:146px; object-fit:contain; display:block !important;}
        .page-hero-card {margin-bottom:0 !important; min-height:118px; display:flex; flex-direction:column; justify-content:center;}

        </style>
    """,
    unsafe_allow_html=True,
)


# V23.20 helpers: render important conclusions without raw markdown markers and sync MOS globally.
MOS_OPTIONS_GLOBAL = [0, 10, 20, 25, 30, 35, 40, 45, 50, 60, 70]


def _normalize_mos_value(value, default: int = 50) -> int:
    try:
        v = int(float(value))
    except Exception:
        v = default
    if v not in MOS_OPTIONS_GLOBAL:
        # Choose nearest supported value.
        v = min(MOS_OPTIONS_GLOBAL, key=lambda x: abs(x - v))
    return v


def _prepare_mos_widget(widget_key: str) -> int:
    canonical = _normalize_mos_value(st.session_state.get("target_mos_pct", st.session_state.get("module2_target_mos_pct", 50)))
    # Náº¿u MOS vá»«a Ä‘á»•i á»Ÿ module khÃ¡c, Ã©p widget hiá»‡n táº¡i theo canonical chung.
    # Náº¿u MOS vá»«a Ä‘á»•i á»Ÿ chÃ­nh widget nÃ y, callback _commit_mos_widget Ä‘Ã£ cáº­p nháº­t canonical trÆ°á»›c khi rerun.
    if widget_key not in st.session_state or _normalize_mos_value(st.session_state.get(widget_key)) != canonical:
        st.session_state[widget_key] = canonical
    st.session_state["target_mos_pct"] = canonical
    st.session_state["module1_target_mos_pct"] = canonical
    st.session_state["module2_target_mos_pct"] = canonical
    return canonical


def _commit_mos_widget(widget_key: str) -> None:
    canonical = _normalize_mos_value(st.session_state.get(widget_key, st.session_state.get("target_mos_pct", 50)))
    st.session_state["target_mos_pct"] = canonical
    st.session_state["module1_target_mos_pct"] = canonical
    st.session_state["module2_target_mos_pct"] = canonical
    st.session_state["last_mos_source_widget"] = widget_key
    st.session_state["mos_sync_status"] = f"ÄÃ£ Ä‘á»“ng bá»™ MOS yÃªu cáº§u {canonical}% cho Tá»•ng quan doanh nghiá»‡p vÃ  Äá»‹nh giÃ¡ chuyÃªn sÃ¢u."


def _markdownish_to_html(text: object) -> str:
    raw = "" if text is None else str(text)
    # Normalize common markdown fragments from engine summaries into HTML so ** does not appear on screen.
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    escaped = html.escape(raw)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = escaped.replace("\n", "<br>")
    # Keep bullet-like output readable.
    escaped = escaped.replace("â€¢ ", "&bull; ").replace("- ", "&ndash; ")
    return escaped


def _render_important_red(title: str, body: object) -> None:
    st.markdown(
        f"""
        <div class="important-red" style="color:#B91C1C !important;font-size:1.08rem !important;line-height:1.65 !important;font-weight:850 !important;background:linear-gradient(180deg,#FFF1F2 0%,#FEF2F2 100%) !important;border:2px solid rgba(220,38,38,.34) !important;border-left:10px solid #DC2626 !important;padding:16px 18px !important;border-radius:16px !important;margin:12px 0 16px 0 !important;box-shadow:0 8px 22px rgba(185,28,28,.10) !important;">
            <div class="important-red-title" style="color:#991B1B !important;font-size:1.22rem !important;font-weight:950 !important;margin-bottom:8px !important;">{html.escape(str(title))}</div>
            <div>{_markdownish_to_html(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# V23.20: card HTML ná»™i tuyáº¿n Ä‘á»ƒ cháº¯c cháº¯n Tá»•ng quan doanh nghiá»‡p luÃ´n ná»•i báº­t ticker vÃ  thu nhá» KPI,
# khÃ´ng phá»¥ thuá»™c CSS Streamlit bá»‹ cache/rerun.

def _safe_public_text(value: object) -> str:
    text = str(value or "")
    replacements = {
        "FireAnt": "Dá»¯ liá»‡u Æ°u tiÃªn",
        "Vietstock": "Dá»¯ liá»‡u Æ°u tiÃªn",
        "Simplize": "Danh sÃ¡ch cÃ¹ng ngÃ nh",
        "Financial tÃ­ch há»£p": "Dá»¯ liá»‡u tÃ­ch há»£p",
        "CSV máº«u tÃ­ch há»£p": "Dá»¯ liá»‡u máº«u",
        "raw_data": "nháº­t kÃ½ ná»™i bá»™",
        "data_cache": "bá»™ nhá»› dá»¯ liá»‡u",
    }
    for raw, public in replacements.items():
        text = text.replace(raw, public)
    text = re.sub(r"(?:Dá»¯ liá»‡u Æ°u tiÃªn|Dá»¯ liá»‡u tÃ­ch há»£p|Dá»¯ liá»‡u máº«u|FireAnt|Vietstock|Simplize)?\s*(?:VBA\s+)?endpoints?\s*", "Dá»¯ liá»‡u cáº­p nháº­t ", text, flags=re.I)
    text = re.sub(r"\bCrawler\s+[^0-9]*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", r"Dá»¯ liá»‡u cáº­p nháº­t \1", text, flags=re.I)
    text = re.sub(r"https?://\S+", "liÃªn káº¿t ná»™i bá»™", text, flags=re.I)
    text = re.sub(r"[A-Za-z]:\\[^\s<>]+", "Ä‘Æ°á»ng dáº«n ná»™i bá»™", text)
    text = re.sub(r"/(?:mnt|home|Users|raw_data|data_cache)[^\s<>]+", "Ä‘Æ°á»ng dáº«n ná»™i bá»™", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

def _render_ticker_title_inline(company, current_price: object = None, updated_at: object = None) -> None:
    ticker = html.escape(str(getattr(company, 'ticker', '') or 'N/A'))
    name = html.escape(str(getattr(company, 'company_name', '') or 'Äang cáº­p nháº­t tÃªn doanh nghiá»‡p'))
    exchange = html.escape(str(getattr(company, 'exchange', '') or 'N/A'))
    industry = html.escape(_display_industry_value(getattr(company, 'industry', '')))
    sub_industry = html.escape(_display_industry_value(getattr(company, 'sub_industry', '')))
    if sub_industry == industry:
        industry_line = f"<b>NgÃ nh:</b> {industry}"
    else:
        industry_line = f"<b>NgÃ nh:</b> {industry} &nbsp; | &nbsp; <b>PhÃ¢n ngÃ nh:</b> {sub_industry}"
    price_text = html.escape(str(current_price if current_price not in {None, ''} else 'N/A'))
    updated_text = html.escape(_safe_public_text(updated_at if updated_at not in {None, ''} else 'N/A'))
    st.markdown(
        f"""
        <div style="border:3px solid rgba(11,127,117,.45);border-left:13px solid #F5B21B;border-radius:31px;
                    padding:20px 26px;background:linear-gradient(135deg,rgba(234,247,241,.98) 0%,rgba(255,255,255,.98) 100%);
                    margin:12px 0 16px 0;box-shadow:0 14px 34px rgba(11,127,117,.18);">
          <div style="line-height:1.08;"><span style="font-size:2.76rem;font-weight:1000;color:#0B7F75;letter-spacing:-.04em;">{ticker}</span>
          <span style="font-size:1.80rem;font-weight:950;color:#9A6600;"> - {name}</span></div>
          <div style="display:inline-flex;align-items:center;gap:19px;margin-top:16px;margin-bottom:10px;padding:14px 20px;
                      border-radius:22px;border:2.2px solid #F5B21B;border-left:10px solid #F5B21B;background:#FFFFFF;
                      box-shadow:0 8px 20px rgba(245,178,27,.13);min-width:336px;">
             <div style="font-size:.86rem;line-height:1.05;color:#50646B;font-weight:900;text-transform:uppercase;letter-spacing:.03em;">GiÃ¡ hiá»‡n táº¡i</div>
             <div style="font-size:1.42rem;line-height:1.1;color:#064E47;font-weight:1000;">{price_text}</div>
             <div style="font-size:.94rem;color:#64748B;font-weight:720;">Cáº­p nháº­t: {updated_text}</div>
          </div>
          <div style="font-size:1.22rem;color:#0B5F58;margin-top:7px;font-weight:780;"><b>SÃ n:</b> {exchange} &nbsp; | &nbsp; {industry_line}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_compact_metric(label: str, value: object, accent: bool = False) -> None:
    label_html = html.escape(str(label))
    value_html = html.escape(str(value if value is not None else 'N/A'))
    border = '#F5B21B' if accent else 'rgba(11,127,117,.22)'
    left = '#F5B21B' if accent else '#0B7F75'
    st.markdown(
        f"""
        <div style="background:rgba(255,255,255,.94);border:1.6px solid {border};border-left:6px solid {left};
                    border-radius:17px;padding:8px 12px;margin:5px 0 8px 0;min-height:64px;
                    box-shadow:0 3px 11px rgba(11,127,117,.07);overflow:hidden;">
          <div style="font-size:.80rem;line-height:1.08;color:#50646B;font-weight:820;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label_html}</div>
          <div style="font-size:1.24rem;line-height:1.20;color:#064E47;font-weight:980;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{value_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



# V23.20: CSS pháº£i Ä‘Æ°á»£c inject trong render_dashboard(), khÃ´ng Ä‘á»ƒ á»Ÿ top-level import.
# LÃ½ do: Streamlit cache module Python; khi widget MOS lÃ m rerun thÃ¬ import khÃ´ng cháº¡y láº¡i,
# dáº«n Ä‘áº¿n máº¥t style tab vÃ  style nháº­n xÃ©t. HÃ m nÃ y cháº¡y á»Ÿ má»—i láº§n render Ä‘á»ƒ style luÃ´n cÃ²n.
def _inject_runtime_ui_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --tre-teal:#0B7F75;
            --tre-teal-dark:#064E47;
            --tre-teal-soft:#EAF7F1;
            --tre-yellow:#F5B21B;
            --tre-red:#B91C1C;
        }
        .main .block-container {padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: none !important; width: 100% !important;}
        .stApp {background: radial-gradient(circle at 10% 0%, rgba(11,127,117,.08), transparent 28%), linear-gradient(180deg, #F7FBF8 0%, #FFFFFF 60%) !important;}
        section[data-testid="stSidebar"] {background: linear-gradient(180deg, #EAF7F1 0%, #FFFFFF 72%) !important; border-right: 1px solid rgba(11,127,117,.14) !important;}
    /* V23.25: hide Streamlit built-in multipage nav; app provides branded page links manually. */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {display:none !important;}
    div[data-testid="stPageLink"] a {
        border: 1.7px solid rgba(11,127,117,.28) !important;
        border-radius: 17px !important;
        margin: 6px 0 !important;
        padding: 11px 14px !important;
        background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(248,255,251,.88)) !important;
        color: #064E47 !important;
        font-weight: 900 !important;
        box-shadow: 0 7px 17px rgba(11,127,117,.08) !important;
        text-decoration: none !important;
    }
    div[data-testid="stPageLink"] a:hover {
        border-color:#F5B21B !important;
        background: linear-gradient(135deg, #F8FFFB 0%, #FFF7E6 100%) !important;
        color:#0B5F58 !important;
        box-shadow: 0 10px 22px rgba(11,127,117,.16) !important;
    }


        /* Streamlit Tabs - dÃ¹ng selector rá»™ng cho nhiá»u version Streamlit/BaseWeb */
        div[data-testid="stTabs"] {margin-top: 14px !important; margin-bottom: 14px !important;}
        div[data-testid="stTabs"] div[data-baseweb="tab-list"],
        div[data-testid="stTabs"] div[role="tablist"],
        div[data-baseweb="tab-list"],
        div[role="tablist"] {
            display: flex !important;
            flex-wrap: wrap !important;
            align-items: center !important;
            gap: 14px !important;
            min-height: 76px !important;
            padding: 14px 16px !important;
            margin: 12px 0 20px 0 !important;
            background: linear-gradient(180deg, #EAF7F1 0%, #F8FFFB 100%) !important;
            border: 2.5px solid rgba(11,127,117,.42) !important;
            border-radius: 28px !important;
            box-shadow: 0 12px 30px rgba(11,127,117,.16) !important;
            overflow: visible !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        div[data-testid="stTabs"] button[data-baseweb="tab"],
        div[data-testid="stTabs"] button[role="tab"],
        button[data-baseweb="tab"],
        button[role="tab"],
        div[data-testid="stTabs"] div[role="tab"] {
            min-height: 58px !important;
            height: 58px !important;
            padding: 0 28px !important;
            border-radius: 999px !important;
            border: 2.5px solid rgba(11,127,117,.45) !important;
            background: #FFFFFF !important;
            color: #0B5F58 !important;
            font-size: 17px !important;
            font-weight: 950 !important;
            letter-spacing: .01em !important;
            box-shadow: 0 8px 18px rgba(11,127,117,.14) !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        div[data-testid="stTabs"] button[data-baseweb="tab"] p,
        div[data-testid="stTabs"] button[role="tab"] p,
        button[data-baseweb="tab"] p,
        button[role="tab"] p,
        div[data-testid="stTabs"] button[data-baseweb="tab"] span,
        div[data-testid="stTabs"] button[role="tab"] span,
        button[data-baseweb="tab"] span,
        button[role="tab"] span {
            font-size: 17px !important;
            font-weight: 950 !important;
            line-height: 1.2 !important;
            color: inherit !important;
        }
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        button[data-baseweb="tab"][aria-selected="true"],
        button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] div[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #0B7F75 0%, #128C7E 100%) !important;
            color: #FFFFFF !important;
            border-color: #F5B21B !important;
            box-shadow: 0 12px 26px rgba(11,127,117,.32) !important;
            transform: translateY(-1px) !important;
        }
        div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {display:none !important;}
        button[data-baseweb="tab"][aria-selected="true"] p,
        button[role="tab"][aria-selected="true"] p,
        button[data-baseweb="tab"][aria-selected="true"] span,
        button[role="tab"][aria-selected="true"] span {color:#FFFFFF !important;}

        /* Nháº­n xÃ©t/Ä‘Ã¡nh giÃ¡/káº¿t luáº­n quan trá»ng */
        .important-red, .important-red * {
            color: #B91C1C !important;
            font-size: 1.10rem !important;
            line-height: 1.68 !important;
            font-weight: 850 !important;
        }
        .important-red-title {
            color: #991B1B !important;
            font-size: 1.25rem !important;
            font-weight: 950 !important;
            margin-bottom: 9px !important;
        }
        .important-red {
            background: linear-gradient(180deg, #FFF1F2 0%, #FEF2F2 100%) !important;
            border: 2px solid rgba(220,38,38,.36) !important;
            border-left: 11px solid #DC2626 !important;
            padding: 17px 19px !important;
            border-radius: 17px !important;
            margin: 12px 0 17px 0 !important;
            box-shadow: 0 9px 24px rgba(185,28,28,.11) !important;
        }
        .hero-card {padding: 20px 23px; border-radius: 24px; background: linear-gradient(135deg, #0B7F75 0%, #128C7E 56%, #F5B21B 135%); color: white; margin-bottom: 18px; box-shadow: 0 14px 34px rgba(11,127,117,.20); border:1px solid rgba(255,255,255,.28);}
        .hero-card h1 {font-size: 1.8rem; margin: 0 0 6px 0; color: white; letter-spacing: -.02em;}
        .hero-card p {font-size: .88rem; margin: 0; opacity: .95;}
        .logo-card {display:flex; align-items:center; justify-content:center; padding: 10px 6px; border-radius:22px; background: transparent; border:1px solid rgba(11,127,117,.10); box-shadow: 0 10px 24px rgba(11,127,117,.10); margin-bottom: 16px;}
    .page-brand-shell {display:grid; grid-template-columns: 152px minmax(0,1fr); gap:18px; align-items:center; margin:8px 0 20px 0;}
    .page-logo-wrap {height:150px; display:flex; align-items:center; justify-content:center; border-radius:26px; background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%); border:1.8px solid rgba(11,127,117,.18); box-shadow:0 12px 30px rgba(11,127,117,.10);}
    .page-logo-img {max-height:132px; max-width:132px; object-fit:contain;}
    .page-hero-card {margin-bottom:0 !important; min-height:112px; display:flex; flex-direction:column; justify-content:center;}
    div[data-testid="stDataFrame"] [role="columnheader"], div[data-testid="stDataEditor"] [role="columnheader"] {font-weight:950 !important; color:#064E47 !important;}
        .workflow-card {border: 1px solid rgba(11,127,117,.28); border-radius: 18px; padding: 14px 16px; background: linear-gradient(180deg, rgba(234,247,241,.96), rgba(255,255,255,.88)); margin-bottom: 14px;}
        .source-card {border: 1px solid rgba(11,127,117,.28); border-radius: 16px; padding: 12px 14px; background: rgba(234,247,241,.72); margin-top: 8px; margin-bottom: 12px;}
        .note-card {border: 1px solid rgba(11,127,117,.22); border-radius: 16px; padding: 13px 16px; background: rgba(255,251,235,.75); margin-bottom: 10px;}
        .ok-card {border: 1px solid rgba(11,127,117,.32); border-radius: 16px; padding: 14px 16px; background: rgba(234,247,241,.76); margin-bottom: 12px;}
        .warn-card {border: 1px solid rgba(245,178,27,.48); border-radius: 16px; padding: 14px 16px; background: rgba(255,247,230,.88); margin-bottom: 12px;}
        .big-warning-card {border: 3px solid #0B7F75; border-left: 16px solid #F5B21B; border-radius: 22px; padding: 25px 27px; background: linear-gradient(135deg, #FFF4C7 0%, #FFE68A 100%); margin: 18px 0 22px 0; box-shadow: 0 16px 38px rgba(245,178,27,.28);}
        .big-warning-title {font-size: 1.62rem; font-weight: 950; color: #0B7F75; margin-bottom: 10px; letter-spacing:-.01em;}
        .big-warning-text {font-size: 1.42rem; font-weight: 900; color: #5F3B00; line-height: 1.50;}
        div[data-testid="stMetric"] {background: rgba(255,255,255,.90); border: 1px solid rgba(11,127,117,.18); border-radius: 19px; padding: 14px 17px; min-height: 72px; box-shadow: 0 5px 19px rgba(11,127,117,.07);}
        div.stButton > button {border-radius: 999px !important; border: 1px solid rgba(11,127,117,.35) !important; background: linear-gradient(135deg, #0B7F75, #139486) !important; color: white !important; font-weight: 800 !important;}
        div.stButton > button:hover {border-color:#F5B21B !important; color:white !important; box-shadow: 0 0 0 3px rgba(245,178,27,.16) !important;}
        .small-muted {font-size: .88rem; color: #64748b;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    try:
        from ui_oaktree_theme import inject_oaktree_theme

        inject_oaktree_theme()
    except Exception:
        pass
    # V23.56: final override after theme injection so sidebar nav remains colored like tabs.
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] a,
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"],
    section[data-testid="stSidebar"] nav a {
        border-radius:999px !important; border:2.4px solid #0B7F75 !important; border-bottom:4px solid rgba(6,78,71,.38) !important;
        background:linear-gradient(135deg,#FFF7E6 0%,#EAF7F1 100%) !important; color:#064E47 !important; -webkit-text-fill-color:#064E47 !important;
        font-weight:950 !important; box-shadow:0 8px 18px rgba(11,127,117,.14) !important; margin:7px 2px !important; padding:10px 16px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover,
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
    section[data-testid="stSidebar"] nav a:hover {background:linear-gradient(135deg,#FFE8A3 0%,#D8F3E4 100%) !important; border-color:#F5B21B !important;}
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] a[aria-current="page"],
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"],
    section[data-testid="stSidebar"] nav a[aria-current="page"] {background:linear-gradient(135deg,#064E47 0%,#0B7F75 70%,#F5B21B 132%) !important; color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; border-color:#F5B21B !important;}
    div[data-testid="stDataFrame"] [role="columnheader"], div[data-testid="stDataEditor"] [role="columnheader"] {position:sticky !important; top:0 !important; z-index:50 !important; background:#EAF7F1 !important; color:#064E47 !important; font-weight:950 !important;}

    /* V23.59: logo Trecapital card styled like colored tabs. */
    .page-logo-wrap, .logo-card {
        background:linear-gradient(135deg,#FFF7E6 0%,#EAF7F1 100%) !important;
        border:2.6px solid #0B7F75 !important;
        border-bottom:4px solid rgba(6,78,71,.38) !important;
        box-shadow:0 12px 30px rgba(11,127,117,.16) !important;
        transition:all .16s ease-in-out !important;
    }
    .page-logo-wrap:hover, .logo-card:hover {
        background:linear-gradient(135deg,#FFE8A3 0%,#D8F3E4 100%) !important;
        border-color:#F5B21B !important;
        box-shadow:0 16px 36px rgba(245,178,27,.20), 0 10px 22px rgba(11,127,117,.16) !important;
        transform:translateY(-1px) !important;
    }

    </style>
    """, unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def _load_overview_cached(path: str, ticker: str):
    return load_overview_from_csv(path, ticker)


@st.cache_data(show_spinner=False)
def _load_timeseries_cached(path: str, ticker: str, period_type: str, limit: int) -> pd.DataFrame:
    return ensure_derived_metrics(load_timeseries_from_csv(path, ticker, period_type, limit))


@st.cache_data(show_spinner=False)
def _export_bundled_financial_cached(xlsm_path: str, ticker: str, cache_dir: str) -> tuple[str, str, str, str]:
    out_dir = Path(cache_dir) / "financial_xlsm" / ticker.upper()
    result = ExcelFinancialProvider(xlsm_path).export_csv(ticker, out_dir)
    return (
        str(out_dir / "company_overview_sample.csv"),
        str(out_dir / "financial_timeseries_year.csv"),
        str(out_dir / "financial_timeseries_quarter.csv"),
        f"Dá»¯ liá»‡u tÃ­ch há»£p | NÄƒm: {len(result.annual)} dÃ²ng | QuÃ½: {len(result.quarterly)} dÃ²ng",
    )


def _badge(level: str) -> str:
    if level == "good":
        return "âœ…"
    if level == "risk":
        return "âš ï¸"
    return "ðŸ”Ž"


def _plot(fig, empty_message: str = "ChÆ°a cÃ³ dá»¯ liá»‡u Ä‘á»ƒ váº½ biá»ƒu Ä‘á»“ nÃ y.") -> None:
    if not fig.data:
        st.warning(empty_message)
        return
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "locale": "vi",
        },
    )




def _parse_display_number(value: object) -> float | None:
    """Parse numbers from both raw numeric values and formatted display strings."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "nan", "None", "N/A"}:
        return None
    text = text.replace("\u00a0", " ")
    # Keep only numeric signs, decimal points, commas and percent markers.
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch in "-+.,")
    if cleaned in {"", "-", "+"}:
        return None
    # Values displayed by the app use comma as thousands separator and dot as decimal separator.
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except Exception:
        return None



def _signal_class(value: object) -> str:
    """Classify qualitative signals for traffic-light/heatmap styling."""
    s = str(value or "").strip().lower()
    if not s or s in {"nan", "none", "n/a", "na", "-"}:
        return ""
    if "lá»£i tháº¿" in s or "moat" in s:
        if "ráº¥t máº¡nh" in s or "very strong" in s or "xuáº¥t sáº¯c" in s:
            return "sig-purple-strong"
        if "máº¡nh" in s or "strong" in s:
            return "sig-purple"
        if "khÃ¡" in s or "good" in s:
            return "sig-yellow"
        if "bÃ¬nh" in s or "trung" in s or "normal" in s or "average" in s:
            return "sig-yellow"
        if "yáº¿u" in s or "khÃ´ng" in s or "weak" in s or "no moat" in s:
            return "sig-red"
    if s in {"cao", "high"}:
        return "sig-purple-strong"
    if s in {"trung bÃ¬nh", "medium", "moderate"}:
        return "sig-yellow"
    if s in {"tháº¥p", "low", "khÃ´ng cÃ³ dá»¯ liá»‡u", "no data"}:
        return "sig-red"
    if any(k in s for k in ["cáº£nh bÃ¡o", "rá»§i ro", "rá»§i ro chu ká»³", "yáº¿u", "Ã¢m", "suy giáº£m", "khÃ´ng Ä‘áº¡t", "chÆ°a Ä‘áº¡t", "khÃ´ng phÃ¹ há»£p", "thiáº¿u dá»¯ liá»‡u", "khÃ´ng cÃ³ dá»¯ liá»‡u", "chÆ°a Ä‘á»§", "chÆ°a cÃ³", "lá»—i", "Ä‘Ã²n báº©y cao", "xáº¥u"]):
        if any(k in s for k in ["nghiÃªm trá»ng", "ráº¥t", "khÃ´ng Ä‘áº¡t", "chÆ°a Ä‘áº¡t", "rá»§i ro", "yáº¿u", "xáº¥u"]):
            return "sig-red-strong"
        return "sig-red"
    if any(k in s for k in ["tá»‘t", "Ä‘áº¡t", "máº¡nh", "an toÃ n", "hiá»‡u quáº£", "tÃ­ch cá»±c", "vÆ°á»£t", "cao", "bá»n", "á»•n Ä‘á»‹nh", "cÃ³ runway", "runway", "pricing power", "cÃ³ báº±ng chá»©ng", "quality", "cash tá»‘t", "táº¡o giÃ¡ trá»‹"]):
        if any(k in s for k in ["ráº¥t", "máº¡nh", "vÆ°á»£t", "tá»‘t", "cao", "bá»n"]):
            return "sig-purple-strong"
        return "sig-purple"
    if any(k in s for k in ["theo dÃµi", "cáº§n kiá»ƒm", "cáº§n soi", "cáº§n xÃ¡c minh", "cáº§n kiá»ƒm chá»©ng", "cáº§n bá»• sung", "cáº§n tÃ¬m", "cáº©n trá»ng", "trung bÃ¬nh", "bÃ¬nh thÆ°á»ng", "khÃ¡", "chÆ°a rÃµ", "háº¡n cháº¿", "gáº§n vÃ¹ng", "chá»", "kiá»ƒm chá»©ng", "chÆ°a káº¿t luáº­n"]):
        return "sig-yellow"
    return ""


def _signal_cell_style(value: object) -> str:
    cls = _signal_class(value)
    mapping = {
        "sig-red-strong": "background-color:#FECACA;color:#7F1D1D;font-weight:900;border-left:5px solid #DC2626;",
        "sig-red": "background-color:#FEE2E2;color:#991B1B;font-weight:800;border-left:4px solid #EF4444;",
        "sig-purple-strong": "background-color:#E9D5FF;color:#581C87;font-weight:900;border-left:5px solid #7E22CE;",
        "sig-purple": "background-color:#F3E8FF;color:#6B21A8;font-weight:800;border-left:4px solid #A855F7;",
        "sig-yellow": "background-color:#FEF3C7;color:#92400E;font-weight:800;border-left:4px solid #F59E0B;",
    }
    return mapping.get(cls, "")

def _style_financial_table(df: pd.DataFrame):
    """Heatmap for all numeric-like cells: red for negative, emerald for positive."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    display_df = df.copy()

    def _display_formatter_for_col(col: str):
        name = str(col).lower()
        # Ordering matters: price/share values can contain a percent sign in names such as "GiÃ¡ MOS 50%".
        if "eps" in name or "oeps" in name or "Ä‘/cp" in name or "_vnd" in name or "vnd" in name or "giÃ¡" in name or "cplh" in name or "cá»• phiáº¿u" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if ("%" in name or "_pct" in name or "pct" in name or "tá»· lá»‡" in name or "margin" in name or "roe" in name or "roa" in name or "roic" in name or "growth" in name or "tÄƒng trÆ°á»Ÿng" in name or "biÃªn an toÃ n" in name or "wacc" in name):
            return lambda x: "" if pd.isna(x) else f"{x:,.1f}%"
        if "ngÃ y" in name or "dso" in name or "dio" in name or "dpo" in name or "ccc" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if ("tá»·" in name or "_bil" in name or " bil" in name or "vá»‘n hÃ³a" in name or "assets" in name or "capital" in name or "cash" in name or "fcf" in name or "cfo" in name or "owner earnings" in name or "profit" in name or "lá»£i nhuáº­n" in name or "doanh thu" in name or "ná»£" in name or "vay" in name or "Ä‘áº§u tÆ°" in name):
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if "_mil" in name or "triá»‡u" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if "ratio" in name or "/" in name or "turnover" in name or "coverage" in name or "multiplier" in name or "p/e" in name or "p/b" in name or "p/s" in name or "vÃ²ng quay" in name or "há»‡ sá»‘" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.1f}"
        if "Ä‘iá»ƒm" in name or "trá»ng sá»‘" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.1f}"
        return lambda x: "" if pd.isna(x) else x

    formatters = {}
    for _col in display_df.columns:
        if pd.api.types.is_numeric_dtype(display_df[_col]):
            formatters[_col] = _display_formatter_for_col(_col)

    exclude_cols = {
        "Ká»³", "period", "ticker", "company_name", "exchange", "industry", "sub_industry", "updated_at",
        "NhÃ³m / chá»‰ tiÃªu", "NhÃ³m tiÃªu chÃ­", "TÃ­n hiá»‡u", "Nháº­n xÃ©t tá»± Ä‘á»™ng", "TÃ¬nh huá»‘ng", "Má»©c Ä‘á»™", "Diá»…n giáº£i", "PhÆ°Æ¡ng phÃ¡p", "CÆ¡ sá»Ÿ tÃ­nh", "Nguá»“n Ä‘Ã¡nh giÃ¡", "Ná»™i dung"
    }
    parsed = pd.DataFrame(index=display_df.index, columns=display_df.columns, dtype="float64")
    for col in display_df.columns:
        if col in exclude_cols:
            continue
        parsed[col] = display_df[col].map(_parse_display_number)
    max_pos = parsed.where(parsed > 0).max().max()
    max_neg = parsed.where(parsed < 0).abs().max().max()
    max_pos = float(max_pos) if pd.notna(max_pos) and max_pos > 0 else 1.0
    max_neg = float(max_neg) if pd.notna(max_neg) and max_neg > 0 else 1.0

    def styles(data: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame("", index=data.index, columns=data.columns)
        for col in data.columns:
            if col in {"TÃ­n hiá»‡u", "Má»©c Ä‘á»™", "TÃ¬nh tráº¡ng", "Khuyáº¿n nghá»‹", "Káº¿t luáº­n", "Káº¿t luáº­n theo mÃ£", "Moat level", "Äá»™ tin cáº­y", "ÄÃ¡nh giÃ¡ sÆ¡ bá»™", "Loáº¡i lá»£i tháº¿"}:
                for idx, val in data[col].items():
                    out.at[idx, col] = _signal_cell_style(val)
                continue
            if col in exclude_cols:
                continue
            for idx, val in data[col].items():
                num = _parse_display_number(val)
                if num is None or abs(num) < 1e-12:
                    continue
                if num < 0:
                    rel = min(abs(num) / max_neg, 1.0)
                    alpha = 0.10 + 0.58 * rel
                    out.at[idx, col] = f"background-color: rgba(239, 68, 68, {alpha:.3f}); color: #7f1d1d; font-weight: 600;"
                else:
                    rel = min(num / max_pos, 1.0)
                    alpha = 0.08 + 0.52 * rel
                    out.at[idx, col] = f"background-color: rgba(16, 185, 129, {alpha:.3f}); color: #064e3b; font-weight: 600;"
        return out

    return display_df.style.format(formatters).apply(styles, axis=None)


def _show_table(df: pd.DataFrame, height: int = 520) -> None:
    st.dataframe(_style_financial_table(df), use_container_width=True, hide_index=True, height=height)


def _render_bold_table_title(title: str) -> None:
    """Render table title exactly like core analysis table titles.

    The reference title `Báº£ng PHÃ‚N TÃCH CHá»ˆ Sá» TC theo nÄƒm` is rendered by
    Streamlit `st.subheader(...)`; using the same component avoids CSS scoping
    differences and guarantees bold heading weight in the running app.
    """
    st.subheader(str(title))


def _render_fcf_analysis_table(df: pd.DataFrame, key: str = "fcf_analysis") -> None:
    """Render FCF analysis using the same numeric heatmap format as other app tables.

    Section-title rows such as (I)/(II)/(III) are still bold, but all numeric
    period columns keep the app-wide heatmap: negative values red, positive
    values emerald, stronger color for larger absolute values.
    """
    if df is None or df.empty:
        st.info("ChÆ°a cÃ³ dá»¯ liá»‡u.")
        return
    display = df.copy()

    def section_styles(data: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame("", index=data.index, columns=data.columns)
        first_col = data.columns[0] if len(data.columns) else None
        if first_col is None:
            return out
        for idx, val in data[first_col].items():
            txt = str(val or "").strip().upper()
            if txt.startswith("(I)") or txt.startswith("(II)") or txt.startswith("(III)"):
                out.loc[idx, :] = "font-weight:950; background-color:#F3EFE4; color:#12362F;"
            elif not txt:
                out.loc[idx, :] = "background-color:#FFFFFF;"
        return out

    styled = (_style_financial_table(display).apply(section_styles, axis=None)
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("font-weight", "950"),
                    ("background-color", "#EAF7F1"),
                    ("color", "#123D3A"),
                    ("border-bottom", "1px solid rgba(11,127,117,.22)"),
                ],
            }
        ])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=420)


def _fmt_note_value(value: object) -> str:
    if value is None:
        return "N/A"
    try:
        if pd.isna(value):
            return "N/A"
    except Exception:
        pass
    if isinstance(value, float):
        return f"{value:,.1f}" if abs(value) < 1000 else f"{value:,.0f}"
    if isinstance(value, int):
        return f"{value:,.0f}"
    return str(value)


def _latest_record(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    try:
        if "period" in df.columns:
            ttm = df[df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
            if not ttm.empty:
                return ttm.iloc[-1].to_dict()
    except Exception:
        pass
    return df.iloc[-1].to_dict()


def _module1_company_context(company, annual_df: pd.DataFrame | None) -> str:
    latest = _latest_record(annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame())
    period = latest.get("period") or latest.get("year") or "ká»³ má»›i nháº¥t/TTM"
    rev = latest.get("revenue_bil")
    np = latest.get("net_profit_bil")
    cfo = latest.get("cfo_bil")
    fcf = latest.get("free_cash_flow_bil")
    roe = latest.get("roe_actual_pct") or latest.get("roe_pct")
    roic = latest.get("roic_standard_pct") or latest.get("roic_pct")
    return "\n".join([
        f"Doanh nghiá»‡p: {getattr(company, 'ticker', '')} - {getattr(company, 'company_name', '')}",
        f"NgÃ nh/phÃ¢n ngÃ nh: {_display_industry_value(getattr(company, 'industry', ''))} / {_display_industry_value(getattr(company, 'sub_industry', ''))}",
        f"Ká»³ dá»¯ liá»‡u dÃ¹ng Ä‘á»ƒ giáº£i thÃ­ch: {period}; giÃ¡ hiá»‡n táº¡i: {_fmt_note_value(getattr(company, 'current_price', None))} Ä‘/cp.",
        f"Sá»‘ liá»‡u chÃ­nh ká»³ gáº§n nháº¥t: doanh thu {_fmt_note_value(rev)} tá»·, LNST {_fmt_note_value(np)} tá»·, CFO {_fmt_note_value(cfo)} tá»·, FCF {_fmt_note_value(fcf)} tá»·, ROE {_fmt_note_value(roe)}%, ROIC {_fmt_note_value(roic)}%.",
    ])


def _build_module1_note(row: pd.Series, table_kind: str, company=None, annual_df: pd.DataFrame | None = None, quarterly_df: pd.DataFrame | None = None) -> str:
    rowd = row.to_dict()
    ctx = _module1_company_context(company, annual_df) if company is not None else ""
    lines = [ctx, ""] if ctx else []

    if "PhÆ°Æ¡ng phÃ¡p" in rowd and "GiÃ¡ trá»‹ ná»™i táº¡i (Ä‘/cp)" in rowd:
        intrinsic = _parse_display_number(rowd.get("GiÃ¡ trá»‹ ná»™i táº¡i (Ä‘/cp)"))
        mos_col = "GiÃ¡ MOS chá»n (Ä‘/cp)" if "GiÃ¡ MOS chá»n (Ä‘/cp)" in rowd else "GiÃ¡ MOS 50% (Ä‘/cp)"
        _raw_mos_level = _parse_display_number(rowd.get("Má»©c MOS Ã¡p dá»¥ng (%)"))
        mos_level = st.session_state.get("target_mos_pct", 50) if _raw_mos_level is None else _raw_mos_level
        mos_price = _parse_display_number(rowd.get(mos_col))
        price = _parse_display_number(rowd.get("GiÃ¡ hiá»‡n táº¡i (Ä‘/cp)"))
        margin = _parse_display_number(rowd.get("BiÃªn an toÃ n hiá»‡n táº¡i (%)"))
        lines += [
            f"PHÆ¯Æ NG PHÃP MOS: {rowd.get('PhÆ°Æ¡ng phÃ¡p', '')}",
            f"- GiÃ¡ trá»‹ ná»™i táº¡i Æ°á»›c tÃ­nh: {_fmt_note_value(intrinsic)} Ä‘/cp.",
            f"- GiÃ¡ mua theo MOS {float(mos_level):.0f}%: {_fmt_note_value(mos_price)} Ä‘/cp.",
            f"- GiÃ¡ hiá»‡n táº¡i: {_fmt_note_value(price)} Ä‘/cp; biÃªn an toÃ n hiá»‡n táº¡i: {_fmt_note_value(margin)}%.",
            f"- TÃ­n hiá»‡u: {rowd.get('TÃ­n hiá»‡u', 'N/A')}.",
            f"- CÃ´ng thá»©c/cÆ¡ sá»Ÿ tÃ­nh: {rowd.get('CÆ¡ sá»Ÿ tÃ­nh', 'N/A')}.",
            f"- Diá»…n giáº£i theo dá»¯ liá»‡u hiá»‡n táº¡i: {rowd.get('Diá»…n giáº£i', 'N/A')}.",
            f"NguyÃªn táº¯c: MOS khÃ´ng pháº£i lá»‡nh mua/bÃ¡n. ÄÃ¢y lÃ  lá»›p báº£o vá»‡ khi Æ°á»›c tÃ­nh giÃ¡ trá»‹ cÃ³ thá»ƒ sai. Láº§n cháº¡y nÃ y dÃ¹ng MOS yÃªu cáº§u {float(mos_level):.0f}% do ngÆ°á»i dÃ¹ng chá»n; cáº§n Ä‘á»c cÃ¹ng cháº¥t lÆ°á»£ng lá»£i nhuáº­n, dÃ²ng tiá»n, ROIC vÃ  báº£ng cÃ¢n Ä‘á»‘i cá»§a chÃ­nh doanh nghiá»‡p.",
        ]
        return "\n".join(lines)

    if "Nguá»“n Ä‘Ã¡nh giÃ¡" in rowd and "Má»©c Ä‘á»™" in rowd:
        src = str(rowd.get("Nguá»“n Ä‘Ã¡nh giÃ¡", ""))
        principle = ""
        if "MOS" in src or "Äá»‹nh giÃ¡" in src:
            principle = "NguyÃªn táº¯c: Ä‘á»‹nh giÃ¡ pháº£i gáº¯n vá»›i biÃªn an toÃ n, khÃ´ng dÃ¹ng má»™t Ä‘iá»ƒm fair value duy nháº¥t. Kiá»ƒm tra láº¡i giáº£ Ä‘á»‹nh tÄƒng trÆ°á»Ÿng, P/E má»¥c tiÃªu vÃ  cháº¥t lÆ°á»£ng dÃ²ng tiá»n."
        elif "FCF" in src or "dÃ²ng tiá»n" in src:
            principle = "NguyÃªn táº¯c: lá»£i nhuáº­n káº¿ toÃ¡n pháº£i Ä‘Æ°á»£c kiá»ƒm chá»©ng báº±ng CFO/FCF/Owner Earnings; thay Ä‘á»•i vá»‘n lÆ°u Ä‘á»™ng vÃ  capex cÃ³ thá»ƒ lÃ m dÃ²ng tiá»n khÃ¡c xa LNST."
        elif "Chá»‰ sá»‘" in src:
            principle = "NguyÃªn táº¯c: chá»‰ sá»‘ tÃ i chÃ­nh Ä‘Æ°á»£c Ä‘á»c theo cá»¥m: tÄƒng trÆ°á»Ÿng, biÃªn lá»£i nhuáº­n, ROE/ROIC, vá»‘n lÆ°u Ä‘á»™ng, Ä‘Ã²n báº©y vÃ  Ä‘á»‹nh giÃ¡; khÃ´ng káº¿t luáº­n chá»‰ tá»« má»™t chá»‰ tiÃªu Ä‘Æ¡n láº»."
        else:
            principle = "NguyÃªn táº¯c: Ä‘Ã¢y lÃ  cáº£nh bÃ¡o tá»± Ä‘á»™ng Ä‘á»ƒ nháº¯c analyst kiá»ƒm tra thÃªm dá»¯ liá»‡u gá»‘c vÃ  bá»‘i cáº£nh ngÃ nh trÆ°á»›c khi káº¿t luáº­n."
        lines += [
            f"Cáº¢NH BÃO/ÄIá»‚M Cáº¦N KIá»‚M TRA: {rowd.get('Ná»™i dung', '')}",
            f"- Nguá»“n Ä‘Ã¡nh giÃ¡: {src}; má»©c Ä‘á»™: {rowd.get('Má»©c Ä‘á»™', 'N/A')}.",
            f"- Diá»…n giáº£i cá»¥ thá»ƒ: {rowd.get('Diá»…n giáº£i', 'N/A')}.",
            f"- Viá»‡c cáº§n lÃ m: Ä‘á»‘i chiáº¿u láº¡i BCTC/BCTN, xem chuá»—i nhiá»u nÄƒm/quÃ½ vÃ  so vá»›i doanh nghiá»‡p cÃ¹ng ngÃ nh náº¿u cÃ³.",
            principle,
        ]
        return "\n".join(lines)

    if "NhÃ³m tiÃªu chÃ­" in rowd and "Äiá»ƒm" in rowd:
        group = str(rowd.get("NhÃ³m tiÃªu chÃ­", ""))
        extra = ""
        if "TÄƒng trÆ°á»Ÿng" in group:
            extra = "CÃ¡ch Ä‘á»c: xem CAGR doanh thu, LNST, EPS; tÄƒng trÆ°á»Ÿng tá»‘t pháº£i Ä‘i cÃ¹ng biÃªn lá»£i nhuáº­n vÃ  dÃ²ng tiá»n, khÃ´ng chá»‰ tÄƒng quy mÃ´."
        elif "BiÃªn" in group:
            extra = "CÃ¡ch Ä‘á»c: biÃªn gá»™p/biÃªn rÃ²ng á»•n Ä‘á»‹nh cho tháº¥y quyá»n Ä‘á»‹nh giÃ¡ hoáº·c kiá»ƒm soÃ¡t chi phÃ­; biÃªn giáº£m cáº§n kiá»ƒm tra cáº¡nh tranh, nguyÃªn liá»‡u, chi phÃ­ bÃ¡n hÃ ng."
        elif "Sinh lá»i" in group or "vá»‘n" in group:
            extra = "CÃ¡ch Ä‘á»c: ROE/ROA/ROIC cho biáº¿t hiá»‡u quáº£ sá»­ dá»¥ng vá»‘n; ROIC cao cáº§n Ä‘Æ°á»£c xÃ¡c nháº­n báº±ng CFO/FCF vÃ  tÃ­nh bá»n vá»¯ng qua nhiá»u ká»³."
        elif "vá»‘n lÆ°u Ä‘á»™ng" in group or "Hiá»‡u quáº£" in group:
            extra = "CÃ¡ch Ä‘á»c: DSO/DIO/DPO/CCC vÃ  CFO/LNST cho biáº¿t tiá»n bá»‹ káº¹t á»Ÿ pháº£i thu, tá»“n kho hay Ä‘Æ°á»£c tÃ i trá»£ bá»Ÿi pháº£i tráº£/khÃ¡ch hÃ ng."
        elif "Thanh khoáº£n" in group or "ÄÃ²n báº©y" in group:
            extra = "CÃ¡ch Ä‘á»c: current ratio, quick ratio, ná»£ vay rÃ²ng/VCSH, interest coverage giÃºp Ä‘Ã¡nh giÃ¡ kháº£ nÄƒng chá»‹u Ä‘á»±ng chu ká»³ xáº¥u."
        elif "Äá»‹nh giÃ¡" in group:
            extra = "CÃ¡ch Ä‘á»c: Ä‘á»‹nh giÃ¡ ráº» chá»‰ cÃ³ Ã½ nghÄ©a khi cháº¥t lÆ°á»£ng doanh nghiá»‡p/dÃ²ng tiá»n/tÃ i sáº£n Ä‘á»§ tá»‘t; trÃ¡nh báº«y giÃ¡ trá»‹."
        else:
            extra = "CÃ¡ch Ä‘á»c: Ä‘iá»ƒm sá»‘ lÃ  checklist Ä‘á»‹nh hÆ°á»›ng, khÃ´ng thay tháº¿ phÃ¢n tÃ­ch Ä‘á»‹nh tÃ­nh vÃ  so sÃ¡nh ngÃ nh."
        latest = _latest_record(annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame())
        ratio_context = []
        for k in ["revenue_growth_yoy_pct", "net_profit_growth_yoy_pct", "gross_margin_pct", "net_margin_pct", "roe_actual_pct", "roic_standard_pct", "roic_operating_profit_pct", "wacc_pct", "cfo_to_net_profit", "fcf_to_net_profit", "current_ratio", "quick_ratio", "net_debt_to_equity", "interest_coverage", "cash_conversion_cycle_days"]:
            if k in latest and str(latest.get(k)) not in {"", "nan", "None", "<NA>"}:
                suffix = "%" if any(x in k for x in ["pct", "margin", "roe", "roic", "wacc", "growth"]) else (" ngÃ y" if "days" in k else " láº§n")
                ratio_context.append(f"{k}={_fmt_note_value(latest.get(k))}{suffix}")
        point = _parse_display_number(rowd.get('Äiá»ƒm'))
        weight = _parse_display_number(rowd.get('Trá»ng sá»‘'))
        pct = (point / weight * 100) if point is not None and weight and abs(weight) > 1e-9 else _parse_display_number(rowd.get('Tá»· lá»‡ Ä‘áº¡t'))
        lines += [
            f"Bá»˜ TIÃŠU CHÃ: {group}",
            f"- Trá»ng sá»‘: {_fmt_note_value(rowd.get('Trá»ng sá»‘'))}; Ä‘iá»ƒm Ä‘áº¡t: {_fmt_note_value(rowd.get('Äiá»ƒm'))}; tá»· lá»‡ Ä‘áº¡t: {_fmt_note_value(pct)}%.",
            f"- VÃ¬ sao ra Ä‘iá»ƒm nÃ y: Ä‘iá»ƒm = tá»•ng cÃ¡c Ä‘iá»u kiá»‡n nhá» trong nhÃ³m. Tá»· lá»‡ Ä‘áº¡t = Ä‘iá»ƒm/trá»ng sá»‘; nhÃ³m Ä‘Æ°á»£c xáº¿p Tá»‘t náº¿u Ä‘áº¡t khoáº£ng â‰¥75%, Theo dÃµi náº¿u khoáº£ng 50%-75%, Cáº£nh bÃ¡o náº¿u tháº¥p hÆ¡n hoáº·c cÃ³ chá»‰ tiÃªu Ä‘á».",
            f"- Chá»‰ tiÃªu chÃ­nh Ä‘ang áº£nh hÆ°á»Ÿng Ä‘áº¿n Ä‘iá»ƒm: {'; '.join(ratio_context[:10]) if ratio_context else 'chÆ°a Ä‘á»§ dá»¯ liá»‡u chá»‰ tiÃªu thÃ nh pháº§n trong ká»³ má»›i nháº¥t.'}",
            f"- TÃ­n hiá»‡u: {rowd.get('TÃ­n hiá»‡u', 'N/A')}.",
            f"- Nháº­n xÃ©t tá»± Ä‘á»™ng: {rowd.get('Nháº­n xÃ©t tá»± Ä‘á»™ng', 'N/A')}.",
            extra,
        ]
        return "\n".join(lines)

    if "TÃ¬nh huá»‘ng" in rowd and "Má»©c Ä‘á»™" in rowd:
        lines += [
            f"TÃŒNH HUá»NG/Cáº¢NH BÃO: {rowd.get('TÃ¬nh huá»‘ng', '')}",
            f"- Má»©c Ä‘á»™: {rowd.get('Má»©c Ä‘á»™', 'N/A')}.",
            f"- Diá»…n giáº£i: {rowd.get('Diá»…n giáº£i', 'N/A')}.",
            "NguyÃªn táº¯c: cáº£nh bÃ¡o Ä‘Æ°á»£c kÃ­ch hoáº¡t tá»« dá»¯ liá»‡u thá»±c táº¿ ká»³ gáº§n nháº¥t hoáº·c chuá»—i nhiá»u ká»³. Cáº§n kiá»ƒm tra nguyÃªn nhÃ¢n: chu ká»³ ngÃ nh, sá»± kiá»‡n báº¥t thÆ°á»ng, chÃ­nh sÃ¡ch káº¿ toÃ¡n, vá»‘n lÆ°u Ä‘á»™ng, ná»£ vay hoáº·c thay Ä‘á»•i chiáº¿n lÆ°á»£c.",
        ]
        return "\n".join(lines)

    if "NhÃ³m / chá»‰ tiÃªu" in rowd:
        label = str(rowd.get("NhÃ³m / chá»‰ tiÃªu", ""))
        latest_pairs = [(k, v) for k, v in rowd.items() if k != "NhÃ³m / chá»‰ tiÃªu" and str(v).strip() not in {"", "nan", "None"}]
        tail = latest_pairs[-4:]
        data_text = "; ".join([f"{k}: {v}" for k, v in tail]) if tail else "ChÆ°a cÃ³ sá»‘ liá»‡u."
        principle = ""
        if "ROIC" in label or "ROE" in label or "ROA" in label:
            principle = "NguyÃªn táº¯c: nhÃ³m sinh lá»i trÃªn vá»‘n cho biáº¿t doanh nghiá»‡p biáº¿n vá»‘n thÃ nh lá»£i nhuáº­n ra sao; cáº§n xem xu hÆ°á»›ng nhiá»u ká»³ vÃ  cháº¥t lÆ°á»£ng dÃ²ng tiá»n Ä‘i kÃ¨m."
        elif "CFO" in label or "FCF" in label or "Owner Earnings" in label or "OEPS" in label:
            principle = "NguyÃªn táº¯c: dÃ²ng tiá»n tháº­t vÃ  Owner Earnings giÃºp kiá»ƒm tra lá»£i nhuáº­n káº¿ toÃ¡n cÃ³ chuyá»ƒn thÃ nh tiá»n cho chá»§ sá»Ÿ há»¯u hay khÃ´ng."
        elif "DSO" in label or "DIO" in label or "DPO" in label or "CCC" in label or "vá»‘n lÆ°u Ä‘á»™ng" in label:
            principle = "NguyÃªn táº¯c: vá»‘n lÆ°u Ä‘á»™ng cho biáº¿t tiá»n bá»‹ hÃºt vÃ o pháº£i thu/tá»“n kho hay Ä‘Æ°á»£c tÃ i trá»£ bá»Ÿi pháº£i tráº£; tÃ¡c Ä‘á»™ng trá»±c tiáº¿p tá»›i FCF."
        elif "Ná»£" in label or "Debt" in label or "Coverage" in label or "Ratio" in label:
            principle = "NguyÃªn táº¯c: thanh khoáº£n vÃ  Ä‘Ã²n báº©y cho biáº¿t sá»©c chá»‹u Ä‘á»±ng khi doanh thu/lá»£i nhuáº­n suy giáº£m hoáº·c lÃ£i suáº¥t tÄƒng."
        elif "TÄƒng trÆ°á»Ÿng" in label:
            principle = "NguyÃªn táº¯c: tÄƒng trÆ°á»Ÿng bá»n vá»¯ng pháº£i Ä‘i cÃ¹ng biÃªn lá»£i nhuáº­n, ROIC vÃ  dÃ²ng tiá»n; tÄƒng trÆ°á»Ÿng khÃ´ng cháº¥t lÆ°á»£ng cÃ³ thá»ƒ phÃ¡ há»§y giÃ¡ trá»‹."
        else:
            principle = "NguyÃªn táº¯c: Ä‘á»c chá»‰ tiÃªu theo xu hÆ°á»›ng nhiá»u ká»³, so vá»›i ngÃ nh vÃ  Ä‘á»‘i chiáº¿u sá»± kiá»‡n báº¥t thÆ°á»ng trong BCTN/BCTC."
        lines += [
            f"CHá»ˆ TIÃŠU TÃ€I CHÃNH: {label}",
            f"- CÃ¡c sá»‘ liá»‡u gáº§n nháº¥t trong báº£ng: {data_text}.",
            principle,
        ]
        return "\n".join(lines)

    lines += ["Dá»® LIá»†U DÃ’NG ÄANG CHá»ŒN:", "\n".join([f"- {k}: {_fmt_note_value(v)}" for k, v in rowd.items()])]
    return "\n".join(lines)


def _render_explainable_table(df: pd.DataFrame, table_kind: str, company=None, annual_df: pd.DataFrame | None = None, quarterly_df: pd.DataFrame | None = None, height: int = 380) -> None:
    if df is None or df.empty:
        st.info("ChÆ°a cÃ³ dá»¯ liá»‡u.")
        return
    display_df = df.copy()
    notes = [_build_module1_note(row, table_kind, company=company, annual_df=annual_df, quarterly_df=quarterly_df) for _, row in display_df.iterrows()]
    table_id = "m1tbl_" + str(abs(hash((table_kind, tuple(display_df.columns), len(display_df), "V23.32-fix-note-mos"))))[:10]
    headers = "".join(f"<th>{html.escape(str(c))}</th>" for c in display_df.columns)
    rows_html = []
    for i, (_, row) in enumerate(display_df.iterrows()):
        tds = []
        for c in display_df.columns:
            val = row.get(c)
            text = _fmt_note_value(val)
            num = _parse_display_number(val)
            cls = _signal_class(val) if c in {"TÃ­n hiá»‡u", "Má»©c Ä‘á»™", "TÃ¬nh tráº¡ng", "Khuyáº¿n nghá»‹", "Káº¿t luáº­n", "Káº¿t luáº­n theo mÃ£", "Moat level", "Äá»™ tin cáº­y", "ÄÃ¡nh giÃ¡ sÆ¡ bá»™", "Loáº¡i lá»£i tháº¿"} else ""
            if not cls and num is not None and c not in {"Ká»³", "period", "NhÃ³m / chá»‰ tiÃªu", "NhÃ³m tiÃªu chÃ­", "TÃ­n hiá»‡u", "Má»©c Ä‘á»™", "Ná»™i dung", "Diá»…n giáº£i", "PhÆ°Æ¡ng phÃ¡p", "CÆ¡ sá»Ÿ tÃ­nh", "Nguá»“n Ä‘Ã¡nh giÃ¡", "TÃ¬nh huá»‘ng"}:
                cls = "pos" if num > 0 else "neg" if num < 0 else ""
            tds.append(f"<td class='{cls}'>{html.escape(text)}</td>")
        rows_html.append(f"<tr data-note='{html.escape(json.dumps(notes[i], ensure_ascii=False), quote=True)}'>{''.join(tds)}</tr>")
    full_table = table_kind == "mos_valuation"
    wrap_css = "max-height:none; overflow-x:auto; overflow-y:visible;" if full_table else f"max-height:{height}px; overflow:auto;"
    component_height = min(max(280 + 38 * (len(display_df) + 1), 520), 1800) if full_table else min(max(height + 240, 430), 980)
    html_doc = f"""
    <div class='hint'>ðŸ’¡ Nháº¥p má»™t láº§n vÃ o dÃ²ng/chá»‰ tiÃªu Ä‘á»ƒ xem cÃ¡ch tÃ­nh, sá»‘ liá»‡u vÃ  nguyÃªn táº¯c Ä‘Ã¡nh giÃ¡.</div>
    <div class='wrap'>
      <table id='{table_id}'>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    <div id='{table_id}_note' class='note'>ChÆ°a chá»n chá»‰ tiÃªu. HÃ£y nháº¥p má»™t láº§n vÃ o má»™t dÃ²ng trong báº£ng.</div>
    <script>
      const table = document.getElementById('{table_id}');
      const note = document.getElementById('{table_id}_note');
      if (table && note) {{
        table.querySelectorAll('tbody tr').forEach(function(row) {{
          row.addEventListener('click', function() {{
            table.querySelectorAll('tbody tr').forEach(function(r) {{ r.classList.remove('selected'); }});
            row.classList.add('selected');
            let raw = row.getAttribute('data-note') || '""';
            let msg = '';
            try {{ msg = JSON.parse(raw); }} catch(e) {{ msg = raw; }}
            note.innerText = msg;
          }});
        }});
      }}
    </script>
    <style>
      .hint {{font-size:13px; color:#0B7F75; margin: 2px 0 8px 0; font-weight:600;}}
      .wrap {{{wrap_css} border:1px solid rgba(11,127,117,.22); border-radius:14px;}}
      table {{border-collapse:collapse; width:100%; font-family: system-ui, -apple-system, Segoe UI, sans-serif; font-size:13px;}}
      th {{position: sticky; top:0; background:#EAF7F1; color:#123D3A; text-align:left; border-bottom:1px solid rgba(11,127,117,.22); padding:8px; z-index:8; font-weight:950; box-shadow:0 2px 0 rgba(11,127,117,.18);}}
      td {{border-bottom:1px solid #edf2f7; padding:7px 8px; vertical-align:top; color:#123D3A;}}
      tr:hover td {{background:#F7FBF8; cursor:pointer;}}
      tr.selected td {{background:#FEF3C7 !important;}}
      td.pos {{background:rgba(16,185,129,.12); color:#064e3b; font-weight:600;}}
      td.neg {{background:rgba(239,68,68,.12); color:#7f1d1d; font-weight:600;}}
      td.sig-red-strong {{background:#FECACA !important; color:#7F1D1D !important; font-weight:900; border-left:5px solid #DC2626;}}
      td.sig-red {{background:#FEE2E2 !important; color:#991B1B !important; font-weight:800; border-left:4px solid #EF4444;}}
      td.sig-purple-strong {{background:#E9D5FF !important; color:#581C87 !important; font-weight:900; border-left:5px solid #7E22CE;}}
      td.sig-purple {{background:#F3E8FF !important; color:#6B21A8 !important; font-weight:800; border-left:4px solid #A855F7;}}
      td.sig-yellow {{background:#FEF3C7 !important; color:#92400E !important; font-weight:800; border-left:4px solid #F59E0B;}}
      .critical-note-label {{color:#B91C1C !important; font-weight:950 !important;}}
      .note {{white-space:pre-wrap; margin-top:10px; padding:13px 15px; border-radius:14px; background:#FFF7E6; border:1px solid rgba(245,178,27,.52); color:#5f3b00; font-size:13px; line-height:1.48;}}
    </style>
    """
    components.html(html_doc, height=component_height, scrolling=not full_table)


def _recent_median_m1(df: pd.DataFrame, col: str, n: int = 5) -> float | None:
    if df is None or df.empty or col not in df.columns:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna().tail(n)
    return float(vals.median()) if not vals.empty else None


def _build_roic_investment_comment(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "ChÆ°a Ä‘á»§ dá»¯ liá»‡u Ä‘á»ƒ nháº­n xÃ©t ROIC & Ä‘áº§u tÆ°."
    latest = _latest_record(df)
    roic = _recent_median_m1(df, "roic_operating_profit_pct") or _recent_median_m1(df, "roic_standard_pct") or _recent_median_m1(df, "roic_pct")
    wacc = _recent_median_m1(df, "wacc_pct")
    spread = (roic - wacc) if roic is not None and wacc is not None else None
    deployed = _parse_display_number(latest.get("deployed_capital_bil")) or _parse_display_number(latest.get("avg_deployed_capital_bil"))
    total_inv = _parse_display_number(latest.get("total_investment_bil"))
    capex = _parse_display_number(latest.get("capex_bil"))
    expansion = _parse_display_number(latest.get("expansion_investment_bil"))
    cfo_np = _recent_median_m1(df, "cfo_to_net_profit")
    fcf_np = _recent_median_m1(df, "fcf_to_net_profit")
    if roic is None:
        signal = "ChÆ°a Ä‘á»§ dá»¯ liá»‡u ROIC nhiá»u ká»³ Ä‘á»ƒ káº¿t luáº­n kháº£ nÄƒng táº¡o giÃ¡ trá»‹ trÃªn vá»‘n."
    elif wacc is not None and spread is not None and spread > 5:
        signal = "ROIC Ä‘ang cao hÆ¡n WACC vá»›i spread khÃ¡ tá»‘t; Ä‘Ã¢y lÃ  tÃ­n hiá»‡u táº¡o giÃ¡ trá»‹ náº¿u dÃ²ng tiá»n vÃ  chu ká»³ ngÃ nh xÃ¡c nháº­n."
    elif wacc is not None and spread is not None and spread >= 0:
        signal = "ROIC chá»‰ vá»«a cao hÆ¡n WACC; cáº§n kiá»ƒm tra cháº¥t lÆ°á»£ng dÃ²ng tiá»n, capex vÃ  kháº£ nÄƒng tÃ¡i Ä‘áº§u tÆ° trÆ°á»›c khi tráº£ premium."
    elif wacc is not None:
        signal = "ROIC tháº¥p hÆ¡n WACC; Ä‘áº§u tÆ° má»Ÿ rá»™ng cÃ³ rá»§i ro phÃ¡ há»§y giÃ¡ trá»‹ náº¿u khÃ´ng cáº£i thiá»‡n lá»£i nhuáº­n/vÃ²ng quay vá»‘n."
    else:
        signal = "CÃ³ ROIC nhÆ°ng thiáº¿u WACC Ä‘á»ƒ so spread; cáº§n kiá»ƒm tra láº¡i chi phÃ­ vá»‘n vÃ  rá»§i ro ngÃ nh."
    return (
        f"{signal} Sá»‘ liá»‡u dÃ¹ng Ä‘á»ƒ Ä‘á»c: ROIC trung vá»‹ {_fmt_note_value(roic)}%, WACC trung vá»‹ {_fmt_note_value(wacc)}%, "
        f"spread ROIC-WACC {_fmt_note_value(spread)} Ä‘iá»ƒm %, deployed capital ká»³ má»›i nháº¥t {_fmt_note_value(deployed)} tá»·, "
        f"capex ká»³ má»›i nháº¥t {_fmt_note_value(capex)} tá»·, Ä‘áº§u tÆ° má»Ÿ rá»™ng {_fmt_note_value(expansion)} tá»·, tá»•ng Ä‘áº§u tÆ° {_fmt_note_value(total_inv)} tá»·, "
        f"CFO/LNST trung vá»‹ {_fmt_note_value(cfo_np)} láº§n, FCF/LNST trung vá»‹ {_fmt_note_value(fcf_np)} láº§n. "
        "CÃ¡ch Ä‘á»c: ROIC cao chá»‰ cÃ³ Ã½ nghÄ©a khi cao hÆ¡n WACC nhiá»u ká»³, vá»‘n Ä‘áº§u tÆ° tÄƒng nhÆ°ng khÃ´ng kÃ©o ROIC xuá»‘ng máº¡nh, vÃ  CFO/FCF xÃ¡c nháº­n lá»£i nhuáº­n káº¿ toÃ¡n chuyá»ƒn thÃ nh tiá»n."
    )



def _build_dupont_comment(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "ChÆ°a Ä‘á»§ dá»¯ liá»‡u Ä‘á»ƒ nháº­n xÃ©t DuPont."
    latest = _latest_record(df)
    roe = _recent_median_m1(df, "roe_actual_pct") or _recent_median_m1(df, "roe_pct") or _recent_median_m1(df, "roe_dupont_pct")
    roa = _recent_median_m1(df, "roa_actual_pct") or _recent_median_m1(df, "roa_pct")
    net_margin = _recent_median_m1(df, "net_margin_pct")
    gross_margin = _recent_median_m1(df, "gross_margin_pct")
    turnover = _recent_median_m1(df, "asset_turnover")
    multiplier = _recent_median_m1(df, "equity_multiplier")
    latest_roe = _parse_display_number(latest.get("roe_actual_pct")) or _parse_display_number(latest.get("roe_pct"))
    latest_margin = _parse_display_number(latest.get("net_margin_pct"))
    latest_turnover = _parse_display_number(latest.get("asset_turnover"))
    latest_multiplier = _parse_display_number(latest.get("equity_multiplier"))
    comments: list[str] = []
    if roe is None:
        comments.append("ChÆ°a Ä‘á»§ chuá»—i ROE Ä‘á»ƒ káº¿t luáº­n cháº¥t lÆ°á»£ng sinh lá»i theo DuPont.")
    elif roe >= 18:
        comments.append("ROE trung vá»‹ Ä‘ang á»Ÿ má»©c cao; cáº§n xÃ¡c Ä‘á»‹nh ROE Ä‘áº¿n tá»« biÃªn lá»£i nhuáº­n/vÃ²ng quay tÃ i sáº£n hay do Ä‘Ã²n báº©y tÃ i chÃ­nh.")
    elif roe >= 12:
        comments.append("ROE trung vá»‹ á»Ÿ má»©c khÃ¡; nÃªn Æ°u tiÃªn kiá»ƒm tra xu hÆ°á»›ng biÃªn lá»£i nhuáº­n vÃ  hiá»‡u quáº£ sá»­ dá»¥ng tÃ i sáº£n.")
    else:
        comments.append("ROE trung vá»‹ chÆ°a cao; cáº§n kiá»ƒm tra doanh nghiá»‡p cÃ³ bá»‹ suy giáº£m biÃªn lá»£i nhuáº­n, vÃ²ng quay tÃ i sáº£n tháº¥p hoáº·c vá»‘n chá»§ tÄƒng nhÆ°ng lá»£i nhuáº­n khÃ´ng theo ká»‹p hay khÃ´ng.")
    if multiplier is not None and multiplier >= 3.0 and roe is not None and roe >= 12:
        comments.append("Má»™t pháº§n ROE cÃ³ thá»ƒ Ä‘áº¿n tá»« Ä‘Ã²n báº©y; cáº§n Ä‘á»c cÃ¹ng ná»£ vay, chi phÃ­ lÃ£i vay vÃ  kháº£ nÄƒng chuyá»ƒn lá»£i nhuáº­n thÃ nh CFO/FCF.")
    elif turnover is not None and turnover >= 1.0 and net_margin is not None and net_margin >= 10:
        comments.append("ROE cÃ³ dáº¥u hiá»‡u Ä‘Æ°á»£c há»— trá»£ bá»Ÿi cáº£ biÃªn lá»£i nhuáº­n vÃ  vÃ²ng quay tÃ i sáº£n, Ä‘Ã¢y lÃ  cáº¥u trÃºc cháº¥t lÆ°á»£ng hÆ¡n so vá»›i ROE chá»‰ nhá» Ä‘Ã²n báº©y.")
    elif net_margin is not None and net_margin < 5:
        comments.append("BiÃªn lá»£i nhuáº­n rÃ²ng má»ng; ROE dá»… nháº¡y cáº£m vá»›i biáº¿n Ä‘á»™ng giÃ¡ bÃ¡n, chi phÃ­ Ä‘áº§u vÃ o vÃ  chi phÃ­ tÃ i chÃ­nh.")
    return (
        " ".join(comments) + " "
        f"Sá»‘ liá»‡u Ä‘á»c nhanh: ROE trung vá»‹ {_fmt_note_value(roe)}%, ROA trung vá»‹ {_fmt_note_value(roa)}%, "
        f"biÃªn gá»™p trung vá»‹ {_fmt_note_value(gross_margin)}%, biÃªn rÃ²ng trung vá»‹ {_fmt_note_value(net_margin)}%, "
        f"vÃ²ng quay tÃ i sáº£n trung vá»‹ {_fmt_note_value(turnover)} láº§n, há»‡ sá»‘ nhÃ¢n vá»‘n chá»§ trung vá»‹ {_fmt_note_value(multiplier)} láº§n. "
        f"Ká»³ má»›i nháº¥t: ROE {_fmt_note_value(latest_roe)}%, biÃªn rÃ²ng {_fmt_note_value(latest_margin)}%, "
        f"vÃ²ng quay tÃ i sáº£n {_fmt_note_value(latest_turnover)} láº§n, há»‡ sá»‘ nhÃ¢n vá»‘n chá»§ {_fmt_note_value(latest_multiplier)} láº§n. "
        "CÃ¡ch Ä‘á»c: DuPont tá»‘t khi ROE cao Ä‘áº¿n tá»« biÃªn lá»£i nhuáº­n bá»n vá»¯ng vÃ  vÃ²ng quay tÃ i sáº£n tá»‘t, khÃ´ng phá»¥ thuá»™c quÃ¡ nhiá»u vÃ o Ä‘Ã²n báº©y."
    )

def _render_scorecard_radar(scorecard: pd.DataFrame, title: str, name: str = "Äiá»ƒm nhiá»‡t") -> None:
    """Render radar/spider chart for Tá»•ng quan doanh nghiá»‡p scorecards using 'Tá»· lá»‡ Ä‘áº¡t' heat score."""
    if scorecard is None or scorecard.empty or "NhÃ³m tiÃªu chÃ­" not in scorecard.columns:
        st.info("ChÆ°a Ä‘á»§ dá»¯ liá»‡u Ä‘á»ƒ váº½ biá»ƒu Ä‘á»“ máº¡ng nhá»‡n.")
        return
    chart_df = scorecard.copy()
    if "Tá»· lá»‡ Ä‘áº¡t" in chart_df.columns:
        chart_df["Äiá»ƒm nhiá»‡t"] = pd.to_numeric(chart_df["Tá»· lá»‡ Ä‘áº¡t"], errors="coerce")
    elif {"Äiá»ƒm", "Trá»ng sá»‘"}.issubset(chart_df.columns):
        score = pd.to_numeric(chart_df["Äiá»ƒm"], errors="coerce")
        weight = pd.to_numeric(chart_df["Trá»ng sá»‘"], errors="coerce").replace(0, pd.NA)
        chart_df["Äiá»ƒm nhiá»‡t"] = score / weight * 100
    else:
        st.info("Báº£ng chÆ°a cÃ³ cá»™t Tá»· lá»‡ Ä‘áº¡t hoáº·c Äiá»ƒm/Trá»ng sá»‘ Ä‘á»ƒ váº½ máº¡ng nhá»‡n.")
        return
    chart_df["Äiá»ƒm nhiá»‡t"] = pd.to_numeric(chart_df["Äiá»ƒm nhiá»‡t"], errors="coerce").fillna(0).clip(0, 100)
    labels = chart_df["NhÃ³m tiÃªu chÃ­"].astype(str).tolist()
    values = chart_df["Äiá»ƒm nhiá»‡t"].astype(float).tolist()
    custom = []
    for _, row in chart_df.iterrows():
        custom.append(
            f"{row.get('NhÃ³m tiÃªu chÃ­','')}<br>Äiá»ƒm nhiá»‡t: {row.get('Äiá»ƒm nhiá»‡t',0):.1f}/100"
            f"<br>Äiá»ƒm Ä‘áº¡t: {row.get('Äiá»ƒm','N/A')}/{row.get('Trá»ng sá»‘','N/A')}"
            f"<br>TÃ­n hiá»‡u: {row.get('TÃ­n hiá»‡u','N/A')}"
        )
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + values[:1],
        theta=labels + labels[:1],
        fill="toself",
        name=name,
        text=custom + custom[:1],
        hovertemplate="%{text}<extra></extra>",
    ))
    fig.update_layout(
        title=title,
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10))),
        showlegend=False,
        height=500,
        margin=dict(l=45, r=45, t=68, b=42),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Biá»ƒu Ä‘á»“ dÃ¹ng cá»™t 'Tá»· lá»‡ Ä‘áº¡t' cá»§a báº£ng Ä‘Ã¡nh giÃ¡, quy Ä‘á»•i vá» thang 0-100 Ä‘á»ƒ nhÃ¬n nhanh Ä‘iá»ƒm máº¡nh/yáº¿u theo tá»«ng nhÃ³m tiÃªu chÃ­.")


def _scorecard_important_comment(scorecard: pd.DataFrame, label: str = "bá»™ tiÃªu chÃ­") -> str:
    """Generate a concise important comment from scorecard rows, not a generic note."""
    if scorecard is None or scorecard.empty:
        return f"ChÆ°a Ä‘á»§ dá»¯ liá»‡u Ä‘á»ƒ Ä‘Æ°a ra nháº­n xÃ©t quan trá»ng cho {label}."
    df = scorecard.copy()
    if "Tá»· lá»‡ Ä‘áº¡t" in df.columns:
        heat = pd.to_numeric(df["Tá»· lá»‡ Ä‘áº¡t"], errors="coerce")
    elif {"Äiá»ƒm", "Trá»ng sá»‘"}.issubset(df.columns):
        heat = pd.to_numeric(df["Äiá»ƒm"], errors="coerce") / pd.to_numeric(df["Trá»ng sá»‘"], errors="coerce").replace(0, pd.NA) * 100
    else:
        heat = pd.Series(float("nan"), index=df.index)
    df["_heat"] = heat
    # Tá»•ng Ä‘iá»ƒm náº¿u cÃ³ dÃ²ng tá»•ng, náº¿u khÃ´ng láº¥y bÃ¬nh quÃ¢n cÃ³ trá»ng sá»‘ tÆ°Æ¡ng Ä‘á»‘i.
    total_rows = df[df.get("NhÃ³m tiÃªu chÃ­", pd.Series(dtype=str)).astype(str).str.contains("Tá»”NG ÄIá»‚M|TONG DIEM", case=False, na=False)]
    if not total_rows.empty:
        total = float(pd.to_numeric(total_rows.iloc[-1].get("_heat"), errors="coerce"))
        total_signal = str(total_rows.iloc[-1].get("TÃ­n hiá»‡u", ""))
    else:
        total = float(pd.to_numeric(df["_heat"], errors="coerce").dropna().mean()) if pd.to_numeric(df["_heat"], errors="coerce").notna().any() else float("nan")
        total_signal = "Tá»‘t" if total >= 75 else "Theo dÃµi" if total >= 50 else "Cáº£nh bÃ¡o"
    detail_rows = df[~df.get("NhÃ³m tiÃªu chÃ­", pd.Series(dtype=str)).astype(str).str.contains("Tá»”NG ÄIá»‚M|TONG DIEM", case=False, na=False)].copy()
    strengths = detail_rows.sort_values("_heat", ascending=False).head(2)
    weaknesses = detail_rows.sort_values("_heat", ascending=True).head(2)
    def fmt_rows(rows):
        out = []
        for _, r in rows.iterrows():
            name = str(r.get("NhÃ³m tiÃªu chÃ­", "")).strip()
            val = r.get("_heat")
            sig = str(r.get("TÃ­n hiá»‡u", "")).strip()
            try:
                out.append(f"{name} {float(val):.1f}/100 ({sig})")
            except Exception:
                out.append(f"{name} ({sig})")
        return "; ".join([x for x in out if x.strip()])
    total_txt = "N/A" if pd.isna(total) else f"{total:.1f}/100"
    if total >= 75:
        lead = f"{label} Ä‘ang á»Ÿ tráº¡ng thÃ¡i tá»‘t: tá»•ng Ä‘iá»ƒm {total_txt}, tÃ­n hiá»‡u {total_signal}."
    elif total >= 50:
        lead = f"{label} á»Ÿ má»©c theo dÃµi: tá»•ng Ä‘iá»ƒm {total_txt}, chÆ°a Ä‘á»§ máº¡nh Ä‘á»ƒ káº¿t luáº­n cháº¥t lÆ°á»£ng bá»n vá»¯ng náº¿u cÃ¡c nhÃ³m yáº¿u khÃ´ng cáº£i thiá»‡n."
    else:
        lead = f"{label} phÃ¡t tÃ­n hiá»‡u cáº£nh bÃ¡o: tá»•ng Ä‘iá»ƒm {total_txt}; cáº§n kiá»ƒm tra ká»¹ cháº¥t lÆ°á»£ng lá»£i nhuáº­n, dÃ²ng tiá»n vÃ  rá»§i ro vá»‘n."
    strong_txt = fmt_rows(strengths)
    weak_txt = fmt_rows(weaknesses)
    return lead + (f" Äiá»ƒm máº¡nh ná»•i báº­t: {strong_txt}." if strong_txt else "") + (f" Äiá»ƒm yáº¿u cáº§n kiá»ƒm tra: {weak_txt}." if weak_txt else "")

def _format_company_overview_for_display(company) -> pd.DataFrame:
    """Human-readable company overview table for the Data tab."""
    rows = [
        {"Chá»‰ tiÃªu": "MÃ£ cá»• phiáº¿u", "GiÃ¡ trá»‹": company.ticker},
        {"Chá»‰ tiÃªu": "TÃªn cÃ´ng ty", "GiÃ¡ trá»‹": company.company_name},
        {"Chá»‰ tiÃªu": "SÃ n", "GiÃ¡ trá»‹": company.exchange or "N/A"},
        {"Chá»‰ tiÃªu": "NgÃ nh", "GiÃ¡ trá»‹": _display_industry_value(company.industry)},
        {"Chá»‰ tiÃªu": "PhÃ¢n ngÃ nh", "GiÃ¡ trá»‹": _display_industry_value(company.sub_industry)},
        {"Chá»‰ tiÃªu": "Vá»‘n hÃ³a", "GiÃ¡ trá»‹": "" if company.market_cap_bil is None else f"{company.market_cap_bil:,.0f} tá»· Ä‘á»“ng"},
        {"Chá»‰ tiÃªu": "Sá»‘ lÆ°á»£ng cá»• phiáº¿u lÆ°u hÃ nh", "GiÃ¡ trá»‹": "" if company.shares_outstanding_mil is None else f"{company.shares_outstanding_mil:,.0f} triá»‡u cp"},
        {"Chá»‰ tiÃªu": "GiÃ¡ hiá»‡n táº¡i", "GiÃ¡ trá»‹": "" if company.current_price is None else f"{company.current_price:,.0f} Ä‘á»“ng/cp"},
        {"Chá»‰ tiÃªu": "EPS", "GiÃ¡ trá»‹": "" if company.eps is None else f"{company.eps:,.0f} Ä‘á»“ng/cp"},
        {"Chá»‰ tiÃªu": "P/E", "GiÃ¡ trá»‹": "" if company.pe is None else f"{company.pe:,.1f} láº§n"},
        {"Chá»‰ tiÃªu": "P/B", "GiÃ¡ trá»‹": "" if company.pb is None else f"{company.pb:,.1f} láº§n"},
        {"Chá»‰ tiÃªu": "P/S", "GiÃ¡ trá»‹": "" if company.ps is None else f"{company.ps:,.1f} láº§n"},
        {"Chá»‰ tiÃªu": "ROE", "GiÃ¡ trá»‹": "" if company.roe is None else f"{company.roe:,.1f}%"},
        {"Chá»‰ tiÃªu": "ROA", "GiÃ¡ trá»‹": "" if company.roa is None else f"{company.roa:,.1f}%"},
        {"Chá»‰ tiÃªu": "ROIC", "GiÃ¡ trá»‹": "" if company.roic is None else f"{company.roic:,.1f}%"},
        {"Chá»‰ tiÃªu": "Cáº­p nháº­t", "GiÃ¡ trá»‹": _safe_public_text(company.updated_at or "N/A")},
    ]
    return pd.DataFrame(rows)

def render_line_chart(title: str, df: pd.DataFrame, columns: list[str], unit: str = "", help_text: str = "") -> None:
    if help_text:
        st.caption(help_text)
    _plot(make_line_fig(df, columns, title=title, unit=unit, subtitle=help_text))


def _has_meaningful_overview(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    row = df.iloc[0]
    useful_cols = ["company_name", "exchange", "industry", "market_cap_bil", "current_price", "eps", "pe", "roe"]
    count = 0
    for col in useful_cols:
        val = row.get(col) if col in row.index else None
        if pd.notna(val) and str(val).strip() not in {"", "nan", "None", "N/A"}:
            count += 1
    return count >= 3


def _result_has_dashboard_data(result: ProviderResult) -> bool:
    # A single placeholder row with only ticker/company_name is not enough; it creates the DGC - nan issue.
    if isinstance(result.annual, pd.DataFrame) and len(result.annual) >= 2:
        return True
    if isinstance(result.quarterly, pd.DataFrame) and len(result.quarterly) >= 2:
        return True
    return _has_meaningful_overview(result.overview)

def _active_bundle_has_data_for_ticker(ticker: str) -> bool:
    ticker = _safe_ticker(ticker)
    active = _safe_ticker(str(st.session_state.get("active_ticker", "")))
    paths = [st.session_state.get("active_overview_csv"), st.session_state.get("active_year_csv"), st.session_state.get("active_quarter_csv")]
    return bool(active == ticker and all(p and Path(str(p)).exists() for p in paths))


def _result_score(result: ProviderResult) -> int:
    score = 0
    if isinstance(result.overview, pd.DataFrame) and _has_meaningful_overview(result.overview):
        score += 5
    if isinstance(result.annual, pd.DataFrame):
        score += min(len(result.annual), 10) * 10
    if isinstance(result.quarterly, pd.DataFrame):
        score += min(len(result.quarterly), 20) * 5
    return score


def _safe_ticker(ticker: str) -> str:
    return "".join(ch for ch in ticker.upper().strip() if ch.isalnum())[:10]


def _empty_timeseries_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")


def _minimal_overview(ticker: str, source_name: str) -> pd.DataFrame:
    return normalize_columns(
        pd.DataFrame([
            {
                "ticker": ticker.upper(),
                "company_name": f"{ticker.upper()} - Ä‘ang cáº­p nháº­t há»“ sÆ¡ doanh nghiá»‡p",
                "exchange": "",
                "industry": "",
                "sub_industry": "",
                "updated_at": f"Crawler {source_name} {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}",
            }
        ]),
        MODULE1_OVERVIEW_COLUMNS,
    )


def _write_df(df: pd.DataFrame, path: Path, fallback_columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(df, pd.DataFrame) or df.empty:
        pd.DataFrame(columns=fallback_columns).to_csv(path, index=False, encoding="utf-8-sig")
        return 0
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return len(df)


def _fallback_same_ticker(current_path: str | None, ticker: str) -> pd.DataFrame:
    if not current_path:
        return pd.DataFrame()
    path = Path(current_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if "ticker" in df.columns:
        df = df[df["ticker"].astype(str).str.upper() == ticker.upper()]
    return df


def _export_provider_result_to_cache(result: ProviderResult, ticker: str, source_name: str) -> tuple[Path, Path, Path, dict[str, int]]:
    """Save normalized data and make it immediately usable by dashboard.

    V14 writes a complete dashboard bundle every time: overview, annual and quarterly CSV files.
    If a public crawler only returns partial data, the missing slices are filled from the current same-ticker
    dashboard data when available; otherwise an empty schema file is written so the dashboard will not break.
    """
    ticker = _safe_ticker(ticker)
    out_dir = DATA_CACHE_DIR / source_name.lower().replace(" ", "_").replace("+", "plus") / ticker
    overview_path = out_dir / "company_overview_sample.csv"
    year_path = out_dir / "financial_timeseries_year.csv"
    quarter_path = out_dir / "financial_timeseries_quarter.csv"

    overview_df = result.overview if isinstance(result.overview, pd.DataFrame) else pd.DataFrame()
    annual_df = result.annual if isinstance(result.annual, pd.DataFrame) else pd.DataFrame()
    quarterly_df = result.quarterly if isinstance(result.quarterly, pd.DataFrame) else pd.DataFrame()

    if overview_df.empty:
        same_ticker_overview = _fallback_same_ticker(st.session_state.get("active_overview_csv"), ticker)
        overview_df = same_ticker_overview if not same_ticker_overview.empty else _minimal_overview(ticker, source_name)
    if annual_df.empty:
        annual_df = _fallback_same_ticker(st.session_state.get("active_year_csv"), ticker)
    if quarterly_df.empty:
        quarterly_df = _fallback_same_ticker(st.session_state.get("active_quarter_csv"), ticker)

    counts = {
        "overview": _write_df(normalize_columns(overview_df, MODULE1_OVERVIEW_COLUMNS), overview_path, MODULE1_OVERVIEW_COLUMNS),
        "annual": _write_df(normalize_columns(annual_df, MODULE1_TIMESERIES_COLUMNS), year_path, MODULE1_TIMESERIES_COLUMNS),
        "quarterly": _write_df(normalize_columns(quarterly_df, MODULE1_TIMESERIES_COLUMNS), quarter_path, MODULE1_TIMESERIES_COLUMNS),
    }
    return overview_path, year_path, quarter_path, counts


def _activate_data_source(overview_csv: Path, year_csv: Path, quarter_csv: Path, label: str, ticker: str) -> None:
    ticker = _safe_ticker(ticker)
    st.session_state["active_ticker"] = ticker
    st.session_state["module1_ticker"] = ticker
    st.session_state["module2_ticker"] = ticker
    st.session_state["shared_ticker"] = ticker
    st.session_state["active_overview_csv"] = str(overview_csv)
    st.session_state["active_year_csv"] = str(year_csv)
    st.session_state["active_quarter_csv"] = str(quarter_csv)
    st.session_state["active_source_label"] = label
    st.session_state["module_sync_status"] = f"ÄÃ£ Ä‘á»“ng bá»™ {ticker} vÃ o Tá»•ng quan doanh nghiá»‡p + Äá»‹nh giÃ¡ chuyÃªn sÃ¢u lÃºc {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}"
    _load_overview_cached.clear()
    _load_timeseries_cached.clear()


def _load_active_or_default(default_ticker: str = "DCM") -> tuple[Path, Path, Path, str, str]:
    active_ticker = st.session_state.get("active_ticker")
    paths = [st.session_state.get("active_overview_csv"), st.session_state.get("active_year_csv"), st.session_state.get("active_quarter_csv")]
    if active_ticker and all(p and Path(p).exists() for p in paths):
        return Path(paths[0]), Path(paths[1]), Path(paths[2]), st.session_state.get("active_source_label", "Dá»¯ liá»‡u Ä‘ang hoáº¡t Ä‘á»™ng"), active_ticker

    ticker = _safe_ticker(default_ticker) or "DCM"
    if BUNDLED_XLSM.exists():
        overview, year, quarter, label = _export_bundled_financial_cached(str(BUNDLED_XLSM), ticker, str(DATA_CACHE_DIR))
        _activate_data_source(Path(overview), Path(year), Path(quarter), label, ticker)
        return Path(overview), Path(year), Path(quarter), label, ticker

    _activate_data_source(DEFAULT_OVERVIEW_CSV, DEFAULT_YEAR_CSV, DEFAULT_QUARTER_CSV, "Dá»¯ liá»‡u máº«u", ticker)
    return DEFAULT_OVERVIEW_CSV, DEFAULT_YEAR_CSV, DEFAULT_QUARTER_CSV, "Dá»¯ liá»‡u máº«u", ticker


def _merge_provider_results(results: list[tuple[str, ProviderResult]], ticker: str) -> ProviderResult:
    overview = pd.DataFrame()
    annual = pd.DataFrame()
    quarterly = pd.DataFrame()
    notes: list[str] = []
    raw_paths: list[str] = []

    # Prefer the source that returns the largest valid slice for each dataframe.
    for source_name, result in results:
        notes.append(f"provider_{len(notes)+1}: overview={len(result.overview)}, year={len(result.annual)}, quarter={len(result.quarterly)}")
        if result.raw_path:
            raw_paths.append(str(result.raw_path))
        if isinstance(result.overview, pd.DataFrame) and len(result.overview) > len(overview):
            overview = result.overview
        if isinstance(result.annual, pd.DataFrame) and len(result.annual) > len(annual):
            annual = result.annual
        if isinstance(result.quarterly, pd.DataFrame) and len(result.quarterly) > len(quarterly):
            quarterly = result.quarterly

    raw_manifest = _save_search_manifest(ticker, "both_sources", {"sources": notes, "raw_paths": raw_paths})
    return ProviderResult(overview=overview, annual=annual, quarterly=quarterly, raw_path=raw_manifest, note=" | ".join(notes))


def _save_search_manifest(ticker: str, source_key: str, payload: dict) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"search_{source_key}_{ticker.upper()}_{pd.Timestamp.now():%Y%m%d_%H%M%S}.json"
    path.write_text(pd.Series(payload).to_json(force_ascii=False, indent=2), encoding="utf-8")
    return path


def _fetch_source(ticker: str, source: str) -> tuple[ProviderResult, str]:
    ticker = _safe_ticker(ticker)
    if source == "FireAnt":
        return PublicFireAntCrawler(RAW_DIR).fetch(ticker), "fireant"
    if source == "Vietstock":
        return PublicVietstockCrawler(RAW_DIR).fetch(ticker), "vietstock"
    if source == "FireAnt + Vietstock":
        collected: list[tuple[str, ProviderResult]] = []
        errors: list[str] = []
        for label, crawler in [("FireAnt", PublicFireAntCrawler(RAW_DIR)), ("Vietstock", PublicVietstockCrawler(RAW_DIR))]:
            try:
                collected.append((label, crawler.fetch(ticker)))
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        if not collected:
            raw = _save_search_manifest(ticker, "both_errors", {"errors": errors})
            return ProviderResult(
                overview=pd.DataFrame(columns=MODULE1_OVERVIEW_COLUMNS),
                annual=pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS),
                quarterly=pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS),
                raw_path=raw,
                note=" | ".join(errors),
            ), "fireant_vietstock"
        merged = _merge_provider_results(collected, ticker)
        if errors:
            merged.note += " | " + " | ".join(errors)
        return merged, "fireant_vietstock"
    if source == "Financial tÃ­ch há»£p":
        if not BUNDLED_XLSM.exists():
            raise FileNotFoundError("KhÃ´ng tÃ¬m tháº¥y data_sources/Financial-v1.3.0.xlsm trong thÆ° má»¥c app.")
        return ExcelFinancialProvider(BUNDLED_XLSM).fetch(ticker), "financial_xlsm"
    raise ValueError(f"Cháº¿ Ä‘á»™ dá»¯ liá»‡u khÃ´ng há»£p lá»‡: {_safe_source_label(source)}")


def _fetch_fallback_sources(ticker: str, selected_source: str) -> list[tuple[str, str, ProviderResult]]:
    """Fallback chain used only when the selected preferred data mode cannot populate dashboard.

    The selected source is always tried first in _search_and_bind. If it returns only HTML/raw without usable
    tables, V18 khÃ´ng dÃ¹ng vnstock. Náº¿u cháº¿ Ä‘á»™ dá»¯ liá»‡u Æ°u tiÃªn khÃ´ng cÃ³ dá»¯ liá»‡u, chá»‰ thá»­ dá»¯ liá»‡u tÃ­ch há»£p náº¿u cÃ³ Ä‘Ãºng mÃ£.
    """
    fallbacks: list[tuple[str, str, ProviderResult]] = []
    # V14: khÃ´ng dÃ¹ng vnstock/TCBS/VCI fallback ná»¯a.
    # Chá»‰ fallback vá» dá»¯ liá»‡u tÃ­ch há»£p náº¿u file tháº­t sá»± cÃ³ dá»¯ liá»‡u cá»§a Ä‘Ãºng mÃ£.
    if BUNDLED_XLSM.exists():
        try:
            xlsm = ExcelFinancialProvider(BUNDLED_XLSM).fetch(ticker)
            if _result_has_dashboard_data(xlsm):
                fallbacks.append(("financial_xlsm", "Dá»¯ liá»‡u tÃ­ch há»£p dá»± phÃ²ng", xlsm))
        except Exception as exc:
            raw = _save_search_manifest(ticker, "financial_fallback_error", {"error": str(exc)})
            fallbacks.append(("financial_xlsm", "Dá»¯ liá»‡u tÃ­ch há»£p dá»± phÃ²ng lá»—i", ProviderResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), raw, str(exc))))
    return fallbacks


def _auto_update_module2_web_evidence(ticker: str, overview_df: pd.DataFrame | None = None) -> None:
    """Tá»± tÃ¬m vÃ  lÆ°u báº±ng chá»©ng internet cho Äá»‹nh giÃ¡ chuyÃªn sÃ¢u sau khi Tá»•ng quan doanh nghiá»‡p cáº­p nháº­t BCTC.

    Má»¥c tiÃªu: khi ngÆ°á»i dÃ¹ng tÃ¬m mÃ£ á»Ÿ Tá»•ng quan doanh nghiá»‡p, Äá»‹nh giÃ¡ chuyÃªn sÃ¢u Ä‘Ã£ cÃ³ sáºµn evidence table
    vá» BCTN/BCTC/moat/rá»§i ro/thá»‹ pháº§n mÃ  khÃ´ng cáº§n báº¥m thÃªm nÃºt riÃªng.
    """
    ticker = _safe_ticker(ticker)
    if not ticker:
        return
    company_name = ""
    try:
        if isinstance(overview_df, pd.DataFrame) and not overview_df.empty and "company_name" in overview_df.columns:
            first = overview_df.iloc[0].get("company_name", "")
            if pd.notna(first):
                company_name = str(first)
    except Exception:
        company_name = ""
    try:
        result = WebEvidenceAgent(RAW_DIR).search(ticker, company_name)
        st.session_state["module2_web_table"] = result.table
        st.session_state["module2_web_note"] = result.note
        st.session_state["module2_web_ticker"] = ticker
        st.session_state["module2_web_updated_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["module2_auto_update_status"] = (
            f"Äá»‹nh giÃ¡ chuyÃªn sÃ¢u Ä‘Ã£ tá»± cáº­p nháº­t báº±ng chá»©ng Ä‘á»‹nh tÃ­nh cho {ticker} lÃºc {st.session_state['module2_web_updated_at']}"
        )
    except Exception as exc:
        st.session_state["module2_auto_update_status"] = f"KhÃ´ng tá»± cáº­p nháº­t Ä‘Æ°á»£c báº±ng chá»©ng Ä‘á»‹nh tÃ­nh cho {ticker}: {_safe_source_label(exc)}"


def _search_and_bind(ticker: str, source: str) -> None:
    ticker = _safe_ticker(ticker)
    if not ticker:
        st.error("Vui lÃ²ng nháº­p mÃ£ cá»• phiáº¿u.")
        return
    with st.spinner(f"Äang tÃ¬m kiáº¿m {ticker} vÃ  liÃªn káº¿t dá»¯ liá»‡u vÃ o dashboard..."):
        diagnostics: list[str] = []
        try:
            result, source_key = _fetch_source(ticker, source)
            raw_note = f" Raw: {result.raw_path}" if result.raw_path else ""
            diagnostics.append(f"Cháº¿ Ä‘á»™ dá»¯ liá»‡u: score={_result_score(result)}, overview={len(result.overview)}, nÄƒm={len(result.annual)}, quÃ½={len(result.quarterly)}.")

            final_result = result
            final_source_key = source_key
            final_label_source = source
            used_fallback = False

            if not _result_has_dashboard_data(result):
                for fb_key, fb_label, fb_result in _fetch_fallback_sources(ticker, source):
                    diagnostics.append(f"{fb_label}: score={_result_score(fb_result)}, overview={len(fb_result.overview)}, nÄƒm={len(fb_result.annual)}, quÃ½={len(fb_result.quarterly)}. {fb_result.note}")
                    if _result_has_dashboard_data(fb_result) and _result_score(fb_result) > _result_score(final_result):
                        final_result = fb_result
                        final_source_key = fb_key
                        final_label_source = f"{source} khÃ´ng tráº£ báº£ng chuáº©n â†’ {fb_label}"
                        used_fallback = True
                        break

            if not _result_has_dashboard_data(final_result):
                diag_path = _save_search_manifest(ticker, "search_diagnostics", {"ticker": ticker, "source": source, "diagnostics": diagnostics, "raw": str(result.raw_path) if result.raw_path else ""})
                st.session_state["last_search_message"] = (
                    f"ÄÃ£ cháº¡y cáº­p nháº­t nhÆ°ng chÆ°a láº¥y Ä‘Æ°á»£c báº£ng tÃ i chÃ­nh Ä‘á»§ Ä‘á»ƒ cáº­p nháº­t dashboard. "
                    f"Chi tiáº¿t ká»¹ thuáº­t Ä‘Ã£ Ä‘Æ°á»£c lÆ°u trong nháº­t kÃ½ ná»™i bá»™ Ä‘á»ƒ kiá»ƒm tra sau."
                )
                st.warning(st.session_state["last_search_message"])
                return

            overview_csv, year_csv, quarter_csv, counts = _export_provider_result_to_cache(final_result, ticker, final_source_key)
            label = f"Dá»¯ liá»‡u cáº­p nháº­t | {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}"
            _activate_data_source(overview_csv, year_csv, quarter_csv, label, ticker)
            _auto_update_module2_web_evidence(ticker, final_result.overview)
            detail = " ÄÃ£ dÃ¹ng fallback public vÃ¬ nguá»“n Ä‘Ã£ chá»n khÃ´ng tráº£ dá»¯ liá»‡u tÃ i chÃ­nh chuáº©n." if used_fallback else ""
            st.session_state["last_search_message"] = (
                f"ÄÃ£ tÃ¬m kiáº¿m {ticker} tá»« {source} vÃ  tá»± liÃªn káº¿t vÃ o dashboard. "
                f"Tá»•ng quan: {counts['overview']} dÃ²ng, NÄƒm: {counts['annual']} dÃ²ng, QuÃ½: {counts['quarterly']} dÃ²ng.{detail}{raw_note}"
            )
            st.session_state["last_search_diagnostics"] = diagnostics
            st.success(st.session_state["last_search_message"])
            st.rerun()
        except Exception as exc:
            _save_search_manifest(ticker, "search_exception", {"ticker": ticker, "source": source, "error": str(exc), "diagnostics": diagnostics})
            st.session_state["last_search_message"] = f"Lá»—i khi tÃ¬m kiáº¿m {ticker}: {_safe_source_label(exc)}. Chi tiáº¿t Ä‘Ã£ lÆ°u trong nháº­t kÃ½ ná»™i bá»™."
            st.error(st.session_state["last_search_message"])




def _render_tre_sidebar_nav() -> None:
    """Manual branded navigation so the technical root page name 'app' is never shown."""
    st.markdown("### Äiá»u hÆ°á»›ng")
    st.page_link("app.py", label="Tá»•ng quan doanh nghiá»‡p", icon="ðŸ“Š")
    st.page_link("pages/02_Dinh_gia_Porter_Moat.py", label="Äá»‹nh giÃ¡ chuyÃªn sÃ¢u", icon="ðŸ§ ")
    st.page_link("pages/03_So_sanh_doanh_nghiep.py", label="So sÃ¡nh doanh nghiá»‡p", icon="âš–ï¸")
    st.page_link("pages/04_Bao_cao_tong_hop.py", label="BÃ¡o cÃ¡o tá»•ng há»£p toÃ n bá»™ ná»™i dung", icon="ðŸ“„")
    st.divider()


def _render_search_panel() -> tuple[int, int]:
    with st.sidebar:
        _render_tre_sidebar_nav()
        st.header("ðŸ”Ž TÃ¬m kiáº¿m dá»¯ liá»‡u")
        st.markdown(
            """
            <div class='workflow-card'>
            <b>Luá»“ng dá»¯ liá»‡u</b><br>
            1) Nháº­p mÃ£ cá»• phiáº¿u á»Ÿ Tá»•ng quan doanh nghiá»‡p hoáº·c Äá»‹nh giÃ¡ chuyÃªn sÃ¢u<br>
            2) App tá»± cháº¡y pipeline Tá»•ng quan doanh nghiá»‡p Ä‘á»ƒ láº¥y/chuáº©n hÃ³a BCTC<br>
            3) CÃ¹ng bá»™ cache Ä‘Æ°á»£c dÃ¹ng ngay cho pháº§n Ä‘á»‹nh giÃ¡/moat.
            </div>
            """,
            unsafe_allow_html=True,
        )
        default_ticker = st.session_state.get("shared_ticker", st.session_state.get("module2_ticker", st.session_state.get("last_query_ticker", st.session_state.get("active_ticker", "DCM"))))
        ticker = st.text_input("MÃ£ cá»• phiáº¿u", value=default_ticker, max_chars=10, key="module1_input_ticker").upper().strip()
        source_display = st.selectbox("Cháº¿ Ä‘á»™ dá»¯ liá»‡u", SOURCE_OPTIONS, index=0, key="module1_source")
        source = _to_internal_source(source_display)
        mos_canonical = _prepare_mos_widget("module1_mos_widget")
        st.selectbox(
            "Má»©c MOS yÃªu cáº§u (%)",
            MOS_OPTIONS_GLOBAL,
            index=MOS_OPTIONS_GLOBAL.index(mos_canonical),
            key="module1_mos_widget",
            on_change=_commit_mos_widget,
            args=("module1_mos_widget",),
            help="MOS dÃ¹ng chung toÃ n app: chá»n á»Ÿ Tá»•ng quan doanh nghiá»‡p sáº½ tá»± Ä‘á»“ng bá»™ sang Äá»‹nh giÃ¡ chuyÃªn sÃ¢u vÃ  ngÆ°á»£c láº¡i.",
        )
        if st.session_state.get("mos_sync_status"):
            st.caption(st.session_state["mos_sync_status"])
        auto_sync = st.checkbox("Tá»± Ä‘á»™ng táº£i & Ä‘á»“ng bá»™ khi Ä‘á»•i mÃ£", value=True, help="Khi nháº­p Ä‘á»§ mÃ£ cá»• phiáº¿u, app tá»± gá»i pipeline Tá»•ng quan doanh nghiá»‡p vÃ  cáº­p nháº­t dá»¯ liá»‡u dÃ¹ng chung cho Äá»‹nh giÃ¡ chuyÃªn sÃ¢u.")
        submitted = st.button("ðŸ”Ž TÃ¬m kiáº¿m & cáº­p nháº­t dashboard", use_container_width=True)

        safe = _safe_ticker(ticker)
        attempt_key = f"{safe}|{source}"
        if submitted:
            st.session_state["last_query_ticker"] = safe
            st.session_state["last_query_source"] = source
            st.session_state["_last_auto_sync_attempt"] = attempt_key
            _search_and_bind(ticker, source)
        elif auto_sync and len(safe) >= 3 and not _active_bundle_has_data_for_ticker(safe) and st.session_state.get("_last_auto_sync_attempt") != attempt_key:
            st.session_state["last_query_ticker"] = safe
            st.session_state["last_query_source"] = source
            st.session_state["_last_auto_sync_attempt"] = attempt_key
            _search_and_bind(ticker, source)

        if st.session_state.get("module_sync_status"):
            st.success(st.session_state["module_sync_status"])
        if st.session_state.get("module2_auto_update_status"):
            st.info(st.session_state["module2_auto_update_status"])

        st.divider()
        limit_years = st.slider("Sá»‘ nÄƒm hiá»ƒn thá»‹", 5, 10, 10)
        limit_quarters = st.slider("Sá»‘ quÃ½ hiá»ƒn thá»‹", 4, 20, 20)

        st.markdown(
            """
            <div class='source-card'>
            Dá»¯ liá»‡u sau khi cáº­p nháº­t sáº½ Ä‘Æ°á»£c kÃ­ch hoáº¡t thÃ nh bá»™ dá»¯ liá»‡u chung cho cáº£ Tá»•ng quan doanh nghiá»‡p vÃ  Äá»‹nh giÃ¡ chuyÃªn sÃ¢u.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.get("last_search_message"):
            st.caption(_safe_source_label(st.session_state["last_search_message"]))
    return limit_years, limit_quarters

def render_dashboard() -> None:
    _inject_runtime_ui_css()
    # V23.33: logo chuyá»ƒn ra page, khÃ´ng Ä‘áº·t trong sidebar Ä‘á»ƒ trÃ¡nh bá»‹ áº©n khi sidebar thu gá»n.
    _render_brand_page_header(
        "ðŸ“Š Tá»•ng quan doanh nghiá»‡p",
        "Trecapital dashboard â€“ tá»± Ä‘á»“ng bá»™ dá»¯ liá»‡u sang Äá»‹nh giÃ¡ chuyÃªn sÃ¢u.",
    )

    limit_years, limit_quarters = _render_search_panel()
    overview_csv, year_csv, quarter_csv, source_label, active_ticker = _load_active_or_default("DCM")

    try:
        company = _load_overview_cached(str(overview_csv), active_ticker)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    annual_df_raw = _load_timeseries_cached(str(year_csv), active_ticker, "Y", limit_years)
    quarterly_df = _load_timeseries_cached(str(quarter_csv), active_ticker, "Q", limit_quarters)
    # V22: for the annual view, append a TTM/T12M row calculated from the latest four quarters.
    annual_df = append_ttm_row(annual_df_raw, quarterly_df)
    # V23.20: WACC Ä‘Æ°á»£c tÃ­nh tá»± Ä‘á»™ng trong ensure_derived_metrics/append_ttm_row; khÃ´ng dÃ¹ng WACC tham chiáº¿u sidebar.

    metrics = build_metric_dict(company)
    valuation_df = build_mos_valuation_table(company, annual_df, mos_rate=float(st.session_state.get("target_mos_pct", 50)) / 100)
    ratio_scorecard_for_summary = build_financial_ratio_scorecard(annual_df) if annual_df is not None and not annual_df.empty else pd.DataFrame()
    flags = build_flags(company, annual_df=annual_df, quarterly_df=quarterly_df)
    summary = build_quick_summary(company, annual_df=annual_df)
    value_investing_summary = build_value_investing_assessment(company, annual_df, ratio_scorecard_for_summary) if annual_df is not None and not annual_df.empty else "ChÆ°a Ä‘á»§ dá»¯ liá»‡u nÄƒm Ä‘á»ƒ tá»•ng há»£p nháº­n xÃ©t theo triáº¿t lÃ½ Ä‘áº§u tÆ° giÃ¡ trá»‹."
    mos_detailed_summary = build_mos_detailed_summary(valuation_df)

    st.markdown(
        f"""
        <div class='workflow-card'>
        <b>Dashboard Ä‘ang hiá»ƒn thá»‹ mÃ£:</b> {company.ticker} &nbsp; | &nbsp;
        <b>MÃ£ Ä‘ang phÃ¢n tÃ­ch:</b> {company.ticker}<br>
        <span class='small-muted'>Muá»‘n Ä‘á»•i mÃ£ hoáº·c cháº¿ Ä‘á»™ dá»¯ liá»‡u, dÃ¹ng khung TÃ¬m kiáº¿m á»Ÿ sidebar rá»“i báº¥m TÃ¬m kiáº¿m & cáº­p nháº­t dashboard.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_ticker_title_inline(company, metrics["GiÃ¡ hiá»‡n táº¡i"], metrics["Cáº­p nháº­t"])
    if "Demo" in str(company.updated_at):
        st.warning(_safe_public_text(company.updated_at))

    row1 = st.columns(4)
    for col, label in zip(row1, ["Vá»‘n hÃ³a", "Cá»• phiáº¿u lÆ°u hÃ nh", "EPS", "P/E"]):
        with col:
            _render_compact_metric(label, metrics[label])

    row2 = st.columns(6)
    for col, label in zip(row2, ["P/B", "P/S", "ROE", "ROA", "ROIC", "SÃ n"]):
        with col:
            _render_compact_metric(label, metrics[label])

    # V23.39: Ä‘Ã£ bá» nÃºt/khung xuáº¥t bÃ¡o cÃ¡o trong tá»«ng pháº§n; chá»‰ cÃ²n trang BÃ¡o cÃ¡o tá»•ng há»£p toÃ n bá»™ ná»™i dung á»Ÿ sidebar.

    if not annual_df.empty:
        with st.container(border=True):
            st.subheader("KPI ká»³ gáº§n nháº¥t tá»« chuá»—i tÃ i chÃ­nh")
            cards = latest_metric_cards(annual_df)
            cols = st.columns(6)
            for idx, key in enumerate(["Ká»³ dá»¯ liá»‡u", "Doanh thu", "LNST", "CFO", "FCF", "Owner Earnings"]):
                with cols[idx]:
                    _render_compact_metric(key, cards.get(key, "N/A"))
            cols2 = st.columns(8)
            for col, key, label in [
                (cols2[0], "ROE", "ROE"),
                (cols2[1], "ROE thá»±c táº¿", "ROE tá»± tÃ­nh"),
                (cols2[2], "ROIC", "ROIC chuáº©n"),
                (cols2[3], "ROIC Operating Profit", "ROIC OP MOS"),
                (cols2[4], "ROIC Owner Earnings", "ROIC OE MOS"),
                (cols2[5], "Deployed Capital", "Deployed Capital"),
                (cols2[6], "EPS", "EPS"),
                (cols2[7], "OEPS", "OEPS"),
            ]:
                with col:
                    _render_compact_metric(label, cards.get(key, "N/A"))

    tab_overview, tab_fincharts, tab_fcf, tab_ratios, tab_dupont, tab_roic, tab_data = st.tabs([
        "TÃ³m táº¯t", "Biá»ƒu Ä‘á»“ tÃ i chÃ­nh", "FCF & dÃ²ng tiá»n", "PhÃ¢n tÃ­ch chá»‰ sá»‘ TC", "DuPont", "ROIC & Ä‘áº§u tÆ°", "Dá»¯ liá»‡u"
    ])

    with tab_overview:
        with st.container(border=True):
            st.subheader("TÃ³m táº¯t nhanh tÃ¬nh tráº¡ng doanh nghiá»‡p")
            _render_important_red("Tá»•ng quan nhanh", summary)
            _render_important_red("Nháº­n xÃ©t tá»± Ä‘á»™ng theo triáº¿t lÃ½ Ä‘áº§u tÆ° giÃ¡ trá»‹", value_investing_summary)
            _render_important_red("Äá»‹nh giÃ¡ MOS chi tiáº¿t", mos_detailed_summary)
        with st.container(border=True):
            st.subheader("Káº¿t quáº£ Ä‘á»‹nh giÃ¡ MOS")
            if valuation_df.empty:
                st.info("ChÆ°a Ä‘á»§ dá»¯ liá»‡u Ä‘á»ƒ tÃ­nh giÃ¡ MOS.")
            else:
                _render_explainable_table(valuation_df, "mos_valuation", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=330)
        with st.container(border=True):
            st.subheader("Cáº£nh bÃ¡o / Ä‘iá»ƒm cáº§n kiá»ƒm tra")
            combined = build_combined_assessment_table(company, annual_df, quarterly_df, valuation_df)
            _render_explainable_table(combined, "combined_alerts", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=430)

    with tab_fincharts:
        chart_year_tab, chart_quarter_tab = st.tabs(["NÄƒm + TTM", "20 quÃ½"])
        with chart_year_tab:
            if annual_df.empty:
                st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u nÄƒm cho mÃ£ nÃ y. Vui lÃ²ng báº¥m TÃ¬m kiáº¿m & cáº­p nháº­t dashboard hoáº·c Ä‘á»•i cháº¿ Ä‘á»™ dá»¯ liá»‡u.")
            else:
                render_line_chart("Doanh thu vÃ  lá»£i nhuáº­n nÄƒm + TTM", annual_df, ["revenue_bil", "net_profit_bil"], "tá»· Ä‘á»“ng", "RÃª chuá»™t vÃ o tá»«ng Ä‘iá»ƒm Ä‘á»ƒ xem sá»‘ liá»‡u.")
                render_line_chart("CFO, Free Cash Flow, Owner Earnings nÄƒm + TTM", annual_df, ["cfo_bil", "free_cash_flow_bil", "owner_earnings_bil"], "tá»· Ä‘á»“ng", "So sÃ¡nh cháº¥t lÆ°á»£ng dÃ²ng tiá»n vÃ  lá»£i nhuáº­n chá»§ sá»Ÿ há»¯u.")
                render_line_chart("Tá»· suáº¥t cá»• tá»©c tiá»n máº·t thá»±c táº¿ theo nÄƒm", annual_df, ["cash_dividend_yield_pct"], "%", "CÃ´ng thá»©c: |cá»• tá»©c tiá»n máº·t Ä‘Ã£ tráº£ theo nÄƒm tÃ i chÃ­nh| / giÃ¡ cá»• phiáº¿u cuá»‘i nÄƒm. Náº¿u dá»¯ liá»‡u Ä‘áº§u vÃ o chÆ°a cÃ³ lá»‹ch sá»­ giÃ¡ cuá»‘i nÄƒm, chá»‰ tiÃªu sáº½ Ä‘á»ƒ trá»‘ng thay vÃ¬ dÃ¹ng sai giÃ¡ hiá»‡n táº¡i.")
                render_line_chart("ROE vÃ  ROE tá»± tÃ­nh nÄƒm + TTM", annual_df, ["roe_pct", "roe_actual_pct"], "%", "ROE tá»± tÃ­nh = LNST / VCSH bÃ¬nh quÃ¢n.")
                render_line_chart("ROIC Operating Profit vs WACC nÄƒm + TTM", annual_df, ["roic_operating_profit_pct", "wacc_pct"], "%", "Chá»‰ giá»¯ ROIC Operating Profit vÃ  WACC doanh nghiá»‡p tá»± tÃ­nh Ä‘á»ƒ so sÃ¡nh hiá»‡u quáº£ vá»‘n cá»‘t lÃµi vá»›i chi phÃ­ vá»‘n.")
                render_line_chart("EPS vÃ  OEPS nÄƒm + TTM", annual_df, ["eps_vnd", "oeps_vnd"], "Ä‘á»“ng/cp", "EPS káº¿ toÃ¡n vÃ  EPS theo Owner Earnings.")

        with chart_quarter_tab:
            if quarterly_df.empty:
                st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u quÃ½ cho mÃ£ nÃ y. App há»— trá»£ tá»‘i Ä‘a 20 quÃ½, nguá»“n cÃ³ bao nhiÃªu quÃ½ sáº½ hiá»ƒn thá»‹ báº¥y nhiÃªu.")
            else:
                render_line_chart("Doanh thu vÃ  lá»£i nhuáº­n theo quÃ½", quarterly_df, ["revenue_bil", "net_profit_bil"], "tá»· Ä‘á»“ng", "Thá»© tá»± quÃ½ Ä‘Ã£ Ä‘Æ°á»£c chuáº©n hÃ³a tÄƒng dáº§n.")
                render_line_chart("CFO, Free Cash Flow, Owner Earnings theo quÃ½", quarterly_df, ["cfo_bil", "free_cash_flow_bil", "owner_earnings_bil"], "tá»· Ä‘á»“ng", "RÃª chuá»™t Ä‘á»ƒ xem tá»«ng quÃ½.")
                render_line_chart("ROIC Operating Profit vs WACC theo quÃ½", quarterly_df, ["roic_operating_profit_pct", "wacc_pct"], "%", "Chá»‰ giá»¯ ROIC Operating Profit vÃ  WACC doanh nghiá»‡p tá»± tÃ­nh Ä‘á»ƒ so sÃ¡nh hiá»‡u quáº£ vá»‘n cá»‘t lÃµi vá»›i chi phÃ­ vá»‘n.")
                render_line_chart("EPS vÃ  OEPS theo quÃ½", quarterly_df, ["eps_vnd", "oeps_vnd"], "Ä‘á»“ng/cp", "EPS theo tá»«ng quÃ½; OEPS theo Owner Earnings.")

    with tab_fcf:
        st.markdown(
            """
            <div class='note-card'>
            <b>Tab FCF & dÃ²ng tiá»n</b> Ä‘Æ°á»£c xÃ¢y theo cáº¥u trÃºc sheet <b>FCF-Years</b> vÃ  <b>FCF-Quaters</b> trong file máº«u:
            phÃ¢n tÃ­ch quÃ¡ trÃ¬nh <b>LNTT â†’ Ä‘iá»u chá»‰nh phi tiá»n máº·t â†’ thay Ä‘á»•i vá»‘n lÆ°u Ä‘á»™ng â†’ Capex â†’ FCF</b>, sau Ä‘Ã³ xem doanh nghiá»‡p dÃ¹ng FCF cho tráº£ ná»£, cá»• tá»©c, Ä‘áº§u tÆ° vÃ  tÄƒng/giáº£m tiá»n + Ä‘áº§u tÆ° tÃ i chÃ­nh ngáº¯n háº¡n trong ká»³ nhÆ° tháº¿ nÃ o.
            </div>
            """,
            unsafe_allow_html=True,
        )
        fcf_year_tab, fcf_quarter_tab = st.tabs(["Theo nÄƒm", "Theo quÃ½"])
        with fcf_year_tab:
            if annual_df.empty:
                st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u FCF theo nÄƒm cho mÃ£ nÃ y.")
            else:
                _plot(make_fcf_generation_fig(annual_df, "FCF theo nÄƒm: LNTT â†’ FCF"))
                _plot(make_fcf_usage_fig(annual_df, "Sá»­ dá»¥ng dÃ²ng tiá»n theo nÄƒm"))
                _plot(make_fcf_conversion_fig(annual_df, "FCF Conversion theo nÄƒm"))
                st.subheader("Bá»™ tiÃªu chÃ­ Ä‘Ã¡nh giÃ¡ tá»± Ä‘á»™ng theo nÄƒm")
                cashflow_scorecard_year = build_cashflow_scorecard(annual_df)
                _render_important_red("Nháº­n xÃ©t quan trá»ng theo báº£ng Ä‘iá»ƒm FCF & dÃ²ng tiá»n", _scorecard_important_comment(cashflow_scorecard_year, "FCF & dÃ²ng tiá»n theo nÄƒm"))
                _render_scorecard_radar(cashflow_scorecard_year, "Biá»ƒu Ä‘á»“ máº¡ng nhá»‡n Ä‘Ã¡nh giÃ¡ FCF & dÃ²ng tiá»n theo nÄƒm", "FCF & dÃ²ng tiá»n")
                _render_explainable_table(cashflow_scorecard_year, "cashflow_scorecard_year", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=350)
                _render_explainable_table(build_cashflow_situation_alerts(annual_df), "cashflow_alerts_year", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=300)
                st.subheader("Báº£ng phÃ¢n tÃ­ch sá»­ dá»¥ng dÃ²ng tiá»n theo nÄƒm")
                _render_fcf_analysis_table(build_fcf_analysis_table(annual_df), "fcf_analysis_year")
        with fcf_quarter_tab:
            if quarterly_df.empty:
                st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u FCF theo quÃ½ cho mÃ£ nÃ y.")
            else:
                _plot(make_fcf_generation_fig(quarterly_df, "FCF theo quÃ½: LNTT â†’ FCF"))
                _plot(make_fcf_usage_fig(quarterly_df, "Sá»­ dá»¥ng dÃ²ng tiá»n theo quÃ½"))
                _plot(make_fcf_conversion_fig(quarterly_df, "FCF Conversion theo quÃ½"))
                st.subheader("Bá»™ tiÃªu chÃ­ Ä‘Ã¡nh giÃ¡ tá»± Ä‘á»™ng theo quÃ½")
                cashflow_scorecard_quarter = build_cashflow_scorecard(quarterly_df)
                _render_important_red("Nháº­n xÃ©t quan trá»ng theo báº£ng Ä‘iá»ƒm FCF & dÃ²ng tiá»n quÃ½", _scorecard_important_comment(cashflow_scorecard_quarter, "FCF & dÃ²ng tiá»n theo quÃ½"))
                _render_scorecard_radar(cashflow_scorecard_quarter, "Biá»ƒu Ä‘á»“ máº¡ng nhá»‡n Ä‘Ã¡nh giÃ¡ FCF & dÃ²ng tiá»n theo quÃ½", "FCF & dÃ²ng tiá»n quÃ½")
                _render_explainable_table(cashflow_scorecard_quarter, "cashflow_scorecard_quarter", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=350)
                _render_explainable_table(build_cashflow_situation_alerts(quarterly_df), "cashflow_alerts_quarter", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=300)
                st.subheader("Báº£ng phÃ¢n tÃ­ch sá»­ dá»¥ng dÃ²ng tiá»n theo quÃ½")
                _render_fcf_analysis_table(build_fcf_analysis_table(quarterly_df), "fcf_analysis_quarter")


    with tab_ratios:
        st.markdown(
            """
            <div class='note-card'>
            <b>Tab PhÃ¢n tÃ­ch chá»‰ sá»‘ TC</b> nÃ¢ng cáº¥p tá»« sheet <b>PHÃ‚N TÃCH CHá»ˆ Sá» TC</b>.
            App khÃ´ng bÃª nguyÃªn cÃ´ng thá»©c Excel náº¿u cÃ´ng thá»©c tham chiáº¿u lá»—i; thay vÃ o Ä‘Ã³ chuáº©n hÃ³a theo lÃ½ thuyáº¿t tÃ i chÃ­nh: tÄƒng trÆ°á»Ÿng, biÃªn lá»£i nhuáº­n, sinh lá»i trÃªn vá»‘n, hiá»‡u quáº£ vá»‘n lÆ°u Ä‘á»™ng, thanh khoáº£n/Ä‘Ã²n báº©y vÃ  Ä‘á»‹nh giÃ¡ sÆ¡ bá»™.
            ÄÃ¡nh giÃ¡ bÃ¡m triáº¿t lÃ½ Buffett/Graham/Li Lu/Howard Marks: nhÃ¬n cá»• phiáº¿u nhÆ° quyá»n sá»Ÿ há»¯u doanh nghiá»‡p, Æ°u tiÃªn dÃ²ng tiá»n tháº­t, lá»£i nhuáº­n trÃªn vá»‘n, báº£ng cÃ¢n Ä‘á»‘i an toÃ n vÃ  biÃªn an toÃ n khi mua.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if annual_df.empty:
            st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u chá»‰ sá»‘ tÃ i chÃ­nh theo nÄƒm cho mÃ£ nÃ y.")
        else:
            scorecard = ratio_scorecard_for_summary if not ratio_scorecard_for_summary.empty else build_financial_ratio_scorecard(annual_df)
            st.subheader("Nháº­n xÃ©t tá»± Ä‘á»™ng theo triáº¿t lÃ½ Ä‘áº§u tÆ° giÃ¡ trá»‹")
            _render_important_red("Nháº­n xÃ©t quan trá»ng theo chá»‰ sá»‘ tÃ i chÃ­nh", build_value_investing_assessment(company, annual_df, scorecard))
            st.subheader("Bá»™ tiÃªu chÃ­ Ä‘Ã¡nh giÃ¡ tá»± Ä‘á»™ng - 100 Ä‘iá»ƒm")
            _render_scorecard_radar(scorecard, "Biá»ƒu Ä‘á»“ máº¡ng nhá»‡n Ä‘Ã¡nh giÃ¡ phÃ¢n tÃ­ch chá»‰ sá»‘ tÃ i chÃ­nh", "Chá»‰ sá»‘ tÃ i chÃ­nh")
            _render_explainable_table(scorecard, "ratio_scorecard", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=360)
            st.subheader("Cáº£nh bÃ¡o/tÃ¬nh huá»‘ng chá»‰ sá»‘ tÃ i chÃ­nh")
            _render_explainable_table(build_financial_ratio_alerts(annual_df), "ratio_alerts", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=300)
            st.subheader("Báº£ng PHÃ‚N TÃCH CHá»ˆ Sá» TC theo nÄƒm")
            _render_explainable_table(build_financial_ratio_table(annual_df), "ratio_table_year", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=520)
        if not quarterly_df.empty:
            with st.expander("Xem thÃªm báº£ng chá»‰ sá»‘ tÃ i chÃ­nh theo quÃ½", expanded=False):
                _render_explainable_table(build_financial_ratio_table(quarterly_df), "ratio_table_quarter", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=520)

    with tab_dupont:
        source_df = annual_df if not annual_df.empty else quarterly_df
        if source_df.empty:
            st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u DuPont.")
        else:
            _render_important_red("Nháº­n xÃ©t quan trá»ng DuPont", _build_dupont_comment(source_df))
            _plot(make_dupont_profitability_fig(source_df))
            _plot(make_dupont_driver_fig(source_df))
            dup_cols = [c for c in ["period", "roe_pct", "roa_pct", "gross_margin_pct", "net_margin_pct", "asset_turnover", "equity_multiplier", "roe_actual_pct", "roe_dupont_pct"] if c in source_df.columns]
            _show_table(source_df[dup_cols])

    with tab_roic:
        source_df = annual_df if not annual_df.empty else quarterly_df
        if source_df.empty:
            st.warning("ChÆ°a cÃ³ dá»¯ liá»‡u ROIC/Ä‘áº§u tÆ°.")
        else:
            _plot(make_roic_investment_fig(source_df))
            st.caption("Biá»ƒu Ä‘á»“ chá»‰ hiá»ƒn thá»‹ ROIC Operating Profit vÃ  WACC doanh nghiá»‡p tá»± tÃ­nh. Náº¿u ROIC Operating Profit > WACC nhiá»u ká»³, doanh nghiá»‡p cÃ³ dáº¥u hiá»‡u táº¡o giÃ¡ trá»‹ trÃªn vá»‘n sá»­ dá»¥ng; váº«n cáº§n kiá»ƒm tra CFO/FCF vÃ  chu ká»³ ngÃ nh.")
            _render_important_red("Nháº­n xÃ©t quan trá»ng ROIC & Ä‘áº§u tÆ°", _build_roic_investment_comment(source_df))
            roic_cols = [c for c in ["period", "core_operating_profit_bil", "nopat_bil", "deployed_capital_bil", "avg_deployed_capital_bil", "interest_bearing_debt_bil", "avg_interest_bearing_debt_bil", "market_cap_bil", "equity_weight_pct", "debt_weight_pct", "cost_of_equity_pct", "cost_of_debt_pct", "after_tax_cost_of_debt_pct", "tax_rate_pct", "beta", "roic_operating_profit_pct", "wacc_pct", "wacc_quality", "expansion_investment_bil", "inventory_change_bil", "investment_subsidiary_bil", "total_investment_bil", "wacc_formula_detail"] if c in source_df.columns]
            _show_table(format_table_for_display(source_df[roic_cols]))

    with tab_data:
        st.subheader("Dá»¯ liá»‡u tá»•ng quan")
        _show_table(_format_company_overview_for_display(company))
        st.subheader("Dá»¯ liá»‡u nÄƒm + TTM")
        _show_table(format_table_for_display(annual_df))
        st.download_button("Táº£i CSV nÄƒm + TTM", annual_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"{company.ticker}_tong_quan_year.csv", mime="text/csv")
        st.subheader("Dá»¯ liá»‡u quÃ½")
        _show_table(format_table_for_display(quarterly_df))
        st.download_button("Táº£i CSV quÃ½", quarterly_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"{company.ticker}_tong_quan_quarter.csv", mime="text/csv")


if __name__ == "__main__":
    render_dashboard()

