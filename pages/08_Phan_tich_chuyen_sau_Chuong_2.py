from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter2 import load_record, render_chapter2, save_record
from modules.deep_company_analysis.chapter2_auto import (
    Chapter2EvidenceAgent,
    build_chapter2_assistant_draft,
    load_cached_evidence,
    merge_assistant_draft,
)
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav
from ui_oaktree_theme import inject_oaktree_theme

st.set_page_config(
    page_title="Chương 2 - Hiểu doanh nghiệp | Trecapital",
    page_icon="🔎",
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


def _path_signature(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
        return int(stat.st_mtime_ns), int(stat.st_size)
    except Exception:
        return 0, 0


def _active_paths(ticker: str):
    safe = _safe_ticker(ticker)
    active = _safe_ticker(str(st.session_state.get("active_ticker", "")))
    session_paths = (
        st.session_state.get("active_overview_csv"),
        st.session_state.get("active_year_csv"),
        st.session_state.get("active_quarter_csv"),
    )
    if active == safe and all(p and Path(str(p)).exists() for p in session_paths):
        resolved = tuple(Path(str(p)) for p in session_paths)
        label = str(st.session_state.get("active_source_label", "Trecapital active data"))
        return resolved, label

    candidates: list[tuple[float, tuple[Path, Path, Path]]] = []
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
        updated_at, candidate = max(candidates, key=lambda item: item[0])
        return candidate, f"Trecapital cache | {pd.Timestamp.fromtimestamp(updated_at):%Y-%m-%d %H:%M:%S}"

    if safe == "DCM":
        sample = (Path(m1.DEFAULT_OVERVIEW_CSV), Path(m1.DEFAULT_YEAR_CSV), Path(m1.DEFAULT_QUARTER_CSV))
        if all(path.exists() for path in sample):
            return sample, "Dữ liệu mẫu DCM tích hợp"
    return None, ""


@st.cache_data(ttl=120, show_spinner=False)
def _prepare_assistant_cached(
    ticker: str,
    overview_path: str,
    year_path: str,
    quarter_path: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
    evidence_sig: tuple[int, int],
    source_label: str,
):
    del overview_sig, year_sig, quarter_sig, evidence_sig
    safe = _safe_ticker(ticker)
    company = m1._load_overview_cached(overview_path, safe)
    annual_raw = m1._load_timeseries_cached(year_path, safe, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, safe, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    evidence = load_cached_evidence(m1.RAW_DIR, safe)
    draft = build_chapter2_assistant_draft(company, annual, evidence, source_label=source_label)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    return draft, company_name


def _latest_evidence_signature(ticker: str) -> tuple[int, int]:
    folder = Path(m1.RAW_DIR) / "internet_evidence" / _safe_ticker(ticker)
    if not folder.exists():
        return 0, 0
    files = sorted(folder.glob("evidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return 0, 0
    return _path_signature(files[0])


def _prepare_assistant(ticker: str):
    paths, source_label = _active_paths(ticker)
    if not paths:
        evidence = load_cached_evidence(m1.RAW_DIR, ticker)
        if evidence.empty:
            return None, "", "Chưa có Trecapital canonical data hoặc evidence cache cho mã này."
        draft = build_chapter2_assistant_draft(None, pd.DataFrame(), evidence, source_label="Trecapital evidence cache")
        return draft, "", ""
    overview, year, quarter = paths
    try:
        draft, company_name = _prepare_assistant_cached(
            _safe_ticker(ticker),
            str(overview),
            str(year),
            str(quarter),
            _path_signature(overview),
            _path_signature(year),
            _path_signature(quarter),
            _latest_evidence_signature(ticker),
            source_label,
        )
        return draft, company_name, ""
    except Exception as exc:
        return None, "", f"Không dựng được Research Assistant Draft: {exc}"


def _refresh_chapter2_sources(ticker: str) -> tuple[bool, str]:
    safe = _safe_ticker(ticker)
    if len(safe) < 3:
        return False, "Mã cổ phiếu chưa hợp lệ."
    try:
        st.session_state["last_query_ticker"] = safe
        st.session_state["last_query_source"] = "FireAnt + Vietstock"
        m1._search_and_bind(safe, "FireAnt + Vietstock")
        checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
        ok = bool(checker(safe)) if callable(checker) else _safe_ticker(str(st.session_state.get("active_ticker", ""))) == safe
        company_name = ""
        paths, _ = _active_paths(safe)
        if paths:
            company = m1._load_overview_cached(str(paths[0]), safe)
            company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
        evidence_result = Chapter2EvidenceAgent(m1.RAW_DIR).search(safe, company_name, max_results_per_query=5)
        _prepare_assistant_cached.clear()
        note = f"Evidence Chương 2: {len(evidence_result.table)} dòng/link ứng viên được rà soát."
        return ok or not evidence_result.table.empty, note
    except Exception as exc:
        return False, f"Cập nhật Chương 2 chưa thành công: {exc}"


def _evidence_table(rows) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=["Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu"])
    df = pd.DataFrame(rows)
    cols = [col for col in ("Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu") if col in df.columns]
    return df[cols].head(12) if cols else pd.DataFrame()


def _render_assistant_panel(ticker: str, draft: dict | None, company_name: str, error: str) -> None:
    with st.container(border=True):
        left, right = st.columns([3, 1])
        with left:
            st.markdown("### 🤖 Research Assistant — Trecapital Data & Evidence Bridge")
            if draft:
                provenance = draft.get("provenance", {})
                st.success(
                    f"Đã dựng draft cho {ticker} | financial period: {provenance.get('financial_period') or '—'} | "
                    f"evidence candidates: {provenance.get('evidence_count', 0)}"
                )
                st.caption(
                    "Draft chỉ điền bằng dữ liệu canonical/evidence đã tìm được. Không tự kết luận Q1/Q2, không viết 'Own words', "
                    "không viết Skill vs Luck và không ghi đè nội dung analyst đã lưu."
                )
            else:
                st.info(error or "Chưa có Research Assistant Draft.")
        with right:
            if st.button("🔄 Cập nhật Data + Evidence", use_container_width=True, key=f"ch2_refresh_{ticker}"):
                with st.spinner(f"Đang cập nhật dữ liệu/evidence Chương 2 cho {ticker}..."):
                    ok, note = _refresh_chapter2_sources(ticker)
                if ok:
                    st.success(note)
                    st.rerun()
                else:
                    st.warning(note)

        if not draft:
            return

        metrics = draft.get("q4", {}).get("financial_metrics", {})
        if metrics:
            cols = st.columns(5)
            cols[0].metric("Doanh thu", f"{metrics.get('revenue_bil', 0):,.0f} tỷ" if metrics.get("revenue_bil") is not None else "—")
            cols[1].metric("Gross margin", f"{metrics.get('gross_margin_pct', 0):,.1f}%" if metrics.get("gross_margin_pct") is not None else "—")
            cols[2].metric("EBIT margin", f"{metrics.get('ebit_margin_pct', 0):,.1f}%" if metrics.get("ebit_margin_pct") is not None else "—")
            cols[3].metric("FCF", f"{metrics.get('fcf_bil', 0):,.0f} tỷ" if metrics.get("fcf_bil") is not None else "—")
            cols[4].metric("Capex/Revenue", f"{metrics.get('capex_revenue_pct', 0):,.1f}%" if metrics.get("capex_revenue_pct") is not None else "—")

        with st.expander("Evidence candidates Q3–Q6", expanded=False):
            for section, label in (("q3", "Q3 — Business Operations"), ("q4", "Q4 — Money-Making"), ("q5", "Q5 — Evolution"), ("q6", "Q6 — Foreign Markets")):
                st.markdown(f"**{label}**")
                evidence = _evidence_table(draft.get(section, {}).get("evidence", []))
                if evidence.empty:
                    st.caption("Chưa có evidence candidate đủ keyword.")
                else:
                    st.dataframe(evidence, use_container_width=True, hide_index=True)
            currency = draft.get("q6", {}).get("currency_evidence", [])
            if currency:
                st.markdown("**Currency evidence candidates**")
                st.dataframe(pd.DataFrame(currency), use_container_width=True, hide_index=True)

        record = load_record(ticker, company_name)
        if st.button(
            "🧩 Điền các ô trống bằng Research Assistant Draft",
            use_container_width=True,
            key=f"ch2_apply_draft_{ticker}",
            help="Chỉ điền ô trống; không ghi đè nội dung analyst. Own Words, Skill vs Luck, Q1 và Q2 luôn do analyst tự làm.",
        ):
            merged = merge_assistant_draft(record, draft)
            if company_name and not str(merged.get("company_name") or "").strip():
                merged["company_name"] = company_name
            save_record(merged)
            st.success("Đã đưa draft vào các ô trống của workspace. Hãy review/chỉnh sửa rồi bấm Lưu Chương 2 để xác nhận nội dung analyst.")
            st.rerun()


st.title("Phân tích chuyên sâu doanh nghiệp")
st.caption("Chương 2 — Understanding the Business: The Basics | Michael Shearn, The Investment Checklist")

# Reuse the shared ticker selected elsewhere in Trecapital when available.
default_ticker = _safe_ticker(str(
    st.session_state.get("dca_ch2_ticker")
    or st.session_state.get("dca_ch1_ticker")
    or st.session_state.get("active_ticker")
    or st.session_state.get("shared_ticker")
    or st.session_state.get("module2_ticker")
    or "DGC"
)) or "DGC"

assistant_draft, auto_company_name, auto_error = _prepare_assistant(default_ticker)
default_company = str(auto_company_name or st.session_state.get("active_company_name") or "")

_render_assistant_panel(default_ticker, assistant_draft, default_company, auto_error)

render_chapter2(default_ticker=default_ticker, company_name=default_company)
apply_full_width()
