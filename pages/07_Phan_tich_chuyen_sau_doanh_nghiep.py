from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Phân tích chuyên sâu doanh nghiệp | Trecapital",
    page_icon="🔬",
    layout="wide",
)


import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter1 import load_inventory, load_record, render_chapter1
from modules.deep_company_analysis.monitoring import evaluate_and_persist
from modules.deep_company_analysis.opportunity_signals import OpportunityEventEvidenceAgent, build_opportunity_signals
from modules.deep_company_analysis.trecapital_auto import build_chapter1_auto_data
from modules.deep_company_analysis.chapter2_page_support import render_chapter2_tab
from modules.deep_company_analysis.chapter3_page_support import render_chapter3_tab
from modules.deep_company_analysis.chapter4_page_support import render_chapter4_tab
from modules.deep_company_analysis.chapter5_page_support import render_chapter5_tab
from modules.deep_company_analysis.chapter6_page_support import render_chapter6_tab
from modules.deep_company_analysis.chapter7_page_support import render_chapter7_tab
from modules.deep_company_analysis.chapter8_page_support import render_chapter8_tab
from modules.deep_company_analysis.chapter8_integration import build_chapter8_summary
from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record
from modules.investment_checklist.trecapital_bridge import CurrentRepoDataProvider
from modules.investment_checklist.trecapital_debt_enricher import augment_debt_from_latest_fireant_raw
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme


APP_DIR = Path(__file__).resolve().parents[1]
ASSUMPTIONS_PATH = APP_DIR / "configs" / "valuation_assumptions.json"
FRESH_QUOTE_HOURS = 6.0


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
    quote_fresh: bool,
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
    current_price = auto_data.get("valuation", {}).get("current_price") if quote_fresh else None
    auto_data["opportunity_signals"] = build_opportunity_signals(
        provider,
        annual,
        m1.RAW_DIR,
        safe,
        current_price=current_price,
    )
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
            bool(quote_fresh),
        )
        auto_data["source_label"] = source_label
        auto_data["quote_fresh"] = quote_fresh
        if not quote_fresh:
            # Keep statement-only ratios and price-history signals, but never present a stale cached
            # quote as today's price/current valuation percentile.
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
            signals = auto_data.get("opportunity_signals", {})
            signals["valuation_percentile"] = None
            signals["valuation_metric"] = ""
            signals["valuation_current"] = None
            auto_data.setdefault("source_notes", []).append(
                "Quote cache quá 6 giờ hoặc là dữ liệu mẫu: các field phụ thuộc giá thị trường và valuation percentile hiện tại đã bị để trống. Bấm 'Cập nhật dữ liệu & signals' để lấy giá mới."
            )
        return auto_data, company_name, ""
    except Exception as exc:
        return None, "", f"Không đọc được Trecapital canonical data: {exc}"


def _refresh_event_evidence(ticker: str) -> str:
    safe = _safe_ticker(ticker)
    try:
        paths, _, _ = _active_paths(safe)
        company_name = ""
        if paths:
            company = m1._load_overview_cached(str(paths[0]), safe)
            company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
        result = OpportunityEventEvidenceAgent(m1.RAW_DIR).search(safe, company_name, max_results_per_query=4)
        return f"Event evidence đã cập nhật; {len(result.table)} dòng evidence/link nguồn được rà soát."
    except Exception as exc:
        return f"Event evidence chưa cập nhật được: {exc}"


def _scan_review_queue_from_cache() -> tuple[int, int]:
    """Evaluate saved triggers for every inventory ticker that already has a local Trecapital bundle.

    This scan is deliberately cache-only: it does not fan out network calls across the watchlist.
    The normal per-ticker refresh remains the place where market/financial data is downloaded.
    """
    inventory = load_inventory()
    if inventory is None or inventory.empty or "Mã" not in inventory.columns:
        return 0, 0
    checked = 0
    skipped = 0
    for ticker_value in inventory["Mã"].astype(str).tolist():
        safe = _safe_ticker(ticker_value)
        if not safe:
            continue
        data, _, _ = _prepare_auto_data(safe)
        record = load_record(safe)
        if not data or not record.get("triggers"):
            skipped += 1
            continue
        try:
            evaluate_and_persist(safe, record, data)
            checked += 1
        except Exception:
            skipped += 1
    return checked, skipped


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
            st.session_state["dca_event_refresh_note"] = _refresh_event_evidence(safe)
            _prepare_auto_data_cached.clear()
        return ok
    except Exception:
        return False


st.title("Phân tích chuyên sâu doanh nghiệp")
st.caption("Khung phân tích doanh nghiệp theo The Investment Checklist — chọn một chương để làm việc trong cùng workspace, dùng chung dữ liệu Trecapital.")

st.markdown(
    """
    <style>
    div[data-testid="stTabs"] {margin-top: 12px !important;}
    div[data-testid="stTabs"] div[role="tablist"] {
        display:flex !important; flex-wrap:wrap !important; gap:14px !important;
        background:rgba(234,247,241,.96) !important; padding:14px 16px !important;
        border-radius:26px !important; border:2px solid rgba(11,127,117,.30) !important;
        box-shadow:0 10px 26px rgba(11,127,117,.12) !important;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        min-height:58px !important; height:58px !important; border-radius:999px !important;
        padding:0 28px !important; border:2.5px solid rgba(11,127,117,.40) !important;
        background:#FFFFFF !important; color:#0B5F58 !important; font-size:1.04rem !important;
        font-weight:900 !important; box-shadow:0 6px 16px rgba(11,127,117,.10) !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background:linear-gradient(135deg,#0B7F75,#128C7E) !important; color:#FFFFFF !important;
        border-color:#F5B21B !important; box-shadow:0 10px 24px rgba(11,127,117,.28) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

default_ticker = _safe_ticker(
    str(
        st.session_state.get("dca_ch1_ticker")
        or st.session_state.get("dca_ch2_ticker")
        or st.session_state.get("dca_ch3_ticker")
        or st.session_state.get("dca_ch4_ticker")
        or st.session_state.get("dca_ch7_ticker")
        or st.session_state.get("dca_ch8_ticker")
        or st.session_state.get("dca_ch6_ticker")
        or st.session_state.get("dca_ch5_ticker")
        or st.session_state.get("active_ticker")
        or st.session_state.get("shared_ticker")
        or st.session_state.get("module2_ticker")
        or "DGC"
    )
) or "DGC"

CHAPTER_OPTIONS = (
    "📗 Chương 1 — Cơ hội đầu tư",
    "📘 Chương 2 — Hiểu doanh nghiệp",
    "📙 Chương 3 — Góc nhìn khách hàng",
    "📕 Chương 4 — Lợi thế & ngành",
    "📒 Chương 5 — Hoạt động & tài chính",
    "📓 Chương 6 — Earnings & dòng tiền",
    "👥 Chương 7 — Ban điều hành",
    "🧭 Chương 8 — Năng lực vận hành",
)

# Only the selected chapter is executed. Unlike st.tabs, this avoids rebuilding all eight
# chapter bodies after each analyst interaction and materially reduces edit latency.
active_chapter = st.radio(
    "Chương phân tích",
    CHAPTER_OPTIONS,
    horizontal=True,
    key="dca_active_chapter",
    label_visibility="collapsed",
)
# chapter8_tab compatibility marker: Chapter 8 remains embedded in this unified page.

if active_chapter == CHAPTER_OPTIONS[0]:
    with st.expander("📘 Hướng dẫn sử dụng Chương 1 — Hình thành & Sàng lọc Cơ hội đầu tư", expanded=True):
        st.markdown(
            """
**Mục tiêu của Chương 1:** biến một ý tưởng cổ phiếu thành một hồ sơ nghiên cứu có cấu trúc, sàng lọc nhanh chất lượng, ghi nhận định giá ban đầu và đưa doanh nghiệp vào đúng **Research Gate** để tiếp tục theo dõi.

**Quy trình sử dụng khuyến nghị:**

1. **Nhập mã cổ phiếu → bấm `🔄 Cập nhật dữ liệu & signals`.** Trecapital lấy dữ liệu canonical hiện có để prefill phần định lượng. Nếu quote đã cũ, các chỉ tiêu phụ thuộc giá sẽ được để trống thay vì dùng số cũ.
2. **A. Idea Origin:** ghi vì sao doanh nghiệp xuất hiện trên radar, tại sao thị trường có thể đang định giá sai và luận điểm ban đầu.
3. **B. Opportunity Signals:** xem drawdown 52 tuần, valuation percentile, price/fundamental divergence và event candidate. Đây chỉ là **research signal, không phải Buy Signal**.
4. **C. Quality Filter — Table 1.1:** đánh giá 10 tiêu chí `✓ Có / X Không / — Chưa biết / N/A`. `Data Suggested` chỉ hỗ trợ analyst; **Analyst Assessment mới là kết luận chính**. Confidence chỉ có **Thấp / Trung bình / Cao** và không cộng vào Quality Score.
5. **D–E. Research Gaps & Valuation Snapshot:** ghi các điểm chưa biết cần nghiên cứu thêm; kiểm tra Target Price, MOS, FCF Yield, TEV/EBIT, Debt/EBITDA... trước khi lưu snapshot.
6. **F. Research Gate:** chọn `🟢 Continue / 🟡 Watch / 🟠 Pause / 🔴 Reject` và bắt buộc ghi **Reason for Gate**. App **không tự đổi Gate**.
7. **Monitoring Trigger:** đặt điều kiện cần xem lại như `MOS > 25%`, `ROIC < 15%`, `Debt/EBITDA > 2x`, `có BCTC mới`, `BCTC Q3/2026` hoặc `event/CBTT mới`. Nên dùng **Structured Trigger Builder** thay vì gõ câu tự do khi có thể.

**Cách hiểu Monitoring / Review Queue:**  
`Opportunity Inventory` = danh sách cơ hội đang theo dõi → `Monitoring Trigger` = điều kiện anh muốn app kiểm tra → `Review Queue` = các điều kiện đã xảy ra và cần analyst mở hồ sơ xem lại → `Research Gate` = quyết định của analyst sau khi review.

Khi một trigger chuyển từ **chưa thỏa → thỏa**, app tạo một item trong **Review Queue** và tránh tạo cảnh báo trùng khi điều kiện vẫn tiếp tục thỏa. Sau khi đã xem xét, chọn item và bấm **`✅ Đã review item này`**; thao tác này chỉ đóng cảnh báo, **không thay đổi Research Gate**.

**Nguyên tắc cốt lõi:** **AI/Data = Research Assistant; người dùng = Investment Analyst.** Chương 1 không tự đưa ra BUY/HOLD/SELL.
            """
        )

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
                st.caption("Valuation Snapshot, 4 tiêu chí định lượng Table 1.1 và Opportunity Signals được prefill từ pipeline chung; event candidate luôn cần analyst xác minh.")
                event_note = str(st.session_state.get("dca_event_refresh_note", "") or "")
                if event_note:
                    st.caption(event_note)
            else:
                st.info(f"{default_ticker}: {auto_error}")
        with c2:
            if st.button("🔄 Cập nhật dữ liệu & signals", use_container_width=True, key="dca_refresh_trecapital"):
                with st.spinner(f"Đang cập nhật {default_ticker} qua pipeline chung của Trecapital..."):
                    ok = _refresh_trecapital(default_ticker)
                if ok:
                    st.success("Đã cập nhật dữ liệu và Opportunity Signals.")
                    st.rerun()
                else:
                    st.warning("Chưa lấy được bộ dữ liệu chuẩn. App không trộn dữ liệu từ mã khác.")

    if st.button("🔎 Quét Review Queue từ dữ liệu cache", use_container_width=True, key="dca_scan_review_queue"):
        with st.spinner("Đang kiểm tra trigger của Opportunity Inventory bằng dữ liệu local đã có..."):
            checked, skipped = _scan_review_queue_from_cache()
        st.success(f"Đã kiểm tra {checked} mã; bỏ qua {skipped} mã chưa có cache hoặc chưa đặt trigger.")
        st.rerun()

    render_chapter1(default_ticker=default_ticker, auto_data=auto_data, auto_company_name=auto_company_name)

if active_chapter == CHAPTER_OPTIONS[1]:
    chapter2_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter2_tab(chapter2_ticker)

if active_chapter == CHAPTER_OPTIONS[2]:
    chapter3_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch3_ticker")
            or st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter3_tab(chapter3_ticker)

if active_chapter == CHAPTER_OPTIONS[3]:
    chapter4_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch4_ticker")
            or st.session_state.get("dca_ch3_ticker")
            or st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter4_tab(chapter4_ticker)

if active_chapter == CHAPTER_OPTIONS[4]:
    chapter5_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch5_ticker")
            or st.session_state.get("dca_ch4_ticker")
            or st.session_state.get("dca_ch3_ticker")
            or st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter5_tab(chapter5_ticker)

if active_chapter == CHAPTER_OPTIONS[5]:
    chapter6_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch6_ticker")
            or st.session_state.get("dca_ch5_ticker")
            or st.session_state.get("dca_ch4_ticker")
            or st.session_state.get("dca_ch3_ticker")
            or st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter6_tab(chapter6_ticker)

if active_chapter == CHAPTER_OPTIONS[6]:
    chapter7_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch7_ticker")
            or st.session_state.get("dca_ch6_ticker")
            or st.session_state.get("dca_ch5_ticker")
            or st.session_state.get("dca_ch4_ticker")
            or st.session_state.get("dca_ch3_ticker")
            or st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter7_tab(chapter7_ticker)

if active_chapter == CHAPTER_OPTIONS[7]:
    # Phase 8E summary is descriptive only. It never computes a management score or changes the investment gate.
    _ch8_summary_payload = load_chapter8_record(default_ticker)
    _ch8_summary = build_chapter8_summary(_ch8_summary_payload)
    with st.expander("🧭 Trạng thái nghiên cứu Chương 8 — Q39 đến Q47", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Answered", f"{_ch8_summary['answered']}/{_ch8_summary['total_questions']}")
        c2.metric("Partial", _ch8_summary["partial"])
        c3.metric("Promoted evidence", _ch8_summary["promoted_evidence"])
        c4.metric("Open research gaps", _ch8_summary["research_gaps_open"])
        c5.metric("Analyst conclusions", _ch8_summary["analyst_conclusions"])
        st.caption("Đây là research-completeness summary, không phải Management Quality Score và không tạo BUY/HOLD/SELL.")

    chapter8_ticker = _safe_ticker(
        str(
            st.session_state.get("dca_ch8_ticker")
            or st.session_state.get("dca_ch7_ticker")
            or st.session_state.get("dca_ch6_ticker")
            or st.session_state.get("dca_ch5_ticker")
            or st.session_state.get("dca_ch4_ticker")
            or st.session_state.get("dca_ch3_ticker")
            or st.session_state.get("dca_ch2_ticker")
            or st.session_state.get("dca_ch1_ticker")
            or st.session_state.get("active_ticker")
            or default_ticker
        )
    ) or default_ticker
    render_chapter8_tab(chapter8_ticker)

apply_full_width()
