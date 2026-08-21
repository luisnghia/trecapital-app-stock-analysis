from __future__ import annotations

from copy import copy
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
from modules.investment_checklist.trecapital_debt_enricher import augment_debt_from_latest_fireant_raw
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


def _active_live_bundle(ticker: str):
    """Return the existing active bundle only when it came from a fresh runtime update."""
    ticker = m1._safe_ticker(ticker)
    active = m1._safe_ticker(str(st.session_state.get("active_ticker", "")))
    paths = [
        st.session_state.get("active_overview_csv"),
        st.session_state.get("active_year_csv"),
        st.session_state.get("active_quarter_csv"),
    ]
    label = str(st.session_state.get("active_source_label", "") or "")
    is_runtime_update = "Dữ liệu cập nhật" in label
    if active == ticker and is_runtime_update and all(p and Path(str(p)).exists() for p in paths):
        return Path(str(paths[0])), Path(str(paths[1])), Path(str(paths[2])), label, ticker, False
    return None


def _load_checklist_bundle(ticker: str):
    """Use the same live Trecapital pipeline as main; workbook is statement-only fallback."""
    ticker = m1._safe_ticker(ticker) or "DCM"
    active = _active_live_bundle(ticker)
    if active:
        return active

    diagnostics = []
    try:
        result, source_key = m1._fetch_source(ticker, "FireAnt + Vietstock")
        diagnostics.append(
            f"live score={m1._result_score(result)}, overview={len(result.overview)}, năm={len(result.annual)}, quý={len(result.quarterly)}"
        )
        if m1._result_has_dashboard_data(result):
            overview_csv, year_csv, quarter_csv, _counts = m1._export_provider_result_to_cache(result, ticker, source_key)
            label = f"Dữ liệu cập nhật | {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}"
            m1._activate_data_source(overview_csv, year_csv, quarter_csv, label, ticker)
            st.session_state["last_query_ticker"] = ticker
            st.session_state["last_query_source"] = "FireAnt + Vietstock"
            st.session_state["_last_auto_sync_attempt"] = f"{ticker}|FireAnt + Vietstock"
            return overview_csv, year_csv, quarter_csv, label, ticker, False
    except Exception as exc:
        diagnostics.append(f"live error={exc}")

    if m1.BUNDLED_XLSM.exists():
        try:
            overview, year, quarter, label = m1._export_bundled_financial_cached(
                str(m1.BUNDLED_XLSM), ticker, str(m1.DATA_CACHE_DIR)
            )
            fallback_label = "Dữ liệu tích hợp dự phòng — chỉ dùng BCTC, không dùng cached quote làm giá hiện tại"
            st.session_state["checklist_live_load_diagnostics"] = diagnostics
            return Path(overview), Path(year), Path(quarter), fallback_label, ticker, True
        except Exception as exc:
            diagnostics.append(f"workbook error={exc}")

    st.session_state["checklist_live_load_diagnostics"] = diagnostics
    return m1.DEFAULT_OVERVIEW_CSV, m1.DEFAULT_YEAR_CSV, m1.DEFAULT_QUARTER_CSV, "Dữ liệu mẫu — không phải dữ liệu thị trường hiện tại", ticker, True


def _sanitize_statement_only_fallback(company, annual: pd.DataFrame):
    """Never let cached workbook quote fields masquerade as today's market data."""
    safe_company = copy(company)
    for field in ("current_price", "market_cap_bil", "shares_outstanding_mil", "pe", "pb", "ps"):
        try:
            setattr(safe_company, field, None)
        except Exception:
            pass
    safe_annual = annual.copy() if isinstance(annual, pd.DataFrame) else pd.DataFrame()
    for field in ("current_price", "market_price_vnd", "year_end_price"):
        if field in safe_annual.columns:
            safe_annual[field] = pd.NA
    return safe_company, safe_annual


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

    overview_csv, year_csv, quarter_csv, source_label, active_ticker, statement_only_fallback = _load_checklist_bundle(requested_ticker)
    company = m1._load_overview_cached(str(overview_csv), active_ticker)
    # 11 annual rows are loaded internally so the oldest year in the displayed 10-year CCC proxy
    # still has a prior balance for Shearn's average Inventory/AR/AP formula.
    annual_raw = m1._load_timeseries_cached(str(year_csv), active_ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_csv), active_ticker, "Q", 20)

    # Trecapital already downloaded the FireAnt balance-sheet raw payload. The legacy exact parser
    # omitted borrowing labels, so enrich debt from that audit file without another network call.
    annual_raw, quarterly, debt_note = augment_debt_from_latest_fireant_raw(
        annual_raw, quarterly, active_ticker, m1.RAW_DIR
    )
    annual = append_ttm_row(annual_raw, quarterly)
    st.session_state["checklist_debt_source_note"] = debt_note

    if statement_only_fallback:
        company, annual = _sanitize_statement_only_fallback(company, annual)
        st.warning(
            "Nguồn live chưa trả đủ dữ liệu trong lần tải này. Checklist chỉ dùng BCTC từ dữ liệu tích hợp; "
            "giá hiện tại/vốn hóa/P-E/P-B/P-S cached trong workbook bị loại bỏ vì có thể là giá trị công thức cũ. "
            "Khi quay lại Tổng quan, app sẽ tiếp tục thử pipeline live thay vì coi workbook là nguồn đang hoạt động."
        )

    if not statement_only_fallback:
        st.session_state["shared_ticker"] = company.ticker
        st.session_state["active_ticker"] = company.ticker
        st.session_state["module1_ticker"] = company.ticker
        st.session_state["module2_ticker"] = company.ticker
    else:
        st.session_state["shared_ticker"] = active_ticker
        st.session_state["module1_ticker"] = active_ticker
        st.session_state["module2_ticker"] = active_ticker
        if "Dữ liệu tích hợp" in str(st.session_state.get("active_source_label", "")):
            for key in ("active_ticker", "active_overview_csv", "active_year_csv", "active_quarter_csv", "active_source_label"):
                st.session_state.pop(key, None)

    with st.sidebar:
        st.caption(f"Checklist đang dùng dữ liệu thực tế: **{active_ticker}**")
        st.caption(f"Nguồn đang hoạt động: {m1._safe_source_label(source_label)}")

    industry = m1._display_industry_value(getattr(company, "industry", ""))
    host = HostContext(
        company=CompanyContext(
            company_key=f"TICKER:{active_ticker}", ticker=active_ticker,
            company_name=getattr(company, "company_name", "") or active_ticker,
            exchange=getattr(company, "exchange", "UNKNOWN") or "UNKNOWN",
            industry_name=industry, company_type=_company_type(industry),
            metadata={"sub_industry": getattr(company, "sub_industry", "")},
        ),
        analyst=AnalystContext(user_id="analyst", display_name="Analyst"),
        shared_db_path=CHECKLIST_DB,
        database_url=database_url,
    )

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
