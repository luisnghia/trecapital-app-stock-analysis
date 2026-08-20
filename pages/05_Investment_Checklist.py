from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
from module2_engine import build_module2_valuation_table, build_valuation_range, load_assumptions
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme

from modules.investment_checklist.contracts import AnalystContext, CompanyContext, HostContext
from modules.investment_checklist.trecapital_bridge import CurrentRepoDataProvider
from modules.investment_checklist.ui import render_investment_checklist

APP_DIR = Path(__file__).resolve().parents[1]
CHECKLIST_DB = APP_DIR / "data_cache" / "investment_checklist.db"  # Local/dev fallback only; production durable DB is Phase 1C.
ASSUMPTIONS_PATH = APP_DIR / "configs" / "valuation_assumptions.json"


def _default_ticker() -> str:
    for key in ["shared_ticker", "active_ticker", "module2_ticker", "module1_ticker", "last_query_ticker"]:
        value = m1._safe_ticker(str(st.session_state.get(key, "")))
        if value:
            return value
    return "DCM"


def _company_type(industry: str) -> str:
    text = (industry or "").lower()
    if "ngân hàng" in text or "bank" in text: return "bank"
    if "bảo hiểm" in text or "insurance" in text: return "insurance"
    if "chứng khoán" in text or "securities" in text: return "securities"
    if "bất động sản" in text or "real estate" in text: return "real_estate"
    if any(x in text for x in ["thép","steel","dầu","oil","phân bón","fertilizer","cao su","rubber","than","coal","shipping"]): return "cyclical"
    return "normal"


def _valuation_range(company, annual: pd.DataFrame):
    if annual is None or annual.empty: return None
    try:
        assumptions = load_assumptions(ASSUMPTIONS_PATH)
        target_mos = float(st.session_state.get("target_mos_pct", assumptions.get("target_mos_pct", 50.0)))
        assumptions["target_mos_pct"] = target_mos
        valuation_df = build_module2_valuation_table(company, annual, assumptions)
        if valuation_df is None or valuation_df.empty: return None
        return build_valuation_range(valuation_df, getattr(company, "current_price", None), target_mos)
    except Exception as exc:
        st.caption(f"Checklist chưa lấy được valuation bridge từ Module 2: {exc}")
        return None


def render_page() -> None:
    m1._inject_runtime_ui_css(); inject_oaktree_theme(); apply_full_width()
    m1._render_brand_page_header(
        "📋 Investment Research & Checklist",
        "Core Research System — Table 1.1, Table 1.2, Q01–Q59, versioning và snapshot lịch sử.",
    )
    ticker = _default_ticker()
    with st.sidebar:
        render_tre_sidebar_nav()
        st.caption(f"Checklist dùng mã đang đồng bộ toàn app: **{ticker}**")
        st.caption("Phase 1B chưa dùng AI; mọi assessment cuối cùng thuộc về analyst.")

    overview_csv, year_csv, quarter_csv, _, active_ticker = m1._load_active_or_default(ticker)
    company = m1._load_overview_cached(str(overview_csv), active_ticker)
    annual_raw = m1._load_timeseries_cached(str(year_csv), active_ticker, "Y", 10)
    quarterly = m1._load_timeseries_cached(str(quarter_csv), active_ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    st.session_state["shared_ticker"] = company.ticker
    st.session_state["active_ticker"] = company.ticker
    st.session_state["module1_ticker"] = company.ticker
    st.session_state["module2_ticker"] = company.ticker

    industry = m1._display_industry_value(getattr(company, "industry", ""))
    host = HostContext(
        company=CompanyContext(
            company_key=f"TICKER:{company.ticker}", ticker=company.ticker,
            company_name=company.company_name, exchange=getattr(company, "exchange", "UNKNOWN") or "UNKNOWN",
            industry_name=industry, company_type=_company_type(industry),
            metadata={"sub_industry": getattr(company, "sub_industry", "")},
        ),
        analyst=AnalystContext(user_id="analyst", display_name="Analyst"),
        shared_db_path=CHECKLIST_DB,
    )
    render_investment_checklist(
        host,
        data_provider=CurrentRepoDataProvider(company, annual, valuation_range=_valuation_range(company, annual)),
    )


render_page()
apply_full_width()
