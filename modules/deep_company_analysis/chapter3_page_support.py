from __future__ import annotations

"""Reusable Chapter 3 Research Assistant panel for the unified Deep Analysis page."""

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.table_format import render_static_table

import module1_dashboard as m1
from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature
from modules.deep_company_analysis.chapter3 import conflicting_evidence_count, load_record, render_chapter3, save_record
from modules.deep_company_analysis.chapter3_auto import (
    Chapter3EvidenceAgent,
    build_chapter3_assistant_draft,
    load_cached_chapter3_evidence,
    merge_assistant_draft,
)


def _safe_ticker(value: str) -> str:
    try:
        return m1._safe_ticker(value)
    except Exception:
        return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _latest_evidence_signature(ticker: str) -> tuple[int, int]:
    folder = Path(m1.RAW_DIR) / "chapter3_customer_evidence" / _safe_ticker(ticker)
    if not folder.exists():
        return 0, 0
    files = sorted(folder.glob("evidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return _path_signature(files[0]) if files else (0, 0)


def _company_name_from_canonical(ticker: str) -> str:
    paths, _ = _active_paths(ticker)
    if not paths:
        return str(st.session_state.get("active_company_name") or "")
    try:
        company = m1._load_overview_cached(str(paths[0]), _safe_ticker(ticker))
        return str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    except Exception:
        return str(st.session_state.get("active_company_name") or "")


@st.cache_data(ttl=120, show_spinner=False)
def _prepare_chapter3_cached(ticker: str, evidence_sig: tuple[int, int], source_label: str):
    del evidence_sig
    evidence = load_cached_chapter3_evidence(m1.RAW_DIR, ticker)
    if evidence.empty:
        return None
    return build_chapter3_assistant_draft(evidence, source_label=source_label)


def prepare_assistant(ticker: str):
    safe = _safe_ticker(ticker)
    company_name = _company_name_from_canonical(safe)
    draft = _prepare_chapter3_cached(safe, _latest_evidence_signature(safe), "Trecapital Chapter 3 customer evidence cache")
    if not draft:
        return None, company_name, "Chưa có customer evidence cache cho mã này. Bấm Cập nhật Customer Evidence để Research Assistant tìm nguồn."
    return draft, company_name, ""


def refresh_chapter3_sources(ticker: str) -> tuple[bool, str]:
    safe = _safe_ticker(ticker)
    if len(safe) < 3:
        return False, "Mã cổ phiếu chưa hợp lệ."
    company_name = _company_name_from_canonical(safe)
    if not company_name:
        try:
            st.session_state["last_query_ticker"] = safe
            st.session_state["last_query_source"] = "FireAnt + Vietstock"
            m1._search_and_bind(safe, "FireAnt + Vietstock")
            company_name = _company_name_from_canonical(safe)
        except Exception:
            company_name = ""
    try:
        result = Chapter3EvidenceAgent(m1.RAW_DIR).search(safe, company_name, max_results_per_query=5)
        _prepare_chapter3_cached.clear()
        return True, f"Đã cập nhật {len(result.table)} customer-evidence candidates cho Chương 3."
    except Exception as exc:
        return False, f"Cập nhật customer evidence chưa thành công: {exc}"


def _evidence_layer(row: dict) -> str:
    group = str(row.get("Nhóm thông tin") or "").lower()
    url = str(row.get("Nguồn/URL") or "").lower()
    official_tokens = ("nguồn doanh nghiệp", "bctn", "bctc", "pdf chính thức", "official", "investor relations")
    if any(token in group for token in official_tokens) or "ducgiangchem.vn" in url:
        return "A — Company Disclosure"
    return "B — Independent / Customer-side"


def _evidence_table(rows) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=["Layer", "Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu"])
    df = pd.DataFrame(rows)
    df.insert(0, "Layer", [_evidence_layer(row) for row in rows])
    cols = [c for c in ("Layer", "Nhóm thông tin", "Tiêu đề", "Nguồn/URL", "Trích yếu", "Điểm phù hợp") if c in df.columns]
    return df[cols].head(12) if cols else pd.DataFrame()


def _coverage(draft: dict) -> tuple[int, int, dict[str, bool]]:
    quality = draft.get("provenance", {}).get("quality_coverage", {}) if isinstance(draft, dict) else {}
    eligible = quality.get("eligible_fields") if isinstance(quality, dict) else None
    if isinstance(eligible, dict) and eligible:
        return sum(bool(v) for v in eligible.values()), len(eligible), eligible
    eligible = {
        "Q7 Core Customer evidence": bool(draft.get("q7", {}).get("core_customer_summary")),
        "Q8 Concentration evidence": bool(draft.get("q8", {}).get("concentration_table")),
        "Q9 Sales-friction evidence": bool(draft.get("q9", {}).get("sales_friction_summary")),
        "Q10 Retention evidence": bool(draft.get("q10", {}).get("retention_metrics")),
        "Q11 Customer-orientation evidence": bool(draft.get("q11", {}).get("customer_orientation_summary")),
        "Q12 Customer-pain evidence": bool(draft.get("q12", {}).get("pain_summary")),
        "Q13 Dependency evidence": bool(draft.get("q13", {}).get("dependency_reason")),
        "Q14 Replacement/disappearance evidence": bool(draft.get("q14", {}).get("evidence_draft")),
    }
    return sum(bool(v) for v in eligible.values()), len(eligible), eligible


def render_assistant_panel(ticker: str, draft: dict | None, company_name: str, error: str) -> None:
    with st.container(border=True):
        left, right = st.columns([3, 1])
        with left:
            st.markdown("### 🤖 Research Assistant — Customer Perspective Evidence")
            if draft:
                filled, total, _ = _coverage(draft)
                provenance = draft.get("provenance", {})
                st.success(
                    f"Đã dựng customer-evidence draft cho {ticker}: {filled}/{total} nhóm evidence có dữ liệu | "
                    f"{provenance.get('evidence_count', 0)} candidates."
                )
                st.caption(
                    "Research Assistant chỉ tìm và điền evidence/ô trống. Không tự quyết định Customer Concentration, "
                    "Sales Ease, Need-to-have/Dependency, Disappearance Impact hoặc BUY/HOLD/SELL."
                )
            else:
                st.info(error or "Chưa có Customer Perspective Draft.")
        with right:
            if st.button("🔄 Cập nhật Customer Evidence", use_container_width=True, key=f"ch3_refresh_{ticker}"):
                with st.spinner(f"Đang tìm customer evidence cho {ticker}..."):
                    ok, note = refresh_chapter3_sources(ticker)
                if ok:
                    st.success(note)
                    st.rerun()
                else:
                    st.warning(note)

        if not draft:
            return

        all_evidence_rows = []
        counts = []
        for question in ("q7", "q8", "q9", "q10", "q11", "q12", "q13", "q14"):
            rows = draft.get(question, {}).get("evidence", []) or []
            counts.append(len(rows))
            all_evidence_rows.extend(row for row in rows if isinstance(row, dict))
        unique_rows = {}
        for row in all_evidence_rows:
            key = (str(row.get("Nguồn/URL") or ""), str(row.get("Tiêu đề") or ""), str(row.get("Trích yếu") or ""))
            unique_rows[key] = row
        layer_a = sum(1 for row in unique_rows.values() if _evidence_layer(row).startswith("A"))
        layer_b = sum(1 for row in unique_rows.values() if _evidence_layer(row).startswith("B"))
        saved_record = load_record(ticker, company_name)
        layer_c = len(saved_record.get("customer_interviews", []) or [])
        conflicts = conflicting_evidence_count(saved_record)
        ecols = st.columns(4)
        ecols[0].metric("A — Company Disclosure", layer_a)
        ecols[1].metric("B — Independent/Customer-side", layer_b)
        ecols[2].metric("C — Analyst Fieldwork", layer_c)
        ecols[3].metric("Conflicting", conflicts)
        cols = st.columns(8)
        for idx, question in enumerate(("Q7", "Q8", "Q9", "Q10", "Q11", "Q12", "Q13", "Q14")):
            cols[idx].metric(question, counts[idx])

        retention = draft.get("q10", {}).get("retention_metrics", {}) or {}
        concentration = draft.get("q8", {}).get("concentration_table", []) or []
        gaps = draft.get("research_gap_suggestions", []) or []
        if gaps:
            with st.expander("🧭 Research Gaps do Research Assistant phát hiện", expanded=False):
                st.caption("Đây là danh sách việc cần nghiên cứu thêm; app không tự ghi đè Research Gaps của analyst.")
                for gap in gaps:
                    st.markdown(f"- {gap}")

        if retention or concentration:
            info_cols = st.columns(2)
            if retention:
                info_cols[0].info(
                    "Explicit retention metric candidate: "
                    + str(retention.get("retention_rate") or retention.get("churn_rate") or "—")
                    + ". Analyst phải mở nguồn để xác nhận kỳ và định nghĩa."
                )
            if concentration:
                info_cols[1].info(
                    f"Explicit customer-share candidates: {len(concentration)}. Tên khách hàng/period chỉ được xác nhận từ nguồn gốc."
                )

        with st.expander("Evidence candidates Q7–Q14", expanded=False):
            for question, label in (
                ("q7", "Q7 — Core Customer"),
                ("q8", "Q8 — Customer Concentration"),
                ("q9", "Q9 — Sales Friction"),
                ("q10", "Q10 — Retention"),
                ("q11", "Q11 — Customer Orientation"),
                ("q12", "Q12 — Customer Pain"),
                ("q13", "Q13 — Dependency"),
                ("q14", "Q14 — Disappearance / Replacement"),
            ):
                st.markdown(f"**{label}**")
                evidence = _evidence_table(draft.get(question, {}).get("evidence", []))
                if evidence.empty:
                    st.caption("Chưa có evidence candidate phù hợp.")
                else:
                    render_static_table(evidence, use_container_width=True, hide_index=True)

        record = load_record(ticker, company_name)
        if st.button(
            "🧩 Điền các ô trống bằng Customer Evidence Draft",
            use_container_width=True,
            key=f"ch3_apply_draft_{ticker}",
            help="Không ghi đè analyst content. Các classification/judgement của Q8, Q9, Q13, Q14 luôn do analyst quyết định.",
        ):
            merged = merge_assistant_draft(record, draft)
            if company_name and not str(merged.get("company_name") or "").strip():
                merged["company_name"] = company_name
            save_record(merged)
            st.success("Đã đưa evidence draft vào các ô trống. Hãy mở nguồn, review/chỉnh sửa rồi bấm Lưu Chương 3 để xác nhận analyst work.")
            st.rerun()


def render_chapter3_tab(default_ticker: str) -> None:
    safe = _safe_ticker(default_ticker) or "DGC"
    draft, company_name, error = prepare_assistant(safe)
    resolved_name = str(company_name or st.session_state.get("active_company_name") or "")
    render_assistant_panel(safe, draft, resolved_name, error)
    render_chapter3(default_ticker=safe, company_name=resolved_name)
