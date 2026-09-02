from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter1 import render_chapter1
from modules.deep_company_analysis.trecapital_auto import build_chapter1_auto_data
from modules.investment_checklist.trecapital_bridge import CurrentRepoDataProvider
from modules.investment_checklist.trecapital_debt_enricher import augment_debt_from_latest_fireant_raw
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme


APP_DIR = Path(__file__).resolve().parents[1]
ASSUMPTIONS_PATH = APP_DIR / "configs" / "valuation_assumptions.json"
FRESH_QUOTE_HOURS = 6.0


st.set_page_config(
    page_title="Phân tích chuyên sâu doanh nghiệp | Trecapital",
    page_icon="🔬",
    layout="wide",
)

inject_oaktree_theme()

with st.sidebar:
    render_tre_sidebar_nav()


def _safe_ticker(value: str) -> str:
    try:
        return m1._safe_ticker(value)
    except Exception:
        return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _valuation_range(company, annual: pd.DataFrame):
    if annual is None or annual.empty:
        return None
    try:
        from module2_engine import build_module2_valuation_table, build_valuation_range, load_assumptions

        assumptions = load_assumptions(ASSUMPTIONS_PATH)
        target_mos = float(st.session_state.get("target_mos_pct", assumptions.get("target_mos_pct", 50.0)))
        assumptions["target_mos_pct"] = target_mos
        valuation_df = build_module2_valuation_table(company, annual, assumptions)
        if valuation_df is None or valuation_df.empty:
            return None
        return build_valuation_range(valuation_df, getattr(company, "current_price", None), target_mos)
    except Exception:
        return None


def _path_signature(path) -> tuple[int, int]:
    try:
        stat = Path(str(path)).stat()
        return int(stat.st_mtime_ns), int(stat.st_size)
    except Exception:
        return 0, 0


def _bundle_age_hours(paths) -> float:
    try:
        updated_at = max(Path(str(path)).stat().st_mtime for path in paths)
        return max(0.0, (time.time() - updated_at) / 3600.0)
    except Exception:
        return 999999.0


def _active_paths(ticker: str):
    safe = _safe_ticker(ticker)
    active = _safe_ticker(str(st.session_state.get("active_ticker", "")))
    paths = (
        st.session_state.get("active_overview_csv"),
        st.session_state.get("active_year_csv"),
        st.session_state.get("active_quarter_csv"),
    )
    if active == safe and all(p and Path(str(p)).exists() for p in paths):
        resolved = tuple(Path(str(p)) for p in paths)
        label = str(st.session_state.get("active_source_label", "Trecapital active data"))
        stale_marker = any(marker in label.lower() for marker in ("quote đã cũ", "dữ liệu mẫu", "dữ liệu tích hợp", "statement"))
        quote_fresh = (not stale_marker) and _bundle_age_hours(resolved) <= FRESH_QUOTE_HOURS
        return resolved, label, quote_fresh

    # Reuse the newest complete process cache for the requested ticker. Statements remain useful
    # offline, but quote-dependent valuation fields are disabled once the cache is older than 6h.
    candidates = []
    try:
        roots = [path / safe for path in m1.DATA_CACHE_DIR.iterdir() if path.is_dir()]
    except Exception:
        roots = []
    names = ("company_overview_sample.csv", "financial_timeseries_year.csv", "financial_timeseries_quarter.csv")
    for root in roots:
        if root.parent.name == "financial_xlsm":
            continue
        candidate = tuple(root / name for name in names)
        if all(path.exists() and path.stat().st_size > 20 for path in candidate):
            candidates.append((max(path.stat().st_mtime for path in candidate), candidate))
    if candidates:
        updated_at, candidate = max(candidates, key=lambda x: x[0])
        age_hours = max(0.0, (time.time() - updated_at) / 3600.0)
        quote_fresh = age_hours <= FRESH_QUOTE_HOURS
        label = f"Trecapital cache | {pd.Timestamp.fromtimestamp(updated_at):%Y-%m-%d %H:%M:%S}"
        if not quote_fresh:
            label += " | quote đã cũ"
        return candidate, label, quote_fresh

    # Only DCM may use the packaged normalized sample. Never relabel the DCM sample as another ticker.
    if safe == "DCM":
        sample = (m1.DEFAULT_OVERVIEW_CSV, m1.DEFAULT_YEAR_CSV, m1.DEFAULT_QUARTER_CSV)
        if all(Path(path).exists() for path in sample):
            return tuple(Path(path) for path in sample), "Dữ liệu mẫu DCM tích hợp | quote không dùng", False
    return None, "", False


@st.cache_data(ttl=120, show_spinner=False)
def _prepare_auto_data_cached(
    ticker: str,
    overview_path: str,
    year_path: str,
    quarter_path: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
):
    del overview_sig, year_sig, quarter_sig
    safe = _safe_ticker(ticker)
    company = m1._load_overview_cached(overview_path, safe)
    annual_raw = m1._load_timeseries_cached(year_path, safe, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, safe, "Q", 20)
    annual_raw, quarterly, debt_note = augment_debt_from_latest_fireant_raw(annual_raw, quarterly, safe, m1.RAW_DIR)
    annual = append_ttm_row(annual_raw, quarterly)
    provider = CurrentRepoDataProvider(company, annual, valuation_range=_valuation_range)
    auto_data = build_chapter1_auto_data(provider, annual)
    if debt_note:
        auto_data.setdefault("source_notes", []).append(str(debt_note))
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    return auto_data, company_name


def _prepare_auto_data(ticker: str):
    paths, source_label, quote_fresh = _active_paths(ticker)
    if not paths:
        return None, "", "Chưa có bộ dữ liệu Trecapital cho mã này trên máy."
    overview, year, quarter = paths
    try:
        auto_data, company_name = _prepare_auto_data_cached(
            _safe_ticker(ticker),
            str(overview),
            str(year),
            str(quarter),
            _path_signature(overview),
            _path_signature(year),
            _path_signature(quarter),
        )
        auto_data["source_label"] = source_label
        auto_data["quote_fresh"] = quote_fresh
        if not quote_fresh:
            # Keep statement-only ratios (Debt/EBITDA, EBIT/Interest) and qualitative quantitative
            # suggestions, but never present a stale cached quote as today's price/market valuation.
            valuation = auto_data.get("valuation", {})
            for key in (
                "current_price",
                "mos_pct",
                "stock_price_vs_target_pct",
                "fcf_yield_pct",
                "dividend_yield_pct",
                "tev_ebit",
                "tev_ebitda",
            ):
                valuation[key] = None
            auto_data.setdefault("source_notes", []).append(
                "Quote cache quá 6 giờ hoặc là dữ liệu mẫu: các field phụ thuộc giá thị trường đã bị để trống. Bấm 'Cập nhật dữ liệu Trecapital' để lấy giá mới."
            )
        return auto_data, company_name, ""
    except Exception as exc:
        return None, "", f"Không đọc được Trecapital canonical data: {exc}"


def _refresh_trecapital(ticker: str) -> bool:
    safe = _safe_ticker(ticker)
    if len(safe) < 3:
        return False
    try:
        st.session_state["last_query_ticker"] = safe
        st.session_state["last_query_source"] = "FireAnt + Vietstock"
        m1._search_and_bind(safe, "FireAnt + Vietstock")
        checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
        ok = bool(checker(safe)) if callable(checker) else _safe_ticker(str(st.session_state.get("active_ticker", ""))) == safe
        if ok:
            for key in ("active_ticker", "shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker"):
                st.session_state[key] = safe
            _prepare_auto_data_cached.clear()
        return ok
    except Exception:
        return False


st.title("Phân tích chuyên sâu doanh nghiệp")
st.caption("Khung phân tích chi tiết doanh nghiệp theo The Investment Checklist — triển khai từng chương, bắt đầu từ Chương 1.")

default_ticker = _safe_ticker(
    str(
        st.session_state.get("dca_ch1_ticker")
        or st.session_state.get("active_ticker")
        or st.session_state.get("shared_ticker")
        or st.session_state.get("module2_ticker")
        or "DCM"
    )
) or "DCM"

auto_data, auto_company_name, auto_error = _prepare_auto_data(default_ticker)

with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        if auto_data:
            as_of = auto_data.get("as_of") or "—"
            source_label = auto_data.get("source_label") or auto_data.get("source_module") or "Trecapital"
            if auto_data.get("quote_fresh"):
                st.success(f"Đã nối dữ liệu Trecapital cho {default_ticker} | kỳ dữ liệu: {as_of} | {source_label}")
            else:
                st.warning(f"Đã nối BCTC Trecapital cho {default_ticker}, nhưng quote không còn đủ mới | kỳ dữ liệu: {as_of} | {source_label}")
            st.caption("Valuation Snapshot và 4 tiêu chí định lượng của Table 1.1 sẽ được prefill từ dữ liệu này nếu analyst chưa có bản lưu trước đó. Field phụ thuộc giá chỉ prefill khi quote đủ mới.")
        else:
            st.info(f"{default_ticker}: {auto_error}")
    with c2:
        if st.button("🔄 Cập nhật dữ liệu Trecapital", use_container_width=True, key="dca_refresh_trecapital"):
            with st.spinner(f"Đang cập nhật {default_ticker} qua pipeline chung của Trecapital..."):
                ok = _refresh_trecapital(default_ticker)
            if ok:
                st.success("Đã cập nhật dữ liệu.")
                st.rerun()
            else:
                st.warning("Chưa lấy được bộ dữ liệu chuẩn. App không trộn dữ liệu từ mã khác.")

render_chapter1(
    default_ticker=default_ticker,
    auto_data=auto_data,
    auto_company_name=auto_company_name,
)
apply_full_width()
