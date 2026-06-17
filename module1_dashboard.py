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
    "2353": "Xây dựng & Vật liệu",
    "2350": "Xây dựng & Vật liệu",
    "2357": "Vật liệu xây dựng",
    "1353": "Hóa chất",
    "1357": "Hóa chất cơ bản/Phân bón",
    "1753": "Dịch vụ vận tải",
    "2777": "Hạ tầng giao thông & dịch vụ sân bay",
    "8355": "Ngân hàng",
    "8532": "Bảo hiểm",
    "9533": "Bất động sản",
}


def _display_industry_value(value: object) -> str:
    """Convert raw numeric industry codes to readable names so Tổng quan doanh nghiệp never shows only codes like 2353."""
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return "N/A"
    # Some data sources return ICB/industry code as 2353. Show the sector name, not the raw code alone.
    code_text = text[:-2] if re.fullmatch(r"\d{3,6}\.0", text) else text
    if re.fullmatch(r"\d{3,6}", code_text):
        return ICB_CODE_NAME_MAP.get(code_text, f"Chưa nhận diện tên ngành (mã {code_text})")
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
    "Tự động": "FireAnt + Vietstock",
    "Dữ liệu ưu tiên 1": "FireAnt",
    "Dữ liệu ưu tiên 2": "Vietstock",
    "Dữ liệu tích hợp": "Financial tích hợp",
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
        "FireAnt": "Dữ liệu ưu tiên 1",
        "Vietstock": "Dữ liệu ưu tiên 2",
        "Simplize": "Danh sách cùng ngành",
        "vnstock": "Dữ liệu trực tuyến",
        "KBS": "nhóm dữ liệu trực tuyến",
        "VCI": "nhóm dữ liệu trực tuyến",
        "Financial tích hợp": "Dữ liệu tích hợp",
        "CSV mẫu tích hợp": "Dữ liệu mẫu",
        "raw_data": "nhật ký nội bộ",
        "data_cache": "bộ nhớ dữ liệu",
    }
    for raw, public in replacements.items():
        text = text.replace(raw, public)
    text = re.sub(r"/?[^\s<>]*\.(?:csv|json|html|txt|xlsm|xlsx)", "file nội bộ", text, flags=re.I)
    text = re.sub(r"[A-Za-z]:\\[^\s<>]+", "đường dẫn nội bộ", text)
    text = re.sub(r"/(?:mnt|home|Users|raw_data|data_cache)[^\s<>]+", "đường dẫn nội bộ", text)
    return text

st.set_page_config(
    page_title="Tổng quan doanh nghiệp tích hợp V23.36",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1500px;}
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
    
    /* V23.20: robust global Streamlit tab styling for Tổng quan doanh nghiệp + Định giá chuyên sâu */
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
    /* V23.20: thu nhỏ các thẻ thống kê tổng quan xuống khoảng 40% để gọn dashboard */
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
    # Nếu MOS vừa đổi ở module khác, ép widget hiện tại theo canonical chung.
    # Nếu MOS vừa đổi ở chính widget này, callback _commit_mos_widget đã cập nhật canonical trước khi rerun.
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
    st.session_state["mos_sync_status"] = f"Đã đồng bộ MOS yêu cầu {canonical}% cho Tổng quan doanh nghiệp và Định giá chuyên sâu."


def _markdownish_to_html(text: object) -> str:
    raw = "" if text is None else str(text)
    # Normalize common markdown fragments from engine summaries into HTML so ** does not appear on screen.
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    escaped = html.escape(raw)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = escaped.replace("\n", "<br>")
    # Keep bullet-like output readable.
    escaped = escaped.replace("• ", "&bull; ").replace("- ", "&ndash; ")
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


# V23.20: card HTML nội tuyến để chắc chắn Tổng quan doanh nghiệp luôn nổi bật ticker và thu nhỏ KPI,
# không phụ thuộc CSS Streamlit bị cache/rerun.

def _safe_public_text(value: object) -> str:
    text = str(value or "")
    replacements = {
        "FireAnt": "Dữ liệu ưu tiên",
        "Vietstock": "Dữ liệu ưu tiên",
        "Simplize": "Danh sách cùng ngành",
        "Financial tích hợp": "Dữ liệu tích hợp",
        "CSV mẫu tích hợp": "Dữ liệu mẫu",
        "raw_data": "nhật ký nội bộ",
        "data_cache": "bộ nhớ dữ liệu",
    }
    for raw, public in replacements.items():
        text = text.replace(raw, public)
    text = re.sub(r"(?:Dữ liệu ưu tiên|Dữ liệu tích hợp|Dữ liệu mẫu|FireAnt|Vietstock|Simplize)?\s*(?:VBA\s+)?endpoints?\s*", "Dữ liệu cập nhật ", text, flags=re.I)
    text = re.sub(r"\bCrawler\s+[^0-9]*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", r"Dữ liệu cập nhật \1", text, flags=re.I)
    text = re.sub(r"https?://\S+", "liên kết nội bộ", text, flags=re.I)
    text = re.sub(r"[A-Za-z]:\\[^\s<>]+", "đường dẫn nội bộ", text)
    text = re.sub(r"/(?:mnt|home|Users|raw_data|data_cache)[^\s<>]+", "đường dẫn nội bộ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

def _render_ticker_title_inline(company, current_price: object = None, updated_at: object = None) -> None:
    ticker = html.escape(str(getattr(company, 'ticker', '') or 'N/A'))
    name = html.escape(str(getattr(company, 'company_name', '') or 'Đang cập nhật tên doanh nghiệp'))
    exchange = html.escape(str(getattr(company, 'exchange', '') or 'N/A'))
    industry = html.escape(_display_industry_value(getattr(company, 'industry', '')))
    sub_industry = html.escape(_display_industry_value(getattr(company, 'sub_industry', '')))
    if sub_industry == industry:
        industry_line = f"<b>Ngành:</b> {industry}"
    else:
        industry_line = f"<b>Ngành:</b> {industry} &nbsp; | &nbsp; <b>Phân ngành:</b> {sub_industry}"
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
             <div style="font-size:.86rem;line-height:1.05;color:#50646B;font-weight:900;text-transform:uppercase;letter-spacing:.03em;">Giá hiện tại</div>
             <div style="font-size:1.42rem;line-height:1.1;color:#064E47;font-weight:1000;">{price_text}</div>
             <div style="font-size:.94rem;color:#64748B;font-weight:720;">Cập nhật: {updated_text}</div>
          </div>
          <div style="font-size:1.22rem;color:#0B5F58;margin-top:7px;font-weight:780;"><b>Sàn:</b> {exchange} &nbsp; | &nbsp; {industry_line}</div>
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



# V23.20: CSS phải được inject trong render_dashboard(), không để ở top-level import.
# Lý do: Streamlit cache module Python; khi widget MOS làm rerun thì import không chạy lại,
# dẫn đến mất style tab và style nhận xét. Hàm này chạy ở mỗi lần render để style luôn còn.
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
        .main .block-container {padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 1540px !important;}
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


        /* Streamlit Tabs - dùng selector rộng cho nhiều version Streamlit/BaseWeb */
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

        /* Nhận xét/đánh giá/kết luận quan trọng */
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
        f"Dữ liệu tích hợp | Năm: {len(result.annual)} dòng | Quý: {len(result.quarterly)} dòng",
    )


def _badge(level: str) -> str:
    if level == "good":
        return "✅"
    if level == "risk":
        return "⚠️"
    return "🔎"


def _plot(fig, empty_message: str = "Chưa có dữ liệu để vẽ biểu đồ này.") -> None:
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
    if "lợi thế" in s or "moat" in s:
        if "rất mạnh" in s or "very strong" in s or "xuất sắc" in s:
            return "sig-purple-strong"
        if "mạnh" in s or "strong" in s:
            return "sig-purple"
        if "khá" in s or "good" in s:
            return "sig-yellow"
        if "bình" in s or "trung" in s or "normal" in s or "average" in s:
            return "sig-yellow"
        if "yếu" in s or "không" in s or "weak" in s or "no moat" in s:
            return "sig-red"
    if s in {"cao", "high"}:
        return "sig-purple-strong"
    if s in {"trung bình", "medium", "moderate"}:
        return "sig-yellow"
    if s in {"thấp", "low", "không có dữ liệu", "no data"}:
        return "sig-red"
    if any(k in s for k in ["cảnh báo", "rủi ro", "rủi ro chu kỳ", "yếu", "âm", "suy giảm", "không đạt", "chưa đạt", "không phù hợp", "thiếu dữ liệu", "không có dữ liệu", "chưa đủ", "chưa có", "lỗi", "đòn bẩy cao", "xấu"]):
        if any(k in s for k in ["nghiêm trọng", "rất", "không đạt", "chưa đạt", "rủi ro", "yếu", "xấu"]):
            return "sig-red-strong"
        return "sig-red"
    if any(k in s for k in ["tốt", "đạt", "mạnh", "an toàn", "hiệu quả", "tích cực", "vượt", "cao", "bền", "ổn định", "có runway", "runway", "pricing power", "có bằng chứng", "quality", "cash tốt", "tạo giá trị"]):
        if any(k in s for k in ["rất", "mạnh", "vượt", "tốt", "cao", "bền"]):
            return "sig-purple-strong"
        return "sig-purple"
    if any(k in s for k in ["theo dõi", "cần kiểm", "cần soi", "cần xác minh", "cần kiểm chứng", "cần bổ sung", "cần tìm", "cẩn trọng", "trung bình", "bình thường", "khá", "chưa rõ", "hạn chế", "gần vùng", "chờ", "kiểm chứng", "chưa kết luận"]):
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
        # Ordering matters: price/share values can contain a percent sign in names such as "Giá MOS 50%".
        if "eps" in name or "oeps" in name or "đ/cp" in name or "_vnd" in name or "vnd" in name or "giá" in name or "cplh" in name or "cổ phiếu" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if ("%" in name or "_pct" in name or "pct" in name or "tỷ lệ" in name or "margin" in name or "roe" in name or "roa" in name or "roic" in name or "growth" in name or "tăng trưởng" in name or "biên an toàn" in name or "wacc" in name):
            return lambda x: "" if pd.isna(x) else f"{x:,.1f}%"
        if "ngày" in name or "dso" in name or "dio" in name or "dpo" in name or "ccc" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if ("tỷ" in name or "_bil" in name or " bil" in name or "vốn hóa" in name or "assets" in name or "capital" in name or "cash" in name or "fcf" in name or "cfo" in name or "owner earnings" in name or "profit" in name or "lợi nhuận" in name or "doanh thu" in name or "nợ" in name or "vay" in name or "đầu tư" in name):
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if "_mil" in name or "triệu" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.0f}"
        if "ratio" in name or "/" in name or "turnover" in name or "coverage" in name or "multiplier" in name or "p/e" in name or "p/b" in name or "p/s" in name or "vòng quay" in name or "hệ số" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.1f}"
        if "điểm" in name or "trọng số" in name:
            return lambda x: "" if pd.isna(x) else f"{x:,.1f}"
        return lambda x: "" if pd.isna(x) else x

    formatters = {}
    for _col in display_df.columns:
        if pd.api.types.is_numeric_dtype(display_df[_col]):
            formatters[_col] = _display_formatter_for_col(_col)

    exclude_cols = {
        "Kỳ", "period", "ticker", "company_name", "exchange", "industry", "sub_industry", "updated_at",
        "Nhóm / chỉ tiêu", "Nhóm tiêu chí", "Tín hiệu", "Nhận xét tự động", "Tình huống", "Mức độ", "Diễn giải", "Phương pháp", "Cơ sở tính", "Nguồn đánh giá", "Nội dung"
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
            if col in {"Tín hiệu", "Mức độ", "Tình trạng", "Khuyến nghị", "Kết luận", "Kết luận theo mã", "Moat level", "Độ tin cậy", "Đánh giá sơ bộ", "Loại lợi thế"}:
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

    The reference title `Bảng PHÂN TÍCH CHỈ SỐ TC theo năm` is rendered by
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
        st.info("Chưa có dữ liệu.")
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
    period = latest.get("period") or latest.get("year") or "kỳ mới nhất/TTM"
    rev = latest.get("revenue_bil")
    np = latest.get("net_profit_bil")
    cfo = latest.get("cfo_bil")
    fcf = latest.get("free_cash_flow_bil")
    roe = latest.get("roe_actual_pct") or latest.get("roe_pct")
    roic = latest.get("roic_standard_pct") or latest.get("roic_pct")
    return "\n".join([
        f"Doanh nghiệp: {getattr(company, 'ticker', '')} - {getattr(company, 'company_name', '')}",
        f"Ngành/phân ngành: {_display_industry_value(getattr(company, 'industry', ''))} / {_display_industry_value(getattr(company, 'sub_industry', ''))}",
        f"Kỳ dữ liệu dùng để giải thích: {period}; giá hiện tại: {_fmt_note_value(getattr(company, 'current_price', None))} đ/cp.",
        f"Số liệu chính kỳ gần nhất: doanh thu {_fmt_note_value(rev)} tỷ, LNST {_fmt_note_value(np)} tỷ, CFO {_fmt_note_value(cfo)} tỷ, FCF {_fmt_note_value(fcf)} tỷ, ROE {_fmt_note_value(roe)}%, ROIC {_fmt_note_value(roic)}%.",
    ])


def _build_module1_note(row: pd.Series, table_kind: str, company=None, annual_df: pd.DataFrame | None = None, quarterly_df: pd.DataFrame | None = None) -> str:
    rowd = row.to_dict()
    ctx = _module1_company_context(company, annual_df) if company is not None else ""
    lines = [ctx, ""] if ctx else []

    if "Phương pháp" in rowd and "Giá trị nội tại (đ/cp)" in rowd:
        intrinsic = _parse_display_number(rowd.get("Giá trị nội tại (đ/cp)"))
        mos_col = "Giá MOS chọn (đ/cp)" if "Giá MOS chọn (đ/cp)" in rowd else "Giá MOS 50% (đ/cp)"
        _raw_mos_level = _parse_display_number(rowd.get("Mức MOS áp dụng (%)"))
        mos_level = st.session_state.get("target_mos_pct", 50) if _raw_mos_level is None else _raw_mos_level
        mos_price = _parse_display_number(rowd.get(mos_col))
        price = _parse_display_number(rowd.get("Giá hiện tại (đ/cp)"))
        margin = _parse_display_number(rowd.get("Biên an toàn hiện tại (%)"))
        lines += [
            f"PHƯƠNG PHÁP MOS: {rowd.get('Phương pháp', '')}",
            f"- Giá trị nội tại ước tính: {_fmt_note_value(intrinsic)} đ/cp.",
            f"- Giá mua theo MOS {float(mos_level):.0f}%: {_fmt_note_value(mos_price)} đ/cp.",
            f"- Giá hiện tại: {_fmt_note_value(price)} đ/cp; biên an toàn hiện tại: {_fmt_note_value(margin)}%.",
            f"- Tín hiệu: {rowd.get('Tín hiệu', 'N/A')}.",
            f"- Công thức/cơ sở tính: {rowd.get('Cơ sở tính', 'N/A')}.",
            f"- Diễn giải theo dữ liệu hiện tại: {rowd.get('Diễn giải', 'N/A')}.",
            f"Nguyên tắc: MOS không phải lệnh mua/bán. Đây là lớp bảo vệ khi ước tính giá trị có thể sai. Lần chạy này dùng MOS yêu cầu {float(mos_level):.0f}% do người dùng chọn; cần đọc cùng chất lượng lợi nhuận, dòng tiền, ROIC và bảng cân đối của chính doanh nghiệp.",
        ]
        return "\n".join(lines)

    if "Nguồn đánh giá" in rowd and "Mức độ" in rowd:
        src = str(rowd.get("Nguồn đánh giá", ""))
        principle = ""
        if "MOS" in src or "Định giá" in src:
            principle = "Nguyên tắc: định giá phải gắn với biên an toàn, không dùng một điểm fair value duy nhất. Kiểm tra lại giả định tăng trưởng, P/E mục tiêu và chất lượng dòng tiền."
        elif "FCF" in src or "dòng tiền" in src:
            principle = "Nguyên tắc: lợi nhuận kế toán phải được kiểm chứng bằng CFO/FCF/Owner Earnings; thay đổi vốn lưu động và capex có thể làm dòng tiền khác xa LNST."
        elif "Chỉ số" in src:
            principle = "Nguyên tắc: chỉ số tài chính được đọc theo cụm: tăng trưởng, biên lợi nhuận, ROE/ROIC, vốn lưu động, đòn bẩy và định giá; không kết luận chỉ từ một chỉ tiêu đơn lẻ."
        else:
            principle = "Nguyên tắc: đây là cảnh báo tự động để nhắc analyst kiểm tra thêm dữ liệu gốc và bối cảnh ngành trước khi kết luận."
        lines += [
            f"CẢNH BÁO/ĐIỂM CẦN KIỂM TRA: {rowd.get('Nội dung', '')}",
            f"- Nguồn đánh giá: {src}; mức độ: {rowd.get('Mức độ', 'N/A')}.",
            f"- Diễn giải cụ thể: {rowd.get('Diễn giải', 'N/A')}.",
            f"- Việc cần làm: đối chiếu lại BCTC/BCTN, xem chuỗi nhiều năm/quý và so với doanh nghiệp cùng ngành nếu có.",
            principle,
        ]
        return "\n".join(lines)

    if "Nhóm tiêu chí" in rowd and "Điểm" in rowd:
        group = str(rowd.get("Nhóm tiêu chí", ""))
        extra = ""
        if "Tăng trưởng" in group:
            extra = "Cách đọc: xem CAGR doanh thu, LNST, EPS; tăng trưởng tốt phải đi cùng biên lợi nhuận và dòng tiền, không chỉ tăng quy mô."
        elif "Biên" in group:
            extra = "Cách đọc: biên gộp/biên ròng ổn định cho thấy quyền định giá hoặc kiểm soát chi phí; biên giảm cần kiểm tra cạnh tranh, nguyên liệu, chi phí bán hàng."
        elif "Sinh lời" in group or "vốn" in group:
            extra = "Cách đọc: ROE/ROA/ROIC cho biết hiệu quả sử dụng vốn; ROIC cao cần được xác nhận bằng CFO/FCF và tính bền vững qua nhiều kỳ."
        elif "vốn lưu động" in group or "Hiệu quả" in group:
            extra = "Cách đọc: DSO/DIO/DPO/CCC và CFO/LNST cho biết tiền bị kẹt ở phải thu, tồn kho hay được tài trợ bởi phải trả/khách hàng."
        elif "Thanh khoản" in group or "Đòn bẩy" in group:
            extra = "Cách đọc: current ratio, quick ratio, nợ vay ròng/VCSH, interest coverage giúp đánh giá khả năng chịu đựng chu kỳ xấu."
        elif "Định giá" in group:
            extra = "Cách đọc: định giá rẻ chỉ có ý nghĩa khi chất lượng doanh nghiệp/dòng tiền/tài sản đủ tốt; tránh bẫy giá trị."
        else:
            extra = "Cách đọc: điểm số là checklist định hướng, không thay thế phân tích định tính và so sánh ngành."
        latest = _latest_record(annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame())
        ratio_context = []
        for k in ["revenue_growth_yoy_pct", "net_profit_growth_yoy_pct", "gross_margin_pct", "net_margin_pct", "roe_actual_pct", "roic_standard_pct", "roic_operating_profit_pct", "wacc_pct", "cfo_to_net_profit", "fcf_to_net_profit", "current_ratio", "quick_ratio", "net_debt_to_equity", "interest_coverage", "cash_conversion_cycle_days"]:
            if k in latest and str(latest.get(k)) not in {"", "nan", "None", "<NA>"}:
                suffix = "%" if any(x in k for x in ["pct", "margin", "roe", "roic", "wacc", "growth"]) else (" ngày" if "days" in k else " lần")
                ratio_context.append(f"{k}={_fmt_note_value(latest.get(k))}{suffix}")
        point = _parse_display_number(rowd.get('Điểm'))
        weight = _parse_display_number(rowd.get('Trọng số'))
        pct = (point / weight * 100) if point is not None and weight and abs(weight) > 1e-9 else _parse_display_number(rowd.get('Tỷ lệ đạt'))
        lines += [
            f"BỘ TIÊU CHÍ: {group}",
            f"- Trọng số: {_fmt_note_value(rowd.get('Trọng số'))}; điểm đạt: {_fmt_note_value(rowd.get('Điểm'))}; tỷ lệ đạt: {_fmt_note_value(pct)}%.",
            f"- Vì sao ra điểm này: điểm = tổng các điều kiện nhỏ trong nhóm. Tỷ lệ đạt = điểm/trọng số; nhóm được xếp Tốt nếu đạt khoảng ≥75%, Theo dõi nếu khoảng 50%-75%, Cảnh báo nếu thấp hơn hoặc có chỉ tiêu đỏ.",
            f"- Chỉ tiêu chính đang ảnh hưởng đến điểm: {'; '.join(ratio_context[:10]) if ratio_context else 'chưa đủ dữ liệu chỉ tiêu thành phần trong kỳ mới nhất.'}",
            f"- Tín hiệu: {rowd.get('Tín hiệu', 'N/A')}.",
            f"- Nhận xét tự động: {rowd.get('Nhận xét tự động', 'N/A')}.",
            extra,
        ]
        return "\n".join(lines)

    if "Tình huống" in rowd and "Mức độ" in rowd:
        lines += [
            f"TÌNH HUỐNG/CẢNH BÁO: {rowd.get('Tình huống', '')}",
            f"- Mức độ: {rowd.get('Mức độ', 'N/A')}.",
            f"- Diễn giải: {rowd.get('Diễn giải', 'N/A')}.",
            "Nguyên tắc: cảnh báo được kích hoạt từ dữ liệu thực tế kỳ gần nhất hoặc chuỗi nhiều kỳ. Cần kiểm tra nguyên nhân: chu kỳ ngành, sự kiện bất thường, chính sách kế toán, vốn lưu động, nợ vay hoặc thay đổi chiến lược.",
        ]
        return "\n".join(lines)

    if "Nhóm / chỉ tiêu" in rowd:
        label = str(rowd.get("Nhóm / chỉ tiêu", ""))
        latest_pairs = [(k, v) for k, v in rowd.items() if k != "Nhóm / chỉ tiêu" and str(v).strip() not in {"", "nan", "None"}]
        tail = latest_pairs[-4:]
        data_text = "; ".join([f"{k}: {v}" for k, v in tail]) if tail else "Chưa có số liệu."
        principle = ""
        if "ROIC" in label or "ROE" in label or "ROA" in label:
            principle = "Nguyên tắc: nhóm sinh lời trên vốn cho biết doanh nghiệp biến vốn thành lợi nhuận ra sao; cần xem xu hướng nhiều kỳ và chất lượng dòng tiền đi kèm."
        elif "CFO" in label or "FCF" in label or "Owner Earnings" in label or "OEPS" in label:
            principle = "Nguyên tắc: dòng tiền thật và Owner Earnings giúp kiểm tra lợi nhuận kế toán có chuyển thành tiền cho chủ sở hữu hay không."
        elif "DSO" in label or "DIO" in label or "DPO" in label or "CCC" in label or "vốn lưu động" in label:
            principle = "Nguyên tắc: vốn lưu động cho biết tiền bị hút vào phải thu/tồn kho hay được tài trợ bởi phải trả; tác động trực tiếp tới FCF."
        elif "Nợ" in label or "Debt" in label or "Coverage" in label or "Ratio" in label:
            principle = "Nguyên tắc: thanh khoản và đòn bẩy cho biết sức chịu đựng khi doanh thu/lợi nhuận suy giảm hoặc lãi suất tăng."
        elif "Tăng trưởng" in label:
            principle = "Nguyên tắc: tăng trưởng bền vững phải đi cùng biên lợi nhuận, ROIC và dòng tiền; tăng trưởng không chất lượng có thể phá hủy giá trị."
        else:
            principle = "Nguyên tắc: đọc chỉ tiêu theo xu hướng nhiều kỳ, so với ngành và đối chiếu sự kiện bất thường trong BCTN/BCTC."
        lines += [
            f"CHỈ TIÊU TÀI CHÍNH: {label}",
            f"- Các số liệu gần nhất trong bảng: {data_text}.",
            principle,
        ]
        return "\n".join(lines)

    lines += ["DỮ LIỆU DÒNG ĐANG CHỌN:", "\n".join([f"- {k}: {_fmt_note_value(v)}" for k, v in rowd.items()])]
    return "\n".join(lines)


def _render_explainable_table(df: pd.DataFrame, table_kind: str, company=None, annual_df: pd.DataFrame | None = None, quarterly_df: pd.DataFrame | None = None, height: int = 380) -> None:
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
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
            cls = _signal_class(val) if c in {"Tín hiệu", "Mức độ", "Tình trạng", "Khuyến nghị", "Kết luận", "Kết luận theo mã", "Moat level", "Độ tin cậy", "Đánh giá sơ bộ", "Loại lợi thế"} else ""
            if not cls and num is not None and c not in {"Kỳ", "period", "Nhóm / chỉ tiêu", "Nhóm tiêu chí", "Tín hiệu", "Mức độ", "Nội dung", "Diễn giải", "Phương pháp", "Cơ sở tính", "Nguồn đánh giá", "Tình huống"}:
                cls = "pos" if num > 0 else "neg" if num < 0 else ""
            tds.append(f"<td class='{cls}'>{html.escape(text)}</td>")
        rows_html.append(f"<tr data-note='{html.escape(json.dumps(notes[i], ensure_ascii=False), quote=True)}'>{''.join(tds)}</tr>")
    full_table = table_kind == "mos_valuation"
    wrap_css = "max-height:none; overflow-x:auto; overflow-y:visible;" if full_table else f"max-height:{height}px; overflow:auto;"
    component_height = min(max(280 + 38 * (len(display_df) + 1), 520), 1800) if full_table else min(max(height + 240, 430), 980)
    html_doc = f"""
    <div class='hint'>💡 Nhấp một lần vào dòng/chỉ tiêu để xem cách tính, số liệu và nguyên tắc đánh giá.</div>
    <div class='wrap'>
      <table id='{table_id}'>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    <div id='{table_id}_note' class='note'>Chưa chọn chỉ tiêu. Hãy nhấp một lần vào một dòng trong bảng.</div>
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
        return "Chưa đủ dữ liệu để nhận xét ROIC & đầu tư."
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
        signal = "Chưa đủ dữ liệu ROIC nhiều kỳ để kết luận khả năng tạo giá trị trên vốn."
    elif wacc is not None and spread is not None and spread > 5:
        signal = "ROIC đang cao hơn WACC với spread khá tốt; đây là tín hiệu tạo giá trị nếu dòng tiền và chu kỳ ngành xác nhận."
    elif wacc is not None and spread is not None and spread >= 0:
        signal = "ROIC chỉ vừa cao hơn WACC; cần kiểm tra chất lượng dòng tiền, capex và khả năng tái đầu tư trước khi trả premium."
    elif wacc is not None:
        signal = "ROIC thấp hơn WACC; đầu tư mở rộng có rủi ro phá hủy giá trị nếu không cải thiện lợi nhuận/vòng quay vốn."
    else:
        signal = "Có ROIC nhưng thiếu WACC để so spread; cần kiểm tra lại chi phí vốn và rủi ro ngành."
    return (
        f"{signal} Số liệu dùng để đọc: ROIC trung vị {_fmt_note_value(roic)}%, WACC trung vị {_fmt_note_value(wacc)}%, "
        f"spread ROIC-WACC {_fmt_note_value(spread)} điểm %, deployed capital kỳ mới nhất {_fmt_note_value(deployed)} tỷ, "
        f"capex kỳ mới nhất {_fmt_note_value(capex)} tỷ, đầu tư mở rộng {_fmt_note_value(expansion)} tỷ, tổng đầu tư {_fmt_note_value(total_inv)} tỷ, "
        f"CFO/LNST trung vị {_fmt_note_value(cfo_np)} lần, FCF/LNST trung vị {_fmt_note_value(fcf_np)} lần. "
        "Cách đọc: ROIC cao chỉ có ý nghĩa khi cao hơn WACC nhiều kỳ, vốn đầu tư tăng nhưng không kéo ROIC xuống mạnh, và CFO/FCF xác nhận lợi nhuận kế toán chuyển thành tiền."
    )



def _build_dupont_comment(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "Chưa đủ dữ liệu để nhận xét DuPont."
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
        comments.append("Chưa đủ chuỗi ROE để kết luận chất lượng sinh lời theo DuPont.")
    elif roe >= 18:
        comments.append("ROE trung vị đang ở mức cao; cần xác định ROE đến từ biên lợi nhuận/vòng quay tài sản hay do đòn bẩy tài chính.")
    elif roe >= 12:
        comments.append("ROE trung vị ở mức khá; nên ưu tiên kiểm tra xu hướng biên lợi nhuận và hiệu quả sử dụng tài sản.")
    else:
        comments.append("ROE trung vị chưa cao; cần kiểm tra doanh nghiệp có bị suy giảm biên lợi nhuận, vòng quay tài sản thấp hoặc vốn chủ tăng nhưng lợi nhuận không theo kịp hay không.")
    if multiplier is not None and multiplier >= 3.0 and roe is not None and roe >= 12:
        comments.append("Một phần ROE có thể đến từ đòn bẩy; cần đọc cùng nợ vay, chi phí lãi vay và khả năng chuyển lợi nhuận thành CFO/FCF.")
    elif turnover is not None and turnover >= 1.0 and net_margin is not None and net_margin >= 10:
        comments.append("ROE có dấu hiệu được hỗ trợ bởi cả biên lợi nhuận và vòng quay tài sản, đây là cấu trúc chất lượng hơn so với ROE chỉ nhờ đòn bẩy.")
    elif net_margin is not None and net_margin < 5:
        comments.append("Biên lợi nhuận ròng mỏng; ROE dễ nhạy cảm với biến động giá bán, chi phí đầu vào và chi phí tài chính.")
    return (
        " ".join(comments) + " "
        f"Số liệu đọc nhanh: ROE trung vị {_fmt_note_value(roe)}%, ROA trung vị {_fmt_note_value(roa)}%, "
        f"biên gộp trung vị {_fmt_note_value(gross_margin)}%, biên ròng trung vị {_fmt_note_value(net_margin)}%, "
        f"vòng quay tài sản trung vị {_fmt_note_value(turnover)} lần, hệ số nhân vốn chủ trung vị {_fmt_note_value(multiplier)} lần. "
        f"Kỳ mới nhất: ROE {_fmt_note_value(latest_roe)}%, biên ròng {_fmt_note_value(latest_margin)}%, "
        f"vòng quay tài sản {_fmt_note_value(latest_turnover)} lần, hệ số nhân vốn chủ {_fmt_note_value(latest_multiplier)} lần. "
        "Cách đọc: DuPont tốt khi ROE cao đến từ biên lợi nhuận bền vững và vòng quay tài sản tốt, không phụ thuộc quá nhiều vào đòn bẩy."
    )

def _render_scorecard_radar(scorecard: pd.DataFrame, title: str, name: str = "Điểm nhiệt") -> None:
    """Render radar/spider chart for Tổng quan doanh nghiệp scorecards using 'Tỷ lệ đạt' heat score."""
    if scorecard is None or scorecard.empty or "Nhóm tiêu chí" not in scorecard.columns:
        st.info("Chưa đủ dữ liệu để vẽ biểu đồ mạng nhện.")
        return
    chart_df = scorecard.copy()
    if "Tỷ lệ đạt" in chart_df.columns:
        chart_df["Điểm nhiệt"] = pd.to_numeric(chart_df["Tỷ lệ đạt"], errors="coerce")
    elif {"Điểm", "Trọng số"}.issubset(chart_df.columns):
        score = pd.to_numeric(chart_df["Điểm"], errors="coerce")
        weight = pd.to_numeric(chart_df["Trọng số"], errors="coerce").replace(0, pd.NA)
        chart_df["Điểm nhiệt"] = score / weight * 100
    else:
        st.info("Bảng chưa có cột Tỷ lệ đạt hoặc Điểm/Trọng số để vẽ mạng nhện.")
        return
    chart_df["Điểm nhiệt"] = pd.to_numeric(chart_df["Điểm nhiệt"], errors="coerce").fillna(0).clip(0, 100)
    labels = chart_df["Nhóm tiêu chí"].astype(str).tolist()
    values = chart_df["Điểm nhiệt"].astype(float).tolist()
    custom = []
    for _, row in chart_df.iterrows():
        custom.append(
            f"{row.get('Nhóm tiêu chí','')}<br>Điểm nhiệt: {row.get('Điểm nhiệt',0):.1f}/100"
            f"<br>Điểm đạt: {row.get('Điểm','N/A')}/{row.get('Trọng số','N/A')}"
            f"<br>Tín hiệu: {row.get('Tín hiệu','N/A')}"
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
    st.caption("Biểu đồ dùng cột 'Tỷ lệ đạt' của bảng đánh giá, quy đổi về thang 0-100 để nhìn nhanh điểm mạnh/yếu theo từng nhóm tiêu chí.")


def _scorecard_important_comment(scorecard: pd.DataFrame, label: str = "bộ tiêu chí") -> str:
    """Generate a concise important comment from scorecard rows, not a generic note."""
    if scorecard is None or scorecard.empty:
        return f"Chưa đủ dữ liệu để đưa ra nhận xét quan trọng cho {label}."
    df = scorecard.copy()
    if "Tỷ lệ đạt" in df.columns:
        heat = pd.to_numeric(df["Tỷ lệ đạt"], errors="coerce")
    elif {"Điểm", "Trọng số"}.issubset(df.columns):
        heat = pd.to_numeric(df["Điểm"], errors="coerce") / pd.to_numeric(df["Trọng số"], errors="coerce").replace(0, pd.NA) * 100
    else:
        heat = pd.Series(float("nan"), index=df.index)
    df["_heat"] = heat
    # Tổng điểm nếu có dòng tổng, nếu không lấy bình quân có trọng số tương đối.
    total_rows = df[df.get("Nhóm tiêu chí", pd.Series(dtype=str)).astype(str).str.contains("TỔNG ĐIỂM|TONG DIEM", case=False, na=False)]
    if not total_rows.empty:
        total = float(pd.to_numeric(total_rows.iloc[-1].get("_heat"), errors="coerce"))
        total_signal = str(total_rows.iloc[-1].get("Tín hiệu", ""))
    else:
        total = float(pd.to_numeric(df["_heat"], errors="coerce").dropna().mean()) if pd.to_numeric(df["_heat"], errors="coerce").notna().any() else float("nan")
        total_signal = "Tốt" if total >= 75 else "Theo dõi" if total >= 50 else "Cảnh báo"
    detail_rows = df[~df.get("Nhóm tiêu chí", pd.Series(dtype=str)).astype(str).str.contains("TỔNG ĐIỂM|TONG DIEM", case=False, na=False)].copy()
    strengths = detail_rows.sort_values("_heat", ascending=False).head(2)
    weaknesses = detail_rows.sort_values("_heat", ascending=True).head(2)
    def fmt_rows(rows):
        out = []
        for _, r in rows.iterrows():
            name = str(r.get("Nhóm tiêu chí", "")).strip()
            val = r.get("_heat")
            sig = str(r.get("Tín hiệu", "")).strip()
            try:
                out.append(f"{name} {float(val):.1f}/100 ({sig})")
            except Exception:
                out.append(f"{name} ({sig})")
        return "; ".join([x for x in out if x.strip()])
    total_txt = "N/A" if pd.isna(total) else f"{total:.1f}/100"
    if total >= 75:
        lead = f"{label} đang ở trạng thái tốt: tổng điểm {total_txt}, tín hiệu {total_signal}."
    elif total >= 50:
        lead = f"{label} ở mức theo dõi: tổng điểm {total_txt}, chưa đủ mạnh để kết luận chất lượng bền vững nếu các nhóm yếu không cải thiện."
    else:
        lead = f"{label} phát tín hiệu cảnh báo: tổng điểm {total_txt}; cần kiểm tra kỹ chất lượng lợi nhuận, dòng tiền và rủi ro vốn."
    strong_txt = fmt_rows(strengths)
    weak_txt = fmt_rows(weaknesses)
    return lead + (f" Điểm mạnh nổi bật: {strong_txt}." if strong_txt else "") + (f" Điểm yếu cần kiểm tra: {weak_txt}." if weak_txt else "")

def _format_company_overview_for_display(company) -> pd.DataFrame:
    """Human-readable company overview table for the Data tab."""
    rows = [
        {"Chỉ tiêu": "Mã cổ phiếu", "Giá trị": company.ticker},
        {"Chỉ tiêu": "Tên công ty", "Giá trị": company.company_name},
        {"Chỉ tiêu": "Sàn", "Giá trị": company.exchange or "N/A"},
        {"Chỉ tiêu": "Ngành", "Giá trị": _display_industry_value(company.industry)},
        {"Chỉ tiêu": "Phân ngành", "Giá trị": _display_industry_value(company.sub_industry)},
        {"Chỉ tiêu": "Vốn hóa", "Giá trị": "" if company.market_cap_bil is None else f"{company.market_cap_bil:,.0f} tỷ đồng"},
        {"Chỉ tiêu": "Số lượng cổ phiếu lưu hành", "Giá trị": "" if company.shares_outstanding_mil is None else f"{company.shares_outstanding_mil:,.0f} triệu cp"},
        {"Chỉ tiêu": "Giá hiện tại", "Giá trị": "" if company.current_price is None else f"{company.current_price:,.0f} đồng/cp"},
        {"Chỉ tiêu": "EPS", "Giá trị": "" if company.eps is None else f"{company.eps:,.0f} đồng/cp"},
        {"Chỉ tiêu": "P/E", "Giá trị": "" if company.pe is None else f"{company.pe:,.1f} lần"},
        {"Chỉ tiêu": "P/B", "Giá trị": "" if company.pb is None else f"{company.pb:,.1f} lần"},
        {"Chỉ tiêu": "P/S", "Giá trị": "" if company.ps is None else f"{company.ps:,.1f} lần"},
        {"Chỉ tiêu": "ROE", "Giá trị": "" if company.roe is None else f"{company.roe:,.1f}%"},
        {"Chỉ tiêu": "ROA", "Giá trị": "" if company.roa is None else f"{company.roa:,.1f}%"},
        {"Chỉ tiêu": "ROIC", "Giá trị": "" if company.roic is None else f"{company.roic:,.1f}%"},
        {"Chỉ tiêu": "Cập nhật", "Giá trị": _safe_public_text(company.updated_at or "N/A")},
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
                "company_name": f"{ticker.upper()} - đang cập nhật hồ sơ doanh nghiệp",
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
    st.session_state["module_sync_status"] = f"Đã đồng bộ {ticker} vào Tổng quan doanh nghiệp + Định giá chuyên sâu lúc {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}"
    _load_overview_cached.clear()
    _load_timeseries_cached.clear()


def _load_active_or_default(default_ticker: str = "DCM") -> tuple[Path, Path, Path, str, str]:
    active_ticker = st.session_state.get("active_ticker")
    paths = [st.session_state.get("active_overview_csv"), st.session_state.get("active_year_csv"), st.session_state.get("active_quarter_csv")]
    if active_ticker and all(p and Path(p).exists() for p in paths):
        return Path(paths[0]), Path(paths[1]), Path(paths[2]), st.session_state.get("active_source_label", "Dữ liệu đang hoạt động"), active_ticker

    ticker = _safe_ticker(default_ticker) or "DCM"
    if BUNDLED_XLSM.exists():
        overview, year, quarter, label = _export_bundled_financial_cached(str(BUNDLED_XLSM), ticker, str(DATA_CACHE_DIR))
        _activate_data_source(Path(overview), Path(year), Path(quarter), label, ticker)
        return Path(overview), Path(year), Path(quarter), label, ticker

    _activate_data_source(DEFAULT_OVERVIEW_CSV, DEFAULT_YEAR_CSV, DEFAULT_QUARTER_CSV, "Dữ liệu mẫu", ticker)
    return DEFAULT_OVERVIEW_CSV, DEFAULT_YEAR_CSV, DEFAULT_QUARTER_CSV, "Dữ liệu mẫu", ticker


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
    if source == "Financial tích hợp":
        if not BUNDLED_XLSM.exists():
            raise FileNotFoundError("Không tìm thấy data_sources/Financial-v1.3.0.xlsm trong thư mục app.")
        return ExcelFinancialProvider(BUNDLED_XLSM).fetch(ticker), "financial_xlsm"
    raise ValueError(f"Chế độ dữ liệu không hợp lệ: {_safe_source_label(source)}")


def _fetch_fallback_sources(ticker: str, selected_source: str) -> list[tuple[str, str, ProviderResult]]:
    """Fallback chain used only when the selected preferred data mode cannot populate dashboard.

    The selected source is always tried first in _search_and_bind. If it returns only HTML/raw without usable
    tables, V18 không dùng vnstock. Nếu chế độ dữ liệu ưu tiên không có dữ liệu, chỉ thử dữ liệu tích hợp nếu có đúng mã.
    """
    fallbacks: list[tuple[str, str, ProviderResult]] = []
    # V14: không dùng vnstock/TCBS/VCI fallback nữa.
    # Chỉ fallback về dữ liệu tích hợp nếu file thật sự có dữ liệu của đúng mã.
    if BUNDLED_XLSM.exists():
        try:
            xlsm = ExcelFinancialProvider(BUNDLED_XLSM).fetch(ticker)
            if _result_has_dashboard_data(xlsm):
                fallbacks.append(("financial_xlsm", "Dữ liệu tích hợp dự phòng", xlsm))
        except Exception as exc:
            raw = _save_search_manifest(ticker, "financial_fallback_error", {"error": str(exc)})
            fallbacks.append(("financial_xlsm", "Dữ liệu tích hợp dự phòng lỗi", ProviderResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), raw, str(exc))))
    return fallbacks


def _auto_update_module2_web_evidence(ticker: str, overview_df: pd.DataFrame | None = None) -> None:
    """Tự tìm và lưu bằng chứng internet cho Định giá chuyên sâu sau khi Tổng quan doanh nghiệp cập nhật BCTC.

    Mục tiêu: khi người dùng tìm mã ở Tổng quan doanh nghiệp, Định giá chuyên sâu đã có sẵn evidence table
    về BCTN/BCTC/moat/rủi ro/thị phần mà không cần bấm thêm nút riêng.
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
            f"Định giá chuyên sâu đã tự cập nhật bằng chứng định tính cho {ticker} lúc {st.session_state['module2_web_updated_at']}"
        )
    except Exception as exc:
        st.session_state["module2_auto_update_status"] = f"Không tự cập nhật được bằng chứng định tính cho {ticker}: {_safe_source_label(exc)}"


def _search_and_bind(ticker: str, source: str) -> None:
    ticker = _safe_ticker(ticker)
    if not ticker:
        st.error("Vui lòng nhập mã cổ phiếu.")
        return
    with st.spinner(f"Đang tìm kiếm {ticker} và liên kết dữ liệu vào dashboard..."):
        diagnostics: list[str] = []
        try:
            result, source_key = _fetch_source(ticker, source)
            raw_note = f" Raw: {result.raw_path}" if result.raw_path else ""
            diagnostics.append(f"Chế độ dữ liệu: score={_result_score(result)}, overview={len(result.overview)}, năm={len(result.annual)}, quý={len(result.quarterly)}.")

            final_result = result
            final_source_key = source_key
            final_label_source = source
            used_fallback = False

            if not _result_has_dashboard_data(result):
                for fb_key, fb_label, fb_result in _fetch_fallback_sources(ticker, source):
                    diagnostics.append(f"{fb_label}: score={_result_score(fb_result)}, overview={len(fb_result.overview)}, năm={len(fb_result.annual)}, quý={len(fb_result.quarterly)}. {fb_result.note}")
                    if _result_has_dashboard_data(fb_result) and _result_score(fb_result) > _result_score(final_result):
                        final_result = fb_result
                        final_source_key = fb_key
                        final_label_source = f"{source} không trả bảng chuẩn → {fb_label}"
                        used_fallback = True
                        break

            if not _result_has_dashboard_data(final_result):
                diag_path = _save_search_manifest(ticker, "search_diagnostics", {"ticker": ticker, "source": source, "diagnostics": diagnostics, "raw": str(result.raw_path) if result.raw_path else ""})
                st.session_state["last_search_message"] = (
                    f"Đã chạy cập nhật nhưng chưa lấy được bảng tài chính đủ để cập nhật dashboard. "
                    f"Chi tiết kỹ thuật đã được lưu trong nhật ký nội bộ để kiểm tra sau."
                )
                st.warning(st.session_state["last_search_message"])
                return

            overview_csv, year_csv, quarter_csv, counts = _export_provider_result_to_cache(final_result, ticker, final_source_key)
            label = f"Dữ liệu cập nhật | {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}"
            _activate_data_source(overview_csv, year_csv, quarter_csv, label, ticker)
            _auto_update_module2_web_evidence(ticker, final_result.overview)
            detail = " Đã dùng fallback public vì nguồn đã chọn không trả dữ liệu tài chính chuẩn." if used_fallback else ""
            st.session_state["last_search_message"] = (
                f"Đã tìm kiếm {ticker} từ {source} và tự liên kết vào dashboard. "
                f"Tổng quan: {counts['overview']} dòng, Năm: {counts['annual']} dòng, Quý: {counts['quarterly']} dòng.{detail}{raw_note}"
            )
            st.session_state["last_search_diagnostics"] = diagnostics
            st.success(st.session_state["last_search_message"])
            st.rerun()
        except Exception as exc:
            _save_search_manifest(ticker, "search_exception", {"ticker": ticker, "source": source, "error": str(exc), "diagnostics": diagnostics})
            st.session_state["last_search_message"] = f"Lỗi khi tìm kiếm {ticker}: {_safe_source_label(exc)}. Chi tiết đã lưu trong nhật ký nội bộ."
            st.error(st.session_state["last_search_message"])




def _render_tre_sidebar_nav() -> None:
    """Manual branded navigation so the technical root page name 'app' is never shown."""
    st.markdown("### Điều hướng")
    st.page_link("app.py", label="Tổng quan doanh nghiệp", icon="📊")
    st.page_link("pages/02_Dinh_gia_Porter_Moat.py", label="Định giá chuyên sâu", icon="🧠")
    st.page_link("pages/03_So_sanh_doanh_nghiep.py", label="So sánh doanh nghiệp", icon="⚖️")
    st.page_link("pages/04_Bao_cao_tong_hop.py", label="Báo cáo tổng hợp toàn bộ nội dung", icon="📄")
    st.divider()


def _render_search_panel() -> tuple[int, int]:
    with st.sidebar:
        _render_tre_sidebar_nav()
        st.header("🔎 Tìm kiếm dữ liệu")
        st.markdown(
            """
            <div class='workflow-card'>
            <b>Luồng dữ liệu</b><br>
            1) Nhập mã cổ phiếu ở Tổng quan doanh nghiệp hoặc Định giá chuyên sâu<br>
            2) App tự chạy pipeline Tổng quan doanh nghiệp để lấy/chuẩn hóa BCTC<br>
            3) Cùng bộ cache được dùng ngay cho phần định giá/moat.
            </div>
            """,
            unsafe_allow_html=True,
        )
        default_ticker = st.session_state.get("shared_ticker", st.session_state.get("module2_ticker", st.session_state.get("last_query_ticker", st.session_state.get("active_ticker", "DCM"))))
        ticker = st.text_input("Mã cổ phiếu", value=default_ticker, max_chars=10, key="module1_input_ticker").upper().strip()
        source_display = st.selectbox("Chế độ dữ liệu", SOURCE_OPTIONS, index=0, key="module1_source")
        source = _to_internal_source(source_display)
        mos_canonical = _prepare_mos_widget("module1_mos_widget")
        st.selectbox(
            "Mức MOS yêu cầu (%)",
            MOS_OPTIONS_GLOBAL,
            index=MOS_OPTIONS_GLOBAL.index(mos_canonical),
            key="module1_mos_widget",
            on_change=_commit_mos_widget,
            args=("module1_mos_widget",),
            help="MOS dùng chung toàn app: chọn ở Tổng quan doanh nghiệp sẽ tự đồng bộ sang Định giá chuyên sâu và ngược lại.",
        )
        if st.session_state.get("mos_sync_status"):
            st.caption(st.session_state["mos_sync_status"])
        auto_sync = st.checkbox("Tự động tải & đồng bộ khi đổi mã", value=True, help="Khi nhập đủ mã cổ phiếu, app tự gọi pipeline Tổng quan doanh nghiệp và cập nhật dữ liệu dùng chung cho Định giá chuyên sâu.")
        submitted = st.button("🔎 Tìm kiếm & cập nhật dashboard", use_container_width=True)

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
        limit_years = st.slider("Số năm hiển thị", 5, 10, 10)
        limit_quarters = st.slider("Số quý hiển thị", 4, 20, 20)

        st.markdown(
            """
            <div class='source-card'>
            Dữ liệu sau khi cập nhật sẽ được kích hoạt thành bộ dữ liệu chung cho cả Tổng quan doanh nghiệp và Định giá chuyên sâu.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.get("last_search_message"):
            st.caption(_safe_source_label(st.session_state["last_search_message"]))
    return limit_years, limit_quarters

def render_dashboard() -> None:
    _inject_runtime_ui_css()
    # V23.33: logo chuyển ra page, không đặt trong sidebar để tránh bị ẩn khi sidebar thu gọn.
    _render_brand_page_header(
        "📊 Tổng quan doanh nghiệp",
        "Trecapital dashboard – tự đồng bộ dữ liệu sang Định giá chuyên sâu.",
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
    # V23.20: WACC được tính tự động trong ensure_derived_metrics/append_ttm_row; không dùng WACC tham chiếu sidebar.

    metrics = build_metric_dict(company)
    valuation_df = build_mos_valuation_table(company, annual_df, mos_rate=float(st.session_state.get("target_mos_pct", 50)) / 100)
    ratio_scorecard_for_summary = build_financial_ratio_scorecard(annual_df) if annual_df is not None and not annual_df.empty else pd.DataFrame()
    flags = build_flags(company, annual_df=annual_df, quarterly_df=quarterly_df)
    summary = build_quick_summary(company, annual_df=annual_df)
    value_investing_summary = build_value_investing_assessment(company, annual_df, ratio_scorecard_for_summary) if annual_df is not None and not annual_df.empty else "Chưa đủ dữ liệu năm để tổng hợp nhận xét theo triết lý đầu tư giá trị."
    mos_detailed_summary = build_mos_detailed_summary(valuation_df)

    st.markdown(
        f"""
        <div class='workflow-card'>
        <b>Dashboard đang hiển thị mã:</b> {company.ticker} &nbsp; | &nbsp;
        <b>Mã đang phân tích:</b> {company.ticker}<br>
        <span class='small-muted'>Muốn đổi mã hoặc chế độ dữ liệu, dùng khung Tìm kiếm ở sidebar rồi bấm Tìm kiếm & cập nhật dashboard.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_ticker_title_inline(company, metrics["Giá hiện tại"], metrics["Cập nhật"])
    if "Demo" in str(company.updated_at):
        st.warning(_safe_public_text(company.updated_at))

    row1 = st.columns(4)
    for col, label in zip(row1, ["Vốn hóa", "Cổ phiếu lưu hành", "EPS", "P/E"]):
        with col:
            _render_compact_metric(label, metrics[label])

    row2 = st.columns(6)
    for col, label in zip(row2, ["P/B", "P/S", "ROE", "ROA", "ROIC", "Sàn"]):
        with col:
            _render_compact_metric(label, metrics[label])

    # V23.39: đã bỏ nút/khung xuất báo cáo trong từng phần; chỉ còn trang Báo cáo tổng hợp toàn bộ nội dung ở sidebar.

    if not annual_df.empty:
        with st.container(border=True):
            st.subheader("KPI kỳ gần nhất từ chuỗi tài chính")
            cards = latest_metric_cards(annual_df)
            cols = st.columns(6)
            for idx, key in enumerate(["Kỳ dữ liệu", "Doanh thu", "LNST", "CFO", "FCF", "Owner Earnings"]):
                with cols[idx]:
                    _render_compact_metric(key, cards.get(key, "N/A"))
            cols2 = st.columns(8)
            for col, key, label in [
                (cols2[0], "ROE", "ROE"),
                (cols2[1], "ROE thực tế", "ROE tự tính"),
                (cols2[2], "ROIC", "ROIC chuẩn"),
                (cols2[3], "ROIC Operating Profit", "ROIC OP MOS"),
                (cols2[4], "ROIC Owner Earnings", "ROIC OE MOS"),
                (cols2[5], "Deployed Capital", "Deployed Capital"),
                (cols2[6], "EPS", "EPS"),
                (cols2[7], "OEPS", "OEPS"),
            ]:
                with col:
                    _render_compact_metric(label, cards.get(key, "N/A"))

    tab_overview, tab_fincharts, tab_fcf, tab_ratios, tab_dupont, tab_roic, tab_data = st.tabs([
        "Tóm tắt", "Biểu đồ tài chính", "FCF & dòng tiền", "Phân tích chỉ số TC", "DuPont", "ROIC & đầu tư", "Dữ liệu"
    ])

    with tab_overview:
        with st.container(border=True):
            st.subheader("Tóm tắt nhanh tình trạng doanh nghiệp")
            _render_important_red("Tổng quan nhanh", summary)
            _render_important_red("Nhận xét tự động theo triết lý đầu tư giá trị", value_investing_summary)
            _render_important_red("Định giá MOS chi tiết", mos_detailed_summary)
        with st.container(border=True):
            st.subheader("Kết quả định giá MOS")
            if valuation_df.empty:
                st.info("Chưa đủ dữ liệu để tính giá MOS.")
            else:
                _render_explainable_table(valuation_df, "mos_valuation", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=330)
        with st.container(border=True):
            st.subheader("Cảnh báo / điểm cần kiểm tra")
            combined = build_combined_assessment_table(company, annual_df, quarterly_df, valuation_df)
            _render_explainable_table(combined, "combined_alerts", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=430)

    with tab_fincharts:
        chart_year_tab, chart_quarter_tab = st.tabs(["Năm + TTM", "20 quý"])
        with chart_year_tab:
            if annual_df.empty:
                st.warning("Chưa có dữ liệu năm cho mã này. Vui lòng bấm Tìm kiếm & cập nhật dashboard hoặc đổi chế độ dữ liệu.")
            else:
                render_line_chart("Doanh thu và lợi nhuận năm + TTM", annual_df, ["revenue_bil", "net_profit_bil"], "tỷ đồng", "Rê chuột vào từng điểm để xem số liệu.")
                render_line_chart("CFO, Free Cash Flow, Owner Earnings năm + TTM", annual_df, ["cfo_bil", "free_cash_flow_bil", "owner_earnings_bil"], "tỷ đồng", "So sánh chất lượng dòng tiền và lợi nhuận chủ sở hữu.")
                render_line_chart("Tỷ suất cổ tức tiền mặt thực tế theo năm", annual_df, ["cash_dividend_yield_pct"], "%", "Công thức: |cổ tức tiền mặt đã trả theo năm tài chính| / giá cổ phiếu cuối năm. Nếu dữ liệu đầu vào chưa có lịch sử giá cuối năm, chỉ tiêu sẽ để trống thay vì dùng sai giá hiện tại.")
                render_line_chart("ROE và ROE tự tính năm + TTM", annual_df, ["roe_pct", "roe_actual_pct"], "%", "ROE tự tính = LNST / VCSH bình quân.")
                render_line_chart("ROIC Operating Profit vs WACC năm + TTM", annual_df, ["roic_operating_profit_pct", "wacc_pct"], "%", "Chỉ giữ ROIC Operating Profit và WACC doanh nghiệp tự tính để so sánh hiệu quả vốn cốt lõi với chi phí vốn.")
                render_line_chart("EPS và OEPS năm + TTM", annual_df, ["eps_vnd", "oeps_vnd"], "đồng/cp", "EPS kế toán và EPS theo Owner Earnings.")

        with chart_quarter_tab:
            if quarterly_df.empty:
                st.warning("Chưa có dữ liệu quý cho mã này. App hỗ trợ tối đa 20 quý, nguồn có bao nhiêu quý sẽ hiển thị bấy nhiêu.")
            else:
                render_line_chart("Doanh thu và lợi nhuận theo quý", quarterly_df, ["revenue_bil", "net_profit_bil"], "tỷ đồng", "Thứ tự quý đã được chuẩn hóa tăng dần.")
                render_line_chart("CFO, Free Cash Flow, Owner Earnings theo quý", quarterly_df, ["cfo_bil", "free_cash_flow_bil", "owner_earnings_bil"], "tỷ đồng", "Rê chuột để xem từng quý.")
                render_line_chart("ROIC Operating Profit vs WACC theo quý", quarterly_df, ["roic_operating_profit_pct", "wacc_pct"], "%", "Chỉ giữ ROIC Operating Profit và WACC doanh nghiệp tự tính để so sánh hiệu quả vốn cốt lõi với chi phí vốn.")
                render_line_chart("EPS và OEPS theo quý", quarterly_df, ["eps_vnd", "oeps_vnd"], "đồng/cp", "EPS theo từng quý; OEPS theo Owner Earnings.")

    with tab_fcf:
        st.markdown(
            """
            <div class='note-card'>
            <b>Tab FCF & dòng tiền</b> được xây theo cấu trúc sheet <b>FCF-Years</b> và <b>FCF-Quaters</b> trong file mẫu:
            phân tích quá trình <b>LNTT → điều chỉnh phi tiền mặt → thay đổi vốn lưu động → Capex → FCF</b>, sau đó xem doanh nghiệp dùng FCF cho trả nợ, cổ tức, đầu tư và tăng/giảm tiền + đầu tư tài chính ngắn hạn trong kỳ như thế nào.
            </div>
            """,
            unsafe_allow_html=True,
        )
        fcf_year_tab, fcf_quarter_tab = st.tabs(["Theo năm", "Theo quý"])
        with fcf_year_tab:
            if annual_df.empty:
                st.warning("Chưa có dữ liệu FCF theo năm cho mã này.")
            else:
                _plot(make_fcf_generation_fig(annual_df, "FCF theo năm: LNTT → FCF"))
                _plot(make_fcf_usage_fig(annual_df, "Sử dụng dòng tiền theo năm"))
                _plot(make_fcf_conversion_fig(annual_df, "FCF Conversion theo năm"))
                st.subheader("Bộ tiêu chí đánh giá tự động theo năm")
                cashflow_scorecard_year = build_cashflow_scorecard(annual_df)
                _render_important_red("Nhận xét quan trọng theo bảng điểm FCF & dòng tiền", _scorecard_important_comment(cashflow_scorecard_year, "FCF & dòng tiền theo năm"))
                _render_scorecard_radar(cashflow_scorecard_year, "Biểu đồ mạng nhện đánh giá FCF & dòng tiền theo năm", "FCF & dòng tiền")
                _render_explainable_table(cashflow_scorecard_year, "cashflow_scorecard_year", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=350)
                _render_explainable_table(build_cashflow_situation_alerts(annual_df), "cashflow_alerts_year", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=300)
                st.subheader("Bảng phân tích sử dụng dòng tiền theo năm")
                _render_fcf_analysis_table(build_fcf_analysis_table(annual_df), "fcf_analysis_year")
        with fcf_quarter_tab:
            if quarterly_df.empty:
                st.warning("Chưa có dữ liệu FCF theo quý cho mã này.")
            else:
                _plot(make_fcf_generation_fig(quarterly_df, "FCF theo quý: LNTT → FCF"))
                _plot(make_fcf_usage_fig(quarterly_df, "Sử dụng dòng tiền theo quý"))
                _plot(make_fcf_conversion_fig(quarterly_df, "FCF Conversion theo quý"))
                st.subheader("Bộ tiêu chí đánh giá tự động theo quý")
                cashflow_scorecard_quarter = build_cashflow_scorecard(quarterly_df)
                _render_important_red("Nhận xét quan trọng theo bảng điểm FCF & dòng tiền quý", _scorecard_important_comment(cashflow_scorecard_quarter, "FCF & dòng tiền theo quý"))
                _render_scorecard_radar(cashflow_scorecard_quarter, "Biểu đồ mạng nhện đánh giá FCF & dòng tiền theo quý", "FCF & dòng tiền quý")
                _render_explainable_table(cashflow_scorecard_quarter, "cashflow_scorecard_quarter", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=350)
                _render_explainable_table(build_cashflow_situation_alerts(quarterly_df), "cashflow_alerts_quarter", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=300)
                st.subheader("Bảng phân tích sử dụng dòng tiền theo quý")
                _render_fcf_analysis_table(build_fcf_analysis_table(quarterly_df), "fcf_analysis_quarter")


    with tab_ratios:
        st.markdown(
            """
            <div class='note-card'>
            <b>Tab Phân tích chỉ số TC</b> nâng cấp từ sheet <b>PHÂN TÍCH CHỈ SỐ TC</b>.
            App không bê nguyên công thức Excel nếu công thức tham chiếu lỗi; thay vào đó chuẩn hóa theo lý thuyết tài chính: tăng trưởng, biên lợi nhuận, sinh lời trên vốn, hiệu quả vốn lưu động, thanh khoản/đòn bẩy và định giá sơ bộ.
            Đánh giá bám triết lý Buffett/Graham/Li Lu/Howard Marks: nhìn cổ phiếu như quyền sở hữu doanh nghiệp, ưu tiên dòng tiền thật, lợi nhuận trên vốn, bảng cân đối an toàn và biên an toàn khi mua.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if annual_df.empty:
            st.warning("Chưa có dữ liệu chỉ số tài chính theo năm cho mã này.")
        else:
            scorecard = ratio_scorecard_for_summary if not ratio_scorecard_for_summary.empty else build_financial_ratio_scorecard(annual_df)
            st.subheader("Nhận xét tự động theo triết lý đầu tư giá trị")
            _render_important_red("Nhận xét quan trọng theo chỉ số tài chính", build_value_investing_assessment(company, annual_df, scorecard))
            st.subheader("Bộ tiêu chí đánh giá tự động - 100 điểm")
            _render_scorecard_radar(scorecard, "Biểu đồ mạng nhện đánh giá phân tích chỉ số tài chính", "Chỉ số tài chính")
            _render_explainable_table(scorecard, "ratio_scorecard", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=360)
            st.subheader("Cảnh báo/tình huống chỉ số tài chính")
            _render_explainable_table(build_financial_ratio_alerts(annual_df), "ratio_alerts", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=300)
            st.subheader("Bảng PHÂN TÍCH CHỈ SỐ TC theo năm")
            _render_explainable_table(build_financial_ratio_table(annual_df), "ratio_table_year", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=520)
        if not quarterly_df.empty:
            with st.expander("Xem thêm bảng chỉ số tài chính theo quý", expanded=False):
                _render_explainable_table(build_financial_ratio_table(quarterly_df), "ratio_table_quarter", company=company, annual_df=annual_df, quarterly_df=quarterly_df, height=520)

    with tab_dupont:
        source_df = annual_df if not annual_df.empty else quarterly_df
        if source_df.empty:
            st.warning("Chưa có dữ liệu DuPont.")
        else:
            _render_important_red("Nhận xét quan trọng DuPont", _build_dupont_comment(source_df))
            _plot(make_dupont_profitability_fig(source_df))
            _plot(make_dupont_driver_fig(source_df))
            dup_cols = [c for c in ["period", "roe_pct", "roa_pct", "gross_margin_pct", "net_margin_pct", "asset_turnover", "equity_multiplier", "roe_actual_pct", "roe_dupont_pct"] if c in source_df.columns]
            _show_table(source_df[dup_cols])

    with tab_roic:
        source_df = annual_df if not annual_df.empty else quarterly_df
        if source_df.empty:
            st.warning("Chưa có dữ liệu ROIC/đầu tư.")
        else:
            _plot(make_roic_investment_fig(source_df))
            st.caption("Biểu đồ chỉ hiển thị ROIC Operating Profit và WACC doanh nghiệp tự tính. Nếu ROIC Operating Profit > WACC nhiều kỳ, doanh nghiệp có dấu hiệu tạo giá trị trên vốn sử dụng; vẫn cần kiểm tra CFO/FCF và chu kỳ ngành.")
            _render_important_red("Nhận xét quan trọng ROIC & đầu tư", _build_roic_investment_comment(source_df))
            roic_cols = [c for c in ["period", "core_operating_profit_bil", "nopat_bil", "deployed_capital_bil", "avg_deployed_capital_bil", "interest_bearing_debt_bil", "avg_interest_bearing_debt_bil", "market_cap_bil", "equity_weight_pct", "debt_weight_pct", "cost_of_equity_pct", "cost_of_debt_pct", "after_tax_cost_of_debt_pct", "tax_rate_pct", "beta", "roic_operating_profit_pct", "wacc_pct", "wacc_quality", "expansion_investment_bil", "inventory_change_bil", "investment_subsidiary_bil", "total_investment_bil", "wacc_formula_detail"] if c in source_df.columns]
            _show_table(format_table_for_display(source_df[roic_cols]))

    with tab_data:
        st.subheader("Dữ liệu tổng quan")
        _show_table(_format_company_overview_for_display(company))
        st.subheader("Dữ liệu năm + TTM")
        _show_table(format_table_for_display(annual_df))
        st.download_button("Tải CSV năm + TTM", annual_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"{company.ticker}_tong_quan_year.csv", mime="text/csv")
        st.subheader("Dữ liệu quý")
        _show_table(format_table_for_display(quarterly_df))
        st.download_button("Tải CSV quý", quarterly_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"{company.ticker}_tong_quan_quarter.csv", mime="text/csv")


if __name__ == "__main__":
    render_dashboard()
