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
CHECKLIST_DB = APP_DIR / "data_cache" / "investment_checklist.db"  # Local/dev fallback only.
ASSUMPTIONS_PATH = APP_DIR / "configs" / "valuation_assumptions.json"


def _secret_database_url() -> str | None:
    """Read durable DB URL from Streamlit secrets without ever rendering/logging it."""
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
        if value and str(value).strip():
            return str(value).strip()
    try:
        connections = st.secrets.get("connections", {})
        pg = connections.get("postgresql", {}) if hasattr(connections, "get") else {}
        value = pg.get("url") if hasattr(pg, "get") else None
        if value and str(value).strip():
            return str(value).strip()
    except Exception:
        pass
    return None


def _default_ticker() -> str:
    # The active data bundle is the source of truth. This prevents the sidebar saying DCM while
    # the actual CSV bundle still belongs to another ticker from an earlier page/session action.
    for key in ["active_ticker", "shared_ticker", "module2_ticker", "module1_ticker", "last_query_ticker"]:
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
    if any(x in text for x in ["thép", "steel", "dầu", "oil", "phân bón", "fertilizer", "cao su", "rubber", "than", "coal", "shipping"]): return "cyclical"
    return "normal"


def _valuation_range(company, annual: pd.DataFrame):
    if annual is None or annual.empty:
        return None
    try:
        assumptions = load_assumptions(ASSUMPTIONS_PATH)
        target_mos = float(st.session_state.get("target_mos_pct", assumptions.get("target_mos_pct", 50.0)))
        assumptions["target_mos_pct"] = target_mos
        valuation_df = build_module2_valuation_table(company, annual, assumptions)
        if valuation_df is None or valuation_df.empty:
            return None
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
    requested_ticker = _default_ticker()
    database_url = _secret_database_url()
    with st.sidebar:
        render_tre_sidebar_nav()
        st.caption("Phase 1C chưa dùng AI; mọi assessment cuối cùng thuộc về analyst.")
        if database_url:
            st.success("Lưu trữ Checklist: PostgreSQL/Supabase bền vững")
        else:
            st.warning("Lưu trữ Checklist: SQLite local/dev — chưa dùng cho dữ liệu production")

    overview_csv, year_csv, quarter_csv, source_label, active_ticker = m1._load_active_or_default(requested_ticker)
    company = m1._load_overview_cached(str(overview_csv), active_ticker)
    annual_raw = m1._load_timeseries_cached(str(year_csv), active_ticker, "Y", 10)
    quarterly = m1._load_timeseries_cached(str(quarter_csv), active_ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)

    # From this point on every module key follows the data that was actually loaded, not a stale
    # session label. The sidebar therefore cannot claim one ticker while Table 1.2 reads another.
    st.session_state["shared_ticker"] = company.ticker
    st.session_state["active_ticker"] = company.ticker
    st.session_state["module1_ticker"] = company.ticker
    st.session_state["module2_ticker"] = company.ticker
    with st.sidebar:
        st.caption(f"Checklist đang dùng dữ liệu thực tế: **{company.ticker}**")
        st.caption(f"Nguồn đang hoạt động: {m1._safe_source_label(source_label)}")

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
        database_url=database_url,
    )

    # Valuation is deliberately lazy. The bridge passes a reconciled Trecapital company/TTM frame
    # into Module 2 only when Table 1.2 is opened, so bad overview units cannot corrupt target price.
    render_investment_checklist(
        host,
        data_provider=CurrentRepoDataProvider(
            company,
            annual,
            valuation_range=lambda safe_company, safe_annual: _valuation_range(safe_company, safe_annual),
        ),
    )


render_page()
apply_full_width()
