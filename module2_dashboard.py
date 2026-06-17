from __future__ import annotations

from pathlib import Path
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
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

from module1_engine import (
    CompanyOverview,
    load_overview_from_csv,
    load_timeseries_from_csv,
    ensure_derived_metrics,
    append_ttm_row,
    latest_metric_cards,
    format_table_for_display,
)
from adapters.excel_financial_provider import ExcelFinancialProvider
from adapters.module2_web_research import WebEvidenceAgent
from adapters.vn_public_crawler import PublicFireAntCrawler, PublicVietstockCrawler, PublicSimplizeCrawler
from adapters.base import ProviderResult, MODULE1_OVERVIEW_COLUMNS, MODULE1_TIMESERIES_COLUMNS, normalize_columns
from module2_engine import (
    load_assumptions,
    classify_company,
    build_module2_valuation_table,
    build_valuation_range,
    build_porter_moat_scorecard,
    build_value_chain_table,
    build_risk_scenario_table,
    build_beneish_mscore_table,
    build_accrual_quality_table,
    build_modified_jones_kothari_table,
    build_real_earnings_management_table,
    build_module2_summary,
    export_module2_report_markdown,
)

from report_exporter import render_full_report_export_box

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "trecapital_logo.png"
DEFAULT_OVERVIEW_CSV = APP_DIR / "sample_data" / "company_overview_sample.csv"
DEFAULT_YEAR_CSV = APP_DIR / "sample_data" / "financial_timeseries_year.csv"
DEFAULT_QUARTER_CSV = APP_DIR / "sample_data" / "financial_timeseries_quarter.csv"
BUNDLED_XLSM = APP_DIR / "data_sources" / "Financial-v1.3.0.xlsm"
DATA_CACHE_DIR = APP_DIR / "data_cache"
RAW_DIR = APP_DIR / "raw_data"
REPORT_DIR = APP_DIR / "reports"
ASSUMPTIONS_PATH = APP_DIR / "configs" / "valuation_assumptions.json"
APP_NAME = "Định giá chuyên sâu"
APP_VERSION = "V23.66-formula-source-audit-fix"

DATA_SOURCE_DISPLAY_TO_INTERNAL = {
    "Tự động": "Tự động từ dữ liệu tổng quan",
    "Dữ liệu ưu tiên 1": "FireAnt + Vietstock",
    "Dữ liệu ưu tiên 2": "FireAnt",
    "Dữ liệu ưu tiên 3": "Vietstock",
    "Dữ liệu tích hợp": "Financial tích hợp",
    "Dữ liệu mẫu": "CSV mẫu tích hợp",
}
DATA_SOURCE_INTERNAL_TO_DISPLAY = {v: k for k, v in DATA_SOURCE_DISPLAY_TO_INTERNAL.items()}
PEER_SOURCE_DISPLAY_TO_INTERNAL = {
    "Cùng chế độ mã gốc": "__same__",
    "Dữ liệu ưu tiên": "FireAnt",
    "Dữ liệu tích hợp": "Financial tích hợp",
    "Dữ liệu mẫu": "CSV mẫu tích hợp",
}


def _to_internal_source(display_value: object) -> str:
    return DATA_SOURCE_DISPLAY_TO_INTERNAL.get(str(display_value), str(display_value))


def _to_internal_peer_source(display_value: object, current_source: str) -> str:
    val = PEER_SOURCE_DISPLAY_TO_INTERNAL.get(str(display_value), str(display_value))
    return current_source if val == "__same__" else val


def _public_text(value: object) -> str:
    # Pandas pd.NA cannot be evaluated in boolean context: bool(pd.NA) raises
    # "TypeError: boolean value of NA is ambiguous". Keep this helper safe for
    # all nullable/object columns before display.
    if value is None:
        text = ""
    else:
        try:
            if pd.isna(value):
                text = ""
            else:
                text = str(value)
        except Exception:
            text = str(value)
    for raw, public in DATA_SOURCE_INTERNAL_TO_DISPLAY.items():
        text = text.replace(raw, public)
    replacements = {
        "FireAnt": "Dữ liệu ưu tiên",
        "Vietstock": "Dữ liệu ưu tiên",
        "Simplize": "Danh sách cùng ngành",
        "KBS": "nhóm trực tuyến",
        "VCI": "nhóm trực tuyến",
        "CafeF": "Tham khảo",
        "SSC": "Công bố thông tin",
        "HOSE": "Công bố thông tin",
        "HNX": "Công bố thông tin",
        "Financial tích hợp": "Dữ liệu tích hợp",
        "CSV mẫu tích hợp": "Dữ liệu mẫu",
        "raw_data": "nhật ký nội bộ",
        "data_cache": "bộ nhớ dữ liệu",
    }
    for raw, public in replacements.items():
        text = text.replace(raw, public)
    # Ẩn các cụm kỹ thuật/nguồn nội bộ trong mọi thông báo công khai.
    text = re.sub(r"(?:Dữ liệu ưu tiên|Dữ liệu tích hợp|Dữ liệu mẫu|FireAnt|Vietstock|Simplize)?\s*(?:VBA\s+)?endpoints?\s*", "Dữ liệu cập nhật ", text, flags=re.I)
    text = re.sub(r"\bCrawler\s+[^0-9]*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", r"Dữ liệu cập nhật \1", text, flags=re.I)
    text = text.replace("TCReport_", "")
    text = re.sub(r"https?://\S+", "liên kết nội bộ", text, flags=re.I)
    text = re.sub(r"/?[^\s<>]*\.(?:csv|json|html|txt|xlsm|xlsx|md)", "file nội bộ", text, flags=re.I)
    text = re.sub(r"[A-Za-z]:\\[^\s<>]+", "đường dẫn nội bộ", text)
    text = re.sub(r"/(?:mnt|home|Users|raw_data|data_cache)[^\s<>]+", "đường dẫn nội bộ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _hide_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df
    hidden_names = {
        "source", "Source", "Nguồn", "Nguồn/URL", "Nguồn dữ liệu", "URL", "Truy vấn",
        "updated_at", "note", "raw_path", "File", "File năm", "File quý", "source_label"
    }
    out = df.drop(columns=[c for c in df.columns if str(c) in hidden_names or "url" in str(c).lower() or str(c).lower() == "source"], errors="ignore").copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].map(_public_text)
    return out

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
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return "N/A"
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




def _render_warning_card(title: str, body: object) -> None:
    st.markdown(
        f"""
        <div class="big-warning-card" style="border:2px solid #F5B21B;border-left:10px solid #F5B21B;border-radius:16px;padding:14px 16px;background:linear-gradient(135deg,#FFF7E6 0%,#FEF3C7 100%);margin:12px 0 16px 0;box-shadow:0 8px 22px rgba(245,178,27,.13);">
            <div class="big-warning-title" style="font-size:1.08rem;font-weight:950;color:#8A5A00;margin-bottom:7px;">{html.escape(str(title))}</div>
            <div class="big-warning-text" style="font-size:.96rem;font-weight:850;color:#5F3B00;line-height:1.55;">{_markdownish_to_html(body)}</div>
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


        /* V23.25: sidebar module navigation buttons - Trecapital brand identity */
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {padding-top: .35rem !important;}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
            display: flex !important;
            flex-direction: column !important;
            gap: 10px !important;
            padding: 0 8px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li {margin: 0 !important;}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
            border: 1.7px solid rgba(11,127,117,.26) !important;
            border-radius: 17px !important;
            margin: 3px 0 !important;
            padding: 12px 14px !important;
            background: linear-gradient(135deg, rgba(255,255,255,.92), rgba(248,255,251,.86)) !important;
            color: #064E47 !important;
            font-weight: 900 !important;
            box-shadow: 0 7px 17px rgba(11,127,117,.08) !important;
            transition: all .16s ease-in-out !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
            border-color:#F5B21B !important;
            background: linear-gradient(135deg, #F8FFFB 0%, #FFF7E6 100%) !important;
            color:#0B5F58 !important;
            box-shadow: 0 10px 22px rgba(11,127,117,.16) !important;
            transform: translateX(2px) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[data-selected="true"] {
            background: linear-gradient(135deg, #0B7F75 0%, #128C7E 78%, #F5B21B 132%) !important;
            color: #FFFFFF !important;
            border-color: #F5B21B !important;
            box-shadow: 0 12px 26px rgba(11,127,117,.24) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a p {
            color: inherit !important;
            font-size: .94rem !important;
            font-weight: 900 !important;
            line-height: 1.25 !important;
        }


        /* Streamlit Tabs - dùng selector rộng cho nhiều version Streamlit/BaseWeb */
        div[data-testid="stTabs"] {margin-top: 10px !important; margin-bottom: 8px !important;}
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


        /* V23.54: tab buttons có màu rõ hơn, tránh nền trắng khó nhìn. */
        div[data-testid="stTabs"] button[role="tab"],
        div[data-testid="stTabs"] button[data-baseweb="tab"],
        div[data-testid="stTabs"] div[role="tab"] {
            background: linear-gradient(135deg, #FFF7E6 0%, #EAF7F1 100%) !important;
            border: 2.6px solid #0B7F75 !important;
            color: #064E47 !important;
            box-shadow: 0 9px 20px rgba(11,127,117,.16) !important;
        }
        div[data-testid="stTabs"] button[role="tab"]:hover,
        div[data-testid="stTabs"] button[data-baseweb="tab"]:hover,
        div[data-testid="stTabs"] div[role="tab"]:hover {
            background: linear-gradient(135deg, #FEF3C7 0%, #CCFBF1 100%) !important;
            border-color: #F5B21B !important;
            transform: translateY(-1px) !important;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
        div[data-testid="stTabs"] div[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #0B7F75 0%, #128C7E 70%, #F5B21B 132%) !important;
            color: #FFFFFF !important;
            border-color: #F5B21B !important;
            box-shadow: 0 12px 28px rgba(11,127,117,.30) !important;
        }

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
        .hero-card {padding: 23px 28px; border-radius: 22px; background: linear-gradient(135deg, #0B7F75 0%, #128C7E 56%, #F5B21B 135%); color: white; margin-bottom: 18px; box-shadow: 0 14px 34px rgba(11,127,117,.20); border:1px solid rgba(255,255,255,.28);}
        .hero-card h1 {font-size: 2.16rem; margin: 0 0 6px 0; color: white; letter-spacing: -.02em;}
        .hero-card p {font-size: 1.06rem; margin: 0; opacity: .95;}
        .logo-card {display:flex; align-items:center; justify-content:center; padding: 12px 7px; border-radius:23px; background: transparent; border:1px solid rgba(11,127,117,.10); box-shadow: 0 10px 24px rgba(11,127,117,.10); margin-bottom: 16px;}
        .page-brand-shell {display:grid; grid-template-columns: 158px minmax(0,1fr); gap:18px; align-items:center; margin:8px 0 20px 0;}
        .page-logo-wrap {height:156px; display:flex; align-items:center; justify-content:center; border-radius:28px; background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%); border:1.8px solid rgba(11,127,117,.18); box-shadow:0 12px 30px rgba(11,127,117,.10);}
        .page-logo-img {max-height:138px; max-width:138px; object-fit:contain;}
        .page-hero-card {margin-bottom:0 !important; min-height:118px; display:flex; flex-direction:column; justify-content:center;}
        div[data-testid="stDataFrame"] [role="columnheader"], div[data-testid="stDataEditor"] [role="columnheader"] {font-weight:950 !important; color:#064E47 !important;}
        .workflow-card {border: 1px solid rgba(11,127,117,.28); border-radius: 18px; padding: 13px 14px; background: linear-gradient(180deg, rgba(234,247,241,.96), rgba(255,255,255,.88)); margin-bottom: 14px;}
        .source-card {border: 1px solid rgba(11,127,117,.28); border-radius: 16px; padding: 11px 13px; background: rgba(234,247,241,.72); margin-top: 8px; margin-bottom: 12px;}
        .note-card {border: 1px solid rgba(11,127,117,.22); border-radius: 16px; padding: 11px 13px; background: rgba(255,251,235,.75); margin-bottom: 10px;}
        .reason-yellow-card {border:2px solid rgba(245,178,27,.62); border-left:10px solid #F5B21B; border-radius:18px; padding:15px 18px; background:linear-gradient(135deg,#FFF7E6 0%,#FFF3C4 100%); color:#5F3B00; margin:12px 0 15px 0; box-shadow:0 9px 24px rgba(245,178,27,.16);}
        .reason-yellow-card .reason-title {font-size:1.03rem; font-weight:1000; color:#8A5A00; margin-bottom:8px;}
        .reason-yellow-card ul {margin:6px 0 0 20px; padding:0;}
        .reason-yellow-card li {margin:6px 0; font-weight:800; line-height:1.45;}
        .valuation-tab-compact div[data-testid="stVerticalBlock"] {gap:.35rem !important;}
        .ok-card {border: 1px solid rgba(11,127,117,.32); border-radius: 16px; padding: 13px 14px; background: rgba(234,247,241,.76); margin-bottom: 12px;}
        .warn-card {border: 1px solid rgba(245,178,27,.48); border-radius: 16px; padding: 13px 14px; background: rgba(255,247,230,.88); margin-bottom: 12px;}
        .big-warning-card {border: 2px solid #0B7F75; border-left: 8px solid #F5B21B; border-radius: 16px; padding: 13px 14px; background: linear-gradient(135deg, #FFF4C7 0%, #FFE68A 100%); margin: 10px 0 12px 0; box-shadow: 0 8px 20px rgba(245,178,27,.18);}
        .big-warning-title {font-size: .92rem; font-weight: 950; color: #0B7F75; margin-bottom: 4px; letter-spacing:-.01em;}
        .big-warning-text {font-size: .86rem; font-weight: 900; color: #5F3B00; line-height: 1.38;}
        .ticker-title-card {
            border: 2.8px solid rgba(11,127,117,.30);
            border-left: 14px solid #F5B21B;
            border-radius: 26px;
            padding: 20px 26px;
            background: linear-gradient(135deg, rgba(234,247,241,.95) 0%, rgba(255,255,255,.96) 100%);
            margin: 12px 0 16px 0;
            box-shadow: 0 12px 31px rgba(11,127,117,.12);
        }
        .ticker-title-main {font-size: 2.10rem; font-weight: 980; color:#064E47; letter-spacing:-.02em;}
        .ticker-title-code {font-size: 2.40rem; font-weight: 1000; color:#0B7F75;}
        .ticker-title-name {font-size: 1.68rem; font-weight: 930; color:#8A5A00;}
        .ticker-title-meta {font-size: .95rem; color:#0B5F58; margin-top:7px;}
        .current-price-inline-card {display:inline-flex;align-items:center;gap:21px;margin-top:17px;margin-bottom:11px;padding:17px 23px;border-radius:23px;border:2.1px solid #F5B21B;border-left:10px solid #F5B21B;background:#FFFFFF;box-shadow:0 10px 24px rgba(245,178,27,.16);min-width:389px;}
        .current-price-inline-card .price-label {font-size:.93rem;line-height:1.08;color:#50646B;font-weight:950;text-transform:uppercase;letter-spacing:.03em;}
        .current-price-inline-card .price-value {font-size:1.56rem;line-height:1.12;color:#064E47;font-weight:1000;}
        .current-price-inline-card .price-note {font-size:1.02rem;color:#64748B;font-weight:780;}
        div[data-testid="stMetric"] {background: rgba(255,255,255,.92); border: 1.7px solid rgba(11,127,117,.22); border-radius: 28px; padding: 22px 24px; min-height: 127px; box-shadow: 0 7px 23px rgba(11,127,117,.09);}
        div.stButton > button {border-radius: 999px !important; border: 1px solid rgba(11,127,117,.35) !important; background: linear-gradient(135deg, #0B7F75, #139486) !important; color: white !important; font-weight: 800 !important;}
        div.stButton > button:hover {border-color:#F5B21B !important; color:white !important; box-shadow: 0 0 0 3px rgba(245,178,27,.16) !important;}
        .small-muted {font-size: .88rem; color: #64748b;}
        .glossary-fit-table {width:100%; border-collapse:collapse; table-layout:auto; font-size:.94rem; line-height:1.42;}
        .glossary-fit-table th {background:#EAF7F1; color:#064E47; border:1px solid rgba(11,127,117,.22); padding:8px 10px; text-align:left; white-space:nowrap; font-weight:950;}
        .glossary-fit-table td {border:1px solid rgba(11,127,117,.14); padding:8px 10px; vertical-align:top; background:#FFFFFF; color:#12343B;}
        .glossary-fit-table .stt {width:52px; text-align:center; white-space:nowrap;}
        .glossary-fit-table .term {width:220px; min-width:150px; white-space:nowrap; font-weight:850; color:#064E47;}
        .glossary-fit-table .desc {width:auto; white-space:normal;}
        /* V23.33 extra CSS */

        section[data-testid="stSidebar"] img {display:none !important;}
        div[data-testid="stDataFrame"] [role="columnheader"], div[data-testid="stDataEditor"] [role="columnheader"],
        div[data-testid="stDataFrame"] [data-testid="stHeader"], div[data-testid="stDataEditor"] [data-testid="stHeader"],
        .stDataFrame th, .stDataEditor th {font-weight:950 !important; color:#064E47 !important;}
        .page-brand-shell {display:grid; grid-template-columns: 176px minmax(0,1fr); gap:22px; align-items:center; margin:6px 0 22px 0;}
        .page-logo-wrap {height:166px; display:flex; align-items:center; justify-content:center; border-radius:30px; background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%); border:2px solid rgba(11,127,117,.20); box-shadow:0 14px 34px rgba(11,127,117,.12);}
        .page-logo-img {max-height:146px; max-width:146px; object-fit:contain; display:block !important;}
        .page-hero-card {margin-bottom:0 !important; min-height:118px; display:flex; flex-direction:column; justify-content:center;}

        /* V23.54 final override: mọi tab đều có màu nền dễ nhận diện. */
        div[data-testid="stTabs"] button[role="tab"],
        div[data-testid="stTabs"] button[data-baseweb="tab"],
        div[data-testid="stTabs"] div[role="tab"] {
            background: linear-gradient(135deg, #FFF7E6 0%, #EAF7F1 100%) !important;
            border: 2.6px solid #0B7F75 !important;
            color: #064E47 !important;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
        div[data-testid="stTabs"] div[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #0B7F75 0%, #128C7E 70%, #F5B21B 132%) !important;
            color: #FFFFFF !important;
            border-color: #F5B21B !important;
        }

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
def _available_financial_tickers_cached(xlsm_path: str) -> list[str]:
    """Return only tickers with full financial blocks in the integrated workbook.

    Previous build scanned column B in all financial sheets and accidentally treated labels such
    as ROE/ROIC/BasicEPS as tickers. This function reads the configured stock list in the workbook.
    """
    try:
        from openpyxl import load_workbook
        import re
        wb = load_workbook(xlsm_path, data_only=True, read_only=True, keep_vba=False)
        tickers: list[str] = []
        if "BÁO CÁO TÀI CHÍNH" in wb.sheetnames:
            ws = wb["BÁO CÁO TÀI CHÍNH"]
            for row in range(15, ws.max_row + 1):
                code = ws.cell(row=row, column=3).value
                if isinstance(code, str) and re.fullmatch(r"[A-Z0-9]{2,8}", code.strip().upper()):
                    tickers.append(code.strip().upper())
        return sorted(dict.fromkeys(tickers))
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def _listed_ticker_info_cached(xlsm_path: str, ticker: str) -> dict:
    """Find company name/exchange in DANH SÁCH MÃ even if BCTC is not bundled."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(xlsm_path, data_only=True, read_only=True, keep_vba=False)
        ws = wb["DANH SÁCH MÃ"] if "DANH SÁCH MÃ" in wb.sheetnames else None
        if ws is None:
            return {}
        ticker = ticker.upper().strip()
        for row in range(5, ws.max_row + 1):
            code = ws.cell(row=row, column=3).value
            if isinstance(code, str) and code.strip().upper() == ticker:
                return {
                    "ticker": ticker,
                    "company_name": str(ws.cell(row=row, column=4).value or ticker),
                    "exchange": str(ws.cell(row=row, column=5).value or ""),
                    "sub_industry": str(ws.cell(row=row, column=7).value or ""),
                }
    except Exception:
        pass
    return {}


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1540px;}
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
 

        /* V23.25: sidebar module navigation buttons - Trecapital brand identity */
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {padding-top: .35rem ;}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
            display: flex ;
            flex-direction: column ;
            gap: 10px ;
            padding: 0 8px ;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li {margin: 0 ;}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
            border: 1.7px solid rgba(11,127,117,.26) ;
            border-radius: 17px ;
            margin: 3px 0 ;
            padding: 12px 14px ;
            background: linear-gradient(135deg, rgba(255,255,255,.92), rgba(248,255,251,.86)) ;
            color: #064E47 ;
            font-weight: 900 ;
            box-shadow: 0 7px 17px rgba(11,127,117,.08) ;
            transition: all .16s ease-in-out ;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
            border-color:#F5B21B ;
            background: linear-gradient(135deg, #F8FFFB 0%, #FFF7E6 100%) ;
            color:#0B5F58 ;
            box-shadow: 0 10px 22px rgba(11,127,117,.16) ;
            transform: translateX(2px) ;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[data-selected="true"] {
            background: linear-gradient(135deg, #0B7F75 0%, #128C7E 78%, #F5B21B 132%) ;
            color: #FFFFFF ;
            border-color: #F5B21B ;
            box-shadow: 0 12px 26px rgba(11,127,117,.24) ;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a p {
            color: inherit ;
            font-size: .94rem ;
            font-weight: 900 ;
            line-height: 1.25 ;
        }

    .hero-card {padding: 23px 28px; border-radius: 22px; background: linear-gradient(135deg, #0B7F75 0%, #128C7E 56%, #F5B21B 135%); color: white; margin-bottom: 18px; box-shadow: 0 14px 34px rgba(11,127,117,.20); border:1px solid rgba(255,255,255,.28);} 
    .hero-card h1 {font-size: 2.16rem; margin: 0 0 6px 0; color: white; letter-spacing: -.02em;}
    .hero-card p {font-size: 1.06rem; margin: 0; opacity: .95;}
    .logo-card {display:flex; align-items:center; justify-content:center; padding: 12px 7px; border-radius:23px; background: transparent; border:1px solid rgba(11,127,117,.10); box-shadow: 0 10px 24px rgba(11,127,117,.10); margin-bottom: 16px;}
    .note-card {border: 1px solid rgba(11,127,117,.22); border-radius: 16px; padding: 11px 13px; background: rgba(255,251,235,.75); margin-bottom: 10px;}
    .ok-card {border: 1px solid rgba(11,127,117,.32); border-radius: 16px; padding: 13px 14px; background: rgba(234,247,241,.76); margin-bottom: 12px;}
    .warn-card {border: 1px solid rgba(245,178,27,.48); border-radius: 16px; padding: 13px 14px; background: rgba(255,247,230,.88); margin-bottom: 12px;}
    .big-warning-card {border: 2px solid #F5B21B; border-left: 8px solid #0B7F75; border-radius: 16px; padding: 11px 13px; background: linear-gradient(135deg, #FFF7E6 0%, #FEF3C7 100%); margin: 9px 0 11px 0; box-shadow: 0 7px 17px rgba(245,178,27,.16);}
    .big-warning-title {font-size: .88rem; font-weight: 900; color: #0B7F75; margin-bottom: 4px; letter-spacing:-.01em;}
    .big-warning-text {font-size: .84rem; font-weight: 850; color: #5f3b00; line-height: 1.36;}
    div[data-testid="stAlert"] p {font-size: 1.02rem;}
    div[data-testid="stMetric"] {background: rgba(255,255,255,.90); border: 1.5px solid rgba(11,127,117,.20); border-radius: 21px; padding: 15px 18px; min-height: 77px; box-shadow: 0 5px 19px rgba(11,127,117,.07);} 
    div.stButton > button {border-radius: 999px; border: 1px solid rgba(11,127,117,.35); background: linear-gradient(135deg, #0B7F75, #139486); color: white; font-weight: 700;}
    div.stButton > button:hover {border-color:#F5B21B; color:white; box-shadow: 0 0 0 3px rgba(245,178,27,.16);}
    .stTabs [data-baseweb="tab-list"], div[data-testid="stTabs"] [role="tablist"] {gap: 14px !important; background: rgba(234,247,241,.96) !important; padding: 14px 16px !important; border-radius: 26px !important; border:2px solid rgba(11,127,117,.30) !important; box-shadow:0 10px 26px rgba(11,127,117,.12) !important;}
    .stTabs [data-baseweb="tab"], div[data-testid="stTabs"] button[role="tab"] {min-height: 58px !important; height: 58px !important; border-radius: 999px !important; padding: 0 28px !important; border: 2.5px solid rgba(11,127,117,.40) !important; background: #FFFFFF !important; color:#0B5F58 !important; font-size: 1.08rem !important; font-weight: 900 !important; box-shadow:0 6px 16px rgba(11,127,117,.10) !important;}
    .stTabs [aria-selected="true"], div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {background: linear-gradient(135deg, #0B7F75, #128C7E) !important; color: #FFFFFF !important; border-color:#F5B21B !important; box-shadow:0 10px 24px rgba(11,127,117,.28) !important; transform: translateY(-1px);}
    .stTabs [data-baseweb="tab"] p, div[data-testid="stTabs"] button[role="tab"] p {font-size: 1.08rem !important; font-weight: 900 !important;}
    .important-red {color:#B91C1C !important; font-size:1.26rem !important; line-height:1.66 !important; font-weight:900 !important; background:rgba(254,242,242,.92) !important; border:2px solid rgba(239,68,68,.28) !important; border-left:10px solid #DC2626 !important; padding:16px 18px !important; border-radius:16px !important; margin:12px 0 16px 0 !important; box-shadow:0 8px 22px rgba(185,28,28,.08) !important;}
    .small-muted {font-size: .88rem; color: #64748b;}
    
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

    /* V23.54 runtime override: tab thường có màu vàng/xanh, tab active nổi bật. */
    div[data-testid="stTabs"] button[role="tab"],
    div[data-testid="stTabs"] div[role="tab"],
    div[role="tablist"] button,
    button[role="tab"],
    div[role="tab"] {
        background: linear-gradient(135deg, #FFF7E6 0%, #EAF7F1 100%) !important;
        border: 2.6px solid #0B7F75 !important;
        color: #064E47 !important;
        box-shadow: 0 9px 20px rgba(11,127,117,.16) !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover,
    div[data-testid="stTabs"] div[role="tab"]:hover,
    div[role="tablist"] button:hover,
    button[role="tab"]:hover,
    div[role="tab"]:hover {
        background: linear-gradient(135deg, #FEF3C7 0%, #CCFBF1 100%) !important;
        border-color: #F5B21B !important;
    }
    button[role="tab"][aria-selected="true"],
    div[role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #0B7F75 0%, #128C7E 70%, #F5B21B 132%) !important;
        color: #FFFFFF !important;
        border-color: #F5B21B !important;
        box-shadow: 0 12px 28px rgba(11,127,117,.30) !important;
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
    
    </style>
    """,
    unsafe_allow_html=True,
)



def _safe_ticker(ticker: str) -> str:
    return "".join(ch for ch in ticker.upper().strip() if ch.isalnum())[:12]


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


def _provider_result_score(result: ProviderResult) -> int:
    score = 0
    if isinstance(result.overview, pd.DataFrame) and not result.overview.empty:
        score += 5
    if isinstance(result.annual, pd.DataFrame) and not result.annual.empty:
        score += min(len(result.annual), 12) * 10
    if isinstance(result.quarterly, pd.DataFrame) and not result.quarterly.empty:
        score += min(len(result.quarterly), 24) * 5
    return score


def _minimal_overview_df(ticker: str, source_name: str) -> pd.DataFrame:
    return normalize_columns(pd.DataFrame([{
        "ticker": ticker.upper(),
        "company_name": f"{ticker.upper()} - đang cập nhật hồ sơ doanh nghiệp",
        "exchange": "",
        "industry": "",
        "sub_industry": "",
        "updated_at": f"Crawler {source_name} {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}",
    }]), MODULE1_OVERVIEW_COLUMNS)


def _write_provider_df(df: pd.DataFrame, path: Path, fallback_columns: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(df, pd.DataFrame) or df.empty:
        pd.DataFrame(columns=fallback_columns).to_csv(path, index=False, encoding="utf-8-sig")
        return 0
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return len(df)


def _export_provider_result_to_module2_cache(result: ProviderResult, ticker: str, source_name: str, cache_dir: str) -> tuple[str, str, str, str]:
    """Ghi kết quả crawler chuẩn Tổng quan doanh nghiệp ra cache để Định giá chuyên sâu dùng trực tiếp.

    Đây là điểm tích hợp quan trọng: Định giá chuyên sâu không tự bịa dữ liệu và không chỉ tìm bằng chứng định tính;
    nó dùng đúng pipeline crawler/normalizer của Tổng quan doanh nghiệp rồi đưa vào engine định giá.
    """
    ticker = _safe_ticker(ticker)
    source_key = source_name.lower().replace(" ", "_").replace("+", "plus").replace("/", "_")
    out_dir = Path(cache_dir) / "module1_crawler" / source_key / ticker
    overview_path = out_dir / "company_overview_sample.csv"
    year_path = out_dir / "financial_timeseries_year.csv"
    quarter_path = out_dir / "financial_timeseries_quarter.csv"

    overview_df = result.overview if isinstance(result.overview, pd.DataFrame) else pd.DataFrame()
    annual_df = result.annual if isinstance(result.annual, pd.DataFrame) else pd.DataFrame()
    quarterly_df = result.quarterly if isinstance(result.quarterly, pd.DataFrame) else pd.DataFrame()
    if overview_df.empty:
        overview_df = _minimal_overview_df(ticker, source_name)

    counts = {
        "overview": _write_provider_df(normalize_columns(overview_df, MODULE1_OVERVIEW_COLUMNS), overview_path, MODULE1_OVERVIEW_COLUMNS),
        "annual": _write_provider_df(normalize_columns(annual_df, MODULE1_TIMESERIES_COLUMNS), year_path, MODULE1_TIMESERIES_COLUMNS),
        "quarterly": _write_provider_df(normalize_columns(quarterly_df, MODULE1_TIMESERIES_COLUMNS), quarter_path, MODULE1_TIMESERIES_COLUMNS),
    }
    raw_note = ""
    label = f"Dữ liệu đã chuẩn hóa từ Tổng quan doanh nghiệp | Tổng quan: {counts['overview']} dòng | Năm: {counts['annual']} dòng | Quý: {counts['quarterly']} dòng"
    return str(overview_path), str(year_path), str(quarter_path), label


def _fetch_module1_crawler_result(ticker: str, source: str, raw_dir: str) -> ProviderResult:
    ticker = _safe_ticker(ticker)
    if source == "FireAnt":
        return PublicFireAntCrawler(raw_dir).fetch(ticker)
    if source == "Vietstock":
        return PublicVietstockCrawler(raw_dir).fetch(ticker)
    if source in {"FireAnt + Vietstock", "Tự động từ dữ liệu tổng quan"}:
        candidates: list[tuple[str, ProviderResult]] = []
        errors: list[str] = []
        for name, crawler in [("FireAnt", PublicFireAntCrawler(raw_dir)), ("Vietstock", PublicVietstockCrawler(raw_dir))]:
            try:
                candidates.append((name, crawler.fetch(ticker)))
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        if not candidates:
            raise RuntimeError("Không gọi được crawler Tổng quan doanh nghiệp: " + " | ".join(errors))
        # chọn nguồn nào trả được bảng nhiều kỳ tốt nhất
        best_name, best_result = max(candidates, key=lambda item: _provider_result_score(item[1]))
        notes = [f"{n}: overview={len(r.overview)}, năm={len(r.annual)}, quý={len(r.quarterly)}, note={r.note}" for n, r in candidates]
        if errors:
            notes.extend(errors)
        best_result.note = f"Chọn {best_name}. " + " | ".join(notes)
        return best_result
    raise ValueError(f"Chế độ dữ liệu Tổng quan doanh nghiệp không hợp lệ: {_public_text(source)}")


@st.cache_data(show_spinner=False)
def _export_module1_crawler_cached(ticker: str, source: str, cache_dir: str, raw_dir: str) -> tuple[str, str, str, str]:
    result = _fetch_module1_crawler_result(ticker, source, raw_dir)
    return _export_provider_result_to_module2_cache(result, ticker, source, cache_dir)


@st.cache_data(show_spinner=False)
def _load_overview_cached(path: str, ticker: str):
    return load_overview_from_csv(path, ticker)


@st.cache_data(show_spinner=False)
def _load_timeseries_cached(path: str, ticker: str, period_type: str, limit: int) -> pd.DataFrame:
    return ensure_derived_metrics(load_timeseries_from_csv(path, ticker, period_type, limit))



def _set_active_module1_bundle(overview_csv: Path, year_csv: Path, quarter_csv: Path, label: str, ticker: str) -> None:
    """Dùng chung một bộ dữ liệu hoạt động cho Tổng quan doanh nghiệp và Định giá chuyên sâu trong multipage app."""
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


def _active_module1_bundle_for_ticker(ticker: str) -> tuple[Path, Path, Path, str] | None:
    """Ưu tiên dữ liệu đã được Tổng quan doanh nghiệp kích hoạt trong cùng app."""
    ticker = _safe_ticker(ticker)
    active_ticker = _safe_ticker(str(st.session_state.get("active_ticker", "")))
    paths = [st.session_state.get("active_overview_csv"), st.session_state.get("active_year_csv"), st.session_state.get("active_quarter_csv")]
    if active_ticker == ticker and all(p and Path(str(p)).exists() for p in paths):
        return Path(str(paths[0])), Path(str(paths[1])), Path(str(paths[2])), str(st.session_state.get("active_source_label", "Dữ liệu đã đồng bộ từ Tổng quan doanh nghiệp"))
    return None


def _existing_cache_bundle_for_ticker(ticker: str) -> tuple[Path, Path, Path, str] | None:
    """Tìm cache chuẩn mà Tổng quan doanh nghiệp/Định giá chuyên sâu đã tạo trước đó cho cùng mã."""
    ticker = _safe_ticker(ticker)
    roots = [
        DATA_CACHE_DIR / "fireant_vietstock" / ticker,
        DATA_CACHE_DIR / "fireant" / ticker,
        DATA_CACHE_DIR / "vietstock" / ticker,
        DATA_CACHE_DIR / "module1_crawler" / "fireant_plus_vietstock" / ticker,
        DATA_CACHE_DIR / "module1_crawler" / "fireant" / ticker,
        DATA_CACHE_DIR / "module1_crawler" / "vietstock" / ticker,
        DATA_CACHE_DIR / "financial_xlsm" / ticker,
    ]
    for root in roots:
        overview = root / "company_overview_sample.csv"
        year = root / "financial_timeseries_year.csv"
        quarter = root / "financial_timeseries_quarter.csv"
        if overview.exists() and year.exists() and quarter.exists():
            try:
                company, annual, quarterly = _load_csv_bundle(overview, year, quarter, ticker)
                if _has_real_financial_data(annual):
                    return overview, year, quarter, f"Cache Tổng quan doanh nghiệp đã đồng bộ: {root}"
            except Exception:
                continue
    return None


def _format_note_value(value: object) -> str:
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


# ===== V23.20: giữ lại thuật ngữ tài chính tiếng Anh như V23.15 =====
# Các thuật ngữ như Owner Earnings, FCF, Moat score, Low/Base/High/Weighted được giữ nguyên
# để đọc đúng bản chất phân tích. Hàm dưới đây chỉ là compatibility no-op cho code bảng.
def _vi_text(value: object) -> object:
    return value

def _vi_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    return df

# V23.33: bỏ block _build_row_note/_render_explainable_table cũ; chỉ dùng block mới ở dưới để note hoạt động ổn định.

def _load_csv_bundle(overview_csv: Path, year_csv: Path, quarter_csv: Path, ticker: str):
    company = _load_overview_cached(str(overview_csv), ticker)
    annual_raw = _load_timeseries_cached(str(year_csv), ticker, "Y", 12)
    quarterly = _load_timeseries_cached(str(quarter_csv), ticker, "Q", 24)
    annual = append_ttm_row(annual_raw, quarterly)
    return company, annual, quarterly


def _load_data(ticker: str, source: str) -> tuple[object, pd.DataFrame, pd.DataFrame, str, tuple[Path, Path, Path]]:
    ticker = _safe_ticker(ticker) or "DCM"

    if source == "Tự động từ dữ liệu tổng quan":
        # 0) Ưu tiên bộ dữ liệu đang hoạt động của Tổng quan doanh nghiệp trong cùng app.
        active = _active_module1_bundle_for_ticker(ticker)
        if active:
            overview_csv, year_csv, quarter_csv, label = active
            company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
            if _has_real_financial_data(annual):
                _set_active_module1_bundle(overview_csv, year_csv, quarter_csv, label + " | Định giá chuyên sâu dùng trực tiếp", ticker)
                return company, annual, quarterly, label + " | Định giá chuyên sâu dùng trực tiếp", (overview_csv, year_csv, quarter_csv)

        # 1) Nếu đã có cache Tổng quan doanh nghiệp/Định giá chuyên sâu cho đúng mã thì dùng ngay, không crawl lại.
        cached = _existing_cache_bundle_for_ticker(ticker)
        if cached:
            overview_csv, year_csv, quarter_csv, label = cached
            company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
            _set_active_module1_bundle(overview_csv, year_csv, quarter_csv, label, ticker)
            return company, annual, quarterly, label, (overview_csv, year_csv, quarter_csv)

        # 2) Không có cache thì tự gọi pipeline crawler Tổng quan doanh nghiệp.
        overview, year, quarter, label = _export_module1_crawler_cached(ticker, "FireAnt + Vietstock", str(DATA_CACHE_DIR), str(RAW_DIR))
        overview_csv, year_csv, quarter_csv = Path(overview), Path(year), Path(quarter)
        company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
        if _has_real_financial_data(annual):
            _set_active_module1_bundle(overview_csv, year_csv, quarter_csv, label + " | Auto-sync từ Định giá chuyên sâu", ticker)
            return company, annual, quarterly, label + " | Auto-sync từ Định giá chuyên sâu", (overview_csv, year_csv, quarter_csv)

        # 3) Fallback cuối: dữ liệu tích hợp, chỉ dùng nếu mã có dữ liệu thật.
        if BUNDLED_XLSM.exists():
            overview, year, quarter, label2 = _export_bundled_financial_cached(str(BUNDLED_XLSM), ticker, str(DATA_CACHE_DIR))
            overview_csv, year_csv, quarter_csv = Path(overview), Path(year), Path(quarter)
            company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
            if _has_real_financial_data(annual):
                _set_active_module1_bundle(overview_csv, year_csv, quarter_csv, label2 + " | fallback Financial", ticker)
                return company, annual, quarterly, label2 + " | fallback Financial", (overview_csv, year_csv, quarter_csv)
        return company, annual, quarterly, label, (Path(overview), Path(year), Path(quarter))

    elif source in {"FireAnt", "Vietstock", "FireAnt + Vietstock"}:
        overview, year, quarter, label = _export_module1_crawler_cached(ticker, source, str(DATA_CACHE_DIR), str(RAW_DIR))
        overview_csv, year_csv, quarter_csv = Path(overview), Path(year), Path(quarter)
        company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
        if _has_real_financial_data(annual):
            _set_active_module1_bundle(overview_csv, year_csv, quarter_csv, label + " | đồng bộ chủ động", ticker)
        return company, annual, quarterly, label, (overview_csv, year_csv, quarter_csv)
    elif source == "Financial tích hợp" and BUNDLED_XLSM.exists():
        overview, year, quarter, label = _export_bundled_financial_cached(str(BUNDLED_XLSM), ticker, str(DATA_CACHE_DIR))
        overview_csv, year_csv, quarter_csv = Path(overview), Path(year), Path(quarter)
        company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
        if _has_real_financial_data(annual):
            _set_active_module1_bundle(overview_csv, year_csv, quarter_csv, label + " | đồng bộ Financial", ticker)
        return company, annual, quarterly, label, (overview_csv, year_csv, quarter_csv)
    else:
        overview_csv, year_csv, quarter_csv = DEFAULT_OVERVIEW_CSV, DEFAULT_YEAR_CSV, DEFAULT_QUARTER_CSV
        label = "CSV mẫu tích hợp"
    company, annual, quarterly = _load_csv_bundle(overview_csv, year_csv, quarter_csv, ticker)
    return company, annual, quarterly, label, (overview_csv, year_csv, quarter_csv)

def _parse_num(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text or text in {"-", "--", "N/A", "None"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _style_table(df: pd.DataFrame):
    if df is None or df.empty:
        return df
    def styles(data: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame("", index=data.index, columns=data.columns)
        numeric_cols = []
        for col in data.columns:
            if any(k in col.lower() for k in ["giá", "mos", "điểm", "trọng số", "%", "vnd", "cp", "tỷ", "lần", "value", "score"]):
                numeric_cols.append(col)
        vals = []
        for col in numeric_cols:
            vals.extend([v for v in data[col].map(_parse_num).dropna().tolist()])
        max_pos = max([v for v in vals if v > 0], default=1.0)
        max_neg = abs(min([v for v in vals if v < 0], default=-1.0))
        for col in numeric_cols:
            for idx, raw in data[col].items():
                v = _parse_num(raw)
                if v is None:
                    continue
                if v < 0:
                    alpha = min(0.65, 0.12 + 0.53 * min(abs(v) / max_neg, 1))
                    out.loc[idx, col] = f"background-color: rgba(239,68,68,{alpha:.2f}); color:#7f1d1d;"
                elif v > 0:
                    alpha = min(0.55, 0.10 + 0.45 * min(v / max_pos, 1))
                    out.loc[idx, col] = f"background-color: rgba(16,185,129,{alpha:.2f}); color:#064e3b;"
        # Heatmap riêng cho các mức Moat level dạng chữ để không bị bỏ sót như 'Lợi thế khá'.
        for col in data.columns:
            cl = str(col).strip().lower()
            if cl in {"moat level", "mức moat", "moat_level"} or "moat level" in cl:
                for idx, raw in data[col].items():
                    txt = str(raw).strip().lower()
                    if not txt:
                        continue
                    if "rất mạnh" in txt or "very strong" in txt:
                        out.loc[idx, col] = "background-color:#0B7F75; color:#FFFFFF; font-weight:950;"
                    elif "mạnh" in txt or "strong" in txt:
                        out.loc[idx, col] = "background-color:#D1FAE5; color:#065F46; font-weight:900;"
                    elif "khá" in txt or "good" in txt:
                        out.loc[idx, col] = "background-color:#FFF4C7; color:#7A4B00; font-weight:900;"
                    elif "bình" in txt or "trung" in txt or "normal" in txt or "average" in txt:
                        out.loc[idx, col] = "background-color:#FEF3C7; color:#92400E; font-weight:850;"
                    elif "yếu" in txt or "không" in txt or "weak" in txt or "no moat" in txt:
                        out.loc[idx, col] = "background-color:#FEE2E2; color:#991B1B; font-weight:850;"
        return out
    fmt = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            low = str(col).lower()
            if str(col).strip().upper() in {"STT", "#"}:
                fmt[col] = "{:,.0f}"
            elif "%" in str(col) or "mos" in low or "điểm" in low or "trọng số" in low:
                fmt[col] = "{:,.1f}"
            elif "giá" in low or "cp" in low:
                fmt[col] = "{:,.0f}"
            else:
                fmt[col] = "{:,.1f}"
    return df.style.format(fmt, na_rep="").apply(styles, axis=None)


def _show_table(df: pd.DataFrame, height: int | None = 520) -> None:
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
    else:
        safe_df = _hide_source_columns(df)
        st.dataframe(_style_table(safe_df), use_container_width=True, height=(height or 520), hide_index=True)


def _render_static_html_table(df: pd.DataFrame, table_kind: str = "", height: int = 520) -> None:
    """Render a non-clickable HTML table using the same visual language as explainable tables.

    Used for small summary tables where the user needs the standard table format but not row notes.
    """
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
        return
    display_df = _vi_dataframe_for_display(df.copy())
    if "Note" in display_df.columns:
        display_df = display_df.drop(columns=["Note"], errors="ignore")
    display_df = display_df.drop(columns=[c for c in ["Nguồn/logic", "Nguồn / logic"] if c in display_df.columns], errors="ignore")

    table_id = "static_tbl_" + str(abs(hash((table_kind, tuple(display_df.columns), len(display_df), APP_VERSION))))[0:10]
    header_cells = []
    for c in display_df.columns:
        hcls = "summary-layer-header" if table_kind == "financial_manipulation_summary" and str(c).strip() == "Lớp" else ""
        header_cells.append(f"<th class='{hcls}'>{html.escape(str(c))}</th>")
    headers = "".join(header_cells)
    rows_html = []
    for _, row in display_df.iterrows():
        tds = []
        for c in display_df.columns:
            val = row.get(c)
            text = _format_note_value(val)
            cls = _signal_class(val) if c in {"Tín hiệu", "Mức độ", "Mức cảnh báo", "Tình trạng", "Khuyến nghị", "Kết luận", "Kết luận theo mã", "Moat level", "Mức moat", "Độ tin cậy", "Đánh giá sơ bộ", "Loại lợi thế", "Vai trò"} else ""
            num = _parse_num(val)
            if not cls and num is not None and any(k in str(c).lower() for k in ["giá", "mos", "điểm", "điểm nhiệt", "trọng", "%", "value", "score"]):
                cls = "pos" if num > 0 else "neg" if num < 0 else ""
            cell_classes = [cls] if cls else []
            if table_kind == "financial_manipulation_summary" and str(c).strip() == "Lớp":
                cell_classes.append("summary-layer")
            tds.append(f"<td class='{' '.join(cell_classes)}'>{html.escape(text)}</td>")
        rows_html.append(f"<tr>{''.join(tds)}</tr>")

    # V23.61: bảng tổng hợp thao túng tài chính chỉ có 4 lớp nên tự tính chiều cao gọn,
    # không để dư khoảng trắng lớn làm phần phân tích từng lớp bị đẩy xuống xa.
    if table_kind == "financial_manipulation_summary":
        component_height = max(300, min(int(height), 92 + 78 * max(len(display_df), 1)))
    else:
        component_height = max(320, int(height))
    html_doc = f"""
    <div class='wrap'>
      <table id='{table_id}'>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    <style>
      .wrap {{border:1px solid #e2e8f0; border-radius:12px; overflow:visible; background:#FFFFFF;}}
      table {{border-collapse:collapse; width:100%; font-family: system-ui, -apple-system, Segoe UI, sans-serif; font-size:13px; table-layout:auto;}}
      th {{background:#EAF7F1; color:#123D3A; text-align:left; border-bottom:1px solid #e2e8f0; padding:8px; font-weight:950; box-shadow:0 2px 0 rgba(11,127,117,.18); white-space:nowrap;}}
      td {{border-bottom:1px solid #edf2f7; padding:7px 8px; vertical-align:top; color:#123D3A; line-height:1.38;}}
      th.summary-layer-header, td.summary-layer {{font-weight:1000 !important; color:#075E54 !important; background:linear-gradient(135deg,#ECFDF5 0%,#FFF8D6 100%) !important; white-space:nowrap;}}
      tbody tr:nth-child(even) td {{background:#FBFDFB;}}
      tr:hover td {{background:#F7FBF8;}}
      td.pos {{background:rgba(16,185,129,.11); color:#064e3b; font-weight:600;}}
      td.neg {{background:rgba(239,68,68,.11); color:#7f1d1d; font-weight:600;}}
      td.sig-red-strong {{background:#FECACA !important; color:#7F1D1D !important; font-weight:900; border-left:5px solid #DC2626;}}
      td.sig-red {{background:#FEE2E2 !important; color:#991B1B !important; font-weight:800; border-left:4px solid #EF4444;}}
      td.sig-purple-strong {{background:#E9D5FF !important; color:#581C87 !important; font-weight:900; border-left:5px solid #7E22CE;}}
      td.sig-purple {{background:#F3E8FF !important; color:#6B21A8 !important; font-weight:800; border-left:4px solid #A855F7;}}
      td.sig-yellow {{background:#FEF3C7 !important; color:#92400E !important; font-weight:800; border-left:4px solid #F59E0B;}}
      td.heat-green-strong {{background:#047857 !important; color:#FFFFFF !important; font-weight:950 !important;}}
      td.heat-green {{background:#A7F3D0 !important; color:#064E3B !important; font-weight:900 !important;}}
      td.heat-yellow {{background:#FEF3C7 !important; color:#92400E !important; font-weight:900 !important;}}
      td.heat-orange {{background:#FED7AA !important; color:#9A3412 !important; font-weight:900 !important;}}
      td.heat-red {{background:#FECACA !important; color:#7F1D1D !important; font-weight:900 !important;}}
    </style>
    """
    components.html(html_doc, height=component_height, scrolling=False)


def _has_real_financial_data(annual_df: pd.DataFrame) -> bool:
    if annual_df is None or annual_df.empty:
        return False
    core_cols = ["revenue_bil", "net_profit_bil", "equity_bil", "total_assets_bil", "cfo_bil", "owner_earnings_bil"]
    existing = [c for c in core_cols if c in annual_df.columns]
    if not existing:
        return False
    return pd.to_numeric(annual_df[existing].stack(), errors="coerce").notna().sum() >= 5



# ===== V23.9: note engine theo từng doanh nghiệp, số liệu và tài liệu nguồn =====
def _ctx() -> dict:
    obj = st.session_state.get("module2_note_context", {})
    return obj if isinstance(obj, dict) else {}


def _series(df: pd.DataFrame, col: str) -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _latest_dict(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    if "period" in df.columns:
        ttm = df[df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        if not ttm.empty:
            return ttm.iloc[-1].to_dict()
    return df.iloc[-1].to_dict()


def _recent_median2(df: pd.DataFrame, col: str, n: int = 5) -> float | None:
    s = _series(df, col).dropna().tail(n)
    return float(s.median()) if not s.empty else None


def _recent_mean2(df: pd.DataFrame, col: str, n: int = 5) -> float | None:
    s = _series(df, col).dropna().tail(n)
    return float(s.mean()) if not s.empty else None


def _recent_positive_ratio2(df: pd.DataFrame, col: str, n: int = 5) -> float | None:
    s = _series(df, col).dropna().tail(n)
    return float((s > 0).mean()) if not s.empty else None


def _cagr2(df: pd.DataFrame, col: str, years: int = 5) -> float | None:
    s = _series(df, col).dropna().tail(years + 1)
    if len(s) < 2:
        return None
    start, end = float(s.iloc[0]), float(s.iloc[-1])
    periods = len(s) - 1
    if start <= 0 or end <= 0 or periods <= 0:
        return None
    return (end / start) ** (1 / periods) - 1


def _cv2(df: pd.DataFrame, col: str, n: int = 7) -> float | None:
    s = _series(df, col).dropna().tail(n)
    s = s[s.abs() > 1e-9]
    if len(s) < 3 or abs(float(s.mean())) < 1e-9:
        return None
    return float(s.std(ddof=0) / abs(s.mean()))


def _share_count_from_context(company: object, annual_df: pd.DataFrame) -> float | None:
    latest = _latest_dict(annual_df)
    direct = _parse_num(latest.get("shares_outstanding_mil"))
    overview = _parse_num(getattr(company, "shares_outstanding_mil", None))
    np_bil = _parse_num(latest.get("net_profit_bil"))
    eps_vnd = _parse_num(latest.get("eps_vnd"))
    inferred = None
    if np_bil is not None and eps_vnd and eps_vnd > 0:
        inferred = np_bil * 1000 / eps_vnd
    if direct and direct > 0:
        return direct
    if inferred and inferred > 0:
        if overview and overview > 0 and abs(inferred - overview) / max(overview, 1e-9) <= 0.30:
            return overview
        return inferred
    return overview if overview and overview > 0 else None


def _per_share_bil(value_bil: float | None, shares_mil: float | None) -> float | None:
    if value_bil is None or shares_mil is None or shares_mil <= 0:
        return None
    return value_bil * 1000 / shares_mil



def _signal_class(value: object) -> str:
    s = str(value or "").strip().lower()
    if not s or s in {"nan", "none", "n/a", "na", "-"}:
        return ""
    # Heatmap đầy đủ cho Moat level / tín hiệu chữ.
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
    # Độ tin cậy.
    if s in {"cao", "high"}:
        return "sig-purple-strong"
    if s in {"trung bình", "medium", "moderate"}:
        return "sig-yellow"
    if s in {"thấp", "low", "không có dữ liệu", "no data"}:
        return "sig-red"
    # Rủi ro/cảnh báo.
    red_terms = ["cảnh báo", "rủi ro", "rủi ro chu kỳ", "yếu", "âm", "suy giảm", "không đạt", "chưa đạt", "không phù hợp", "thiếu dữ liệu", "không có dữ liệu", "chưa đủ", "chưa có", "lỗi", "đòn bẩy cao", "xấu"]
    if any(k in s for k in red_terms):
        if any(k in s for k in ["nghiêm trọng", "rất", "không đạt", "chưa đạt", "rủi ro", "yếu", "xấu"]):
            return "sig-red-strong"
        return "sig-red"
    # Tín hiệu tích cực.
    purple_terms = ["tốt", "đạt", "mạnh", "an toàn", "hiệu quả", "tích cực", "vượt", "cao", "bền", "ổn định", "có runway", "runway", "pricing power", "có bằng chứng", "quality", "cash tốt", "tạo giá trị"]
    if any(k in s for k in purple_terms):
        if any(k in s for k in ["rất", "mạnh", "vượt", "tốt", "cao", "bền"]):
            return "sig-purple-strong"
        return "sig-purple"
    # Theo dõi/cần kiểm chứng.
    yellow_terms = ["theo dõi", "cần kiểm", "cần soi", "cần xác minh", "cần kiểm chứng", "cần bổ sung", "cần tìm", "cẩn trọng", "trung bình", "bình thường", "khá", "chưa rõ", "hạn chế", "gần vùng", "chờ", "kiểm chứng", "chưa kết luận"]
    if any(k in s for k in yellow_terms):
        return "sig-yellow"
    return ""


def _money(value: object, suffix: str = "") -> str:
    n = _parse_num(value)
    if n is None:
        return "N/A"
    return f"{n:,.0f}{suffix}"


def _pct(value: object) -> str:
    n = _parse_num(value)
    if n is None:
        return "N/A"
    return f"{n:,.1f}%"


def _ratio(value: object) -> str:
    n = _parse_num(value)
    if n is None:
        return "N/A"
    return f"{n:,.1f} lần"


def _bil(value: object) -> str:
    n = _parse_num(value)
    if n is None:
        return "N/A"
    return f"{n:,.0f} tỷ đồng"


def _period_label(annual_df: pd.DataFrame) -> str:
    latest = _latest_dict(annual_df)
    return str(latest.get("period") or latest.get("year") or "kỳ mới nhất/TTM")


def _source_principle_text(kind: str, cls_name: str) -> str:
    base = {
        "owner": "Cơ sở tư duy: Buffett xem Owner Earnings là chỉ tiêu phù hợp cho định giá chủ sở hữu: lợi nhuận báo cáo + khấu hao/phi tiền mặt - capex duy trì cần thiết để giữ vị thế cạnh tranh và sản lượng. Vì vậy với doanh nghiệp vốn nhẹ/dòng tiền thật, OE được ưu tiên; với doanh nghiệp đang mở rộng capex mạnh, cần tách capex duy trì và capex tăng trưởng.",
        "fcf": "Cơ sở tư duy: FCF là kiểm tra dòng tiền, nhưng không tự động thay thế Owner Earnings. Nếu FCF âm do đầu tư mở rộng tạo ROIC cao thì không kết luận xấu ngay; nếu FCF âm kéo dài trong khi ROIC/biên lợi nhuận giảm thì phải cảnh báo chất lượng lợi nhuận.",
        "epv": "Cơ sở tư duy: Graham/Dodd đặt trọng tâm vào earning power và sự khác biệt giữa giá và giá trị. EPS/LNST phải được chuẩn hóa qua nhiều kỳ, đặc biệt với doanh nghiệp chu kỳ hoặc có lợi nhuận bất thường.",
        "asset": "Cơ sở tư duy: Graham ưu tiên biên an toàn và giá trị tài sản khi doanh nghiệp rơi vào nhóm asset play/deep value. Tài sản thanh khoản được haircut bảo thủ để bảo vệ downside, không dùng book value thô khi chất lượng tài sản chưa được kiểm tra.",
        "porter": "Cơ sở tư duy: Porter không xem lợi thế cạnh tranh là khẩu hiệu chung. Moat phải truy về các hoạt động cụ thể trong chuỗi giá trị tạo giá trị cho khách hàng hoặc giảm chi phí, và phải có bằng chứng định lượng/định tính của chính doanh nghiệp.",
        "risk": "Cơ sở tư duy: Howard Marks nhấn mạnh kiểm soát rủi ro và dải kết quả có thể xảy ra. Vì vậy note dùng Bear/Base/Bull và số liệu thực tế của doanh nghiệp thay vì một kết luận cố định.",
        "mos": "Cơ sở tư duy: Graham/Li Lu coi margin of safety là trung tâm vì giá trị chỉ là ước tính. MOS phải phụ thuộc loại doanh nghiệp, độ tin cậy dòng tiền, tài sản bảo vệ downside và rủi ro chu kỳ của chính mã đang phân tích.",
    }
    txt = base.get(kind, base["mos"])
    if "Cyclical" in cls_name:
        txt += " Với doanh nghiệp có tính chu kỳ, hệ thống giảm ý nghĩa của lợi nhuận 1 năm và ưu tiên trung vị nhiều kỳ/kiểm tra biên an toàn cao hơn."
    elif "Quality" in cls_name:
        txt += " Với doanh nghiệp chất lượng/compounder, hệ thống ưu tiên ROIC, Owner Earnings và khả năng tái đầu tư; tuy nhiên vẫn kiểm tra CFO/LNST và FCF để tránh lợi nhuận kế toán."
    elif "Asset" in cls_name:
        txt += " Với doanh nghiệp asset play/deep value, hệ thống ưu tiên tài sản thanh khoản ròng và downside protection trước khi tin vào tăng trưởng."
    elif "Financial" in cls_name:
        txt += " Với ngân hàng/bảo hiểm/tài chính, hệ thống không dùng FCF/VLĐ tổng quát làm lõi, mà ưu tiên P/B, ROE và chất lượng tài sản/vốn."
    return txt


def _company_snapshot() -> str:
    c = _ctx().get("company")
    annual = _ctx().get("annual_df", pd.DataFrame())
    cls = _ctx().get("classification")
    latest = _latest_dict(annual)
    period = _period_label(annual)
    roic = _recent_median2(annual, "roic_standard_pct") or _recent_median2(annual, "roic_pct")
    roe = _recent_median2(annual, "roe_actual_pct") or _recent_median2(annual, "roe_pct")
    cfo_np = _recent_median2(annual, "cfo_to_net_profit")
    fcf_np = _recent_median2(annual, "fcf_to_net_profit")
    rev_cagr = _cagr2(annual, "revenue_bil")
    profit_cv = _cv2(annual, "net_profit_bil")
    price = _parse_num(getattr(c, "current_price", None)) if c is not None else None
    parts = [
        f"Doanh nghiệp: {getattr(c, 'ticker', '')} - {getattr(c, 'company_name', '')}",
        f"Kỳ dữ liệu dùng chính: {period}; bộ dữ liệu: {_public_text(_ctx().get('source_label', 'N/A'))}",
        f"Phân loại hiện tại: {getattr(cls, 'company_type', 'N/A')} | Giá hiện tại: {_money(price, ' đ/cp')}",
        f"Tín hiệu chính của chính doanh nghiệp: ROIC trung vị {_pct(roic)}, ROE trung vị {_pct(roe)}, CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}, CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}, độ biến động LNST {_pct(None if profit_cv is None else profit_cv*100)}.",
    ]
    return "\n".join(parts)


def _module2_numeric_evidence_for_note(topic: str = "") -> str:
    """Return concrete metrics used in click-notes so explanation is not generic."""
    annual = _ctx().get("annual_df", pd.DataFrame())
    latest = _latest_dict(annual)
    topic_l = str(topic or "").lower()
    period = _period_label(annual)
    roic = _recent_median2(annual, "roic_standard_pct") or _recent_median2(annual, "roic_pct")
    roe = _recent_median2(annual, "roe_actual_pct") or _recent_median2(annual, "roe_pct")
    gross = _recent_median2(annual, "gross_margin_pct")
    net = _recent_median2(annual, "net_margin_pct")
    ebit = _recent_median2(annual, "ebit_margin_pct")
    cfo_np = _recent_median2(annual, "cfo_to_net_profit")
    fcf_np = _recent_median2(annual, "fcf_to_net_profit")
    fcf_pos = _recent_positive_ratio2(annual, "free_cash_flow_bil")
    rev_cagr = _cagr2(annual, "revenue_bil")
    np_cagr = _cagr2(annual, "net_profit_bil")
    oe_cagr = _cagr2(annual, "owner_earnings_bil")
    profit_cv = _cv2(annual, "net_profit_bil")
    margin_cv = _cv2(annual, "gross_margin_pct")
    ccc = _recent_median2(annual, "cash_conversion_cycle_days")
    inv_turn = _recent_median2(annual, "inventory_turnover")
    debt_ebitda = _parse_num(latest.get("net_debt_to_ebitda"))
    net_debt_equity = _parse_num(latest.get("net_debt_to_equity"))
    wacc = _recent_median2(annual, "wacc_pct")
    capex = _recent_median2(annual, "capex_bil")
    fcf = _recent_median2(annual, "free_cash_flow_bil")
    oe = _recent_median2(annual, "owner_earnings_bil")
    rev = _recent_median2(annual, "revenue_bil")
    np = _recent_median2(annual, "net_profit_bil")
    total_inv = _recent_median2(annual, "total_investment_bil")
    lines = [f"- Kỳ/chuỗi dữ liệu dùng: {period}."]
    if any(k in topic_l for k in ["tái đầu tư", "runway", "compounder"]):
        lines += [
            f"- Tăng trưởng: CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}, CAGR LNST {_pct(None if np_cagr is None else np_cagr*100)}, CAGR Owner Earnings {_pct(None if oe_cagr is None else oe_cagr*100)}.",
            f"- Hiệu quả vốn: ROIC trung vị {_pct(roic)}, WACC trung vị {_pct(wacc)}, ROE trung vị {_pct(roe)}.",
            f"- Dòng tiền/tái đầu tư: CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}, FCF trung vị {_bil(fcf)}, Owner Earnings trung vị {_bil(oe)}, Capex trung vị {_bil(capex)}, tổng đầu tư trung vị {_bil(total_inv)}.",
            f"- Diễn giải cụ thể: nếu doanh thu/LNST tăng nhưng ROIC không cao hơn WACC hoặc FCF/LNST thấp, tăng trưởng có thể đang tiêu tiền/đòn bẩy chứ chưa chắc tạo giá trị.",
        ]
    elif any(k in topic_l for k in ["dòng tiền", "cash", "fcf", "owner"]):
        lines += [
            f"- Chất lượng tiền: CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}, tỷ lệ kỳ FCF dương {_pct(None if fcf_pos is None else fcf_pos*100)}.",
            f"- Quy mô tiền: CFO kỳ mới nhất {_bil(latest.get('cfo_bil'))}, FCF kỳ mới nhất {_bil(latest.get('free_cash_flow_bil'))}, Owner Earnings kỳ mới nhất {_bil(latest.get('owner_earnings_bil'))}, LNST kỳ mới nhất {_bil(latest.get('net_profit_bil'))}.",
        ]
    elif any(k in topic_l for k in ["cost", "chi phí", "vận hành", "logistics", "chuỗi giá trị"]):
        lines += [
            f"- Hiệu quả hoạt động: biên gộp trung vị {_pct(gross)}, biên EBIT {_pct(ebit)}, biên ròng {_pct(net)}, biến động biên gộp {_pct(None if margin_cv is None else margin_cv*100)}.",
            f"- Vốn lưu động/vận hành: CCC {_money(ccc, ' ngày')}, vòng quay HTK {_ratio(inv_turn)}, CFO/LNST {_ratio(cfo_np)}.",
        ]
    elif any(k in topic_l for k in ["cấu trúc", "chu kỳ", "ngành"]):
        lines += [
            f"- Chu kỳ: độ biến động LNST {_pct(None if profit_cv is None else profit_cv*100)}, CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}, CAGR LNST {_pct(None if np_cagr is None else np_cagr*100)}.",
            f"- Biên lợi nhuận: biên gộp {_pct(gross)}, biên ròng {_pct(net)}; nợ/EBITDA {_ratio(debt_ebitda)}.",
        ]
    elif any(k in topic_l for k in ["quản trị", "phân bổ vốn", "an toàn"]):
        lines += [
            f"- Phân bổ vốn: ROIC {_pct(roic)}, WACC {_pct(wacc)}, ROE {_pct(roe)}, Capex {_bil(capex)}, tổng đầu tư {_bil(total_inv)}.",
            f"- An toàn tài chính: nợ ròng/EBITDA {_ratio(debt_ebitda)}, nợ ròng/VCSH {_ratio(net_debt_equity)}, CFO/LNST {_ratio(cfo_np)}.",
        ]
    else:
        lines += [
            f"- Sinh lời: ROIC {_pct(roic)}, ROE {_pct(roe)}, biên gộp {_pct(gross)}, biên ròng {_pct(net)}.",
            f"- Tăng trưởng & dòng tiền: doanh thu trung vị {_bil(rev)}, LNST trung vị {_bil(np)}, CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}, CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}.",
        ]
    return "\n".join(lines)


def _valuation_method_note(rowd: dict) -> str:
    c = _ctx().get("company")
    annual = _ctx().get("annual_df", pd.DataFrame())
    assumptions = _ctx().get("assumptions", {})
    cls = _ctx().get("classification")
    cls_name = getattr(cls, "company_type", "N/A")
    latest = _latest_dict(annual)
    method = str(rowd.get("Phương pháp", ""))
    shares = _share_count_from_context(c, annual)
    current_price = _parse_num(rowd.get("Giá hiện tại")) or (_parse_num(getattr(c, "current_price", None)) if c is not None else None)
    intrinsic = _parse_num(rowd.get("Giá trị nội tại/cp"))
    mos = _parse_num(rowd.get("MOS hiện tại %"))
    lines = [_company_snapshot(), "", f"CHỈ TIÊU/PHƯƠNG PHÁP ĐANG CHỌN: {method}"]
    if "Earnings Power" in method:
        net_profit_norm = _recent_median2(annual, "net_profit_bil") or _parse_num(latest.get("net_profit_bil"))
        eps_norm = _recent_median2(annual, "eps_vnd") or _per_share_bil(net_profit_norm, shares) or (_parse_num(getattr(c, "eps", None)) if c is not None else None)
        target_pe = assumptions.get("target_pe_quality", 14.0) if cls_name == "Quality Compounder" else assumptions.get("target_pe_normal", assumptions.get("target_pe_default", 10.0))
        calc = eps_norm * target_pe if eps_norm is not None else None
        lines += [
            "Cách tính theo dữ liệu doanh nghiệp:",
            f"- LNST chuẩn hóa = trung vị các kỳ gần đây = {_bil(net_profit_norm)}.",
            f"- Số cổ phiếu pha loãng/ước tính = {_ratio(shares)} triệu cp. Nếu file không có cổ phiếu, hệ thống suy ra từ LNST và EPS.",
            f"- EPS chuẩn hóa = LNST chuẩn hóa / số cổ phiếu = {_money(eps_norm, ' đ/cp')}.",
            f"- P/E mục tiêu áp dụng cho {cls_name} = {_ratio(target_pe)}.",
            f"- Giá trị tính lại = EPS chuẩn hóa x P/E mục tiêu = {_money(calc, ' đ/cp')}; giá trị đang dùng trong bảng = {_money(intrinsic, ' đ/cp')}.",
            f"- MOS hiện tại = (giá trị - giá thị trường) / giá trị = {_pct(mos)} với giá hiện tại {_money(current_price, ' đ/cp')}.",
            _source_principle_text("epv", cls_name),
        ]
    elif "Owner Earnings" in method:
        oe_norm = _recent_median2(annual, "owner_earnings_bil") or _parse_num(latest.get("owner_earnings_bil"))
        oeps = _recent_median2(annual, "oeps_vnd") or _per_share_bil(oe_norm, shares)
        rev_cagr = _cagr2(annual, "revenue_bil") or 0.0
        oe_cagr = _cagr2(annual, "owner_earnings_bil")
        growth_base = min(max(oe_cagr if oe_cagr is not None else rev_cagr, 0.0), assumptions.get("base_growth_cap_pct", 8.0) / 100)
        discount = assumptions.get("required_return", assumptions.get("required_return_pct", 13.0) / 100)
        terminal = assumptions.get("terminal_growth", assumptions.get("terminal_growth_pct", 3.0) / 100)
        calc = oeps * (1 + growth_base) / max(discount - terminal, 0.04) if oeps is not None else None
        lines += [
            "Cách tính theo dữ liệu doanh nghiệp:",
            f"- Owner Earnings chuẩn hóa = trung vị các kỳ gần đây = {_bil(oe_norm)}.",
            f"- OEPS chuẩn hóa = OE / số cổ phiếu = {_money(oeps, ' đ/cp')}.",
            f"- Tăng trưởng cơ sở lấy theo OE CAGR nếu có, nếu không dùng CAGR doanh thu, sau đó chặn trần = {_pct(growth_base*100)}.",
            f"- Required return = {_pct(discount*100)}, terminal growth = {_pct(terminal*100)}.",
            f"- Giá trị tính lại = OEPS x (1+g) / (r-g) = {_money(calc, ' đ/cp')}; bảng đang dùng = {_money(intrinsic, ' đ/cp')}.",
            f"- Kiểm tra phù hợp: CFO/LNST {_ratio(_recent_median2(annual, 'cfo_to_net_profit'))}, FCF/LNST {_ratio(_recent_median2(annual, 'fcf_to_net_profit'))}. Nếu 2 chỉ tiêu này thấp, OE phải bị giảm độ tin cậy.",
            _source_principle_text("owner", cls_name),
        ]
    elif "FCF" in method:
        cfo = _recent_median2(annual, "cfo_bil")
        capex = _recent_median2(annual, "capex_bil")
        fcf_norm = _recent_median2(annual, "free_cash_flow_bil") or _parse_num(latest.get("free_cash_flow_bil"))
        fcf_ps = _per_share_bil(fcf_norm, shares)
        discount = assumptions.get("required_return", assumptions.get("required_return_pct", 13.0) / 100)
        conservative_growth = assumptions.get("conservative_growth_pct", 0.0) / 100
        calc = fcf_ps / max(discount - conservative_growth, 0.06) if fcf_ps is not None and fcf_ps > 0 else None
        lines += [
            "Cách tính theo dữ liệu doanh nghiệp:",
            f"- CFO chuẩn hóa = {_bil(cfo)}; Capex chuẩn hóa = {_bil(capex)}.",
            f"- FCF chuẩn hóa = CFO - Capex = {_bil(fcf_norm)}.",
            f"- FCF/cp = {_money(fcf_ps, ' đ/cp')}.",
            f"- Suất vốn hóa bảo thủ = required return - tăng trưởng bảo thủ = {_pct((discount-conservative_growth)*100)}.",
            f"- Giá trị tính lại = FCF/cp / suất vốn hóa = {_money(calc, ' đ/cp')}; bảng đang dùng = {_money(intrinsic, ' đ/cp')}.",
            f"- Trường hợp doanh nghiệp đang mở rộng: nếu capex lớn nhưng ROIC vẫn cao ({_pct(_recent_median2(annual, 'roic_standard_pct') or _recent_median2(annual, 'roic_pct'))}), FCF âm không nhất thiết xấu; nếu FCF âm và ROIC giảm thì cảnh báo chất lượng tăng trưởng.",
            _source_principle_text("fcf", cls_name),
        ]
    elif "Book Value" in method or "P-B" in method:
        equity = _parse_num(latest.get("equity_bil"))
        bvps = _per_share_bil(equity, shares)
        target_pb = assumptions.get("target_pb_bank", 1.2) if cls_name == "Financial / Bank / Insurance" else 1.0
        calc = bvps * target_pb if bvps is not None else None
        lines += [
            "Cách tính theo dữ liệu doanh nghiệp:",
            f"- Vốn chủ sở hữu kỳ mới nhất = {_bil(equity)}.",
            f"- Số cổ phiếu = {_ratio(shares)} triệu cp.",
            f"- BVPS = vốn chủ sở hữu / cổ phiếu = {_money(bvps, ' đ/cp')}.",
            f"- P/B mục tiêu áp dụng cho {cls_name} = {_ratio(target_pb)}.",
            f"- Giá trị tính lại = BVPS x P/B mục tiêu = {_money(calc, ' đ/cp')}; bảng đang dùng = {_money(intrinsic, ' đ/cp')}.",
            f"- Cần đọc cùng chất lượng tài sản: tổng tài sản {_bil(latest.get('total_assets_bil'))}, nợ phải trả {_bil(latest.get('liabilities_bil'))}, ROE trung vị {_pct(_recent_median2(annual, 'roe_actual_pct') or _recent_median2(annual, 'roe_pct'))}.",
            _source_principle_text("asset", cls_name),
        ]
    elif "Net Liquid" in method or "NCAV" in method:
        cash = _parse_num(latest.get("cash_equivalents_bil")) or 0.0
        sti = _parse_num(latest.get("short_term_investments_bil")) or 0.0
        recv = _parse_num(latest.get("accounts_receivable_bil")) or 0.0
        inv = _parse_num(latest.get("inventory_bil")) or 0.0
        liab = _parse_num(latest.get("liabilities_bil")) or _parse_num(latest.get("current_liabilities_bil")) or 0.0
        h_cash = assumptions.get("asset_haircut_cash_pct", 0.0)
        h_recv = assumptions.get("asset_haircut_receivables_pct", 25.0)
        h_inv = assumptions.get("asset_haircut_inventory_pct", 50.0)
        nlav = cash*(1-h_cash/100) + sti*(1-h_cash/100) + recv*(1-h_recv/100) + inv*(1-h_inv/100) - liab
        calc = _per_share_bil(nlav, shares) if nlav > 0 else None
        lines += [
            "Cách tính theo dữ liệu doanh nghiệp:",
            f"- Tiền = {_bil(cash)}, đầu tư ngắn hạn = {_bil(sti)}, phải thu = {_bil(recv)}, tồn kho = {_bil(inv)}, nợ phải trả = {_bil(liab)}.",
            f"- Haircut áp dụng: tiền/ĐT ngắn hạn {h_cash:.0f}%, phải thu {h_recv:.0f}%, tồn kho {h_inv:.0f}%.",
            f"- NLA/NCAV bảo thủ = tiền + ĐT ngắn hạn + phải thu sau haircut + tồn kho sau haircut - nợ = {_bil(nlav)}.",
            f"- NLA/NCAV/cp = {_money(calc, ' đ/cp')}; bảng đang dùng = {_money(intrinsic, ' đ/cp')}.",
            f"- Nếu NLA âm, phương pháp này chỉ đóng vai trò kiểm tra downside, không dùng làm fair value chính.",
            _source_principle_text("asset", cls_name),
        ]
    else:
        lines += [
            f"Vai trò: {_format_note_value(rowd.get('Vai trò'))}; trọng số {_pct(rowd.get('Trọng số %'))}; độ tin cậy {_format_note_value(rowd.get('Độ tin cậy'))}.",
            f"Cơ sở tính trong bảng: {_format_note_value(rowd.get('Cơ sở tính'))}.",
            f"Cảnh báo: {_format_note_value(rowd.get('Cảnh báo'))}.",
        ]
    return "\n".join(lines)


def _valuation_range_note(rowd: dict) -> str:
    valuation = _ctx().get("valuation_df", pd.DataFrame())
    rng = _ctx().get("value_range")
    c = _ctx().get("company")
    cls = _ctx().get("classification")
    method_lines = []
    if isinstance(valuation, pd.DataFrame) and not valuation.empty:
        valid = valuation[pd.to_numeric(valuation.get("Giá trị nội tại/cp"), errors="coerce").notna()].copy()
        valid = valid[pd.to_numeric(valid.get("Giá trị nội tại/cp"), errors="coerce") > 0]
        for _, r in valid.iterrows():
            method_lines.append(f"- {r.get('Phương pháp')}: giá trị {_money(r.get('Giá trị nội tại/cp'), ' đ/cp')}, trọng số {_pct(r.get('Trọng số %'))}, vai trò {r.get('Vai trò')}")
    current_price = _parse_num(getattr(c, "current_price", None)) if c is not None else None
    chosen = str(rowd.get("Chỉ tiêu", ""))
    return "\n".join([
        _company_snapshot(),
        "",
        f"DẢI GIÁ TRỊ ĐANG CHỌN: {chosen} = {_money(rowd.get('Giá trị/cp'), ' đ/cp')}",
        f"- Low = phân vị 25% của các phương pháp hợp lệ: {_money(getattr(rng, 'low_vnd', None), ' đ/cp')}.",
        f"- Base/Median = trung vị các phương pháp hợp lệ: {_money(getattr(rng, 'base_vnd', None), ' đ/cp')}.",
        f"- High = phân vị 75% của các phương pháp hợp lệ: {_money(getattr(rng, 'high_vnd', None), ' đ/cp')}.",
        f"- Weighted = trung bình trọng số theo vai trò/phù hợp với {getattr(cls, 'company_type', 'N/A')}: {_money(getattr(rng, 'weighted_vnd', None), ' đ/cp')}.",
        f"- MOS hiện tại = (Weighted - giá thị trường) / Weighted = {_pct(getattr(rng, 'mos_to_weighted_pct', None))}; giá thị trường {_money(current_price, ' đ/cp')}.",
        f"- MOS yêu cầu đang chọn = {_pct(_ctx().get('target_mos_pct'))}; giá mua tối đa theo giá trị trọng số = {_money(getattr(rng, 'weighted_vnd', None) * (1 - float(_ctx().get('target_mos_pct', 30)) / 100) if getattr(rng, 'weighted_vnd', None) else None, ' đ/cp')}.",
        "Các phương pháp đang tham gia dải giá trị:",
        "\n".join(method_lines) if method_lines else "- Chưa có phương pháp hợp lệ.",
        _source_principle_text("mos", getattr(cls, 'company_type', 'N/A')),
    ])


def _moat_note(rowd: dict) -> str:
    annual = _ctx().get("annual_df", pd.DataFrame())
    cls = _ctx().get("classification")
    group = str(rowd.get("Nhóm Porter/Moat", ""))
    roic = _recent_median2(annual, "roic_standard_pct") or _recent_median2(annual, "roic_pct")
    roe = _recent_median2(annual, "roe_actual_pct") or _recent_median2(annual, "roe_pct")
    gross = _recent_median2(annual, "gross_margin_pct")
    ebit = _recent_median2(annual, "ebit_margin_pct")
    cfo_np = _recent_median2(annual, "cfo_to_net_profit")
    fcf_np = _recent_median2(annual, "fcf_to_net_profit")
    fcf_pos = _recent_positive_ratio2(annual, "free_cash_flow_bil")
    rev_cagr = _cagr2(annual, "revenue_bil")
    oe_cagr = _cagr2(annual, "owner_earnings_bil")
    ccc = _recent_median2(annual, "cash_conversion_cycle_days")
    inv_turn = _recent_median2(annual, "inventory_turnover")
    sga_ratio = None
    rev = _recent_median2(annual, "revenue_bil")
    if rev and rev > 0:
        sga_ratio = ((abs(_recent_median2(annual, "selling_expense_bil") or 0) + abs(_recent_median2(annual, "admin_expense_bil") or 0)) / rev * 100)
    mapping = {
        "Hiệu quả vốn": f"ROIC trung vị {_pct(roic)} và ROE trung vị {_pct(roe)}. Điểm cao chỉ hợp lý khi lợi suất trên vốn cao lặp lại nhiều kỳ, không phải một năm đột biến.",
        "Cost advantage": f"Biên gộp trung vị {_pct(gross)}, biên EBIT {_pct(ebit)}, CCC {_money(ccc, ' ngày')}, vòng quay HTK {_ratio(inv_turn)}, SG&A/DT {_pct(sga_ratio)}. Đây là dấu hiệu cụ thể xem công ty có cost advantage không.",
        "Differentiation": f"Biên gộp {_pct(gross)} và mức duy trì biên qua nhiều kỳ là tín hiệu định lượng của pricing power. Cần bổ sung BCTN/tin IR về thương hiệu, khách hàng, sản phẩm, kênh phân phối của chính doanh nghiệp.",
        "Cấu trúc ngành": f"Hệ thống hiện dùng biến động lợi nhuận {_pct(None if _cv2(annual, 'net_profit_bil') is None else _cv2(annual, 'net_profit_bil')*100)} và ngành của mã để nhận diện chu kỳ. Với ngành cạnh tranh/chu kỳ, điểm cấu trúc ngành sẽ thận trọng hơn.",
        "Chất lượng dòng tiền": f"CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}, tỷ lệ kỳ FCF dương {_pct(None if fcf_pos is None else fcf_pos*100)}. Nếu LNST cao nhưng tiền không về, moat/valuation phải giảm độ tin cậy.",
        "Tái đầu tư": f"CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}, CAGR Owner Earnings {_pct(None if oe_cagr is None else oe_cagr*100)}, ROIC {_pct(roic)}. Compounder thật cần vừa tăng trưởng vừa duy trì ROIC.",
        "Quản trị & phân bổ vốn": f"Kiểm tra ROIC {_pct(roic)}, nợ/EBITDA {_ratio(_parse_num(_latest_dict(annual).get('net_debt_to_ebitda')))}, cổ tức/capex/nợ vay. Đây là dấu hiệu xem quản trị có phân bổ vốn tạo giá trị hay không.",
        "Chuỗi giá trị Porter": f"Dùng dữ liệu vận hành: biên gộp {_pct(gross)}, SG&A/DT {_pct(sga_ratio)}, CCC {_money(ccc, ' ngày')}, vòng quay HTK {_ratio(inv_turn)} để truy nguồn lợi thế từ hoạt động cụ thể.",
    }
    detail = next((v for k, v in mapping.items() if k in group), rowd.get("Diễn giải", ""))
    return "\n".join([
        _company_snapshot(),
        "",
        f"NHÓM ĐÁNH GIÁ: {group}",
        f"- Điểm đạt: {_format_note_value(rowd.get('Điểm đạt'))}/{_format_note_value(rowd.get('Trọng số %'))}.",
        f"- Tín hiệu trong bảng: {_format_note_value(rowd.get('Tín hiệu'))}.",
        f"- Diễn giải theo dữ liệu của mã này: {detail}",
        "Số liệu cụ thể dẫn đến diễn giải:",
        _module2_numeric_evidence_for_note(group),
        f"- Bằng chứng cần xem thêm: {_format_note_value(rowd.get('Bằng chứng định lượng cần xem'))}.",
        _source_principle_text("porter", getattr(cls, 'company_type', 'N/A')),
    ])


def _value_chain_note(rowd: dict) -> str:
    annual = _ctx().get("annual_df", pd.DataFrame())
    cls = _ctx().get("classification")
    activity = str(rowd.get("Hoạt động chuỗi giá trị", ""))
    gross = _recent_median2(annual, "gross_margin_pct")
    ebit = _recent_median2(annual, "ebit_margin_pct")
    ccc = _recent_median2(annual, "cash_conversion_cycle_days")
    inv_turn = _recent_median2(annual, "inventory_turnover")
    roic = _recent_median2(annual, "roic_standard_pct") or _recent_median2(annual, "roic_pct")
    cfo_np = _recent_median2(annual, "cfo_to_net_profit")
    rev = _recent_median2(annual, "revenue_bil")
    sga_ratio = None
    if rev and rev > 0:
        sga_ratio = ((abs(_recent_median2(annual, "selling_expense_bil") or 0) + abs(_recent_median2(annual, "admin_expense_bil") or 0)) / rev * 100)
    activity_detail = {
        "Logistics đầu vào": f"Vòng quay tồn kho {_ratio(inv_turn)}. Nếu vòng quay cao và tồn kho không phình ra khi doanh thu tăng, có thể có lợi thế mua hàng/quản trị tồn kho. Nếu vòng quay thấp, phải soi tồn kho chậm luân chuyển và giá nguyên liệu.",
        "Vận hành/sản xuất": f"Biên gộp {_pct(gross)}, biên EBIT {_pct(ebit)}, ROIC {_pct(roic)}. Nếu biên cao đi kèm ROIC cao nhiều kỳ, lợi thế có thể đến từ quy mô, công nghệ hoặc hiệu suất vận hành.",
        "Logistics đầu ra": f"CCC {_money(ccc, ' ngày')}, CFO/LNST {_ratio(cfo_np)}. CCC thấp hoặc âm cho thấy doanh nghiệp thu tiền nhanh/chiếm dụng vốn tốt; CCC cao làm giảm chất lượng dòng tiền.",
        "Marketing & bán hàng": f"SG&A/DT {_pct(sga_ratio)} và biên gộp {_pct(gross)}. Nếu chi phí bán hàng thấp nhưng biên gộp cao, có thể có thương hiệu/kênh phân phối mạnh; nếu SG&A cao mà biên không tăng, cần cảnh báo.",
        "Dịch vụ sau bán hàng": "BCTC thường không đủ dữ liệu định lượng. Cần BCTN/IR: bảo hành, tỷ lệ khách hàng lặp lại, hợp đồng dài hạn, khiếu nại, churn. Note này không kết luận moat nếu thiếu bằng chứng doanh nghiệp.",
        "Công nghệ/R&D": "Cần dữ liệu BCTN/IR về R&D, bằng sáng chế, chứng chỉ, tự động hóa, chi phí công nghệ. Nếu ROIC/biên gộp cao nhưng không có bằng chứng hoạt động, chỉ chấm moat thận trọng.",
        "Nhân sự": "Cần dữ liệu nhân sự/năng suất/đào tạo. Nếu doanh thu/nhân viên, năng suất hoặc tỷ lệ nghỉ việc không có, hệ thống chỉ gợi ý kiểm tra, không kết luận moat.",
        "Hạ tầng quản trị": f"ROIC {_pct(roic)}, CFO/LNST {_ratio(cfo_np)}, nợ/EBITDA {_ratio(_parse_num(_latest_dict(annual).get('net_debt_to_ebitda')))}. Quản trị tốt phải thể hiện ở phân bổ vốn, kiểm soát nợ, minh bạch và không làm loãng cổ đông.",
    }
    detail = next((v for k, v in activity_detail.items() if k in activity), "Cần đọc BCTN/IR và đối chiếu số liệu nhiều kỳ.")
    return "\n".join([
        _company_snapshot(),
        "",
        f"HOẠT ĐỘNG CHUỖI GIÁ TRỊ: {activity}",
        f"- Đánh giá sơ bộ trong bảng: {_format_note_value(rowd.get('Đánh giá sơ bộ'))}; loại lợi thế: {_format_note_value(rowd.get('Loại lợi thế'))}.",
        f"- Cách đọc theo dữ liệu doanh nghiệp: {detail}",
        "Số liệu cụ thể dẫn đến diễn giải:",
        _module2_numeric_evidence_for_note(activity),
        f"- Bằng chứng hiện có/cần tìm: {_format_note_value(rowd.get('Bằng chứng hiện có/cần tìm'))}.",
        _source_principle_text("porter", getattr(cls, 'company_type', 'N/A')),
    ])


def _scenario_note(rowd: dict) -> str:
    annual = _ctx().get("annual_df", pd.DataFrame())
    cls = _ctx().get("classification")
    current = _parse_num(getattr(_ctx().get("company"), "current_price", None))
    value = _parse_num(rowd.get("Giá trị/cp"))
    mos = ((value - current) / value * 100) if value and current else _parse_num(rowd.get("MOS so với giá hiện tại %"))
    return "\n".join([
        _company_snapshot(),
        "",
        f"KỊCH BẢN: {_format_note_value(rowd.get('Kịch bản'))}",
        f"- Giá trị/cp của kịch bản = {_money(value, ' đ/cp')}; giá hiện tại = {_money(current, ' đ/cp')}; MOS = {_pct(mos)}.",
        f"- Giả định chính: {_format_note_value(rowd.get('Giả định chính'))}.",
        f"- Rủi ro được kích hoạt bởi dữ liệu: {_format_note_value(rowd.get('Rủi ro cần kiểm tra'))}.",
        f"- Số liệu rủi ro cụ thể: biến động LNST {_pct(None if _cv2(annual, 'net_profit_bil') is None else _cv2(annual, 'net_profit_bil')*100)}, nợ/EBITDA {_ratio(_parse_num(_latest_dict(annual).get('net_debt_to_ebitda')))}, FCF/LNST {_ratio(_recent_median2(annual, 'fcf_to_net_profit'))}.",
        _source_principle_text("risk", getattr(cls, 'company_type', 'N/A')),
    ])


def _latest_card_note(rowd: dict) -> str:
    return "\n".join([
        _company_snapshot(),
        "",
        f"CHỈ TIÊU KỲ GẦN NHẤT: {_format_note_value(rowd.get('Chỉ tiêu'))}",
        f"- Giá trị đang hiển thị: {_format_note_value(rowd.get('Giá trị'))}.",
        "- Số liệu lấy từ bảng BCTC đã chuẩn hóa của Tổng quan doanh nghiệp, ưu tiên TTM nếu đủ 4 quý gần nhất; nếu không có TTM thì dùng năm/kỳ mới nhất.",
        "- Cách đọc không dùng chung: so sánh chỉ tiêu này với phân loại doanh nghiệp, ROIC, CFO/LNST, FCF/LNST và chu kỳ ngành của mã đang nhập. Ví dụ cùng một FCF âm: với doanh nghiệp mở rộng ROIC cao thì cần tách capex tăng trưởng; với doanh nghiệp suy giảm ROIC thì là cảnh báo.",
    ])



def _median_pct_for_note(df: pd.DataFrame, cols: list[str], n: int = 5) -> float | None:
    for col in cols:
        v = _recent_median2(df, col, n=n)
        if v is not None:
            return v
    return None


def _profit_sustainability_assessment(annual_df: pd.DataFrame) -> tuple[str, str, str]:
    roic = _median_pct_for_note(annual_df, ["roic_standard_pct", "roic_pct"])
    roe = _median_pct_for_note(annual_df, ["roe_actual_pct", "roe_pct"])
    cfo_np = _recent_median2(annual_df, "cfo_to_net_profit")
    fcf_np = _recent_median2(annual_df, "fcf_to_net_profit")
    profit_pos = _recent_positive_ratio2(annual_df, "net_profit_bil")
    fcf_pos = _recent_positive_ratio2(annual_df, "free_cash_flow_bil")
    rev_cagr = _cagr2(annual_df, "revenue_bil")
    profit_cagr = _cagr2(annual_df, "net_profit_bil")
    profit_cv = _cv2(annual_df, "net_profit_bil")
    margin_cv = _cv2(annual_df, "net_margin_pct")
    net_margin = _recent_median2(annual_df, "net_margin_pct")
    facts = (
        f"ROIC trung vị {_pct(roic)}, ROE trung vị {_pct(roe)}, CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}, "
        f"tỷ lệ LNST dương {_pct(None if profit_pos is None else profit_pos*100)}, tỷ lệ FCF dương {_pct(None if fcf_pos is None else fcf_pos*100)}, "
        f"CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}, CAGR LNST {_pct(None if profit_cagr is None else profit_cagr*100)}, "
        f"độ biến động LNST {_pct(None if profit_cv is None else profit_cv*100)}, biên ròng trung vị {_pct(net_margin)}."
    )
    if profit_pos is not None and profit_pos < 0.6:
        conclusion = "Chưa bền vững: doanh nghiệp có nhiều kỳ không tạo lợi nhuận dương."
    elif profit_cv is not None and profit_cv > 0.65:
        conclusion = "Có tính chu kỳ/biến động cao: lợi nhuận hiện tại cần chuẩn hóa qua nhiều kỳ."
    elif cfo_np is not None and cfo_np < 0.7:
        conclusion = "Cần kiểm tra: lợi nhuận kế toán chưa chuyển hóa tốt thành dòng tiền."
    elif roic is not None and roic >= 15 and cfo_np is not None and cfo_np >= 0.8 and (profit_cv is None or profit_cv <= 0.45):
        conclusion = "Khá bền vững: ROIC cao, dòng tiền hỗ trợ lợi nhuận và biến động lợi nhuận không quá lớn."
    elif profit_cv is not None and profit_cv <= 0.45 and profit_pos is not None and profit_pos >= 0.8:
        conclusion = "Tương đối bền vững nhưng cần theo dõi thêm dòng tiền và khả năng duy trì biên lợi nhuận."
    else:
        conclusion = "Chưa đủ chắc chắn: cần kết hợp thêm BCTN, cơ cấu sản phẩm, chu kỳ ngành và bằng chứng internet."
    principle = (
        "Không dùng chung một nguyên tắc cho mọi mã: nếu lợi nhuận ổn định + CFO/LNST tốt thì ưu tiên earning power/Owner Earnings; "
        "nếu lợi nhuận biến động mạnh thì dùng lợi nhuận chuẩn hóa qua chu kỳ; nếu lợi nhuận không đi kèm tiền thật thì giảm trọng số định giá theo earnings."
    )
    return conclusion, facts, principle


def _infer_advantage_sources(company: object, annual_df: pd.DataFrame, moat_df: pd.DataFrame | None = None) -> tuple[str, str, str]:
    industry = f"{getattr(company, 'industry', '')} {getattr(company, 'sub_industry', '')}".lower()
    roic = _median_pct_for_note(annual_df, ["roic_standard_pct", "roic_pct"])
    roe = _median_pct_for_note(annual_df, ["roe_actual_pct", "roe_pct"])
    gross_margin = _recent_median2(annual_df, "gross_margin_pct")
    net_margin = _recent_median2(annual_df, "net_margin_pct")
    asset_turnover = _recent_median2(annual_df, "asset_turnover")
    cfo_np = _recent_median2(annual_df, "cfo_to_net_profit")
    fcf_np = _recent_median2(annual_df, "fcf_to_net_profit")
    rev_cagr = _cagr2(annual_df, "revenue_bil")
    margin_cv = _cv2(annual_df, "gross_margin_pct")
    latest = _latest_dict(annual_df)
    cash = _parse_num(latest.get("cash_bil")) or _parse_num(latest.get("cash_and_equivalents_bil"))
    debt = _parse_num(latest.get("interest_bearing_debt_bil")) or _parse_num(latest.get("debt_bil"))
    equity = _parse_num(latest.get("equity_bil"))

    sources = []
    evidence = []
    if gross_margin is not None and gross_margin >= 25 and (margin_cv is None or margin_cv <= 0.25):
        sources.append("khác biệt hóa/pricing power")
        evidence.append(f"biên gộp trung vị {_pct(gross_margin)} và biến động biên gộp {_pct(None if margin_cv is None else margin_cv*100)}")
    elif gross_margin is not None and gross_margin < 15 and asset_turnover is not None and asset_turnover >= 1.0:
        sources.append("hiệu quả chi phí/vòng quay")
        evidence.append(f"biên gộp thấp {_pct(gross_margin)} nhưng vòng quay tài sản {_ratio(asset_turnover)}")
    if roic is not None and roic >= 15:
        sources.append("hiệu quả vốn/khả năng tái đầu tư")
        evidence.append(f"ROIC trung vị {_pct(roic)}")
    if cfo_np is not None and cfo_np >= 0.8 and fcf_np is not None and fcf_np >= 0:
        sources.append("mô hình tạo tiền tốt")
        evidence.append(f"CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}")
    if rev_cagr is not None and rev_cagr > 0.05 and roic is not None and roic >= 12:
        sources.append("quy mô/phân phối hoặc nhu cầu thị trường thuận lợi")
        evidence.append(f"CAGR doanh thu {_pct(rev_cagr*100)} đi cùng ROIC {_pct(roic)}")
    if debt is not None and equity is not None and equity > 0 and debt / equity < 0.5:
        sources.append("bảng cân đối thận trọng")
        evidence.append(f"nợ vay/vốn chủ khoảng {_ratio(debt/equity)}")
    if any(k in industry for k in ["dược", "pharma", "điện", "power", "nước", "water", "cảng", "port"]):
        sources.append("giấy phép/tài sản đặc thù ngành")
        evidence.append(f"ngành/phân ngành: {getattr(company, 'industry', '')} {getattr(company, 'sub_industry', '')}")

    # Không khẳng định switching cost/thương hiệu nếu chỉ có số tài chính.
    direct_lack = "Thương hiệu, switching cost, giấy phép độc quyền và kênh phân phối cần đối chiếu thêm với BCTN/tin IR; hệ thống không tự khẳng định nếu chưa có bằng chứng định tính."
    if not sources:
        sources = ["chưa xác định rõ nguồn moat"]
        evidence.append("chỉ số hiện tại chưa đủ mạnh hoặc thiếu dữ liệu so sánh ngang ngành")
    # loại trùng nhưng giữ thứ tự
    uniq_sources = list(dict.fromkeys(sources))
    conclusion = "; ".join(uniq_sources)
    facts = "; ".join(evidence) + ". " + direct_lack
    principle = (
        "Theo Porter, lợi thế cạnh tranh phải truy về hoạt động cụ thể trong chuỗi giá trị: tạo chi phí thấp hơn, tạo khác biệt hóa được khách hàng trả tiền, hoặc tạo rào cản khó bắt chước. "
        "Vì vậy kết luận này thay đổi theo số liệu từng doanh nghiệp và không dùng chung một checklist cố định."
    )
    return conclusion, facts, principle


def _roic_moat_vs_cycle_assessment(company: object, annual_df: pd.DataFrame, cls_name: str) -> tuple[str, str, str]:
    industry = f"{getattr(company, 'industry', '')} {getattr(company, 'sub_industry', '')}".lower()
    roic = _median_pct_for_note(annual_df, ["roic_standard_pct", "roic_pct"])
    # ROCE fallback: EBIT/capital employed nếu có; nếu không dùng ROIC proxy nhưng nói rõ.
    latest = _latest_dict(annual_df)
    ebit = _parse_num(latest.get("ebit_bil")) or _parse_num(latest.get("operating_profit_bil")) or _parse_num(latest.get("pretax_profit_bil"))
    total_assets = _parse_num(latest.get("total_assets_bil"))
    current_liabilities = _parse_num(latest.get("current_liabilities_bil"))
    capital_employed = None
    roce = None
    if total_assets is not None and current_liabilities is not None:
        capital_employed = total_assets - current_liabilities
        if ebit is not None and capital_employed and capital_employed > 0:
            roce = ebit / capital_employed * 100
    cfo_np = _recent_median2(annual_df, "cfo_to_net_profit")
    fcf_np = _recent_median2(annual_df, "fcf_to_net_profit")
    profit_cv = _cv2(annual_df, "net_profit_bil")
    gross_cv = _cv2(annual_df, "gross_margin_pct")
    rev_cagr = _cagr2(annual_df, "revenue_bil")
    cyc_keywords = ["thép", "steel", "phân bón", "fertil", "hóa chất", "chemical", "cao su", "rubber", "dầu", "oil", "bất động sản", "real estate", "commodity", "than", "coal"]
    cyclic_flag = any(k in industry for k in cyc_keywords) or (profit_cv is not None and profit_cv > 0.65)
    facts = (
        f"ROIC trung vị {_pct(roic)}, ROCE kỳ mới nhất {_pct(roce)}" + (f" = EBIT/Pretax {_bil(ebit)} / capital employed {_bil(capital_employed)}" if roce is not None else " (chưa đủ dữ liệu EBIT/current liabilities để tính ROCE riêng, dùng ROIC làm proxy)") +
        f"; CFO/LNST {_ratio(cfo_np)}, FCF/LNST {_ratio(fcf_np)}, biến động LNST {_pct(None if profit_cv is None else profit_cv*100)}, biến động biên gộp {_pct(None if gross_cv is None else gross_cv*100)}, CAGR doanh thu {_pct(None if rev_cagr is None else rev_cagr*100)}."
    )
    if roic is None:
        conclusion = "Chưa kết luận: thiếu ROIC/ROCE nhiều kỳ."
    elif roic >= 15 and not cyclic_flag and (profit_cv is None or profit_cv <= 0.45) and (cfo_np is None or cfo_np >= 0.8):
        conclusion = "ROIC cao nghiêng về moat thật/hiệu quả hoạt động bền vững hơn là chu kỳ ngắn hạn."
    elif roic >= 15 and cyclic_flag:
        conclusion = "ROIC cao nhưng có rủi ro đến từ chu kỳ/ngành đang thuận lợi; cần chuẩn hóa qua chu kỳ trước khi trả premium."
    elif roic >= 15 and cfo_np is not None and cfo_np < 0.7:
        conclusion = "ROIC cao nhưng dòng tiền chưa hỗ trợ đủ; cần kiểm tra vốn lưu động, phải thu, tồn kho và capex."
    elif roic >= 10:
        conclusion = "ROIC khá, nhưng chưa đủ bằng chứng để gọi là moat mạnh."
    else:
        conclusion = "ROIC/ROCE chưa cao; lợi thế cạnh tranh nếu có cần chứng minh bằng tài sản, giấy phép hoặc phục hồi chu kỳ."
    principle = (
        "Hệ thống không mặc định ROIC cao là moat. ROIC chỉ được xem là moat thật khi duy trì nhiều kỳ, ít biến động, có dòng tiền hỗ trợ và không chỉ xuất hiện đúng lúc ngành thuận lợi. "
        "Với doanh nghiệp chu kỳ, dùng trung vị nhiều kỳ và đánh giá downside trước."
    )
    return conclusion, facts, principle


def _mos_assessment(value_range, current_price: float | None, cls_name: str, cls_conf: float, target_mos_pct: float = 30.0) -> tuple[str, str, str]:
    mos = value_range.mos_to_weighted_pct
    target_mos_pct = 30.0 if target_mos_pct is None else float(target_mos_pct)
    buy_price = value_range.weighted_vnd * (1 - target_mos_pct / 100) if getattr(value_range, 'weighted_vnd', None) else None
    facts = f"Giá hiện tại {_money(current_price, ' đ/cp')}; giá trị thấp {_money(value_range.low_vnd, ' đ/cp')}; giá trị cơ sở {_money(value_range.base_vnd, ' đ/cp')}; giá trị cao {_money(value_range.high_vnd, ' đ/cp')}; giá trị trọng số {_money(value_range.weighted_vnd, ' đ/cp')}; MOS hiện tại {_pct(mos)}; MOS yêu cầu {target_mos_pct:.0f}%; giá mua tối đa theo MOS chọn {_money(buy_price, ' đ/cp')}; độ tin cậy phân loại {cls_conf:,.0f}/100."
    if mos is None:
        conclusion = "Chưa đủ dữ liệu để kết luận biên an toàn."
    elif mos >= target_mos_pct:
        conclusion = f"Đạt MOS yêu cầu {target_mos_pct:.0f}% so với giá trị weighted."
    elif mos >= 30:
        conclusion = f"Có biên an toàn đáng chú ý nhưng chưa đạt MOS yêu cầu {target_mos_pct:.0f}%."
    elif mos >= 15:
        conclusion = "Có biên an toàn vừa phải; phù hợp theo dõi thêm, chưa quá rẻ nếu dữ liệu không thật mạnh."
    elif mos >= 0:
        conclusion = "Biên an toàn mỏng; giá không còn rẻ rõ ràng so với giá trị nội tại weighted."
    else:
        conclusion = "Giá thị trường cao hơn giá trị weighted; chưa có biên an toàn theo mô hình hiện tại."
    if "Cyclical" in cls_name and mos is not None and mos < 50:
        conclusion += " Do có tính chu kỳ, nên yêu cầu MOS cao hơn doanh nghiệp ổn định."
    if "Quality" in cls_name and mos is not None and mos >= 20:
        conclusion += " Với compounder chất lượng, MOS không nhất thiết phải cực sâu nhưng phải xác nhận được khả năng tái đầu tư và moat."
    principle = f"Theo Graham/Li Lu, biên an toàn là lớp bảo vệ khi ước tính giá trị có thể sai. Trong lần chạy này, app dùng MOS yêu cầu {target_mos_pct:.0f}% do người dùng chọn; các giá mua MOS và kết luận đủ/chưa đủ MOS được tính lại theo mức này."
    return conclusion, facts, principle


def _build_strategic_assessment_table(company: object, annual_df: pd.DataFrame, cls, value_range, moat_df: pd.DataFrame, target_mos_pct: float = 30.0) -> pd.DataFrame:
    cls_name = getattr(cls, "company_type", "N/A")
    cls_conf = float(getattr(cls, "confidence", 0) or 0)
    current_price = _parse_num(getattr(company, "current_price", None))
    profit_c, profit_f, profit_p = _profit_sustainability_assessment(annual_df)
    adv_c, adv_f, adv_p = _infer_advantage_sources(company, annual_df, moat_df)
    roic_c, roic_f, roic_p = _roic_moat_vs_cycle_assessment(company, annual_df, cls_name)
    mos_c, mos_f, mos_p = _mos_assessment(value_range, current_price, cls_name, cls_conf, target_mos_pct)
    cls_facts = "; ".join(getattr(cls, "reasons", [])[:5]) or _company_snapshot()
    cls_principle = "Phân loại dùng dữ liệu chính của mã đang phân tích: ngành/phân ngành, ROIC/ROE, CFO/LNST, FCF, CAGR doanh thu, độ biến động lợi nhuận, P/B và tài sản ngắn hạn ròng. Do đó mỗi doanh nghiệp sẽ ra kết luận khác nhau."
    return pd.DataFrame([
        {"Câu hỏi đánh giá": "1. Doanh nghiệp thuộc loại nào?", "Kết luận theo mã": f"{cls_name} (độ tin cậy {cls_conf:.0f}/100)", "Số liệu/chứng cứ chính": cls_facts, "Nguyên tắc áp dụng riêng": cls_principle},
        {"Câu hỏi đánh giá": "2. Lợi nhuận hiện tại có bền vững không?", "Kết luận theo mã": profit_c, "Số liệu/chứng cứ chính": profit_f, "Nguyên tắc áp dụng riêng": profit_p},
        {"Câu hỏi đánh giá": "3. Lợi thế cạnh tranh đến từ đâu?", "Kết luận theo mã": adv_c, "Số liệu/chứng cứ chính": adv_f, "Nguyên tắc áp dụng riêng": adv_p},
        {"Câu hỏi đánh giá": "4. ROIC/ROCE cao do moat thật hay chu kỳ?", "Kết luận theo mã": roic_c, "Số liệu/chứng cứ chính": roic_f, "Nguyên tắc áp dụng riêng": roic_p},
        {"Câu hỏi đánh giá": "5. Giá hiện tại có đủ biên an toàn không?", "Kết luận theo mã": mos_c, "Số liệu/chứng cứ chính": mos_f, "Nguyên tắc áp dụng riêng": mos_p},
    ])


def _canonical_company_type_key(cls_text: object) -> str:
    """Map engine classification names/aliases to the guidance keys used by the UI."""
    raw = str(cls_text or "").strip()
    low = raw.lower()
    if not low:
        return "Normal Business"
    if "chưa có dữ liệu" in low or "không có dữ liệu" in low:
        return "Chưa có dữ liệu tài chính"
    if "financial" in low or "bank" in low or "insurance" in low or "ngân hàng" in low or "bảo hiểm" in low:
        return "Bank/Insurance"
    if "asset" in low or "deep value" in low or "net-net" in low or "ncav" in low or "nla" in low:
        return "Asset Play"
    if "quality compounder" in low:
        return "Quality Compounder"
    if "compounder" in low:
        return "Compounder"
    if "cyclical" in low or "chu kỳ" in low:
        return "Cyclical"
    if "turnaround" in low or "phục hồi" in low:
        return "Turnaround"
    key = next((k for k in COMPANY_TYPE_GUIDANCE.keys() if raw.lower().startswith(k.lower())), None)
    if key is None:
        key = next((k for k in COMPANY_TYPE_GUIDANCE.keys() if k.lower() in low), None)
    return key or "Normal Business"


def _company_type_info(cls_text: object) -> tuple[str, dict]:
    key = _canonical_company_type_key(cls_text)
    return key, COMPANY_TYPE_GUIDANCE.get(key, COMPANY_TYPE_GUIDANCE["Normal Business"])


def _company_type_guidance_for_note(cls_text: str) -> str:
    key, info = _company_type_info(cls_text)
    return "\n".join([
        f"DIỄN GIẢI THEO LOẠI DOANH NGHIỆP: {key}",
        f"- Cơ sở tư duy: {info.get('Cơ sở tư duy', 'N/A')}",
        f"- Đặc điểm cần kiểm tra: {info.get('Đặc điểm cần kiểm tra', 'N/A')}",
        f"- Cần phân tích thêm: {info.get('Cần phân tích thêm', 'N/A')}",
        f"- Định giá nên ưu tiên: {info.get('Định giá nên ưu tiên', 'N/A')}",
    ])


def _strategic_assessment_note(rowd: dict) -> str:
    question = str(rowd.get("Câu hỏi đánh giá", "Đánh giá trọng yếu"))
    conclusion = str(rowd.get('Kết luận theo mã', 'N/A'))
    extra_type_guidance = ""
    if "Doanh nghiệp thuộc loại nào" in question:
        extra_type_guidance = "\n\n" + _company_type_guidance_for_note(conclusion)
    return "\n".join([
        _company_snapshot(),
        "",
        question,
        f"Kết luận theo mã: {conclusion}",
        "",
        "Số liệu/chứng cứ chính:",
        str(rowd.get("Số liệu/chứng cứ chính", "N/A")),
        "",
        "Nguyên tắc áp dụng riêng cho doanh nghiệp này:",
        str(rowd.get("Nguyên tắc áp dụng riêng", "N/A")) + extra_type_guidance,
        "",
        "Số liệu cụ thể bổ sung từ chuỗi BCTC:",
        _module2_numeric_evidence_for_note(question),
        "",
        "Cách ra kết luận: app lấy dữ liệu Tổng quan doanh nghiệp đã chuẩn hóa, đọc nhóm chỉ tiêu liên quan đến câu hỏi này, so với ngưỡng trong engine, sau đó kết hợp phân loại doanh nghiệp và MOS yêu cầu hiện tại. Kết luận không dùng một nguyên tắc chung mà phụ thuộc trực tiếp vào ROIC/ROE, CFO/LNST, FCF/LNST, CAGR doanh thu, độ biến động LNST, nợ vay, WACC và MOS của chính mã đang xem.",
        "Lưu ý: đây là đánh giá tự động dựa trên dữ liệu đang có trong từng phần 1 + Định giá chuyên sâu. Khi evidence internet/BCTN được cập nhật, phần moat/nguồn lợi thế cần được đối chiếu lại với bằng chứng định tính."
    ])



def _beneish_note(rowd: dict) -> str:
    c = _ctx().get("company")
    annual = _ctx().get("annual_df", pd.DataFrame())
    latest = _latest_dict(annual)
    period = str(rowd.get("Kỳ", "N/A"))
    mscore = _parse_num(rowd.get("M-Score"))
    dsri = _parse_num(rowd.get("DSRI"))
    gmi = _parse_num(rowd.get("GMI"))
    aqi = _parse_num(rowd.get("AQI"))
    sgi = _parse_num(rowd.get("SGI"))
    depi = _parse_num(rowd.get("DEPI"))
    sgai = _parse_num(rowd.get("SGAI"))
    tata = _parse_num(rowd.get("TATA"))
    lvgi = _parse_num(rowd.get("LVGI"))
    return "\n".join([
        _company_snapshot(),
        "",
        f"BENEISH M-SCORE - KỲ ĐANG CHỌN: {period}",
        f"M-Score: {_format_note_value(mscore)} | Ngưỡng cảnh báo: -2.22 | Mức cảnh báo: {rowd.get('Mức cảnh báo', 'N/A')}",
        "",
        "Công thức sử dụng:",
        "M = -4.84 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI.",
        "Nếu M-Score > -2.22, mô hình gắn cờ rủi ro thao túng lợi nhuận. Đây là cảnh báo định lượng, không phải kết luận pháp lý về gian lận.",
        "",
        "8 biến đầu vào và ý nghĩa theo dữ liệu doanh nghiệp:",
        f"- DSRI {_format_note_value(dsri)}: phải thu/doanh thu kỳ hiện tại so với kỳ trước. DSRI cao có thể báo hiệu doanh thu ghi nhận lỏng hoặc thu tiền chậm.",
        f"- GMI {_format_note_value(gmi)}: biên gộp kỳ trước / biên gộp kỳ hiện tại. GMI > 1 nghĩa là biên gộp suy giảm, tăng áp lực làm đẹp lợi nhuận.",
        f"- AQI {_format_note_value(aqi)}: tỷ trọng tài sản chất lượng thấp/chi phí hoãn lại tăng. AQI > 1 cần soi tài sản dài hạn, chi phí vốn hóa, khoản phải thu/tồn kho.",
        f"- SGI {_format_note_value(sgi)}: tăng trưởng doanh thu. Tăng trưởng cao có thể tạo áp lực duy trì kỳ vọng.",
        f"- DEPI {_format_note_value(depi)}: tỷ lệ khấu hao giảm hay không. DEPI > 1 cần kiểm tra thay đổi thời gian hữu dụng/phương pháp khấu hao.",
        f"- SGAI {_format_note_value(sgai)}: chi phí bán hàng & quản lý/doanh thu. SGAI > 1 phản ánh chi phí vận hành tăng nhanh hơn doanh thu.",
        f"- TATA {_format_note_value(tata)}: tổng accruals/tổng tài sản. TATA dương cao nghĩa là lợi nhuận phụ thuộc accruals nhiều hơn tiền thật.",
        f"- LVGI {_format_note_value(lvgi)}: đòn bẩy kỳ hiện tại so với kỳ trước. LVGI > 1 có thể tăng động cơ đáp ứng covenant hoặc mục tiêu nợ.",
        "",
        "Biến nổi bật/cần kiểm tra:",
        str(rowd.get("Biến nổi bật/cần kiểm tra", "N/A")),
        "",
        "Biến thiếu/cần kiểm tra:",
        str(rowd.get("Biến thiếu/cần kiểm tra", "N/A")),
        "",
        "Số liệu kỳ mới nhất trong app để đối chiếu chất lượng lợi nhuận:",
        f"- Doanh thu: {_bil(latest.get('revenue_bil'))}; LNST: {_bil(latest.get('net_profit_bil'))}; CFO: {_bil(latest.get('cfo_bil'))}; CFO/LNST: {_ratio(latest.get('cfo_to_net_profit'))}.",
        f"- Phải thu: {_bil(latest.get('accounts_receivable_bil'))}; Tồn kho: {_bil(latest.get('inventory_bil'))}; Tổng tài sản: {_bil(latest.get('total_assets_bil'))}; Nợ phải trả: {_bil(latest.get('liabilities_bil'))}.",
        "",
        "Cách dùng trong đầu tư giá trị: nếu Beneish cảnh báo cao, app không kết luận doanh nghiệp gian lận; thay vào đó giảm độ tin cậy của lợi nhuận/định giá, yêu cầu đọc BCTC kiểm toán, thuyết minh doanh thu, phải thu, tồn kho, khấu hao, giao dịch bên liên quan và so sánh với dòng tiền."
    ])



def _financial_manipulation_layer_note(rowd: dict, layer_name: str) -> str:
    """Detailed notes for financial manipulation layers 2-4."""
    lines = [
        _company_snapshot(),
        "",
        f"{layer_name.upper()} - KỲ ĐANG CHỌN: {rowd.get('Kỳ', 'N/A')}",
        f"Mức cảnh báo: {rowd.get('Mức cảnh báo', 'N/A')} | Điểm nhiệt: {_format_note_value(rowd.get('Điểm nhiệt'))}",
        "",
        "Công thức/logic app đang dùng:",
        str(rowd.get("Công thức/logic", "N/A")),
        "",
        "Số liệu/cách tính trên dòng đang chọn:",
    ]
    for key, val in rowd.items():
        if key in {"Nguồn/logic", "Công thức/logic"}:
            continue
        lines.append(f"- {key}: {_format_note_value(val)}")
    lines += [
        "",
        "Diễn giải kết quả:",
        str(rowd.get("Tín hiệu", "N/A")),
        "",
        "Cần kiểm tra sâu:",
        str(rowd.get("Cần kiểm tra", "N/A")),
        "",
        "Lưu ý sử dụng:",
        "Các mô hình thao túng tài chính chỉ là cờ đỏ định lượng. App không kết luận doanh nghiệp gian lận; kết quả được dùng để giảm độ tin cậy của lợi nhuận kế toán, yêu cầu đọc thuyết minh, BCTC kiểm toán, biến động vốn lưu động, giao dịch bên liên quan và so sánh với dòng tiền thật.",
    ]
    if "Accrual" in layer_name or "Sloan" in layer_name:
        lines += [
            "",
            "Ngưỡng tham chiếu nội bộ:",
            "- Sloan accrual ratio > 7% tài sản bình quân: cần theo dõi; > 12%: rủi ro cao.",
            "- CFO/LNST < 0.8: lợi nhuận chưa chuyển hóa tốt thành tiền; < 0.5 hoặc CFO âm: rủi ro cao hơn.",
        ]
    elif "Jones" in layer_name or "Kothari" in layer_name:
        lines += [
            "",
            "Ngưỡng tham chiếu nội bộ:",
            "- |DA| > 7% tổng tài sản đầu kỳ: cần theo dõi; |DA| > 12%: rủi ro cao.",
            "- DA dương thường là accruals làm tăng lợi nhuận; DA âm sâu có thể là big-bath/ghi nhận chi phí trước.",
        ]
    elif "Real" in layer_name or "REM" in layer_name:
        lines += [
            "",
            "Ngưỡng tham chiếu nội bộ:",
            "- Abnormal CFO âm: nghi ngờ kéo doanh thu bằng giảm giá/nới tín dụng.",
            "- Abnormal PROD dương: nghi ngờ sản xuất dư/làm giảm giá vốn đơn vị/tồn kho tăng.",
            "- Abnormal DISEXP âm: nghi ngờ cắt chi phí tùy ý như quảng cáo, R&D, bảo trì để nâng lợi nhuận ngắn hạn.",
        ]
    return "\n".join(lines)

def _render_big_recommendation(text: str) -> None:
    """Render a highly visible recommendation block using inline CSS so it survives Streamlit CSS isolation."""
    message = html.escape(str(text or "Chưa có khuyến nghị"))
    st.markdown(
        f"""
        <div style="border:3px solid #0B7F75; border-left:11px solid #F5B21B; border-radius:18px;
                    padding:16px 20px; margin:14px 0 16px 0;
                    background:linear-gradient(135deg,#FFF176 0%,#FFD54F 46%,#FFF3B0 100%);
                    box-shadow:0 10px 24px rgba(11,127,117,.18), 0 0 0 3px rgba(245,178,27,.12);">
          <div style="font-size:18px; font-weight:1000; color:#0B7F75; margin-bottom:6px; letter-spacing:-.01em;">📌 CẢNH BÁO / KHUYẾN NGHỊ NỔI BẬT</div>
          <div style="font-size:17px; font-weight:950; color:#3B2600; line-height:1.35;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _latest_financial_manipulation_layer_summary(layer_name: str, df: pd.DataFrame, metric_candidates: list[str]) -> dict:
    """One-row latest summary for a financial manipulation warning layer."""
    src = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if src.empty:
        return {
            "Lớp": layer_name,
            "Kỳ": "N/A",
            "Chỉ tiêu chính": metric_candidates[0] if metric_candidates else "N/A",
            "Giá trị": "N/A",
            "Mức cảnh báo": "Chưa đủ dữ liệu",
            "Điểm nhiệt": "N/A",
            "Tín hiệu": "Chưa đủ dữ liệu để tính lớp cảnh báo này.",
            "Cần kiểm tra": "Bổ sung dữ liệu BCTC theo năm, đặc biệt doanh thu, phải thu, tài sản, CFO, tồn kho, chi phí và khấu hao.",
        }
    latest = src.iloc[-1].to_dict()
    metric_name = next((m for m in metric_candidates if m in latest), metric_candidates[0] if metric_candidates else "Chỉ tiêu")
    return {
        "Lớp": layer_name,
        "Kỳ": latest.get("Kỳ", latest.get("period", "N/A")),
        "Chỉ tiêu chính": metric_name,
        "Giá trị": latest.get(metric_name, "N/A"),
        "Mức cảnh báo": latest.get("Mức cảnh báo", "N/A"),
        "Điểm nhiệt": latest.get("Điểm nhiệt", "N/A"),
        "Tín hiệu": latest.get("Tín hiệu", latest.get("Nhận xét", "N/A")),
        "Cần kiểm tra": latest.get("Cần kiểm tra", latest.get("Biến nổi bật/cần kiểm tra", latest.get("Biến thiếu/cần kiểm tra", "N/A"))),
    }


def _build_financial_manipulation_summary_df(
    beneish_df: pd.DataFrame,
    accrual_quality_df: pd.DataFrame,
    modified_jones_df: pd.DataFrame,
    rem_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build the 4-layer summary table shown above the financial manipulation layer tabs."""
    rows = [
        _latest_financial_manipulation_layer_summary("1. Beneish M-Score", beneish_df, ["M-Score"]),
        _latest_financial_manipulation_layer_summary("2. Accrual Quality/Sloan", accrual_quality_df, ["Sloan accrual ratio", "CFO/LNST", "FCF/LNST"]),
        _latest_financial_manipulation_layer_summary("3. Modified Jones/Kothari", modified_jones_df, ["DA Modified Jones", "DA Kothari"]),
        _latest_financial_manipulation_layer_summary("4. REM - hoạt động thật", rem_df, ["REM Score", "Abnormal CFO", "Abnormal PROD", "Abnormal DISEXP"]),
    ]
    return pd.DataFrame(rows)


def _financial_manipulation_summary_note(rowd: dict) -> str:
    return "\n".join([
        _company_snapshot(),
        "",
        "TỔNG HỢP THAO TÚNG TÀI CHÍNH 4 LỚP",
        f"Lớp: {rowd.get('Lớp', 'N/A')}",
        f"Kỳ mới nhất: {rowd.get('Kỳ', 'N/A')}",
        f"Chỉ tiêu chính: {rowd.get('Chỉ tiêu chính', 'N/A')} = {_format_note_value(rowd.get('Giá trị', 'N/A'))}",
        f"Mức cảnh báo: {rowd.get('Mức cảnh báo', 'N/A')} | Điểm nhiệt: {_format_note_value(rowd.get('Điểm nhiệt', 'N/A'))}",
        "",
        "Tín hiệu:",
        str(rowd.get("Tín hiệu", "N/A")),
        "",
        "Cần kiểm tra:",
        str(rowd.get("Cần kiểm tra", "N/A")),
        "",
        "Cách đọc: bảng này gom kỳ mới nhất của 4 lớp để xem nhanh lớp nào đang phát tín hiệu mạnh nhất. Khi một hoặc nhiều lớp cảnh báo cao, cần giảm độ tin cậy của lợi nhuận kế toán và đối chiếu kỹ CFO/LNST/FCF, thuyết minh doanh thu, phải thu, tồn kho, khấu hao, vốn hóa chi phí, giao dịch bên liên quan và ý kiến kiểm toán.",
    ])

def _build_row_note(row: pd.Series, table_kind: str) -> str:
    rowd = row.to_dict()
    if "Câu hỏi đánh giá" in rowd:
        return _strategic_assessment_note(rowd)
    if "Phương pháp" in rowd:
        return _valuation_method_note(rowd)
    if "Nhóm Porter/Moat" in rowd:
        return _moat_note(rowd)
    if "Hoạt động chuỗi giá trị" in rowd:
        return _value_chain_note(rowd)
    if "Kịch bản" in rowd:
        return _scenario_note(rowd)
    if "M-Score" in rowd and "DSRI" in rowd:
        return _beneish_note(rowd)
    if table_kind == "financial_manipulation_summary":
        return _financial_manipulation_summary_note(rowd)
    if table_kind == "accrual_quality" or "Sloan accrual ratio" in rowd:
        return _financial_manipulation_layer_note(rowd, "Lớp 2 - Accrual Quality/Sloan")
    if table_kind == "modified_jones" or "DA Modified Jones" in rowd:
        return _financial_manipulation_layer_note(rowd, "Lớp 3 - Modified Jones/Kothari")
    if table_kind == "real_earnings_management" or "Abnormal CFO" in rowd:
        return _financial_manipulation_layer_note(rowd, "Lớp 4 - Real Earnings Management")
    if "Chỉ tiêu" in rowd and "Giá trị/cp" in rowd:
        return _valuation_range_note(rowd)
    if "Chỉ tiêu" in rowd and "Giá trị" in rowd:
        return _latest_card_note(rowd)
    if "Mã" in rowd and "Điểm tổng hợp" in rowd:
        return _build_peer_row_note(rowd)
    return "\n".join([_company_snapshot(), "", "DỮ LIỆU DÒNG ĐANG CHỌN:", "\n".join([f"- {k}: {_format_note_value(v)}" for k, v in rowd.items()])])


def _render_explainable_table(df: pd.DataFrame, table_kind: str = "", height: int = 420) -> None:
    """Bảng HTML có bắt sự kiện click một lần để hiện note theo dữ liệu doanh nghiệp."""
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
        return
    raw_df = df.copy()
    notes = [_build_row_note(row, table_kind) for _, row in raw_df.iterrows()]
    display_df = _vi_dataframe_for_display(raw_df)
    if "Note" in display_df.columns:
        display_df = display_df.drop(columns=["Note"])
    if table_kind in {"beneish_mscore", "accrual_quality", "modified_jones", "real_earnings_management"}:
        # V23.58: hide source/logic and redundant layer columns in the financial manipulation detail tables.
        # The layer is already visible in the sub-tab title; source/logic remains available in row notes.
        display_df = display_df.drop(columns=[c for c in ["Nguồn/logic", "Nguồn / logic", "Lớp"] if c in display_df.columns], errors="ignore")
    # Internal marker for highlighting the company currently under analysis in peer comparison.
    if table_kind == "peer_compare":
        drop_internal = [c for c in ["Mã đang phân tích", "Nguồn dữ liệu", "source", "Source", "Ngành", "Phân ngành"] if c in display_df.columns]
        if drop_internal:
            display_df = display_df.drop(columns=drop_internal)
    table_id = "tbl_" + str(abs(hash((table_kind, tuple(display_df.columns), len(display_df), APP_VERSION))))[0:10]
    full_table = table_kind == "strategic_assessment"
    if full_table:
        # V23.36: bảng đánh giá trọng yếu chỉ có vài dòng nhưng phần note rất dài.
        # Giữ bảng gọn để không tạo khoảng trống lớn, đồng thời cho note có vùng cuộn riêng.
        table_max_height = min(max(230, 140 + len(display_df) * 34), 300)
        wrap_css = f"max-height:{table_max_height}px; overflow:auto;"
        note_css_extra = "min-height:220px; max-height:360px; overflow-y:auto;"
        component_height = 720
    elif table_kind in {"valuation_range", "valuation_methods"}:
        # V23.38: tăng 20% vùng bảng và note cho Dải giá trị nội tại / Bảng định giá theo phương pháp.
        wrap_css = f"max-height:{height}px; overflow:auto;"
        note_css_extra = "min-height:240px; max-height:432px; overflow-y:auto;"
        component_height = min(max(height + 312, 516), 1128)
    elif table_kind in {"beneish_mscore", "accrual_quality", "modified_jones", "real_earnings_management"}:
        # V23.55: thao túng tài chính có note dài vì phải diễn giải công thức, biến đầu vào,
        # ngưỡng cảnh báo và cách dùng. Tăng vùng đọc cho cả 4 lớp.
        wrap_css = f"max-height:{height}px; overflow:auto;"
        note_css_extra = "min-height:430px; max-height:860px; overflow-y:auto; font-size:14px; line-height:1.62;"
        component_height = min(max(height + 660, 1000), 1660)
    else:
        wrap_css = f"max-height:{height}px; overflow:auto;"
        note_css_extra = "max-height:360px; overflow-y:auto;"
        component_height = min(max(height + 260, 430), 940)
    header_cells = []
    for c in display_df.columns:
        hcls = "summary-layer-header" if table_kind == "financial_manipulation_summary" and str(c).strip() == "Lớp" else ""
        header_cells.append(f"<th class='{hcls}'>{html.escape(str(c))}</th>")
    headers = "".join(header_cells)
    rows_html = []
    current_ticker_for_highlight = _safe_ticker(str(st.session_state.get("module3_base_ticker") or st.session_state.get("active_ticker") or st.session_state.get("module1_ticker") or ""))
    for i, (_, row) in enumerate(display_df.iterrows()):
        raw_rowd = raw_df.iloc[i].to_dict() if i < len(raw_df) else {}
        row_is_current = False
        if table_kind == "peer_compare":
            marker_val = raw_rowd.get("Mã đang phân tích")
            row_is_current = bool(marker_val is True or str(marker_val).strip().lower() in {"true", "1", "yes", "mã gốc", "ma goc"})
            row_is_current = row_is_current or (_safe_ticker(str(raw_rowd.get("Mã", ""))) == current_ticker_for_highlight and current_ticker_for_highlight != "")
        row_class = "base-peer-row" if row_is_current else ""
        tds = []
        for c in display_df.columns:
            val = row.get(c)
            text = _format_note_value(val)
            cls = _signal_class(val) if c in {"Tín hiệu", "Mức độ", "Mức cảnh báo", "Tình trạng", "Khuyến nghị", "Kết luận", "Kết luận theo mã", "Moat level", "Mức moat", "Độ tin cậy", "Đánh giá sơ bộ", "Loại lợi thế", "Vai trò"} else ""
            num = _parse_num(val)
            if table_kind == "peer_compare" and str(c).strip() == "Điểm tổng hợp" and num is not None:
                if num >= 80:
                    cls = "heat-green-strong"
                elif num >= 65:
                    cls = "heat-green"
                elif num >= 50:
                    cls = "heat-yellow"
                elif num >= 35:
                    cls = "heat-orange"
                else:
                    cls = "heat-red"
            elif not cls and num is not None and any(k in str(c).lower() for k in ["giá", "mos", "điểm", "điểm nhiệt", "trọng", "%", "value", "score"]):
                cls = "pos" if num > 0 else "neg" if num < 0 else ""
            tds.append(f"<td class='{cls}'>{html.escape(text)}</td>")
        rows_html.append(f"<tr class='{row_class}' data-note='{html.escape(json.dumps(notes[i], ensure_ascii=False), quote=True)}'>{''.join(tds)}</tr>")
    html_doc = f"""
    <div class='hint'>💡 Nhấp một lần vào một dòng/chỉ tiêu để xem note giải thích theo chính dữ liệu của doanh nghiệp.</div>
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
      .wrap {{{wrap_css} border:1px solid #e2e8f0; border-radius:12px;}}
      table {{border-collapse:collapse; width:100%; font-family: system-ui, -apple-system, Segoe UI, sans-serif; font-size:13px;}}
      th {{position: sticky; top:0; background:#EAF7F1; color:#123D3A; text-align:left; border-bottom:1px solid #e2e8f0; padding:8px; z-index:8; font-weight:950; box-shadow:0 2px 0 rgba(11,127,117,.18);}}
      td {{border-bottom:1px solid #edf2f7; padding:7px 8px; vertical-align:top; color:#123D3A;}}
      tr:hover td {{background:#F7FBF8; cursor:pointer;}}
      tr.selected td {{background:#FEF3C7 !important;}}
      tr.base-peer-row td {{background:#FFF3C4 !important; color:#064E47 !important; font-weight:900 !important; border-top:2px solid #F5B21B; border-bottom:2px solid #F5B21B;}}
      tr.base-peer-row td:first-child {{border-left:7px solid #F5B21B;}}
      td.pos {{background:rgba(16,185,129,.11); color:#064e3b; font-weight:600;}}
      td.neg {{background:rgba(239,68,68,.11); color:#7f1d1d; font-weight:600;}}
      td.sig-red-strong {{background:#FECACA !important; color:#7F1D1D !important; font-weight:900; border-left:5px solid #DC2626;}}
      td.sig-red {{background:#FEE2E2 !important; color:#991B1B !important; font-weight:800; border-left:4px solid #EF4444;}}
      td.sig-purple-strong {{background:#E9D5FF !important; color:#581C87 !important; font-weight:900; border-left:5px solid #7E22CE;}}
      td.sig-purple {{background:#F3E8FF !important; color:#6B21A8 !important; font-weight:800; border-left:4px solid #A855F7;}}
      td.sig-yellow {{background:#FEF3C7 !important; color:#92400E !important; font-weight:800; border-left:4px solid #F59E0B;}}
      td.heat-green-strong {{background:#047857 !important; color:#FFFFFF !important; font-weight:950 !important;}}
      td.heat-green {{background:#A7F3D0 !important; color:#064E3B !important; font-weight:900 !important;}}
      td.heat-yellow {{background:#FEF3C7 !important; color:#92400E !important; font-weight:900 !important;}}
      td.heat-orange {{background:#FED7AA !important; color:#9A3412 !important; font-weight:900 !important;}}
      td.heat-red {{background:#FECACA !important; color:#7F1D1D !important; font-weight:900 !important;}}
      .critical-note-label {{color:#B91C1C !important; font-weight:950 !important;}}
      .note {{white-space:pre-wrap; margin-top:10px; padding:13px 15px; border-radius:14px; background:#FFF7E6; border:1px solid rgba(245,178,27,.52); color:#5f3b00; font-size:13px; line-height:1.48; {note_css_extra}}}
    </style>
    """
    components.html(html_doc, height=component_height, scrolling=True)



GLOSSARY_TERMS = {
    "Asset Play": "Doanh nghiệp có giá thị trường thấp so với tài sản có thể định giá/thu hồi. Trọng tâm là chất lượng tài sản, khả năng thu hồi tiền, tài sản ẩn, nợ tiềm tàng và downside protection.",
    "Bank/Insurance": "Ngân hàng/bảo hiểm có BCTC đặc thù. Không nên dùng FCF/working capital như doanh nghiệp sản xuất; ưu tiên ROE, P/B, chất lượng tài sản, NIM, CASA, NPL, dự phòng và biên an toàn vốn.",
    "Base/Median": "Giá trị cơ sở/trung vị của các phương pháp định giá hợp lệ. Dùng để tránh phụ thuộc vào một mô hình duy nhất.",
    "Beta": "Mức nhạy của cổ phiếu/doanh nghiệp với thị trường hoặc proxy rủi ro. Nếu thiếu dữ liệu giá lịch sử, app chỉ dùng beta proxy và phải ghi rõ chất lượng thấp hơn beta thị trường.",
    "BVPS": "Book Value per Share - giá trị sổ sách trên mỗi cổ phiếu = vốn chủ sở hữu / số cổ phiếu.",
    "Capex": "Capital Expenditure - chi đầu tư tài sản cố định/capex. Capex có thể là duy trì hoặc mở rộng; định giá Owner Earnings cần ước tính capex duy trì.",
    "Capital Employed": "Vốn sử dụng cho hoạt động. Có thể tính bằng tổng tài sản - nợ ngắn hạn, hoặc tài sản cố định + vốn lưu động; phải dùng nhất quán.",
    "CCC": "Cash Conversion Cycle - chu kỳ chuyển đổi tiền = DSO + DIO - DPO. CCC thấp thường tốt hơn, nhưng phải đọc theo mô hình kinh doanh.",
    "CFO": "Cash Flow from Operations - dòng tiền thuần từ hoạt động kinh doanh. CFO/LNST cao thường cho thấy lợi nhuận kế toán chuyển hóa tốt thành tiền.",
    "CFO/LNST": "Tỷ lệ CFO trên lợi nhuận sau thuế. Nếu thấp kéo dài, lợi nhuận kế toán có thể chưa chuyển hóa thành tiền.",
    "Beneish M-Score": "Mô hình 8 biến dùng để cảnh báo khả năng thao túng lợi nhuận. M-Score > -2.22 là vùng cảnh báo; đây là tín hiệu định lượng, không phải kết luận pháp lý về gian lận.",
    "Earnings Management": "Quản trị/thao túng lợi nhuận - việc ban điều hành sử dụng xét đoán kế toán, ước tính hoặc cấu trúc giao dịch để làm lợi nhuận trình bày khác với chất lượng kinh tế thực. Trong app chỉ gọi là cờ đỏ/cần kiểm tra, không kết luận gian lận nếu chưa có bằng chứng pháp lý hoặc kiểm toán.",
    "Thao túng tài chính": "Nhóm dấu hiệu cho thấy số liệu tài chính có thể bị làm đẹp hoặc trình bày chưa phản ánh đúng bản chất kinh tế, ví dụ doanh thu ghi nhận sớm, phải thu tăng nhanh, vốn hóa chi phí, thay đổi khấu hao, hoàn nhập dự phòng hoặc lợi nhuận không đi kèm dòng tiền.",
    "Thao túng lợi nhuận": "Một dạng thao túng tài chính tập trung vào chỉ tiêu lợi nhuận. Dấu hiệu thường gặp là LNST tăng nhưng CFO/FCF yếu, accruals cao, biên lợi nhuận bất thường, thay đổi chính sách kế toán hoặc nhiều khoản mục ước tính.",
    "Accruals": "Các khoản dồn tích kế toán làm lợi nhuận khác dòng tiền. Accruals cao không mặc nhiên xấu, nhưng nếu kéo dài hoặc tăng đột biến thì cần kiểm tra chất lượng lợi nhuận.",
    "Accrual-based Earnings Management (AEM)": "Quản trị lợi nhuận qua accruals: dùng xét đoán kế toán, ước tính, dự phòng, ghi nhận doanh thu/chi phí để điều chỉnh lợi nhuận kế toán mà chưa nhất thiết làm thay đổi dòng tiền ngay.",
    "Real Earnings Management (REM)": "Quản trị lợi nhuận qua hoạt động thật: thay đổi quyết định kinh doanh như giảm giá/nới tín dụng để kéo doanh thu, sản xuất dư để giảm giá vốn đơn vị, hoặc cắt chi phí quảng cáo/R&D/bảo trì để làm đẹp lợi nhuận ngắn hạn.",
    "Sloan accrual ratio": "Chỉ tiêu chất lượng lợi nhuận = (LNST - CFO) / Tổng tài sản bình quân. Tỷ lệ dương cao cho thấy lợi nhuận phụ thuộc nhiều vào accruals hơn dòng tiền thật.",
    "Discretionary Accruals (DA)": "Phần accruals bất thường do mô hình ước lượng không giải thích được bởi tăng trưởng doanh thu, thay đổi phải thu, PPE/TSCĐ và hiệu quả hoạt động. DA dương cao thường là cờ đỏ làm tăng lợi nhuận.",
    "Modified Jones Model": "Mô hình ước lượng discretionary accruals: TA/A(t-1)=α0+α1(1/A(t-1))+α2((ΔREV-ΔREC)/A(t-1))+α3(PPE/A(t-1))+ε. Residual ε là DA.",
    "Kothari Model": "Bản mở rộng của Modified Jones, thêm ROA để kiểm soát hiệu quả hoạt động. Mục tiêu là tránh gắn cờ sai các doanh nghiệp tăng trưởng/hiệu quả cao nhưng accruals tăng do kinh doanh thật.",
    "Abnormal CFO": "Phần CFO bất thường sau khi kiểm soát doanh thu và tăng trưởng doanh thu. Abnormal CFO âm có thể báo hiệu kéo doanh thu bằng giảm giá hoặc nới điều kiện tín dụng.",
    "Abnormal PROD": "Chi phí sản xuất bất thường. Trong app, PROD = Giá vốn hàng bán + ΔTồn kho. Abnormal PROD dương có thể báo hiệu sản xuất dư/tồn kho tăng để giảm giá vốn đơn vị.",
    "Abnormal DISEXP": "Chi phí tùy ý bất thường. DISEXP thường gồm R&D, quảng cáo, SG&A; app dùng SG&A/chi phí bán hàng + quản lý làm proxy nếu thiếu chi tiết. Abnormal DISEXP âm có thể là cắt chi phí để nâng lợi nhuận ngắn hạn.",
    "AQI proxy": "Cách tính thay thế khi nguồn dữ liệu không tách được TSCĐ/PPE thuần. App dùng tỷ trọng tài sản dài hạn/tổng tài sản làm đại diện và ghi rõ proxy để tránh nhầm với AQI chuẩn của Beneish.",
    "PP&E/TSCĐ thuần": "Property, Plant and Equipment - tài sản cố định hữu hình thuần sau khấu hao. Đây là biến đầu vào tốt hơn tài sản dài hạn khi tính AQI chuẩn.",
    "Doanh thu ghi nhận sớm": "Rủi ro doanh nghiệp ghi nhận doanh thu trước khi hoàn tất nghĩa vụ hoặc trước khi khả năng thu tiền đủ chắc chắn. Trong app thường thể hiện qua DSRI/DSO tăng, phải thu tăng nhanh hơn doanh thu và CFO yếu.",
    "Chất lượng lợi nhuận": "Mức độ lợi nhuận kế toán được hỗ trợ bởi dòng tiền thật, biên lợi nhuận bền vững, chính sách kế toán thận trọng và ít phụ thuộc khoản mục một lần/ước tính chủ quan.",
    "Bút toán cuối kỳ": "Các bút toán điều chỉnh gần cuối kỳ hoặc sau ngày khóa sổ. Nếu có giá trị lớn, lặp lại bất thường hoặc thiếu giải thích, cần xem xét rủi ro làm đẹp lợi nhuận.",
    "Management Override": "Rủi ro ban điều hành vượt qua kiểm soát nội bộ để điều chỉnh số liệu kế toán, ước tính hoặc bút toán. Đây là nhóm rủi ro kiểm toán trọng yếu và cần đối chiếu với kiểm soát nội bộ/ý kiến kiểm toán.",
    "Revenue Recognition": "Ghi nhận doanh thu. Đây là khu vực dễ phát sinh rủi ro thao túng lợi nhuận, cần kiểm tra điều kiện ghi nhận, cutoff, phải thu, hoàn trả, chiết khấu, bên liên quan và dòng tiền thu từ khách hàng.",
    "Cutoff": "Kiểm tra doanh thu/chi phí có được ghi nhận đúng kỳ hay không. Sai cutoff có thể làm doanh thu/lợi nhuận kỳ hiện tại bị đẩy lên hoặc đẩy xuống không đúng bản chất.",
    "Capitalized Expense": "Chi phí được vốn hóa thành tài sản thay vì ghi nhận vào chi phí kỳ hiện tại. Nếu vốn hóa quá mức, lợi nhuận hiện tại có thể bị thổi phồng và AQI/TATA thường cần được soi kỹ.",
    "One-off Income": "Thu nhập bất thường/không lặp lại như thanh lý tài sản, hoàn nhập lớn, lãi đánh giá lại. Cần tách khỏi earnings power khi định giá.",
    "Restatement": "Việc điều chỉnh lại BCTC đã công bố. Đây là cờ đỏ cần kiểm tra nguyên nhân, quy mô điều chỉnh và ảnh hưởng đến lợi nhuận, vốn chủ, dòng tiền.",
    "DSRI": "Days Sales in Receivables Index - chỉ số phải thu/doanh thu kỳ hiện tại so với kỳ trước. DSRI cao có thể báo hiệu doanh thu ghi nhận lỏng hoặc thu tiền chậm.",
    "GMI": "Gross Margin Index - biên gộp kỳ trước chia biên gộp kỳ hiện tại. GMI > 1 nghĩa là biên gộp suy giảm, tăng động cơ làm đẹp lợi nhuận.",
    "AQI": "Asset Quality Index - chỉ số chất lượng tài sản. AQI > 1 có thể cho thấy tài sản kém thanh khoản/chi phí hoãn lại tăng.",
    "SGI": "Sales Growth Index - chỉ số tăng trưởng doanh thu. Tăng trưởng cao có thể tạo áp lực duy trì mục tiêu lợi nhuận.",
    "DEPI": "Depreciation Index - chỉ số khấu hao. DEPI > 1 có thể cho thấy tỷ lệ khấu hao giảm, cần kiểm tra thời gian hữu dụng/phương pháp khấu hao.",
    "SGAI": "SG&A Expense Index - chỉ số chi phí bán hàng và quản lý/doanh thu. SGAI > 1 phản ánh chi phí vận hành tăng nhanh hơn doanh thu.",
    "TATA": "Total Accruals to Total Assets - tổng accruals/tổng tài sản. TATA dương cao cho thấy lợi nhuận phụ thuộc accruals nhiều hơn dòng tiền.",
    "LVGI": "Leverage Index - chỉ số đòn bẩy. LVGI > 1 nghĩa là đòn bẩy tăng, có thể tăng động cơ làm đẹp BCTC để đáp ứng covenant/nợ.",
    "Compounder": "Doanh nghiệp chất lượng có thể tái đầu tư lợi nhuận với ROIC cao trong thời gian dài, từ đó làm giá trị nội tại tăng kép.",
    "Cost Advantage": "Lợi thế chi phí - khả năng sản xuất/phân phối/vận hành với chi phí thấp hơn đối thủ một cách bền vững.",
    "Cyclical": "Doanh nghiệp chu kỳ, lợi nhuận phụ thuộc mạnh vào giá hàng hóa, cung cầu ngành, công suất, tồn kho hoặc chu kỳ kinh tế.",
    "Deployed Capital": "Vốn triển khai vào hoạt động kinh doanh, thường loại bớt tiền/đầu tư tài chính dư thừa để nhìn hiệu quả vốn vận hành.",
    "Differentiation": "Khác biệt hóa - khả năng tạo giá trị cho khách hàng để duy trì biên lợi nhuận, thương hiệu, giá bán hoặc lòng trung thành.",
    "DIO": "Days Inventory Outstanding - số ngày tồn kho bình quân. DIO cao/tăng có thể báo hiệu hàng chậm luân chuyển.",
    "DPO": "Days Payable Outstanding - số ngày phải trả bình quân. DPO cao có thể hỗ trợ dòng tiền nhưng cũng có thể phản ánh áp lực thanh toán.",
    "DSO": "Days Sales Outstanding - số ngày phải thu bình quân. DSO tăng mạnh có thể báo hiệu rủi ro thu tiền.",
    "EBIT": "Earnings Before Interest and Taxes - lợi nhuận trước lãi vay và thuế. Dùng để đo lợi nhuận hoạt động trước tác động cấu trúc vốn.",
    "EBITDA": "EBIT + khấu hao và phân bổ. Hữu ích để tham khảo khả năng tạo lợi nhuận trước capex, nhưng không thay thế dòng tiền thật.",
    "EPS": "Earnings per Share - lợi nhuận trên mỗi cổ phiếu = LNST thuộc cổ đông công ty mẹ / số cổ phiếu.",
    "FCF": "Free Cash Flow - dòng tiền tự do. Trong app thường tính FCF = CFO - Capex. Cần phân biệt FCF âm do mở rộng hiệu quả với FCF âm do mô hình kinh doanh hút tiền.",
    "FCF/LNST": "Tỷ lệ FCF trên lợi nhuận sau thuế. Dùng để kiểm tra lợi nhuận có đi kèm dòng tiền tự do hay không.",
    "Giá trị nội tại": "Ước tính giá trị kinh tế của một cổ phiếu dựa trên lợi nhuận, dòng tiền, tài sản và chất lượng doanh nghiệp; không phải một con số tuyệt đối.",
    "High": "Kịch bản giá trị cao trong dải định giá. Chỉ nên dùng khi chất lượng dữ liệu, moat và triển vọng tăng trưởng đủ thuyết phục.",
    "Kd": "Cost of Debt - chi phí nợ vay trước thuế = chi phí lãi vay / nợ vay chịu lãi bình quân.",
    "Ke": "Cost of Equity - chi phí vốn chủ sở hữu. App dùng mô hình: lãi suất phi rủi ro + beta x phần bù rủi ro thị trường, hoặc proxy khi thiếu dữ liệu thị trường.",
    "Low": "Kịch bản giá trị thấp trong dải định giá. Dùng để kiểm tra downside và mức chịu đựng khi giả định xấu hơn xảy ra.",
    "Maintenance Capex": "Capex duy trì - phần vốn đầu tư cần thiết để giữ năng lực cạnh tranh và sản lượng dài hạn hiện tại.",
    "Moat": "Lợi thế cạnh tranh bền vững giúp doanh nghiệp duy trì lợi nhuận cao trên vốn trong thời gian dài.",
    "MOS": "Margin of Safety - biên an toàn. MOS hiện tại = (giá trị nội tại - giá thị trường) / giá trị nội tại. MOS yêu cầu là mức chiết khấu người dùng chọn trước khi xem xét mua.",
    "NCAV": "Net Current Asset Value - giá trị tài sản ngắn hạn ròng, thường dùng trong định giá tài sản theo Graham.",
    "NLA": "Net Liquid Assets - tài sản thanh khoản ròng = tiền + chứng khoán thanh khoản + phải thu có thể thu hồi - nợ ngắn hạn/nợ phải trả liên quan.",
    "NOPAT": "Net Operating Profit After Tax - lợi nhuận hoạt động sau thuế = EBIT x (1 - thuế suất). Dùng làm tử số phổ biến khi tính ROIC.",
    "OEPS": "Owner Earnings per Share - Owner Earnings trên mỗi cổ phiếu = Owner Earnings / số cổ phiếu lưu hành.",
    "Owner Earnings": "Lợi nhuận chủ sở hữu theo Buffett: lợi nhuận báo cáo + khấu hao và chi phí phi tiền mặt - capex duy trì cần thiết ± thay đổi vốn lưu động vận hành cần thiết.",
    "P/B": "Price to Book - giá / giá trị sổ sách. Hữu ích hơn với ngân hàng, bảo hiểm, asset play hoặc doanh nghiệp tài sản lớn.",
    "P/E": "Price to Earnings - giá / EPS. Dùng tốt hơn với doanh nghiệp có EPS ổn định, ít chu kỳ, lợi nhuận kế toán đáng tin.",
    "Porter Value Chain": "Chuỗi giá trị Porter - phân rã doanh nghiệp thành các hoạt động cụ thể để tìm nguồn gốc lợi thế chi phí/khác biệt hóa.",
    "QoQ": "Quarter over Quarter - tăng/giảm so với quý liền trước.",
    "ROCE": "Return on Capital Employed - lợi nhuận trên capital employed. Thường tính EBIT / capital employed.",
    "ROIC": "Return on Invested Capital - lợi nhuận trên vốn đầu tư. App ưu tiên ROIC Operating Profit = NOPAT / vốn đầu tư bình quân.",
    "ROIC Operating Profit": "ROIC dựa trên lợi nhuận hoạt động: NOPAT chia cho vốn đầu tư/capital employed bình quân. Dùng để so sánh với WACC.",
    "Switching Cost": "Chi phí chuyển đổi - mức khó khăn/chi phí khi khách hàng chuyển sang nhà cung cấp khác.",
    "TTM": "Trailing Twelve Months - số liệu 12 tháng gần nhất, thường cộng 4 quý gần nhất để có cái nhìn cập nhật hơn năm tài chính cũ.",
    "Turnaround": "Doanh nghiệp đang trong quá trình phục hồi; định giá cần kịch bản và biên an toàn lớn hơn do rủi ro thực thi.",
    "WACC": "Weighted Average Cost of Capital - chi phí vốn bình quân gia quyền = We x Ke + Wd x Kd x (1 - thuế suất). Dùng so sánh với ROIC, nhưng cần dữ liệu nợ vay, chi phí lãi vay, vốn hóa và chi phí vốn chủ.",
    "Weighted": "Giá trị nội tại trung bình trọng số từ các phương pháp định giá hợp lệ. Trọng số cao hơn được trao cho phương pháp phù hợp hơn với loại doanh nghiệp và chất lượng dữ liệu.",
    "YoY": "Year over Year - tăng/giảm so với cùng kỳ năm trước.",
}

COMPANY_TYPE_GUIDANCE = {
    "Quality Compounder": {
        "Cơ sở tư duy": "Buffett/Munger + ROIC/Moat + Owner Earnings",
        "Đặc điểm cần kiểm tra": "ROIC/ROCE cao và ổn định; biên lợi nhuận bền; CFO/LNST và FCF/LNST tốt; tái đầu tư được với lợi suất cao; nợ vay kiểm soát; moat đến từ thương hiệu, phân phối, quy mô, switching cost hoặc chi phí thấp.",
        "Cần phân tích thêm": "Runway tái đầu tư còn dài không; ROIC cao có bị kéo xuống khi mở rộng không; Owner Earnings có thật không hay bị capex duy trì lớn; ban lãnh đạo phân bổ vốn có kỷ luật không.",
        "Định giá nên ưu tiên": "Owner Earnings, Earnings Power, ROIC Reinvestment, FCF Yield; chỉ trả premium khi moat và tăng trưởng thật sự bền.",
    },
    "Compounder": {
        "Cơ sở tư duy": "Buffett/Munger + ROIC/Moat + Owner Earnings",
        "Đặc điểm cần kiểm tra": "ROIC cao hơn chi phí vốn; dòng tiền tốt; doanh thu/lợi nhuận tăng đều; doanh nghiệp có khả năng tái đầu tư; lợi thế cạnh tranh không phụ thuộc vào một chu kỳ ngắn.",
        "Cần phân tích thêm": "Tăng trưởng đến từ sản lượng, giá bán, mở rộng kênh hay M&A; chất lượng lợi nhuận; capex duy trì; rủi ro pha loãng; sức mạnh định giá.",
        "Định giá nên ưu tiên": "Owner Earnings, FCF, Earnings Power; kiểm tra MOS bằng dải giá trị thay vì một con số duy nhất.",
    },
    "Cyclical": {
        "Cơ sở tư duy": "Peter Lynch về cổ phiếu chu kỳ + Howard Marks về chu kỳ/rủi ro + Graham về chuẩn hóa lợi nhuận",
        "Đặc điểm cần kiểm tra": "Lợi nhuận biến động theo giá hàng hóa, cung cầu ngành, công suất, tồn kho, lãi suất hoặc chu kỳ đầu tư. P/E thấp ở đỉnh chu kỳ có thể là bẫy; P/E cao ở đáy chu kỳ chưa chắc là đắt.",
        "Cần phân tích thêm": "Đang ở giai đoạn nào của chu kỳ; biên lợi nhuận hiện tại so với trung bình 5-10 năm; sản lượng/công suất; tồn kho; nợ vay; capex lớn có rơi vào cuối chu kỳ không; lợi nhuận chuẩn hóa là bao nhiêu.",
        "Định giá nên ưu tiên": "Normalized earnings, P/B, ROCE qua chu kỳ, EV/EBITDA chuẩn hóa, asset value; MOS cần rộng hơn doanh nghiệp ổn định.",
    },
    "Asset Play": {
        "Cơ sở tư duy": "Graham/Dodd + Li Lu Timberland case + Net Liquid Assets",
        "Đặc điểm cần kiểm tra": "Giá thị trường thấp so với tài sản hữu hình/thanh khoản; downside được bảo vệ bởi tiền, tài sản, bất động sản, vốn lưu động hoặc giá trị thanh lý.",
        "Cần phân tích thêm": "Chất lượng tài sản; khoản phải thu/tồn kho có thu hồi được không; tài sản ẩn; nợ tiềm tàng; giao dịch bên liên quan; khả năng hiện thực hóa giá trị; quản trị có thân thiện cổ đông không.",
        "Định giá nên ưu tiên": "Book Value điều chỉnh, NCAV, NLA, Liquidation Value, P/B; không nên trả cao chỉ vì tài sản lớn nếu tài sản khó chuyển thành tiền.",
    },
    "Turnaround": {
        "Cơ sở tư duy": "Graham về bảo vệ downside + Howard Marks về kiểm soát rủi ro",
        "Đặc điểm cần kiểm tra": "Doanh nghiệp đang phục hồi từ suy giảm, lỗ, tái cấu trúc hoặc thay đổi chiến lược. Rủi ro thực thi cao và dữ liệu quá khứ có thể chưa đại diện tương lai.",
        "Cần phân tích thêm": "Nguyên nhân suy giảm đã xử lý chưa; dòng tiền có đủ sống sót không; nợ vay/đáo hạn; tài sản có bán được không; ban lãnh đạo mới; dấu hiệu cải thiện biên lợi nhuận và vòng quay vốn.",
        "Định giá nên ưu tiên": "Downside asset value, bear/base/bull scenario, normalized earnings sau phục hồi; yêu cầu MOS rất rộng.",
    },
    "Bank/Insurance": {
        "Cơ sở tư duy": "Peter Lynch/regional banks + tiêu chí ngân hàng trong bộ nguồn",
        "Đặc điểm cần kiểm tra": "BCTC đặc thù; đòn bẩy cao; ROE/P/B quan trọng hơn FCF; chất lượng tài sản và quản trị rủi ro quyết định giá trị.",
        "Cần phân tích thêm": "NIM, CASA, tăng trưởng tín dụng, NPL, nợ nhóm 2, bao phủ nợ xấu, chi phí tín dụng, CAR, chất lượng trái phiếu/tài sản đầu tư, governance.",
        "Định giá nên ưu tiên": "P/B so với ROE bền vững, residual income/earning power, chất lượng tài sản; không dùng FCF công nghiệp làm phương pháp lõi.",
    },
    "Chưa có dữ liệu tài chính": {
        "Cơ sở tư duy": "Nguyên tắc audit dữ liệu: không định giá khi chưa có BCTC nhiều kỳ đủ kiểm chứng",
        "Đặc điểm cần kiểm tra": "Chưa đủ chuỗi BCTC năm/quý để phân loại đáng tin cậy; cần kiểm tra nguồn dữ liệu, mã chứng khoán, kỳ báo cáo và file import/crawler.",
        "Cần phân tích thêm": "Tải hoặc import BCTC nhiều kỳ; đối chiếu doanh thu, LNST, CFO, capex, ROE/ROIC, nợ vay và vốn chủ trước khi chạy định giá.",
        "Định giá nên ưu tiên": "Tạm dừng định giá tự động; chỉ mở lại P/E, P/B, FCF, Owner Earnings, MOS khi dữ liệu đã đủ và có kiểm chứng nội bộ.",
    },
    "Normal Business": {
        "Cơ sở tư duy": "Graham/Buffett/Peter Lynch kết hợp",
        "Đặc điểm cần kiểm tra": "Doanh nghiệp chưa đủ bằng chứng để xếp compounder, cyclical, asset play hay turnaround. Cần đọc chất lượng lợi nhuận và lợi thế cạnh tranh trước khi trả premium.",
        "Cần phân tích thêm": "ROIC so với WACC; CFO/LNST; FCF; tăng trưởng doanh thu/lợi nhuận; biến động biên lợi nhuận; nợ vay; ngành có cạnh tranh gay gắt không; có moat thật không.",
        "Định giá nên ưu tiên": "Kết hợp P/E chuẩn hóa, FCF, Earnings Power, P/B; giảm trọng số các phương pháp thiếu dữ liệu và yêu cầu MOS phù hợp mức bất định.",
    },
}


def _render_company_type_guidance(current_type: str | None = None) -> None:
    raw_type = str(current_type or "Normal Business")
    current_type, info = _company_type_info(raw_type)
    st.subheader("Diễn giải loại hình doanh nghiệp & điểm cần phân tích thêm")
    st.markdown(
        f"""
        <div class='note-card'>
        <b style='color:#0B7F75;font-size:1.05rem'>Loại hiện tại: {html.escape(current_type)}</b><br>
        <b>Cơ sở tư duy:</b> {html.escape(info['Cơ sở tư duy'])}<br>
        <b>Đặc điểm cần kiểm tra:</b> {html.escape(info['Đặc điểm cần kiểm tra'])}<br>
        <b>Cần phân tích thêm:</b> {html.escape(info['Cần phân tích thêm'])}<br>
        <b>Định giá nên ưu tiên:</b> {html.escape(info['Định giá nên ưu tiên'])}
        </div>
        """,
        unsafe_allow_html=True,
    )
    type_df = pd.DataFrame([
        {"Loại doanh nghiệp": k, **v} for k, v in COMPANY_TYPE_GUIDANCE.items()
    ]).sort_values("Loại doanh nghiệp").reset_index(drop=True)
    type_df.insert(0, "STT", range(1, len(type_df) + 1))
    st.download_button("⬇️ Tải bảng loại hình doanh nghiệp", type_df.to_csv(index=False, encoding="utf-8-sig"), file_name="company_type_guidance.csv", mime="text/csv", use_container_width=True)
    rows_html = []
    for _, r in type_df.iterrows():
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('STT','')))}</td>"
            f"<td class='type-name'>{html.escape(str(r.get('Loại doanh nghiệp','')))}</td>"
            f"<td>{html.escape(str(r.get('Cơ sở tư duy','')))}</td>"
            f"<td>{html.escape(str(r.get('Đặc điểm cần kiểm tra','')))}</td>"
            f"<td>{html.escape(str(r.get('Cần phân tích thêm','')))}</td>"
            f"<td>{html.escape(str(r.get('Định giá nên ưu tiên','')))}</td>"
            "</tr>"
        )
    st.markdown(
        """
        <div style='overflow-x:auto; border:1px solid rgba(11,127,117,.22); border-radius:14px;'>
        <table class='type-fit-table'>
          <thead><tr><th>STT</th><th>Loại doanh nghiệp</th><th>Cơ sở tư duy</th><th>Đặc điểm cần kiểm tra</th><th>Cần phân tích thêm</th><th>Định giá nên ưu tiên</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        </div>
        <style>
        .type-fit-table {{width:100%; border-collapse:collapse; font-size:.92rem; line-height:1.42;}}
        .type-fit-table th {{position:sticky; top:0; background:#EAF7F1; color:#064E47; border:1px solid rgba(11,127,117,.20); padding:8px 10px; text-align:left; font-weight:950;}}
        .type-fit-table td {{border:1px solid rgba(11,127,117,.12); padding:8px 10px; vertical-align:top;}}
        .type-fit-table td.type-name {{font-weight:950; color:#0B5F58; background:#FFF4C7;}}
        </style>
        """.format(rows="".join(rows_html)),
        unsafe_allow_html=True,
    )


def _render_company_type_summary_callout(classification: object | None = None, current_type: str | None = None) -> None:
    """Render the yellow company-type card with ticker-specific classification reasons."""
    if classification is not None and hasattr(classification, "company_type"):
        raw_type = str(getattr(classification, "company_type", "Normal Business") or "Normal Business")
        confidence = getattr(classification, "confidence", None)
        reasons = [str(x).strip() for x in getattr(classification, "reasons", []) if str(x).strip()]
        preferred = [str(x).strip() for x in getattr(classification, "preferred_methods", []) if str(x).strip()]
    else:
        raw_type = str(current_type or classification or "Normal Business")
        confidence = None
        reasons = []
        preferred = []
    guide_type, info = _company_type_info(raw_type)
    confidence_text = f" · độ tin cậy {float(confidence):.0f}/100" if confidence is not None else ""
    reason_items = "".join(f"<li>{html.escape(reason)}</li>" for reason in reasons)
    if not reason_items:
        reason_items = "<li>Chưa có đủ dữ liệu định lượng để giải thích phân loại; cần cập nhật BCTC/nguồn dữ liệu trước khi kết luận.</li>"
    preferred_text = "; ".join(preferred) if preferred else info.get("Định giá nên ưu tiên", "N/A")
    st.markdown(
        f"""
        <div style="border:2px solid rgba(245,178,27,.65); border-left:12px solid #F5B21B; border-radius:18px;
                    padding:15px 18px; margin:10px 0 16px 0; background:linear-gradient(135deg,#FFF9E8 0%,#FFF3C4 100%);
                    color:#5F3B00; font-weight:900; line-height:1.58; box-shadow:0 9px 22px rgba(245,178,27,.13);">
          <div style="font-size:1.08rem; color:#0B7F75; font-weight:1000; margin-bottom:6px;">📌 Phân loại doanh nghiệp: {html.escape(raw_type)}{html.escape(confidence_text)}</div>
          <div style="font-size:.90rem; color:#7A4B00; margin-bottom:8px;"><b>Nhóm hướng dẫn áp dụng:</b> {html.escape(guide_type)}</div>
          <div><b style="color:#9A6600;">Đặc điểm cần kiểm tra:</b> {html.escape(info.get('Đặc điểm cần kiểm tra','N/A'))}</div>
          <div><b style="color:#9A6600;">Cần phân tích thêm:</b> {html.escape(info.get('Cần phân tích thêm','N/A'))}</div>
          <div><b style="color:#9A6600;">Định giá nên ưu tiên:</b> {html.escape(preferred_text)}</div>
          <div style="margin-top:10px; padding-top:9px; border-top:1px solid rgba(154,102,0,.22);">
            <div style="font-size:1.02rem; color:#8A5A00; font-weight:1000; margin-bottom:4px;">🟡 Lý do phân loại theo dữ liệu mã đang phân tích</div>
            <ul style="margin:6px 0 0 20px; padding:0;">{reason_items}</ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _augment_auto_summary_with_checklist(summary: object, current_type: str | None = None) -> str:
    """Không chèn Đặc điểm cần kiểm tra vào card đỏ Tóm tắt tự động."""
    return "" if summary is None else str(summary)


def _render_glossary_panel() -> None:
    st.subheader("Diễn giải thuật ngữ và từ viết tắt")
    st.caption("Bảng thuật ngữ được sắp xếp theo thứ tự chữ cái; cột Thuật ngữ tự ôm sát nội dung, cột Diễn giải mở rộng và xuống dòng để dễ đọc.")
    glossary_df = pd.DataFrame([{"Thuật ngữ": k, "Diễn giải": v} for k, v in GLOSSARY_TERMS.items()])
    glossary_df = glossary_df.sort_values("Thuật ngữ", key=lambda s: s.str.lower()).reset_index(drop=True)
    glossary_df.insert(0, "STT", range(1, len(glossary_df) + 1))
    st.download_button("⬇️ Tải bảng thuật ngữ", glossary_df.to_csv(index=False, encoding="utf-8-sig"), file_name="glossary.csv", mime="text/csv", use_container_width=True)
    rows = []
    for _, r in glossary_df.iterrows():
        rows.append(
            "<tr>"
            f"<td class='stt'>{html.escape(str(r.get('STT', '')))}</td>"
            f"<td class='term'>{html.escape(str(r.get('Thuật ngữ', '')))}</td>"
            f"<td class='desc'>{html.escape(str(r.get('Diễn giải', '')))}</td>"
            "</tr>"
        )
    table_html = """
    <div style='max-height:560px; overflow:auto; border-radius:14px; box-shadow:0 8px 20px rgba(11,127,117,.07);'>
      <table class='glossary-fit-table'>
        <thead><tr><th class='stt'>STT</th><th class='term'>Thuật ngữ</th><th class='desc'>Diễn giải</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """.format(rows="".join(rows))
    st.markdown(table_html, unsafe_allow_html=True)

def _render_no_data(ticker: str, source: str, available_tickers: list[str], error: str | None = None) -> None:
    info = _listed_ticker_info_cached(str(BUNDLED_XLSM), ticker) if BUNDLED_XLSM.exists() else {}
    name = info.get("company_name", ticker)
    exchange = info.get("exchange", "")
    st.error(f"Chưa có dữ liệu BCTC nhiều kỳ để định giá mã {ticker} từ nguồn '{source}'.")
    if info:
        st.info(f"Đã nhận diện mã {ticker}: {name} ({exchange}). Tuy nhiên dữ liệu tích hợp hiện chưa có block BCTC nhiều kỳ cho mã này.")
    if error:
        st.warning(error)
    st.markdown(
        f"""
        <div class='warn-card'>
        <b>Ý nghĩa màn hình này:</b><br>
        App không bị treo. Định giá chuyên sâu đang chặn việc định giá khi chưa có đủ BCTC, để tránh hiện N/A hoặc chấm moat ảo.<br><br>
        <b>Cách xử lý:</b><br>
        1) Chọn một mã có dữ liệu trong danh sách bên trái để test ngay.<br>
        2) Với mã <b>{ticker}</b>, chọn chế độ <b>Tự động</b> hoặc <b>Dữ liệu ưu tiên</b> để app dùng lại bộ BCTC đã chuẩn hóa của Tổng quan doanh nghiệp.<br>
        3) Nếu dữ liệu chưa đủ, có thể thử chế độ <b>Dữ liệu trực tuyến</b> hoặc cập nhật/import file dữ liệu tích hợp có chứa block BCTC của mã này rồi chạy lại.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if available_tickers:
        st.success("Các mã có đủ dữ liệu tích hợp: " + ", ".join(available_tickers))


def _update_module2_web_evidence(company) -> None:
    """Tìm evidence internet và lưu vào session cho đúng mã đang phân tích."""
    try:
        ticker = _safe_ticker(getattr(company, "ticker", ""))
        company_name = str(getattr(company, "company_name", "") or "")
        result = WebEvidenceAgent(RAW_DIR).search(ticker, company_name)
        st.session_state["module2_web_table"] = result.table
        st.session_state["module2_web_note"] = result.note
        st.session_state["module2_web_ticker"] = ticker
        st.session_state["module2_web_updated_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["module2_auto_update_status"] = (
            f"Đã cập nhật BCTC/cache Tổng quan doanh nghiệp → Định giá chuyên sâu và evidence internet cho {ticker} lúc {st.session_state['module2_web_updated_at']}"
        )
    except Exception as exc:
        st.session_state["module2_auto_update_status"] = f"Không cập nhật được evidence internet: {exc}"



PEER_UNIVERSE_CSV = DATA_CACHE_DIR / "peer_universe.csv"


SIMPLIZE_PEER_COLUMNS = [
    "ticker", "company_name", "current_price", "price_change_pct", "change_7d_pct", "change_1y_pct",
    "pe", "pb", "roe_pct", "forecast_profit_growth_3y_pct", "dividend_yield_pct", "exchange",
    "market_cap_bil", "chart_30d", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"
]


PEER_BAD_TICKERS = {
    "ROE", "ROA", "ROIC", "EPS", "PE", "PB", "PS", "P/E", "P/B", "FCF", "CFO", "EBIT", "EBITDA",
    "LNST", "LNTT", "DT", "TTM", "YOY", "QOQ", "MOM", "DPS", "WACC", "MOS", "NIM", "CASA", "NPL",
    "HTML", "HTTP", "HTTPS", "JSON", "POST", "GET", "API", "CSS", "JS", "PDF", "XLS",
    "TRUE", "FALSE", "NULL", "NONE", "NAN", "STOCK", "STOCKS", "HOSTC", "HOST",
    "HOSE", "HNX", "UPCOM", "INDEX", "CODE", "NAME", "SYMBOL", "TICKER", "MARKET",
    "FLOOR", "HOME", "LOGIN", "LOGO", "DATA", "IR", "PR", "ETF", "GDP", "PMI",
}


def _is_probable_peer_ticker(code: object) -> bool:
    """Strict filter for peer tickers; prevents table headers like ROE from becoming rows."""
    text = _safe_ticker(str(code or ""))
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,5}", text):
        return False
    if text in PEER_BAD_TICKERS:
        return False
    if len(text) > 4 and not any(ch.isdigit() for ch in text):
        return False
    if re.search(r"(HTML|HTTP|JSON|STOCK|HOST|INDEX|LOGIN|DATA|ROE|ROA|EPS|FCF|CFO|MOS|WACC)", text):
        return False
    return True


def _empty_peer_universe() -> pd.DataFrame:
    return pd.DataFrame(columns=SIMPLIZE_PEER_COLUMNS)


def _normalize_peer_universe(df: pd.DataFrame | None) -> pd.DataFrame:
    base_cols = SIMPLIZE_PEER_COLUMNS
    if df is None or df.empty:
        return _empty_peer_universe()
    out = df.copy()
    rename = {}
    for c in out.columns:
        lc = str(c).strip().lower()
        if lc in {"mã", "ma", "ma_cp", "mã cp", "mã cổ phiếu", "code", "symbol"}:
            rename[c] = "ticker"
        elif lc in {"tên", "ten", "company", "company_name", "tên doanh nghiệp", "doanh nghiệp"}:
            rename[c] = "company_name"
        elif lc in {"sàn", "san", "exchange"}:
            rename[c] = "exchange"
        elif lc in {"ngành", "nganh", "industry"}:
            rename[c] = "industry"
        elif lc in {"phân ngành", "phan nganh", "sub_industry", "sub industry"}:
            rename[c] = "sub_industry"
        elif lc in {"nhóm ngành", "nhom nganh", "peer_group", "group"}:
            rename[c] = "peer_group"
        elif lc in {"nguồn", "nguon", "source"}:
            rename[c] = "source"
        elif lc in {"ghi chú", "ghi chu", "note"}:
            rename[c] = "note"
        elif lc in {"giá hiện tại", "gia hien tai", "current_price", "last_price", "price"}:
            rename[c] = "current_price"
        elif lc in {"biến động giá", "bien dong gia", "price_change_pct", "change_pct", "thay đổi giá %"}:
            rename[c] = "price_change_pct"
        elif lc in {"7 ngày", "7 ngay", "7d", "change_7d_pct"}:
            rename[c] = "change_7d_pct"
        elif lc in {"1 năm", "1 nam", "1y", "change_1y_pct"}:
            rename[c] = "change_1y_pct"
        elif lc in {"p/e", "pe"}:
            rename[c] = "pe"
        elif lc in {"p/b", "pb"}:
            rename[c] = "pb"
        elif lc in {"roe", "roe %", "roe_pct"}:
            rename[c] = "roe_pct"
        elif lc in {"t.trưởng lnst 3 năm dự phóng", "tang truong lnst 3 nam du phong", "forecast_profit_growth_3y_pct"}:
            rename[c] = "forecast_profit_growth_3y_pct"
        elif lc in {"tỷ suất cổ tức", "ty suat co tuc", "dividend_yield_pct"}:
            rename[c] = "dividend_yield_pct"
        elif lc in {"vốn hóa", "von hoa", "market_cap", "market_cap_bil", "vốn hóa (tỷ đồng)"}:
            rename[c] = "market_cap_bil"
        elif lc in {"biểu đồ giá 30d", "bieu do gia 30d", "chart_30d"}:
            rename[c] = "chart_30d"
    out = out.rename(columns=rename)
    for c in base_cols:
        if c not in out.columns:
            out[c] = ""
    out = out[base_cols].copy()
    out["ticker"] = out["ticker"].astype(str).map(_safe_ticker)
    out = out[out["ticker"].map(_is_probable_peer_ticker)]
    for num_col in ["current_price", "price_change_pct", "change_7d_pct", "change_1y_pct", "pe", "pb", "roe_pct", "forecast_profit_growth_3y_pct", "dividend_yield_pct", "market_cap_bil"]:
        if num_col in out.columns:
            out[num_col] = pd.to_numeric(out[num_col], errors="coerce")
    out["peer_group"] = out["peer_group"].replace({None: ""}).astype(str)
    fallback_group = out["industry"].fillna("").astype(str).where(out["industry"].fillna("").astype(str).str.len() > 0, "Chưa phân nhóm")
    out["peer_group"] = out["peer_group"].where(out["peer_group"].str.strip().str.len() > 0, fallback_group)
    # Giữ bản ghi đầy đủ nhất khi trùng mã; tránh dòng mã đang phân tích bị trống do cache cũ/row kỹ thuật ghi đè dữ liệu cùng ngành.
    non_empty = out.replace("", pd.NA).notna().sum(axis=1)
    out = out.assign(_complete_score=non_empty).sort_values(["ticker", "_complete_score"]).drop_duplicates(subset=["ticker"], keep="last").drop(columns=["_complete_score"])
    if "market_cap_bil" in out.columns and pd.to_numeric(out["market_cap_bil"], errors="coerce").notna().any():
        out = out.assign(_sort_cap=pd.to_numeric(out["market_cap_bil"], errors="coerce")).sort_values(["peer_group", "_sort_cap", "ticker"], ascending=[True, False, True]).drop(columns=["_sort_cap"])
    else:
        out = out.sort_values(["peer_group", "ticker"])
    out = out.reset_index(drop=True)
    return out


def _load_peer_universe() -> pd.DataFrame:
    if PEER_UNIVERSE_CSV.exists():
        try:
            return _normalize_peer_universe(pd.read_csv(PEER_UNIVERSE_CSV))
        except Exception:
            return _empty_peer_universe()
    return _empty_peer_universe()


def _save_peer_universe(df: pd.DataFrame) -> None:
    PEER_UNIVERSE_CSV.parent.mkdir(parents=True, exist_ok=True)
    _normalize_peer_universe(df).to_csv(PEER_UNIVERSE_CSV, index=False, encoding="utf-8-sig")


@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
def _simplize_industry_peers_cached(ticker: str, raw_dir: str, industry_url: str = "") -> tuple[pd.DataFrame, str, str]:
    raw_path, peer_df, note = PublicSimplizeCrawler(raw_dir).fetch_industry_peers(ticker, industry_url or None)
    return _normalize_peer_universe(peer_df), note, str(raw_path)


def _load_simplize_peer_rows(ticker: str, industry_url: str = "") -> tuple[pd.DataFrame, str, str]:
    ticker = _safe_ticker(ticker)
    if not ticker:
        return _empty_peer_universe(), "Chưa có mã cổ phiếu để lấy danh sách ngành.", ""
    try:
        return _simplize_industry_peers_cached(ticker, str(RAW_DIR), industry_url or "")
    except Exception as exc:
        return _empty_peer_universe(), f"Không cập nhật được danh sách cùng ngành cho {ticker}: {_public_text(exc)}", ""


def _company_peer_group(company) -> str:
    sub = _display_industry_value(getattr(company, "sub_industry", ""))
    ind = _display_industry_value(getattr(company, "industry", ""))
    return (sub if sub != "N/A" else "") or (ind if ind != "N/A" else "") or "Chưa phân nhóm"


def _company_to_peer_row(company, source_label: str = "Mã đang phân tích", note: str = "") -> dict:
    ticker = _safe_ticker(str(getattr(company, "ticker", "")))
    return {
        "ticker": ticker,
        "company_name": str(getattr(company, "company_name", "") or ticker),
        "exchange": str(getattr(company, "exchange", "") or ""),
        "industry": _display_industry_value(getattr(company, "industry", "")),
        "sub_industry": _display_industry_value(getattr(company, "sub_industry", "")),
        "peer_group": _company_peer_group(company),
        "current_price": _parse_num(getattr(company, "current_price", None)),
        "market_cap_bil": _parse_num(getattr(company, "market_cap_bil", None)),
        "pe": _parse_num(getattr(company, "pe", None)),
        "pb": _parse_num(getattr(company, "pb", None)),
        "roe_pct": _parse_num(getattr(company, "roe", None)),
        "source": source_label,
        "note": note,
        "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _merge_peer_rows(base: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    add = _normalize_peer_universe(pd.DataFrame(rows)) if rows else _empty_peer_universe()
    return _normalize_peer_universe(pd.concat([base, add], ignore_index=True))


def _ensure_current_peer_row(df: pd.DataFrame, company) -> pd.DataFrame:
    """Ensure the base ticker row is never blank and remains visible in the peer list."""
    out = _normalize_peer_universe(df)
    cur = _company_to_peer_row(company, "Mã đang phân tích", "Dòng mã gốc được ghim và tick mặc định")
    ticker = _safe_ticker(cur.get("ticker"))
    if not ticker:
        return out
    if out.empty or "ticker" not in out.columns:
        return _normalize_peer_universe(pd.DataFrame([cur]))
    mask = out["ticker"].astype(str).map(_safe_ticker).eq(ticker)
    if not mask.any():
        out = pd.concat([pd.DataFrame([cur]), out], ignore_index=True)
        return _normalize_peer_universe(out)
    idx = out.index[mask][0]
    # Always keep identity fields from the active company; preserve richer peer metrics if present.
    out.at[idx, "ticker"] = ticker
    for col in ["company_name", "exchange", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"]:
        cur_val = cur.get(col, "")
        old_val = out.at[idx, col] if col in out.columns else ""
        if str(old_val).strip() in {"", "nan", "None", "N/A"} and str(cur_val).strip():
            out.at[idx, col] = cur_val
    for col in ["current_price", "market_cap_bil", "pe", "pb", "roe_pct"]:
        old_num = _parse_num(out.at[idx, col]) if col in out.columns else None
        cur_num = _parse_num(cur.get(col))
        if old_num is None and cur_num is not None:
            out.at[idx, col] = cur_num
    return _normalize_peer_universe(out)


def _recent_median_local(df: pd.DataFrame, *cols: str, n: int = 5) -> float | None:
    if df is None or df.empty:
        return None
    for col in cols:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna().tail(n)
            if not s.empty:
                return float(s.median())
    return None


def _latest_num_local(df: pd.DataFrame, *cols: str) -> float | None:
    if df is None or df.empty:
        return None
    row = df.iloc[-1].to_dict()
    for col in cols:
        val = _parse_num(row.get(col))
        if val is not None:
            return val
    return None


def _cagr_local(df: pd.DataFrame, col: str, years: int = 5) -> float | None:
    if df is None or df.empty or col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna().tail(years + 1)
    if len(s) < 2:
        return None
    start, end = float(s.iloc[0]), float(s.iloc[-1])
    periods = len(s) - 1
    if start <= 0 or end <= 0 or periods <= 0:
        return None
    return ((end / start) ** (1 / periods) - 1) * 100


def _score_high(value: float | None, good: float, ok: float, weak: float) -> float:
    if value is None:
        return 45.0
    if value >= good:
        return 100.0
    if value >= ok:
        return 75.0
    if value >= weak:
        return 50.0
    return 20.0


def _score_low(value: float | None, good: float, ok: float, bad: float) -> float:
    if value is None or value <= 0:
        return 45.0
    if value <= good:
        return 100.0
    if value <= ok:
        return 75.0
    if value <= bad:
        return 50.0
    return 20.0


def _mean_ignore_none(values: list[float | None]) -> float:
    vals = [float(v) for v in values if v is not None and not pd.isna(v)]
    return sum(vals) / len(vals) if vals else 45.0


def _peer_snapshot(ticker: str, source_for_peer: str, assumptions: dict, target_mos_pct: float) -> tuple[dict, dict | None]:
    ticker = _safe_ticker(ticker)
    try:
        c, annual, quarterly, label, _paths = _load_data(ticker, source_for_peer)
        if not _has_real_financial_data(annual):
            raise RuntimeError("Không có dữ liệu tài chính nhiều kỳ hợp lệ")
        valuation = build_module2_valuation_table(c, annual, assumptions)
        current_price = _parse_num(getattr(c, "current_price", None))
        value_range = build_valuation_range(valuation, current_price, float(target_mos_pct))
        moat = build_porter_moat_scorecard(c, annual)
        cls = classify_company(c, annual)
        roe = _recent_median_local(annual, "roe_actual_pct", "roe_pct")
        roic = _recent_median_local(annual, "roic_standard_pct", "roic_pct")
        gross_margin = _recent_median_local(annual, "gross_margin_pct")
        net_margin = _recent_median_local(annual, "net_margin_pct")
        cfo_np = _recent_median_local(annual, "cfo_to_net_profit")
        fcf_np = _recent_median_local(annual, "fcf_to_net_profit")
        revenue_cagr = _cagr_local(annual, "revenue_bil")
        profit_cagr = _cagr_local(annual, "net_profit_bil")
        net_debt_equity = _latest_num_local(annual, "net_debt_to_equity")
        pe = _parse_num(getattr(c, "pe", None))
        pb = _parse_num(getattr(c, "pb", None))
        mos = value_range.mos_to_weighted_pct
        moat_score = float(moat.attrs.get("total_score", 0) or 0)

        quality_score = _mean_ignore_none([_score_high(roic, 15, 10, 5), _score_high(roe, 18, 12, 6), _score_high(gross_margin, 30, 18, 10)])
        cash_score = _mean_ignore_none([_score_high(cfo_np, 1.0, 0.7, 0.3), _score_high(fcf_np, 0.8, 0.3, 0.0)])
        valuation_score = _mean_ignore_none([_score_high(mos, float(target_mos_pct), 0, -20), _score_low(pe, 8, 12, 20), _score_low(pb, 1.0, 1.8, 3.0)])
        risk_penalty = 10 if net_debt_equity is not None and net_debt_equity > 1.5 else 0
        total_score = max(0.0, min(100.0, 0.30 * quality_score + 0.25 * cash_score + 0.25 * moat_score + 0.20 * valuation_score - risk_penalty))
        if total_score >= 80 and mos is not None and mos >= float(target_mos_pct):
            conclusion = "Ưu tiên cao: chất lượng/định giá cùng thuận lợi, cần xác nhận thêm bằng BCTN và rủi ro ngành."
        elif total_score >= 72 and (mos or -999) >= 0:
            conclusion = "Theo dõi tốt: chất lượng tương đối cao nhưng cần kiểm tra MOS/chu kỳ trước khi giải ngân."
        elif total_score >= 60:
            conclusion = "Trung bình: chỉ nên xem là mã đối chiếu hoặc chờ giá/triển vọng rõ hơn."
        else:
            conclusion = "Thận trọng: điểm tổng hợp yếu hoặc dữ liệu/rủi ro chưa ủng hộ."
        row = {
            "Mã": ticker,
            "Tên doanh nghiệp": getattr(c, "company_name", ""),
            "Sàn": getattr(c, "exchange", ""),
            "Ngành": getattr(c, "industry", ""),
            "Phân ngành": getattr(c, "sub_industry", ""),
            "Loại DN": cls.company_type,
            "Giá hiện tại": current_price,
            "Giá trị weighted": value_range.weighted_vnd,
            "MOS hiện tại %": mos,
            "P/E": pe,
            "P/B": pb,
            "ROE %": roe,
            "ROIC %": roic,
            "Biên gộp %": gross_margin,
            "Biên ròng %": net_margin,
            "CAGR DT 5Y %": revenue_cagr,
            "CAGR LNST 5Y %": profit_cagr,
            "CFO/LNST": cfo_np,
            "FCF/LNST": fcf_np,
            "Nợ ròng/VCSH": net_debt_equity,
            "Vốn hóa (tỷ đồng)": _parse_num(getattr(c, "market_cap_bil", None)),
            "Moat score": moat_score,
            "Moat level": moat.attrs.get("level", "N/A"),
            "Điểm chất lượng": quality_score,
            "Điểm dòng tiền": cash_score,
            "Điểm định giá": valuation_score,
            "Điểm tổng hợp": total_score,
            "Xếp hạng": None,
            "Kết luận so sánh": conclusion,
        }
        return row, _company_to_peer_row(c, label, "Đã cập nhật từ lệnh so sánh")
    except Exception as exc:
        return {
            "Mã": ticker,
            "Tên doanh nghiệp": "",
            "Sàn": "",
            "Ngành": "",
            "Phân ngành": "",
            "Loại DN": "Không đủ dữ liệu",
            "Giá hiện tại": None,
            "Giá trị weighted": None,
            "MOS hiện tại %": None,
            "P/E": None,
            "P/B": None,
            "ROE %": None,
            "ROIC %": None,
            "Biên gộp %": None,
            "Biên ròng %": None,
            "CAGR DT 5Y %": None,
            "CAGR LNST 5Y %": None,
            "CFO/LNST": None,
            "FCF/LNST": None,
            "Nợ ròng/VCSH": None,
            "Vốn hóa (tỷ đồng)": None,
            "Moat score": None,
            "Moat level": "N/A",
            "Điểm chất lượng": None,
            "Điểm dòng tiền": None,
            "Điểm định giá": None,
            "Điểm tổng hợp": 0,
            "Xếp hạng": None,
            "Kết luận so sánh": f"Không so sánh được: {exc}",
        }, None


def _rank_peer_comparison(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["Điểm tổng hợp"] = pd.to_numeric(out.get("Điểm tổng hợp"), errors="coerce").fillna(0)
    out["_mos_sort"] = pd.to_numeric(out.get("MOS hiện tại %"), errors="coerce").fillna(-999)
    out["_moat_sort"] = pd.to_numeric(out.get("Moat score"), errors="coerce").fillna(-999)
    out = out.sort_values(["Điểm tổng hợp", "_mos_sort", "_moat_sort"], ascending=[False, False, False]).drop(columns=["_mos_sort", "_moat_sort"]).reset_index(drop=True)
    out["Xếp hạng"] = range(1, len(out) + 1)
    return out


def _peer_comparison_summary(df: pd.DataFrame, target_mos_pct: float) -> str:
    if df is None or df.empty:
        return "Chưa có kết quả so sánh."
    ok = df[pd.to_numeric(df.get("Điểm tổng hợp"), errors="coerce").fillna(0) > 0].copy()
    if ok.empty:
        return "Các mã đã chọn chưa có đủ dữ liệu để so sánh."
    top = ok.sort_values("Điểm tổng hợp", ascending=False).iloc[0]
    moat_leaders = ok.sort_values("Moat score", ascending=False).head(3)["Mã"].astype(str).tolist() if "Moat score" in ok else []
    mos_candidates = ok[pd.to_numeric(ok.get("MOS hiện tại %"), errors="coerce").fillna(-999) >= float(target_mos_pct)]["Mã"].astype(str).tolist()
    text = (
        f"Mã đứng đầu theo điểm tổng hợp là **{top.get('Mã')}** với {top.get('Điểm tổng hợp', 0):,.1f}/100. "
        f"Các mã có moat score nổi bật: {', '.join(moat_leaders) if moat_leaders else 'chưa đủ dữ liệu'}. "
        f"Các mã đạt MOS yêu cầu {float(target_mos_pct):.0f}%: {', '.join(mos_candidates) if mos_candidates else 'chưa có mã nào đạt'}. "
        "Cách đọc: bảng này chỉ là bộ lọc tương đối trong cùng ngành; quyết định cuối cùng vẫn phải kiểm tra BCTC gốc, lợi thế cạnh tranh, chu kỳ ngành và sự kiện bất thường."
    )
    return text


def _build_peer_row_note(rowd: dict) -> str:
    return "\n".join([
        f"SO SÁNH CÙNG NGÀNH: {rowd.get('Mã', 'N/A')} - {rowd.get('Tên doanh nghiệp', '')}",
        f"- Xếp hạng: {rowd.get('Xếp hạng', 'N/A')}; điểm tổng hợp: {_format_note_value(rowd.get('Điểm tổng hợp'))}/100.",
        f"- Chất lượng vốn: ROE {_format_note_value(rowd.get('ROE %'))}%; ROIC {_format_note_value(rowd.get('ROIC %'))}%; biên gộp {_format_note_value(rowd.get('Biên gộp %'))}%.",
        f"- Chất lượng dòng tiền: CFO/LNST {_format_note_value(rowd.get('CFO/LNST'))}; FCF/LNST {_format_note_value(rowd.get('FCF/LNST'))}.",
        f"- Định giá: giá hiện tại {_format_note_value(rowd.get('Giá hiện tại'))}; giá trị weighted {_format_note_value(rowd.get('Giá trị weighted'))}; MOS {_format_note_value(rowd.get('MOS hiện tại %'))}%; P/E {_format_note_value(rowd.get('P/E'))}; P/B {_format_note_value(rowd.get('P/B'))}.",
        f"- Porter/Moat: {rowd.get('Moat score', 'N/A')}/100 - {rowd.get('Moat level', 'N/A')}.",
        f"- Kết luận tự động: {rowd.get('Kết luận so sánh', 'N/A')}",
        "Nguyên tắc: điểm tổng hợp = 30% chất lượng sinh lời/vốn + 25% chất lượng dòng tiền + 25% Porter Moat + 20% định giá/MOS, có phạt rủi ro nếu đòn bẩy cao. Đây là bộ lọc tương đối, không thay thế phân tích riêng từng mã.",
    ])


def _render_value_chain_spider_chart(value_chain_df: pd.DataFrame, company=None) -> None:
    """Render radar/spider chart from Porter value-chain heat scores."""
    if value_chain_df is None or value_chain_df.empty or "Hoạt động chuỗi giá trị" not in value_chain_df.columns or "Điểm nhiệt" not in value_chain_df.columns:
        st.info("Chưa đủ dữ liệu điểm nhiệt để vẽ biểu đồ màng nhện chuỗi giá trị.")
        return
    chart_df = value_chain_df[["Hoạt động chuỗi giá trị", "Điểm nhiệt", "Đánh giá sơ bộ", "Mức độ"]].copy()
    chart_df["Điểm nhiệt"] = pd.to_numeric(chart_df["Điểm nhiệt"], errors="coerce").fillna(0).clip(0, 100)
    theta = chart_df["Hoạt động chuỗi giá trị"].astype(str).tolist()
    r = chart_df["Điểm nhiệt"].astype(float).tolist()
    custom = [
        f"{act}<br>Điểm nhiệt: {score:.1f}/100<br>Đánh giá: {rating}<br>Mức độ: {level}"
        for act, score, rating, level in zip(chart_df["Hoạt động chuỗi giá trị"], chart_df["Điểm nhiệt"], chart_df["Đánh giá sơ bộ"], chart_df["Mức độ"])
    ]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=r + r[:1],
        theta=theta + theta[:1],
        fill="toself",
        name=str(getattr(company, "ticker", "Chuỗi giá trị") or "Chuỗi giá trị"),
        text=custom + custom[:1],
        hovertemplate="%{text}<extra></extra>",
    ))
    fig.update_layout(
        title="Biểu đồ màng nhện điểm nhiệt Chuỗi giá trị Porter",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10))),
        showlegend=False,
        height=520,
        margin=dict(l=50, r=50, t=70, b=45),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Điểm nhiệt lấy trực tiếp từ bảng 'Bản đồ chuỗi giá trị theo Porter': Tốt = 100, Trung bình = 55, Yếu = 15, Chưa đủ dữ liệu/Cần bổ sung = 35.")





def _render_value_chain_yellow_assessment_card(value_chain_df: pd.DataFrame) -> None:
    """Render a brand-yellow executive assessment card for the Porter value-chain map."""
    if value_chain_df is None or value_chain_df.empty:
        st.markdown(
            """
            <div style="border:2px solid rgba(245,178,27,.72); border-left:12px solid #F5B21B; border-radius:18px;
                        padding:15px 18px; margin:10px 0 14px 0; background:linear-gradient(135deg,#FFF9E8 0%,#FEF3C7 100%);
                        color:#7A4A00; font-weight:850; line-height:1.55; box-shadow:0 9px 22px rgba(245,178,27,.16);">
              <div style="font-size:1.12rem; color:#0B7F75; font-weight:1000; margin-bottom:6px;">🟡 Đánh giá chuỗi giá trị Porter</div>
              <div><b>Trạng thái:</b> Chưa có dữ liệu để tổng hợp.</div>
              <div><b>Cần bổ sung:</b> BCTC/BCTN/tin IR hoặc dữ liệu định lượng từ Tổng quan doanh nghiệp để nhận diện hoạt động nào tạo lợi thế chi phí, khác biệt hóa hoặc rào cản khó bắt chước.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    df = value_chain_df.copy()
    score_series = pd.to_numeric(df.get("Điểm nhiệt", pd.Series(dtype=float)), errors="coerce").dropna()
    avg_score = float(score_series.mean()) if not score_series.empty else 0.0
    rating_series = df.get("Đánh giá sơ bộ", pd.Series(dtype=object)).fillna("").astype(str)

    good_mask = rating_series.str.contains("Tốt", case=False, na=False)
    medium_mask = rating_series.str.contains("Trung bình", case=False, na=False)
    weak_mask = rating_series.str.contains("Yếu", case=False, na=False)
    missing_mask = rating_series.str.contains("Chưa đủ|Cần bổ sung|Thiếu", case=False, regex=True, na=False)

    good_count = int(good_mask.sum())
    medium_count = int(medium_mask.sum())
    weak_count = int(weak_mask.sum())
    missing_count = int(missing_mask.sum())

    def _items(mask, limit: int = 4) -> list[str]:
        if "Hoạt động chuỗi giá trị" not in df.columns:
            return []
        return df.loc[mask, "Hoạt động chuỗi giá trị"].dropna().astype(str).head(limit).tolist()

    strengths = _items(good_mask) or ["Chưa có hoạt động được chấm Tốt"]
    risk_items = (_items(weak_mask) + _items(missing_mask & ~weak_mask)) or ["Chưa có điểm yếu nổi bật từ bảng hiện tại"]

    if avg_score >= 75 and weak_count == 0:
        level = "Chuỗi giá trị mạnh"
        conclusion = "Nhiều hoạt động có tín hiệu lợi thế rõ; có thể xem là điểm cộng cho moat nếu bằng chứng định tính trong BCTN/IR xác nhận được tính bền vững."
    elif avg_score >= 55:
        level = "Chuỗi giá trị khá / cần kiểm chứng"
        conclusion = "Có tín hiệu lợi thế ở một số hoạt động, nhưng chưa nên kết luận moat mạnh nếu còn nhiều khâu thiếu bằng chứng hoặc chỉ số định lượng chưa đồng thuận."
    elif avg_score >= 40:
        level = "Chuỗi giá trị trung bình / chưa rõ moat"
        conclusion = "Lợi thế cạnh tranh chưa đủ rõ; cần ưu tiên kiểm tra hoạt động tạo chi phí thấp, khác biệt hóa và khả năng duy trì ROIC/biên lợi nhuận qua chu kỳ."
    else:
        level = "Cảnh báo chuỗi giá trị yếu"
        conclusion = "Các tín hiệu hiện tại nghiêng về yếu hoặc thiếu dữ liệu; không nên gán moat nếu chưa có bằng chứng mạnh từ báo cáo gốc và so sánh ngành."

    evidence_lines: list[str] = []
    evidence_col = "Bằng chứng hiện có/cần tìm"
    if evidence_col in df.columns:
        for _, row in df.head(8).iterrows():
            act = str(row.get("Hoạt động chuỗi giá trị", "")).strip()
            ev = str(row.get(evidence_col, "")).strip()
            if act and ev:
                evidence_lines.append(f"<li><b>{html.escape(act)}:</b> {html.escape(ev)}</li>")
            if len(evidence_lines) >= 4:
                break

    evidence_html = ""
    if evidence_lines:
        evidence_html = "<ul style='margin:10px 0 5px 18px; padding:0; line-height:1.45;'>" + "".join(evidence_lines) + "</ul>"

    note = (
        "Theo Porter, lợi thế cạnh tranh phải truy về các hoạt động cụ thể trong chuỗi giá trị: "
        "hoạt động nào làm chi phí thấp hơn, hoạt động nào tạo khác biệt hóa được khách hàng trả tiền, "
        "và hoạt động nào khó bị đối thủ sao chép. Card này là đánh giá tự động; click/chọn từng dòng trong bảng để xem note chi tiết."
    )

    st.markdown(
        f"""
        <div style="border:2px solid rgba(245,178,27,.78); border-left:14px solid #F5B21B; border-radius:20px;
                    padding:16px 19px; margin:10px 0 16px 0; background:linear-gradient(135deg,#FFF9E8 0%,#FEF3C7 72%,#FFE8A3 100%);
                    color:#7A4A00; font-weight:850; line-height:1.55; box-shadow:0 10px 25px rgba(245,178,27,.18);">
            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap;">
                <div>
                    <div style="font-size:1.16rem; color:#0B7F75; font-weight:1000; margin-bottom:4px;">🟡 Đánh giá tổng hợp chuỗi giá trị Porter</div>
                    <div style="font-size:.97rem; color:#7A4A00; font-weight:900;">Mức đánh giá: <b>{html.escape(level)}</b></div>
                </div>
                <div style="min-width:142px; text-align:center; border:1.8px solid rgba(245,178,27,.75); border-radius:18px; padding:10px 13px; background:rgba(255,255,255,.84);">
                    <div style="font-size:.78rem; color:#64748B; font-weight:950; text-transform:uppercase;">Điểm nhiệt TB</div>
                    <div style="font-size:1.74rem; line-height:1.05; color:#064E47; font-weight:1000;">{avg_score:.1f}/100</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns:repeat(4,minmax(110px,1fr)); gap:10px; margin:12px 0 11px 0;">
                <div style="border-radius:14px; padding:9px 10px; background:rgba(255,255,255,.76); border:1px solid rgba(245,178,27,.42);"><b>{good_count}</b><br><span style="font-size:.84rem;">Hoạt động tốt</span></div>
                <div style="border-radius:14px; padding:9px 10px; background:rgba(255,255,255,.76); border:1px solid rgba(245,178,27,.42);"><b>{medium_count}</b><br><span style="font-size:.84rem;">Trung bình</span></div>
                <div style="border-radius:14px; padding:9px 10px; background:rgba(255,255,255,.76); border:1px solid rgba(245,178,27,.42);"><b>{weak_count}</b><br><span style="font-size:.84rem;">Cảnh báo yếu</span></div>
                <div style="border-radius:14px; padding:9px 10px; background:rgba(255,255,255,.76); border:1px solid rgba(245,178,27,.42);"><b>{missing_count}</b><br><span style="font-size:.84rem;">Cần bổ sung</span></div>
            </div>
            <div>
                <b>Hoạt động nổi bật:</b> {html.escape(', '.join(strengths[:5]))}<br>
                <b>Điểm yếu/cần kiểm tra:</b> {html.escape(', '.join(risk_items[:5]))}<br>
                <b>Kết luận tự động:</b> {html.escape(conclusion)}
            </div>
            {evidence_html}
            <div style="font-size:.88rem; color:#475569; margin-top:9px;">{html.escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _render_moat_spider_chart(moat_df: pd.DataFrame, company=None) -> None:
    """Render radar/spider chart from Porter moat score heat values.

    Điểm nhiệt của bảng moat được chuẩn hóa = Điểm đạt / Trọng số * 100. Như vậy mỗi trục
    đều nằm trong thang 0-100, không bị méo vì mỗi nhóm Porter có trọng số khác nhau.
    """
    if moat_df is None or moat_df.empty or "Nhóm Porter/Moat" not in moat_df.columns:
        st.info("Chưa đủ dữ liệu để vẽ biểu đồ màng nhện Porter Moat Score.")
        return
    chart_df = moat_df.copy()
    if "Trọng số %" not in chart_df.columns or "Điểm đạt" not in chart_df.columns:
        st.info("Bảng Porter Moat chưa có cột Trọng số %/Điểm đạt để vẽ điểm nhiệt.")
        return
    chart_df["_weight"] = pd.to_numeric(chart_df["Trọng số %"], errors="coerce")
    chart_df["_score"] = pd.to_numeric(chart_df["Điểm đạt"], errors="coerce")
    chart_df["Điểm nhiệt"] = (chart_df["_score"] / chart_df["_weight"].replace(0, pd.NA) * 100).clip(0, 100).fillna(0)
    theta = chart_df["Nhóm Porter/Moat"].astype(str).tolist()
    r = chart_df["Điểm nhiệt"].astype(float).tolist()
    custom = []
    for _, row in chart_df.iterrows():
        custom.append(
            f"{row.get('Nhóm Porter/Moat','')}<br>Điểm nhiệt: {row.get('Điểm nhiệt',0):.1f}/100"
            f"<br>Điểm đạt: {row.get('Điểm đạt','N/A')}/{row.get('Trọng số %','N/A')}"
            f"<br>Tín hiệu: {row.get('Tín hiệu','N/A')}"
        )
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=r + r[:1],
        theta=theta + theta[:1],
        fill="toself",
        name=str(getattr(company, "ticker", "Porter Moat") or "Porter Moat"),
        text=custom + custom[:1],
        hovertemplate="%{text}<extra></extra>",
    ))
    fig.update_layout(
        title="Biểu đồ màng nhện điểm nhiệt Porter Moat Score",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10))),
        showlegend=False,
        height=520,
        margin=dict(l=50, r=50, t=70, b=45),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Điểm nhiệt = Điểm đạt / Trọng số của từng nhóm Porter, quy đổi về thang 0-100 để so sánh trực quan.")


def _simplize_peer_display_df(df: pd.DataFrame, current_ticker: str = "") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    src = _normalize_peer_universe(df)
    out = pd.DataFrame({
        "Mã cổ phiếu": src.get("ticker", pd.Series(dtype=str)),
        "Tên doanh nghiệp": src.get("company_name", pd.Series(dtype=str)),
        "Giá hiện tại": src.get("current_price", pd.Series(dtype=float)),
        "Vốn hóa (tỷ đồng)": src.get("market_cap_bil", pd.Series(dtype=float)),
        "Biến động giá %": src.get("price_change_pct", pd.Series(dtype=float)),
        "7 ngày %": src.get("change_7d_pct", pd.Series(dtype=float)),
        "1 năm %": src.get("change_1y_pct", pd.Series(dtype=float)),
        "P/E": src.get("pe", pd.Series(dtype=float)),
        "P/B": src.get("pb", pd.Series(dtype=float)),
        "ROE %": src.get("roe_pct", pd.Series(dtype=float)),
        "T.trưởng LNST 3Y dự phóng %": src.get("forecast_profit_growth_3y_pct", pd.Series(dtype=float)),
        "Tỷ suất cổ tức %": src.get("dividend_yield_pct", pd.Series(dtype=float)),
        "Sàn": src.get("exchange", pd.Series(dtype=str)),
    })
    current = _safe_ticker(current_ticker)
    out["_active"] = out["Mã cổ phiếu"].astype(str).map(_safe_ticker).eq(current)
    # Chỉ hiển thị tối đa 100 mã như yêu cầu; ưu tiên mã đang phân tích đứng đầu, sau đó theo vốn hóa giảm dần.
    cap = pd.to_numeric(out.get("Vốn hóa (tỷ đồng)"), errors="coerce")
    out = out.assign(_cap_sort=cap.fillna(-1)).sort_values(["_active", "_cap_sort", "Mã cổ phiếu"], ascending=[False, False, True]).drop(columns=["_cap_sort"]).head(100).reset_index(drop=True)
    return out


def _render_simplize_peer_sortable_table(df: pd.DataFrame, current_ticker: str = "") -> pd.DataFrame:
    """Render a sortable/selectable peer list and return edited rows."""
    display_df = _simplize_peer_display_df(df, current_ticker)
    if display_df.empty:
        st.info("Chưa có danh sách cổ phiếu cùng ngành.")
        return pd.DataFrame()
    current = _safe_ticker(current_ticker)
    active_mask = display_df.get("_active", pd.Series(False, index=display_df.index)).fillna(False).astype(bool)
    display_df.insert(0, "Chọn", active_mask)
    if "_active" in display_df.columns:
        # Đảm bảo dòng mã gốc luôn hiện đủ ticker/tên, không còn dòng trống chỉ có icon.
        display_df.loc[active_mask, "Mã cổ phiếu"] = display_df.loc[active_mask, "Mã cổ phiếu"].replace("", current)
        display_df.loc[active_mask & display_df["Tên doanh nghiệp"].astype(str).str.strip().isin(["", "nan", "None"]), "Tên doanh nghiệp"] = current + " - mã đang phân tích"
        display_df.loc[active_mask, "Mã cổ phiếu"] = display_df.loc[active_mask, "Mã cổ phiếu"].astype(str).str.replace("🎯", "", regex=False).str.strip().replace("", current)
        display_df.loc[active_mask, "Tên doanh nghiệp"] = display_df.loc[active_mask, "Tên doanh nghiệp"].astype(str).map(lambda x: ("🎯 " + x.replace("🎯", "").strip()) if x.replace("🎯", "").strip() else "🎯 " + current + " - mã đang phân tích")
    editor_df = display_df.drop(columns=["_active"], errors="ignore")
    st.caption("Bảng danh sách cùng ngành, tối đa 100 mã. Dòng có ký hiệu 🎯 là mã đang phân tích, được tick mặc định và tô vàng thương hiệu; có thể bấm tiêu đề cột để sort tăng/giảm trong bảng.")
    def _active_peer_row_style(row: pd.Series) -> list[str]:
        code = _safe_ticker(str(row.get("Mã cổ phiếu", "")).replace("🎯", ""))
        if code == current:
            return ["background-color:#FFF4C7; color:#3B2600; font-weight:900; border-top:2px solid #F5B21B; border-bottom:2px solid #F5B21B;" for _ in row]
        return ["" for _ in row]
    styled_editor_df = editor_df.style.apply(_active_peer_row_style, axis=1)
    edited = st.data_editor(
        styled_editor_df,
        use_container_width=True,
        height=620,
        hide_index=True,
        disabled=[c for c in editor_df.columns if c != "Chọn"],
        key=f"simplize_peer_selector_{current}_{len(editor_df)}",
        column_config={
            "Chọn": st.column_config.CheckboxColumn("Chọn", help="Tick để đưa mã vào danh sách so sánh", default=False),
            "Giá hiện tại": st.column_config.NumberColumn("Giá hiện tại", format="%d"),
            "Biến động giá %": st.column_config.NumberColumn("Biến động giá %", format="%.2f%%"),
            "7 ngày %": st.column_config.NumberColumn("7 ngày %", format="%.2f%%"),
            "1 năm %": st.column_config.NumberColumn("1 năm %", format="%.2f%%"),
            "P/E": st.column_config.NumberColumn("P/E", format="%.2f"),
            "P/B": st.column_config.NumberColumn("P/B", format="%.2f"),
            "ROE %": st.column_config.NumberColumn("ROE %", format="%.2f%%"),
            "T.trưởng LNST 3Y dự phóng %": st.column_config.NumberColumn("T.trưởng LNST 3Y dự phóng %", format="%.2f%%"),
            "Tỷ suất cổ tức %": st.column_config.NumberColumn("Tỷ suất cổ tức %", format="%.2f%%"),
            "Vốn hóa (tỷ đồng)": st.column_config.NumberColumn("Vốn hóa (tỷ đồng)", format="%d"),
        },
    )
    return pd.DataFrame(edited)

def _render_peer_universe_and_comparison(company, source: str, assumptions: dict, target_mos_pct: float, available_tickers: list[str], *, auto_simplize: bool = False, simplize_industry_url: str = "") -> None:
    st.subheader("So sánh doanh nghiệp cùng ngành")
    st.caption("App tự lấy mã đang phân tích từ Tổng quan doanh nghiệp, cập nhật danh sách cổ phiếu cùng ngành, rồi cho chọn tối đa 10 doanh nghiệp để so sánh.")
    universe = _ensure_current_peer_row(_merge_peer_rows(_load_peer_universe(), [_company_to_peer_row(company, "Mã đang phân tích", "Tự thêm vào peer universe")]), company)
    current_ticker = _safe_ticker(str(getattr(company, "ticker", "")))
    auto_peer_group = None
    if auto_simplize and current_ticker:
        with st.spinner(f"Đang lấy danh sách cùng ngành cho {current_ticker}..."):
            simplize_peers, peer_note, raw_peer_path = _load_simplize_peer_rows(current_ticker, simplize_industry_url)
        if not simplize_peers.empty:
            universe = _ensure_current_peer_row(_merge_peer_rows(universe, simplize_peers.to_dict("records")), company)
            auto_peer_group = str(simplize_peers["peer_group"].dropna().astype(str).iloc[0]) if "peer_group" in simplize_peers.columns and not simplize_peers.empty else None
            _save_peer_universe(universe)
            st.success(_public_text(peer_note))
        else:
            st.warning(_public_text(peer_note))
        if raw_peer_path:
            pass
    col_fetch, col_clear = st.columns([0.55, 0.45])
    with col_fetch:
        if st.button("🔄 Lấy danh sách cùng ngành", use_container_width=True):
            _simplize_industry_peers_cached.clear()
            simplize_peers, peer_note, raw_peer_path = _load_simplize_peer_rows(current_ticker, simplize_industry_url)
            if not simplize_peers.empty:
                universe = _ensure_current_peer_row(_merge_peer_rows(universe, simplize_peers.to_dict("records")), company)
                auto_peer_group = str(simplize_peers["peer_group"].dropna().astype(str).iloc[0]) if "peer_group" in simplize_peers.columns and not simplize_peers.empty else None
                _save_peer_universe(universe)
                st.success(_public_text(peer_note))
            else:
                st.warning(_public_text(peer_note))
            if raw_peer_path:
                pass
    with col_clear:
        if st.button("🧹 Xóa kết quả so sánh tạm", use_container_width=True):
            st.session_state["peer_compare_result"] = pd.DataFrame()
            st.info("Đã xóa kết quả so sánh tạm trong phiên hiện tại.")

    # V23.29: bỏ import CSV và phần thêm nhanh mã ngành. Mã thủ công chỉ nhập tại phần ra lệnh so sánh.

    universe = _ensure_current_peer_row(universe, company)
    current_rows_for_group = universe[universe["ticker"].astype(str).map(_safe_ticker).eq(current_ticker)] if "ticker" in universe.columns else pd.DataFrame()
    current_group_from_row = str(current_rows_for_group.iloc[0].get("peer_group", "")).strip() if not current_rows_for_group.empty else ""
    current_group = auto_peer_group or current_group_from_row or _company_peer_group(company)
    groups = ["Tất cả"] + sorted([g for g in universe["peer_group"].dropna().astype(str).unique().tolist() if g.strip()])
    default_idx = groups.index(current_group) if current_group in groups else 0
    selected_group = st.selectbox("Lọc nhóm ngành", groups, index=default_idx)
    view_df = universe if selected_group == "Tất cả" else universe[universe["peer_group"].astype(str) == selected_group]
    if current_ticker and "ticker" in universe.columns and not view_df["ticker"].astype(str).map(_safe_ticker).eq(current_ticker).any():
        cur_row = universe[universe["ticker"].astype(str).map(_safe_ticker).eq(current_ticker)]
        if not cur_row.empty:
            view_df = pd.concat([cur_row, view_df], ignore_index=True)

    st.subheader("Bảng danh sách cổ phiếu cùng ngành")
    selection_table = _render_simplize_peer_sortable_table(view_df, current_ticker)

    st.divider()
    st.subheader("Chọn mã và ra lệnh so sánh")
    selected_from_ticks = []
    if isinstance(selection_table, pd.DataFrame) and not selection_table.empty and "Chọn" in selection_table.columns:
        mask = selection_table["Chọn"].fillna(False).astype(bool)
        selected_from_ticks = [x for x in selection_table.loc[mask, "Mã cổ phiếu"].astype(str).str.replace("🎯", "", regex=False).map(_safe_ticker).tolist() if _is_probable_peer_ticker(x)]
    manual_codes = st.text_input("Nhập thêm mã thủ công để so sánh, cách nhau bằng dấu ','", value="", placeholder="Ví dụ: CII, HAH, GMD, VSC")
    selected_manual = [_safe_ticker(x) for x in re.split(r"[,;\s]+", manual_codes.upper()) if _is_probable_peer_ticker(_safe_ticker(x))]
    selected_preview = list(dict.fromkeys([current_ticker] + [x for x in selected_from_ticks + selected_manual if x and x != current_ticker]))[:10]
    st.caption(f"Danh sách sẽ so sánh: {', '.join(selected_preview) if selected_preview else 'chưa chọn'}")
    peer_source_options = list(PEER_SOURCE_DISPLAY_TO_INTERNAL.keys())
    peer_source_display = st.selectbox("Chế độ dữ liệu khi chạy so sánh", peer_source_options, index=0, key="peer_compare_source")
    source_for_peer = _to_internal_peer_source(peer_source_display, source)
    total_requested = 1 + len([x for x in list(dict.fromkeys(selected_from_ticks + selected_manual)) if x and x != current_ticker])
    if total_requested > 10:
        st.warning("Anh đang chọn/nhập quá 10 mã tính cả mã đang phân tích; app sẽ lấy mã gốc + 9 mã đầu tiên khi bấm so sánh.")
    if st.button("⚖️ So sánh doanh nghiệp", use_container_width=True):
        selected = selected_preview
        st.session_state["module3_base_ticker"] = current_ticker
        if len(selected) < 2:
            st.error("Cần chọn hoặc nhập tối thiểu 1 mã so sánh ngoài mã đang phân tích.")
        else:
            rows, peer_rows = [], []
            preserve_keys = ["active_ticker", "module1_ticker", "module2_ticker", "shared_ticker", "active_overview_csv", "active_year_csv", "active_quarter_csv", "active_source_label", "module_sync_status"]
            preserved_state = {k: st.session_state.get(k) for k in preserve_keys if k in st.session_state}
            progress = st.progress(0, text="Đang tải dữ liệu và tính điểm peer...")
            try:
                for i, code in enumerate(selected, start=1):
                    row, peer_row = _peer_snapshot(code, source_for_peer, assumptions, float(target_mos_pct))
                    row["Mã đang phân tích"] = (_safe_ticker(code) == current_ticker)
                    rows.append(row)
                    if peer_row:
                        peer_rows.append(peer_row)
                    progress.progress(i / len(selected), text=f"Đã xử lý {i}/{len(selected)}: {code}")
            finally:
                progress.empty()
                # So sánh peer không được làm đổi mã/bộ dữ liệu chính đang hiển thị trên dashboard.
                for k in preserve_keys:
                    if k in preserved_state:
                        st.session_state[k] = preserved_state[k]
            result = _rank_peer_comparison(pd.DataFrame(rows))
            st.session_state["peer_compare_result"] = result
            if peer_rows:
                _save_peer_universe(_merge_peer_rows(universe, peer_rows))
            st.success("Đã hoàn tất so sánh peer.")

    result = st.session_state.get("peer_compare_result", pd.DataFrame())
    if isinstance(result, pd.DataFrame) and not result.empty:
        _render_important_red("Nhận định so sánh cùng ngành", _peer_comparison_summary(result, float(target_mos_pct)))
        display_result = result.drop(columns=[c for c in ["Mã đang phân tích", "Nguồn dữ liệu", "source", "Source", "Ngành", "Phân ngành"] if c in result.columns], errors="ignore")
        _render_explainable_table(display_result, "peer_compare", height=520)
        export_result = display_result
        st.download_button("Tải kết quả so sánh peer", export_result.to_csv(index=False, encoding="utf-8-sig"), file_name=f"peer_compare_{_safe_ticker(str(getattr(company, 'ticker', '')))}.csv", mime="text/csv", use_container_width=True)


def _render_tre_sidebar_nav() -> None:
    """Manual branded navigation so Streamlit never exposes the technical root page name 'app'."""
    st.markdown("### Điều hướng")
    st.page_link("app.py", label="Tổng quan doanh nghiệp", icon="📊")
    st.page_link("pages/02_Dinh_gia_Porter_Moat.py", label="Định giá chuyên sâu", icon="🧠")
    st.page_link("pages/03_So_sanh_doanh_nghiep.py", label="So sánh doanh nghiệp", icon="⚖️")
    st.page_link("pages/04_Bao_cao_tong_hop.py", label="Báo cáo tổng hợp toàn bộ nội dung", icon="📄")
    st.divider()


def render_dashboard() -> None:
    _inject_runtime_ui_css()
    _render_brand_page_header(
        f"🧠 {APP_NAME}",
        "Trecapital valuation dashboard | Tự đồng bộ BCTC Tổng quan doanh nghiệp ⇄ Định giá chuyên sâu, tìm evidence internet, định giá nhiều lớp và chấm lợi thế cạnh tranh theo Porter.",
    )

    available_tickers = _available_financial_tickers_cached(str(BUNDLED_XLSM)) if BUNDLED_XLSM.exists() else []

    with st.sidebar:
        _render_tre_sidebar_nav()
        st.header("Thiết lập phân tích")
        source_display = st.selectbox(
            "Chế độ dữ liệu tài chính",
            list(DATA_SOURCE_DISPLAY_TO_INTERNAL.keys()),
            index=0,
        )
        source = _to_internal_source(source_display)
        ticker = st.text_input("Mã cổ phiếu", value=st.session_state.get("module2_ticker", st.session_state.get("last_query_ticker", "DGC")), max_chars=12).upper()
        mos_canonical = _prepare_mos_widget("module2_mos_widget")
        target_mos_pct = st.selectbox(
            "Mức MOS yêu cầu (%)",
            MOS_OPTIONS_GLOBAL,
            index=MOS_OPTIONS_GLOBAL.index(mos_canonical),
            key="module2_mos_widget",
            on_change=_commit_mos_widget,
            args=("module2_mos_widget",),
            help="MOS dùng chung toàn app: chọn ở Định giá chuyên sâu sẽ tự đồng bộ sang Tổng quan doanh nghiệp và mọi công thức giá mua/kết luận sẽ nhảy theo.",
        )
        target_mos_pct = float(st.session_state.get("target_mos_pct", target_mos_pct))
        if st.session_state.get("mos_sync_status"):
            st.caption(st.session_state["mos_sync_status"])
        if source == "Financial tích hợp" and available_tickers:
            chosen = st.selectbox("Mã có đủ BCTC trong dữ liệu tích hợp", ["-- Giữ mã đang nhập --"] + available_tickers, index=0)
            if chosen != "-- Giữ mã đang nhập --":
                ticker = chosen
        st.caption("Mặc định dùng chế độ Tự động: nhập mã ở Tổng quan doanh nghiệp hoặc Định giá chuyên sâu đều đồng bộ cùng một bộ BCTC/cache để định giá.")
        st.caption("WACC được tự tính theo doanh nghiệp từ cơ cấu vốn, chi phí nợ, thuế và cost of equity proxy; không còn WACC tham chiếu nhập tay.")
        run_all = st.button("🔎 Tìm kiếm/cập nhật tất cả", use_container_width=True, help="Một nút duy nhất: đồng bộ dữ liệu tài chính từ Tổng quan doanh nghiệp sang Định giá chuyên sâu và tìm bằng chứng định tính cho lợi thế/rủi ro/BCTC.")
        if run_all:
            _export_module1_crawler_cached.clear()
            _export_bundled_financial_cached.clear()
            _load_overview_cached.clear()
            _load_timeseries_cached.clear()
            st.session_state["module2_run_all_requested"] = True
            st.info("Đang cập nhật toàn bộ: dữ liệu tài chính Tổng quan doanh nghiệp → Định giá chuyên sâu + bằng chứng định tính.")
        st.divider()
        terminal_growth = st.slider("Terminal growth (%)", 0.0, 6.0, 3.0, 0.5)
        target_pe = st.slider("P/E mục tiêu thường", 5.0, 20.0, 10.0, 0.5)
        st.session_state["module2_ticker"] = _safe_ticker(ticker) or "DGC"

    ticker = st.session_state["module2_ticker"]
    run_all_requested = bool(st.session_state.pop("module2_run_all_requested", False))
    effective_source = "FireAnt + Vietstock" if run_all_requested and source == "Tự động từ dữ liệu tổng quan" else source
    load_error = None
    try:
        company, annual_df, quarterly_df, source_label, paths = _load_data(ticker, effective_source)
    except Exception as exc:
        load_error = str(exc)
        _render_no_data(ticker, effective_source, available_tickers, load_error)
        st.stop()

    if not _has_real_financial_data(annual_df):
        _render_no_data(ticker, effective_source, available_tickers)
        st.info("Chi tiết kỹ thuật đã được ghi trong nhật ký nội bộ.")
        st.stop()

    if run_all_requested:
        with st.spinner("Đang tìm bằng chứng định tính cho Định giá chuyên sâu..."):
            _update_module2_web_evidence(company)

    assumptions = load_assumptions(ASSUMPTIONS_PATH)
    assumptions["required_return"] = assumptions.get("required_return_pct", 13.0) / 100
    assumptions["terminal_growth"] = terminal_growth / 100
    assumptions["target_pe_normal"] = target_pe
    assumptions["target_mos_pct"] = float(target_mos_pct)

    valuation_df = build_module2_valuation_table(company, annual_df, assumptions)
    cls = classify_company(company, annual_df)
    current_price = getattr(company, "current_price", None)
    value_range = build_valuation_range(valuation_df, current_price, float(target_mos_pct))
    moat_df = build_porter_moat_scorecard(company, annual_df)
    value_chain_df = build_value_chain_table(company, annual_df)
    scenario_df = build_risk_scenario_table(company, annual_df, value_range)
    beneish_df = build_beneish_mscore_table(company, annual_df)
    accrual_quality_df = build_accrual_quality_table(company, annual_df)
    modified_jones_df = build_modified_jones_kothari_table(company, annual_df)
    rem_df = build_real_earnings_management_table(company, annual_df)
    summary = build_module2_summary(company, annual_df, valuation_df, moat_df)

    st.session_state["module2_note_context"] = {
        "company": company,
        "annual_df": annual_df,
        "quarterly_df": quarterly_df,
        "valuation_df": valuation_df,
        "value_range": value_range,
        "moat_df": moat_df,
        "value_chain_df": value_chain_df,
        "scenario_df": scenario_df,
        "beneish_df": beneish_df,
        "classification": cls,
        "assumptions": assumptions,
        "source_label": source_label,
        "target_mos_pct": float(target_mos_pct),
    }

    updated_text = html.escape(_public_text(getattr(company, "updated_at", "N/A") or "N/A"))
    current_price_text = f"{current_price:,.0f}" if current_price else "N/A"
    st.markdown(
        f"""
        <div class='ticker-title-card'>
            <div class='ticker-title-main'><span class='ticker-title-code'>{html.escape(str(company.ticker))}</span> - <span class='ticker-title-name'>{html.escape(str(company.company_name))}</span></div>
            <div class='current-price-inline-card'>
                <div class='price-label'>Giá hiện tại</div>
                <div class='price-value'>{html.escape(current_price_text)}</div>
                <div class='price-note'>Cập nhật: {updated_text}</div>
            </div>
            <div class='ticker-title-meta'><b>Phân loại sơ bộ:</b> {html.escape(str(cls.company_type))} &nbsp; | &nbsp; <b>Độ tin cậy:</b> {cls.confidence:.0f}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    cols[0].metric("Giá trị weighted", f"{value_range.weighted_vnd:,.0f}" if value_range.weighted_vnd else "N/A")
    cols[1].metric("MOS hiện tại", f"{value_range.mos_to_weighted_pct:,.1f}%" if value_range.mos_to_weighted_pct is not None else "N/A")
    cols[2].metric("Moat score", f"{moat_df.attrs.get('total_score', 0):,.1f}/100")
    cols[3].metric("Moat level", str(moat_df.attrs.get("level", "N/A")))
    latest_cards = latest_metric_cards(annual_df) if annual_df is not None and not annual_df.empty else {}
    cols[4].metric("Owner Earnings", latest_cards.get("Owner Earnings", "N/A"))

    _render_important_red("Tóm tắt tự động", summary)

    # V23.39: đã bỏ nút/khung xuất báo cáo trong từng phần; chỉ còn trang Báo cáo tổng hợp toàn bộ nội dung ở sidebar.

    tab_val, tab_moat, tab_chain, tab_scenario, tab_beneish, tab_web, tab_data, tab_docs = st.tabs([
        "Định giá chuyên sâu", "Porter Moat Score", "Chuỗi giá trị", "Kịch bản & rủi ro", "Thao túng tài chính", "Bằng chứng định tính", "Dữ liệu", "Công thức & giả định"
    ])

    with tab_val:
        st.markdown("<div class='valuation-tab-compact'>", unsafe_allow_html=True)
        _render_company_type_summary_callout(cls)
        st.subheader("Đánh giá trọng yếu theo dữ liệu doanh nghiệp")
        assessment_df = _build_strategic_assessment_table(company, annual_df, cls, value_range, moat_df, float(target_mos_pct))
        _render_explainable_table(assessment_df, "strategic_assessment", height=240)

        _render_big_recommendation(value_range.recommendation)
        st.subheader("Dải giá trị nội tại")
        range_df = pd.DataFrame([
            {"Chỉ tiêu": "Low", "Giá trị/cp": value_range.low_vnd},
            {"Chỉ tiêu": "Base/Median", "Giá trị/cp": value_range.base_vnd},
            {"Chỉ tiêu": "High", "Giá trị/cp": value_range.high_vnd},
            {"Chỉ tiêu": "Weighted", "Giá trị/cp": value_range.weighted_vnd},
            {"Chỉ tiêu": f"Giá mua theo MOS chọn {float(target_mos_pct):.0f}%", "Giá trị/cp": value_range.weighted_vnd * (1 - float(target_mos_pct) / 100) if value_range.weighted_vnd else None},
            {"Chỉ tiêu": "MOS hiện tại %", "Giá trị/cp": value_range.mos_to_weighted_pct},
            {"Chỉ tiêu": "MOS yêu cầu %", "Giá trị/cp": float(target_mos_pct)},
        ])
        _render_explainable_table(range_df, "valuation_range", height=312)
        st.subheader("Bảng định giá theo từng phương pháp")
        _render_explainable_table(valuation_df, "valuation_methods", height=432)
        st.caption("Không dùng một fair value duy nhất. Hệ thống chọn trọng số theo loại doanh nghiệp và dữ liệu sẵn có; các tham số có thể chỉnh tại sidebar hoặc cấu hình giả định nội bộ.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_moat:
        st.subheader("Bảng điểm lợi thế cạnh tranh theo Porter")
        _render_important_red("Tổng điểm Porter Moat", f"{moat_df.attrs.get('total_score', 0):,.1f}/100 - {moat_df.attrs.get('level', 'N/A')}")
        _render_moat_spider_chart(moat_df, company)
        _render_explainable_table(moat_df, "moat_score", height=430)

    with tab_chain:
        st.subheader("Bản đồ chuỗi giá trị theo Porter")
        st.caption("Mỗi hoạt động được liên kết với tín hiệu định lượng hiện có và bằng chứng định tính cần tìm thêm trong báo cáo/tin doanh nghiệp.")
        _render_value_chain_yellow_assessment_card(value_chain_df)
        _render_value_chain_spider_chart(value_chain_df, company)
        _render_explainable_table(value_chain_df, "value_chain", height=480)

    with tab_scenario:
        st.subheader("Kịch bản định giá và rủi ro")
        _render_explainable_table(scenario_df, "scenario", height=300)
        st.subheader("Tín hiệu kỳ gần nhất")
        cards = latest_metric_cards(annual_df)
        card_df = pd.DataFrame([{"Chỉ tiêu": k, "Giá trị": v} for k, v in cards.items()])
        _render_explainable_table(card_df, "latest_cards", height=360)

    with tab_beneish:
        st.subheader("Thao túng tài chính - 4 lớp cảnh báo định lượng")
        st.markdown(
            """
            <div class='note-card'>
            <b>Nguyên tắc:</b> app không kết luận doanh nghiệp gian lận. Bốn lớp dưới đây chỉ tạo cờ đỏ định lượng để kiểm tra sâu chất lượng BCTC: lợi nhuận có đi kèm tiền thật không, accruals có bất thường không, doanh thu/phải thu/tài sản có bị làm đẹp không và có dấu hiệu quản trị lợi nhuận qua hoạt động thật không.<br><br>
            <b>Cách dùng trong app:</b> khi một hoặc nhiều lớp cảnh báo cao, hãy giảm độ tin cậy của lợi nhuận kế toán khi định giá; đọc kỹ thuyết minh doanh thu, phải thu, tồn kho, khấu hao, chi phí vốn hóa, giao dịch bên liên quan, ý kiến kiểm toán và đối chiếu CFO/LNST/FCF. Với doanh nghiệp tài chính/ngân hàng, các mô hình công nghiệp như Beneish/Jones/REM chỉ dùng tham khảo nếu dữ liệu đủ.
            </div>
            """,
            unsafe_allow_html=True,
        )
        financial_manipulation_summary_df = _build_financial_manipulation_summary_df(
            beneish_df,
            accrual_quality_df,
            modified_jones_df,
            rem_df,
        )
        st.subheader("Tổng hợp thao túng tài chính 4 lớp")
        # V23.61: bảng tổng hợp nằm sát nhóm phân tích từng lớp; vẫn dùng format chuẩn,
        # chỉ bỏ note/click của riêng bảng tổng hợp và in đậm cột Lớp.
        _render_static_html_table(financial_manipulation_summary_df, "financial_manipulation_summary", height=404)

        layer_beneish, layer_accrual, layer_jones, layer_rem = st.tabs([
            "1. Beneish M-Score",
            "2. Accrual Quality / Sloan",
            "3. Modified Jones / Kothari",
            "4. REM - hoạt động thật",
        ])

        with layer_beneish:
            st.subheader("Lớp 1 - Beneish M-Score: cảnh báo thao túng lợi nhuận bằng 8 biến")
            latest_mscore = beneish_df.attrs.get("latest_score") if isinstance(beneish_df, pd.DataFrame) else None
            latest_risk = beneish_df.attrs.get("latest_risk", "N/A") if isinstance(beneish_df, pd.DataFrame) else "N/A"
            latest_period = beneish_df.attrs.get("latest_period", "N/A") if isinstance(beneish_df, pd.DataFrame) else "N/A"
            latest_note = beneish_df.attrs.get("latest_note", "N/A") if isinstance(beneish_df, pd.DataFrame) else "N/A"
            mscore_text = _format_note_value(latest_mscore) if latest_mscore is not None else "N/A"
            latest_missing = ""
            if isinstance(beneish_df, pd.DataFrame) and not beneish_df.empty and "Biến thiếu/cần kiểm tra" in beneish_df.columns:
                latest_missing = str(beneish_df.iloc[-1].get("Biến thiếu/cần kiểm tra") or "")
            if latest_mscore is None:
                _render_warning_card(
                    "Tín hiệu Beneish M-Score",
                    f"Kỳ mới nhất {latest_period}: chưa đủ 8 biến để tính M-Score chính thức. Biến thiếu/cần kiểm tra: {latest_missing or 'N/A'}. {latest_note}"
                )
            else:
                _render_important_red(
                    "Tín hiệu Beneish M-Score",
                    f"Kỳ mới nhất {latest_period}: M-Score {mscore_text}; mức cảnh báo: {latest_risk}. {latest_note}"
                )
            st.caption("Công thức: M = -4.84 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI. Ngưỡng: M-Score > -2.22 là vùng cảnh báo. AQI ưu tiên TSCĐ/PPE thật; nếu nguồn chỉ có Tài sản dài hạn, app dùng AQI proxy và ghi chú rõ.")
            _render_explainable_table(beneish_df, "beneish_mscore", height=470)

        with layer_accrual:
            st.subheader("Lớp 2 - Accrual Quality/Sloan: lợi nhuận có đi kèm dòng tiền thật không")
            latest_risk = accrual_quality_df.attrs.get("latest_risk", "N/A") if isinstance(accrual_quality_df, pd.DataFrame) else "N/A"
            latest_score = accrual_quality_df.attrs.get("latest_score") if isinstance(accrual_quality_df, pd.DataFrame) else None
            latest_note = accrual_quality_df.attrs.get("latest_note", "N/A") if isinstance(accrual_quality_df, pd.DataFrame) else "N/A"
            _render_warning_card("Tín hiệu Accrual Quality/Sloan", f"Kỳ mới nhất: Sloan accrual ratio {_format_note_value(latest_score)}; mức cảnh báo: {latest_risk}. {latest_note}")
            st.caption("Công thức chính: Sloan accrual ratio = (LNST - CFO) / Tổng tài sản bình quân. App kiểm tra thêm CFO/LNST, FCF/LNST và Balance-sheet accruals = ΔCA - ΔCash - ΔCL + ΔSTD - Khấu hao.")
            _render_explainable_table(accrual_quality_df, "accrual_quality", height=470)

        with layer_jones:
            st.subheader("Lớp 3 - Modified Jones/Kothari: discretionary accruals")
            latest_risk = modified_jones_df.attrs.get("latest_risk", "N/A") if isinstance(modified_jones_df, pd.DataFrame) else "N/A"
            latest_score = modified_jones_df.attrs.get("latest_score") if isinstance(modified_jones_df, pd.DataFrame) else None
            latest_note = modified_jones_df.attrs.get("latest_note", "N/A") if isinstance(modified_jones_df, pd.DataFrame) else "N/A"
            _render_warning_card("Tín hiệu Modified Jones/Kothari", f"Kỳ mới nhất: DA Modified Jones {_format_note_value(latest_score)}; mức cảnh báo: {latest_risk}. {latest_note}")
            st.caption("Modified Jones: TA/A(t-1)=α0+α1(1/A(t-1))+α2((ΔREV-ΔREC)/A(t-1))+α3(PPE/A(t-1))+ε. Kothari thêm ROA để kiểm soát hiệu quả hoạt động. DA=residual ε.")
            _render_explainable_table(modified_jones_df, "modified_jones", height=490)

        with layer_rem:
            st.subheader("Lớp 4 - Real Earnings Management: quản trị lợi nhuận qua hoạt động thật")
            latest_risk = rem_df.attrs.get("latest_risk", "N/A") if isinstance(rem_df, pd.DataFrame) else "N/A"
            latest_score = rem_df.attrs.get("latest_score") if isinstance(rem_df, pd.DataFrame) else None
            latest_note = rem_df.attrs.get("latest_note", "N/A") if isinstance(rem_df, pd.DataFrame) else "N/A"
            _render_warning_card("Tín hiệu REM", f"Kỳ mới nhất: REM Score {_format_note_value(latest_score)}; mức cảnh báo: {latest_risk}. {latest_note}")
            st.caption("REM gồm 3 residual bất thường: Abnormal CFO, Abnormal PROD = COGS + ΔInventory, và Abnormal DISEXP. CFO âm bất thường, sản xuất dư/tồn kho cao bất thường hoặc cắt chi phí tùy ý là các cờ đỏ cần kiểm tra.")
            _render_explainable_table(rem_df, "real_earnings_management", height=490)


    with tab_web:
        st.subheader("Bằng chứng định tính cho lợi thế/rủi ro/BCTC")
        st.markdown(
            """
            <div class='note-card'>
            <b>Tab này là kho bằng chứng định tính phục vụ kiểm tra nhận định.</b><br>
            App dùng nút <b>Tìm kiếm/cập nhật tất cả</b> để cập nhật thông tin liên quan đến: BCTC, báo cáo thường niên, tin công bố, moat/lợi thế cạnh tranh, rủi ro ngành, thị phần, quản trị và sự kiện bất thường.<br><br>
            <b>Cách dùng:</b> dữ liệu BCTC số học vẫn ưu tiên bộ dữ liệu tài chính đã chuẩn hóa; bằng chứng định tính chủ yếu dùng để <b>đối chiếu, kiểm chứng và giải thích</b> các nhận định về lợi thế/rủi ro/BCTC. Không nên xem đây là căn cứ duy nhất để ra quyết định nếu chưa đối chiếu với tài liệu gốc.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Bằng chứng định tính được cập nhật bằng nút duy nhất ở sidebar: 'Tìm kiếm/cập nhật tất cả'. Nếu anh tìm mã ở Tổng quan doanh nghiệp, dữ liệu này cũng được tự cập nhật sẵn cho Định giá chuyên sâu.")
        if st.session_state.get("module2_auto_update_status"):
            st.info(_public_text(st.session_state["module2_auto_update_status"]))
        if st.session_state.get("module2_web_note"):
            st.success(_public_text(st.session_state["module2_web_note"]))
        web_ticker = st.session_state.get("module2_web_ticker")
        if web_ticker and _safe_ticker(str(web_ticker)) != _safe_ticker(company.ticker):
            st.warning(f"Bằng chứng định tính hiện đang thuộc mã {web_ticker}; bấm 'Tìm kiếm/cập nhật tất cả' để cập nhật lại cho {company.ticker}.")
        _show_table(st.session_state.get("module2_web_table", pd.DataFrame()), height=520)

    with tab_data:
        st.subheader("Dữ liệu năm + TTM dùng cho Định giá chuyên sâu")
        _show_table(format_table_for_display(annual_df), height=480)
        st.download_button("Tải dữ liệu năm + TTM", annual_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"{company.ticker}_dinh_gia_year_ttm.csv", mime="text/csv")
        st.subheader("Dữ liệu quý")
        _show_table(format_table_for_display(quarterly_df), height=420)
        st.download_button(
            "Tải dữ liệu quý",
            quarterly_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"{company.ticker}_dinh_gia_quarter.csv",
            mime="text/csv",
            key=f"download_quarterly_data_{company.ticker}",
        )

    with tab_docs:
        st.subheader("Công thức và giả định")
        st.markdown(
            """
            <div class='note-card'>
            <b>Khu vực này hiển thị công thức, giả định và nguyên tắc đánh giá.</b><br>
            Các đường dẫn kỹ thuật, tên nhà cung cấp dữ liệu và nhật ký nội bộ không hiển thị trên giao diện để đảm bảo bảo mật vận hành.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Tóm tắt công thức chính")
        formula_df = pd.DataFrame([
            {"Nhóm": "Giá trị nội tại", "Công thức/logic": "Dải giá trị Low - Base - High từ các phương pháp hợp lệ; Weighted là trung bình trọng số theo mức phù hợp dữ liệu và loại doanh nghiệp."},
            {"Nhóm": "MOS", "Công thức/logic": "MOS hiện tại = (Giá trị nội tại - Giá thị trường) / Giá trị nội tại. Giá mua MOS = Giá trị nội tại x (1 - MOS yêu cầu)."},
            {"Nhóm": "Owner Earnings", "Công thức/logic": "LNST + khấu hao và chi phí phi tiền mặt - capex duy trì ± thay đổi vốn lưu động vận hành cần thiết."},
            {"Nhóm": "FCF", "Công thức/logic": "Dòng tiền tự do = CFO - Capex. Nếu Capex trong dữ liệu là số âm thì quy đổi đúng chiều dòng tiền trước khi tính."},
            {"Nhóm": "ROIC/ROCE", "Công thức/logic": "ROIC chính = NOPAT / vốn đầu tư bình quân; ROCE = EBIT / capital employed khi đủ dữ liệu."},
            {"Nhóm": "DuPont", "Công thức/logic": "ROE được tách thành biên lợi nhuận, vòng quay tài sản và đòn bẩy tài chính để nhận diện nguồn tạo ROE."},
            {"Nhóm": "Porter Moat", "Công thức/logic": "Điểm moat là tổng trọng số các tiêu chí hiệu quả vốn, lợi thế chi phí/khác biệt hóa, cấu trúc ngành, runway, chất lượng tài chính và rủi ro."},
            {"Nhóm": "Beneish M-Score", "Công thức/logic": "M = -4.84 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI. M > -2.22 là vùng cảnh báo thao túng lợi nhuận."},
            {"Nhóm": "Accrual Quality/Sloan", "Công thức/logic": "Sloan accrual ratio = (LNST - CFO) / Tổng tài sản bình quân. Kiểm tra thêm CFO/LNST, FCF/LNST và Balance-sheet accruals = ΔCA - ΔCash - ΔCL + ΔSTD - Khấu hao."},
            {"Nhóm": "Modified Jones/Kothari", "Công thức/logic": "TA/A(t-1)=α0+α1(1/A(t-1))+α2((ΔREV-ΔREC)/A(t-1))+α3(PPE/A(t-1))+ε. Kothari thêm ROA. DA = residual ε; DA dương cao là accruals làm tăng lợi nhuận."},
            {"Nhóm": "Real Earnings Management", "Công thức/logic": "REM kiểm tra Abnormal CFO, Abnormal PROD và Abnormal DISEXP. PROD = COGS + ΔInventory; DISEXP dùng chi phí bán hàng + quản lý hoặc proxy SG&A khi thiếu chi tiết."},
        ])
        formula_headers = "".join(
            f"<th>{html.escape(str(col))}</th>" for col in formula_df.columns
        )
        formula_rows = []
        for _, formula_row in formula_df.iterrows():
            formula_rows.append(
                "<tr>"
                f"<td class='formula-group'>{html.escape(str(formula_row.get('Nhóm', '')))}</td>"
                f"<td>{html.escape(str(formula_row.get('Công thức/logic', '')))}</td>"
                "</tr>"
            )
        st.markdown(
            f"""
            <div class='formula-table-wrap'>
              <table class='formula-table'>
                <thead><tr>{formula_headers}</tr></thead>
                <tbody>{''.join(formula_rows)}</tbody>
              </table>
            </div>
            <style>
              .formula-table-wrap {{border:1px solid #E2E8F0; border-radius:14px; overflow:hidden; margin: 8px 0 16px 0;}}
              .formula-table {{border-collapse:collapse; width:100%; font-size:13.5px; background:#FFFFFF;}}
              .formula-table th {{background:#EAF7F1; color:#123D3A; font-weight:950; text-align:left; padding:10px 12px; border-bottom:1px solid #D5E6DD;}}
              .formula-table td {{padding:9px 12px; border-bottom:1px solid #EDF2F7; color:#123D3A; vertical-align:top;}}
              .formula-table .formula-group {{font-weight:950; color:#064E47; white-space:nowrap; background:#F7FBF8;}}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Giả định đang dùng")
        try:
            assumption_items = load_assumptions(ASSUMPTIONS_PATH).__dict__
        except Exception:
            assumption_items = {}
        if assumption_items:
            assumption_label_map = {
                "required_return_pct": "Tỷ suất sinh lời yêu cầu (%)",
                "terminal_growth_pct": "Tăng trưởng dài hạn (%)",
                "conservative_growth_pct": "Tăng trưởng thận trọng (%)",
                "base_growth_cap_pct": "Trần tăng trưởng cơ sở (%)",
                "high_growth_cap_pct": "Trần tăng trưởng cao (%)",
                "mos_conservative_pct": "MOS thận trọng (%)",
                "mos_base_pct": "MOS cơ sở (%)",
                "target_pe_default": "P/E mục tiêu mặc định",
                "target_pe_quality": "P/E mục tiêu doanh nghiệp chất lượng",
                "target_pb_bank": "P/B mục tiêu ngân hàng/bảo hiểm",
                "asset_haircut_cash_pct": "Haircut tiền (%)",
                "asset_haircut_receivables_pct": "Haircut phải thu (%)",
                "asset_haircut_inventory_pct": "Haircut tồn kho (%)",
                "asset_haircut_fixed_assets_pct": "Haircut tài sản cố định (%)",
                "min_required_years_for_high_confidence": "Số năm tối thiểu để tăng độ tin cậy",
            }
            assumption_df = pd.DataFrame([
                {"Giả định": assumption_label_map.get(k, k), "Giá trị": v}
                for k, v in assumption_items.items()
                if not str(k).startswith("_")
            ])
            _show_table(assumption_df, height=300)
        else:
            st.warning("Chưa đọc được bộ giả định định giá; app vẫn chạy với giá trị mặc định trong engine.")

        _render_company_type_guidance(getattr(cls, "company_type", "Normal Business"))
        st.divider()
        _render_glossary_panel()
        st.divider()
        if st.button("📄 Xuất báo cáo Markdown định giá", use_container_width=True):
            out_path = REPORT_DIR / f"{company.ticker}_Valuation_Porter_Report.md"
            export_module2_report_markdown(company, valuation_df, moat_df, value_chain_df, scenario_df, out_path, annual_df)
            st.success("Đã xuất báo cáo Markdown vào thư mục báo cáo nội bộ.")
        docs = [
            APP_DIR / "docs" / "FORMULA_EXPLANATION_MODULE2.md",
            APP_DIR / "docs" / "PORTER_MOAT_SCORING_GUIDE.md",
            APP_DIR / "docs" / "BENEISH_M_SCORE_GUIDE.md",
        ]
        for doc in docs:
            if doc.exists():
                doc_label = (
                    doc.name
                    .replace("MODULE2", "DINH_GIA")
                    .replace("MODULE1", "TONG_QUAN")
                    .replace("Module", "Phan")
                    .replace("module", "phan")
                )
                with st.expander(doc_label, expanded=False):
                    doc_text = doc.read_text(encoding="utf-8").replace("Module", "Phần").replace("module", "phần")
                    st.markdown(doc_text)


def _module3_default_ticker() -> str:
    for key in ["module1_ticker", "active_ticker", "shared_ticker", "module2_ticker", "last_query_ticker"]:
        val = _safe_ticker(str(st.session_state.get(key, "")))
        if val:
            return val
    return "DGC"


def _minimal_company_for_ticker(ticker: str) -> CompanyOverview:
    ticker = _safe_ticker(ticker) or "DGC"
    return CompanyOverview(
        ticker=ticker,
        company_name=ticker,
        exchange="",
        industry="",
        sub_industry="",
        market_cap_bil=None,
        shares_outstanding_mil=None,
        current_price=None,
        eps=None,
        pe=None,
        pb=None,
        ps=None,
        roe=None,
        roa=None,
        roic=None,
        updated_at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def render_module3_comparison_dashboard() -> None:
    """Standalone So sánh doanh nghiệp page: peer universe + 10-company comparison."""
    _inject_runtime_ui_css()
    _render_brand_page_header(
        "⚖️ So sánh doanh nghiệp",
        "Tự lấy mã từ Tổng quan doanh nghiệp, cập nhật danh sách doanh nghiệp cùng ngành, chọn tối đa 10 mã và chấm điểm so sánh theo định giá, chất lượng, dòng tiền và Porter Moat.",
    )
    if st.session_state.get("module_sync_status"):
        st.info(st.session_state.get("module_sync_status"))

    with st.sidebar:
        _render_tre_sidebar_nav()
        st.markdown("### Tham số so sánh")
        default_ticker = _module3_default_ticker()
        ticker = st.text_input("Mã lấy từ Tổng quan doanh nghiệp / mã gốc để crawl cùng ngành", value=default_ticker, max_chars=12).upper()
        source_options = ["Dữ liệu ưu tiên", "Dữ liệu tích hợp", "Dữ liệu mẫu"]
        source_display = st.selectbox("Chế độ dữ liệu để định giá các mã peer", source_options, index=0)
        source = {"Dữ liệu ưu tiên": "FireAnt", "Dữ liệu tích hợp": "Financial tích hợp", "Dữ liệu mẫu": "CSV mẫu tích hợp"}.get(source_display, "FireAnt")
        simplize_default_url = str(st.session_state.get("module3_simplize_industry_url", ""))
        simplize_industry_url = st.text_input(
            "URL nhóm ngành nếu muốn cố định",
            value=simplize_default_url,
            placeholder="Dán URL nhóm ngành nếu cần",
            help="Có thể để trống; app sẽ tự tìm link ngành. Khi website đổi bố cục, dán trực tiếp URL nhóm ngành tại đây để lấy nhanh hơn."
        ).strip()
        st.session_state["module3_simplize_industry_url"] = simplize_industry_url
        assumptions = load_assumptions(ASSUMPTIONS_PATH)
        assumptions["required_return"] = assumptions.get("required_return_pct", 13.0) / 100
        target_mos_pct = st.selectbox("MOS yêu cầu khi lọc peer (%)", MOS_OPTIONS_GLOBAL, index=MOS_OPTIONS_GLOBAL.index(_normalize_mos_value(st.session_state.get("target_mos_pct", 30), 30)))
        st.session_state["target_mos_pct"] = target_mos_pct

    ticker = _safe_ticker(ticker) or default_ticker
    st.session_state["module3_base_ticker"] = ticker
    company = None
    annual_df = pd.DataFrame()
    quarterly_df = pd.DataFrame()
    source_label = source
    paths = []
    available_tickers = _available_financial_tickers_cached(str(BUNDLED_XLSM)) if BUNDLED_XLSM.exists() else []
    try:
        company, annual_df, quarterly_df, source_label, paths = _load_data(ticker, source)
        if not _has_real_financial_data(annual_df):
            raise RuntimeError("Chưa có BCTC nhiều kỳ cho mã gốc; vẫn có thể crawl danh sách cùng ngành và so sánh các mã khác.")
        st.markdown(
            f"""
            <div class='ticker-title-card'>
                <div class='ticker-title-main'><span class='ticker-title-code'>{html.escape(str(company.ticker))}</span> - <span class='ticker-title-name'>{html.escape(str(company.company_name))}</span></div>
                <div class='ticker-title-meta'><b>Chế độ dữ liệu mã gốc:</b> {html.escape(source_display)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception as exc:
        company = _minimal_company_for_ticker(ticker)
        st.warning(f"Không tải được đầy đủ BCTC mã gốc {ticker}: {_public_text(exc)}. So sánh doanh nghiệp vẫn cập nhật danh sách cùng ngành và cho chọn mã để so sánh.")

    _render_peer_universe_and_comparison(company, source, assumptions, float(target_mos_pct), available_tickers, auto_simplize=True, simplize_industry_url=simplize_industry_url)

    # V23.39: đã bỏ nút/khung xuất báo cáo trong từng phần; chỉ còn trang Báo cáo tổng hợp toàn bộ nội dung ở sidebar.


if __name__ == "__main__":
    render_dashboard()
