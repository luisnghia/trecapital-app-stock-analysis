from __future__ import annotations

import os
from copy import copy
from pathlib import Path
from typing import Callable

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
from modules.investment_checklist.ui.integration_preview_v3 import render_investment_checklist

APP_DIR = Path(__file__).resolve().parents[1]
CHECKLIST_DB = APP_DIR / "data_cache" / "investment_checklist.db"  # Local/dev fallback only.
ASSUMPTIONS_PATH = APP_DIR / "configs" / "valuation_assumptions.json"


def _secret_database_url() -> str | None:
    """Read durable DB URL from Streamlit secrets without ever rendering/logging it."""
    # Root-level Streamlit secrets are also exposed as environment variables. Reading them first
    # keeps local/dev execution quiet when no secrets.toml exists and supports non-Streamlit hosts.
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(key)
        if value and str(value).strip():
            return str(value).strip()

    # `st.secrets.get(...)` renders a red Streamlit error before raising when no secrets file is
    # configured. `load_if_toml_exists()` is the public, silent probe intended for optional secrets.
    try:
        if not st.secrets.load_if_toml_exists():
            return None
        secrets = st.secrets.to_dict()
    except Exception:
        return None

    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = secrets.get(key)
        if value and str(value).strip():
            return str(value).strip()
    try:
        connections = secrets.get("connections", {})
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
    if "ngân hàng" in text or "bank" in text:
        return "bank"
    if "bảo hiểm" in text or "insurance" in text:
        return "insurance"
    if "chứng khoán" in text or "securities" in text:
        return "securities"
    if "bất động sản" in text or "real estate" in text:
        return "real_estate"
    if any(x in text for x in ["thép", "steel", "dầu", "oil", "phân bón", "fertilizer", "cao su", "rubber", "than", "coal", "shipping"]):
        return "cyclical"
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


def _active_reusable_bundle(ticker: str):
    """Reuse any valid active Trecapital bundle instead of refetching it on page navigation.

    Previous code reused only labels containing 'Dữ liệu cập nhật'. That forced an avoidable live
    network fetch when another Trecapital page had already activated a valid bundle under a
    different label. Reusing the active files makes the common cross-page path network-free.
    """
    ticker = m1._safe_ticker(ticker)
    checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
    has_active = bool(checker(ticker)) if callable(checker) else False
    paths = [
        st.session_state.get("active_overview_csv"),
        st.session_state.get("active_year_csv"),
        st.session_state.get("active_quarter_csv"),
    ]
    if not has_active:
        active = m1._safe_ticker(str(st.session_state.get("active_ticker", "")))
        has_active = active == ticker and all(p and Path(str(p)).exists() for p in paths)
    if not has_active or not all(p and Path(str(p)).exists() for p in paths):
        return None

    label = str(st.session_state.get("active_source_label", "Dữ liệu đang hoạt động") or "Dữ liệu đang hoạt động")
    statement_only = "Dữ liệu tích hợp" in label or "Dữ liệu mẫu" in label
    st.session_state["checklist_bundle_mode"] = "reused_active"
    return Path(str(paths[0])), Path(str(paths[1])), Path(str(paths[2])), label, ticker, statement_only


def _load_checklist_bundle(ticker: str):
    """Prefer the already-active Trecapital bundle; fetch only when no reusable bundle exists."""
    ticker = m1._safe_ticker(ticker) or "DCM"
    active = _active_reusable_bundle(ticker)
    if active:
        return active

    diagnostics = []
    st.session_state["checklist_bundle_mode"] = "live_fetch"
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
            overview, year, quarter, _label = m1._export_bundled_financial_cached(
                str(m1.BUNDLED_XLSM), ticker, str(m1.DATA_CACHE_DIR)
            )
            fallback_label = "Dữ liệu tích hợp dự phòng — chỉ dùng BCTC, không dùng cached quote làm giá hiện tại"
            st.session_state["checklist_live_load_diagnostics"] = diagnostics
            st.session_state["checklist_bundle_mode"] = "statement_fallback"
            return Path(overview), Path(year), Path(quarter), fallback_label, ticker, True
        except Exception as exc:
            diagnostics.append(f"workbook error={exc}")

    st.session_state["checklist_live_load_diagnostics"] = diagnostics
    st.session_state["checklist_bundle_mode"] = "sample_fallback"
    return (
        m1.DEFAULT_OVERVIEW_CSV,
        m1.DEFAULT_YEAR_CSV,
        m1.DEFAULT_QUARTER_CSV,
        "Dữ liệu mẫu — không phải dữ liệu thị trường hiện tại",
        ticker,
        True,
    )


def _sync_global_ticker(ticker: str, *, force_refresh: bool = False) -> bool:
    """Run the canonical Module 1 pipeline and bind one ticker to every Trecapital page."""
    safe = m1._safe_ticker(ticker)
    if len(safe) < 3:
        return False
    if not force_refresh:
        checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
        if callable(checker) and checker(safe):
            for key in ("shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker"):
                st.session_state[key] = safe
            st.session_state["module1_input_ticker"] = safe
            st.session_state["_checklist_bound_ticker"] = safe
            return True

    st.session_state["last_query_ticker"] = safe
    st.session_state["last_query_source"] = "FireAnt + Vietstock"
    m1._search_and_bind(safe, "FireAnt + Vietstock")
    checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
    success = bool(checker(safe)) if callable(checker) else m1._safe_ticker(str(st.session_state.get("active_ticker", ""))) == safe
    if success:
        for key in ("shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker"):
            st.session_state[key] = safe
        # Module 1 has a keyed widget; update it too so returning to Tổng quan never shows an old symbol.
        st.session_state["module1_input_ticker"] = safe
        st.session_state["checklist_ticker_input"] = safe
        st.session_state["_checklist_bound_ticker"] = safe
        st.session_state.pop("_checklist_prepared_financials", None)
    return success


def _render_ticker_search() -> str:
    """Checklist ticker control with the same shared-session behavior as the other Trecapital pages."""
    current = _default_ticker()
    if st.session_state.get("_checklist_bound_ticker") != current:
        st.session_state["checklist_ticker_input"] = current
        st.session_state["_checklist_bound_ticker"] = current
    elif "checklist_ticker_input" not in st.session_state:
        st.session_state["checklist_ticker_input"] = current

    raw = st.text_input(
        "Mã cổ phiếu",
        max_chars=10,
        key="checklist_ticker_input",
        help="Nhập mã và app sẽ đồng bộ cùng mã cho Tổng quan, Định giá chuyên sâu, Thao túng tài chính và Investment Checklist.",
    )
    safe = m1._safe_ticker(raw)
    auto_sync = st.checkbox(
        "Tự động cập nhật khi đổi mã",
        value=True,
        key="checklist_auto_sync_ticker",
        help="Khi mã hợp lệ thay đổi, Checklist gọi đúng pipeline dữ liệu chung của Trecapital; không tạo nguồn dữ liệu riêng.",
    )
    refresh = st.button("🔎 Tìm kiếm & cập nhật toàn app", use_container_width=True, key="checklist_refresh_ticker")
    attempt = f"{safe}|FireAnt + Vietstock"
    changed = len(safe) >= 3 and safe != current
    should_auto = auto_sync and changed and st.session_state.get("_checklist_last_auto_attempt") != attempt

    if refresh or should_auto:
        st.session_state["_checklist_last_auto_attempt"] = attempt
        with st.spinner(f"Đang đồng bộ {safe} cho toàn bộ Trecapital..."):
            ok = _sync_global_ticker(safe, force_refresh=bool(refresh))
        if ok:
            st.success(f"Đã đồng bộ {safe} cho toàn bộ các page.")
            st.rerun()
        else:
            st.warning(f"Chưa lấy được bộ dữ liệu chuẩn cho {safe}; app giữ nguyên bộ dữ liệu đang hoạt động để tránh trộn mã.")
    return _default_ticker()


def _path_signature(path) -> tuple[int, int]:
    try:
        stat = Path(str(path)).stat()
        return int(stat.st_mtime_ns), int(stat.st_size)
    except Exception:
        return 0, 0


def _dir_signature(path) -> int:
    try:
        return int(Path(str(path)).stat().st_mtime_ns)
    except Exception:
        return 0


@st.cache_data(ttl=120, show_spinner=False)
def _prepare_financials_cached(
    overview_path: str,
    year_path: str,
    quarter_path: str,
    ticker: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
    raw_dir_sig: int,
):
    """Prepare annual/TTM only when a Checklist section actually needs quantitative data."""
    del overview_sig, year_sig, quarter_sig, raw_dir_sig  # cache-key only
    company = m1._load_overview_cached(overview_path, ticker)
    annual_raw = m1._load_timeseries_cached(year_path, ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, ticker, "Q", 20)
    annual_raw, quarterly, debt_note = augment_debt_from_latest_fireant_raw(
        annual_raw, quarterly, ticker, m1.RAW_DIR
    )
    annual = append_ttm_row(annual_raw, quarterly)
    return company, annual, debt_note


def _prepare_financials_session(
    overview_path,
    year_path,
    quarter_path,
    ticker: str,
):
    """Session hot-cache avoids dataframe deserialization/hash overhead after first quantitative use."""
    key = (
        m1._safe_ticker(ticker),
        str(overview_path), _path_signature(overview_path),
        str(year_path), _path_signature(year_path),
        str(quarter_path), _path_signature(quarter_path),
        _dir_signature(m1.RAW_DIR),
    )
    cached = st.session_state.get("_checklist_prepared_financials")
    if isinstance(cached, dict) and cached.get("key") == key:
        return cached["company"], cached["annual"], cached["debt_note"]
    result = _prepare_financials_cached(
        str(overview_path), str(year_path), str(quarter_path), ticker,
        key[2], key[4], key[6], key[7],
    )
    st.session_state["_checklist_prepared_financials"] = {
        "key": key, "company": result[0], "annual": result[1], "debt_note": result[2]
    }
    return result


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


class _LazyChecklistDataProvider(CurrentRepoDataProvider):
    """Delay annual/quarter/debt/TTM work until Analytical Tools/Watchlist asks for it.

    Research Home, Workspace and History can therefore open from another page without reading and
    enriching the full financial history. Once loaded, annual data stays hot in session state.
    """

    def __init__(self, company, annual_loader: Callable[[], pd.DataFrame], valuation_range=None):
        self.company = company
        self._annual_loader = annual_loader
        self._annual_df: pd.DataFrame | None = None
        self.valuation_range = valuation_range

    @property
    def annual_df(self) -> pd.DataFrame:
        if self._annual_df is None:
            loaded = self._annual_loader()
            self._annual_df = loaded if isinstance(loaded, pd.DataFrame) else pd.DataFrame()
        return self._annual_df


def render_page() -> None:
    m1._inject_runtime_ui_css()
    inject_oaktree_theme()
    apply_full_width()
    m1._render_brand_page_header(
        "📋 Investment Research & Checklist",
        "Integrated research workspace — Analytical Tools, Watchlist, Q01–Q59, versioning và lịch sử analyst.",
    )
    database_url = _secret_database_url()
    with st.sidebar:
        render_tre_sidebar_nav()
        st.markdown("#### 🔎 Mã phân tích")
        requested_ticker = _render_ticker_search()
        st.caption("Checklist chưa dùng AI; mọi assessment cuối cùng thuộc về analyst.")
        if database_url:
            st.success("Lưu trữ Checklist: PostgreSQL/Supabase bền vững")
        else:
            st.warning("Lưu trữ Checklist: SQLite local/dev — chưa dùng cho dữ liệu production")

    overview_csv, year_csv, quarter_csv, source_label, active_ticker, statement_only_fallback = _load_checklist_bundle(requested_ticker)

    # Fast entry: load only the tiny overview row here. Full annual/quarter/debt/TTM is lazy.
    company = m1._load_overview_cached(str(overview_csv), active_ticker)
    if statement_only_fallback:
        company, _ = _sanitize_statement_only_fallback(company, pd.DataFrame())
        st.warning(
            "Nguồn live chưa trả đủ dữ liệu trong lần tải này. Checklist chỉ dùng BCTC từ dữ liệu tích hợp; "
            "giá hiện tại/vốn hóa/P-E/P-B/P-S cached trong workbook bị loại bỏ vì có thể là giá trị công thức cũ. "
            "Bấm 'Tìm kiếm & cập nhật toàn app' để thử lại pipeline live."
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

    def _load_annual_lazy() -> pd.DataFrame:
        loaded_company, annual, debt_note = _prepare_financials_session(
            overview_csv, year_csv, quarter_csv, active_ticker
        )
        st.session_state["checklist_debt_source_note"] = debt_note
        if statement_only_fallback:
            _safe_company, annual = _sanitize_statement_only_fallback(loaded_company, annual)
        return annual

    with st.sidebar:
        st.caption(f"Checklist đang dùng dữ liệu: **{active_ticker}**")
        st.caption(f"Nguồn đang hoạt động: {m1._safe_source_label(source_label)}")
        if st.session_state.get("checklist_bundle_mode") == "reused_active":
            st.caption("⚡ Fast entry: tái sử dụng bundle đang hoạt động, không gọi lại nguồn dữ liệu khi chuyển page.")
        else:
            st.caption("⚡ Fast mode: annual/TTM chỉ tải khi Analytical Tools/Watchlist thực sự cần.")
        # Keep the established performance contract explicit for regression checks and users.
        st.caption("Fast mode: đổi Question/tool không tải lại pipeline tài chính")

    industry = m1._display_industry_value(getattr(company, "industry", ""))
    host = HostContext(
        company=CompanyContext(
            company_key=f"TICKER:{active_ticker}",
            ticker=active_ticker,
            company_name=getattr(company, "company_name", "") or active_ticker,
            exchange=getattr(company, "exchange", "UNKNOWN") or "UNKNOWN",
            industry_name=industry,
            company_type=_company_type(industry),
            metadata={"sub_industry": getattr(company, "sub_industry", "")},
        ),
        analyst=AnalystContext(user_id="analyst", display_name="Analyst"),
        shared_db_path=CHECKLIST_DB,
        database_url=database_url,
    )

    provider = _LazyChecklistDataProvider(
        company,
        _load_annual_lazy,
        valuation_range=lambda safe_company, safe_annual: _valuation_range(safe_company, safe_annual),
    )
    render_investment_checklist(host, data_provider=provider)


render_page()
apply_full_width()
