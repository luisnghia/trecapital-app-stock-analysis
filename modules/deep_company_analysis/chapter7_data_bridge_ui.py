from __future__ import annotations

from typing import Any
import json

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter7 import save_record
from modules.deep_company_analysis.chapter7_data_bridge import (
    RECORD_TYPES,
    SOURCE_GRADES,
    SOURCE_TYPES,
    SourceMeta,
    apply_candidate_ids,
    bridge_status_frame,
    candidate_review_frame,
    fetch_structured_source,
    ingest_structured_rows,
    latest_refresh_runs,
    list_conflicts,
    list_review_queue,
    list_sources,
    parse_structured_bytes,
    refresh_registered_sources,
    register_source,
    resolve_review_item,
    staleness_warnings,
)
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _source_meta_from_ui(ticker: str) -> SourceMeta:
    c1, c2, c3 = st.columns(3)
    with c1:
        record_type = st.selectbox("Loại dữ liệu", list(RECORD_TYPES), key=f"dca7b_{ticker}_record_type")
        source_grade = st.selectbox("Source grade", list(SOURCE_GRADES), key=f"dca7b_{ticker}_source_grade")
    with c2:
        source_type = st.selectbox("Loại nguồn", list(SOURCE_TYPES), key=f"dca7b_{ticker}_source_type")
        source_title = st.text_input("Tên tài liệu / nguồn", key=f"dca7b_{ticker}_source_title")
    with c3:
        publication_date = st.text_input("Publication date", placeholder="DD/MM/YYYY hoặc YYYY", key=f"dca7b_{ticker}_publication")
        effective_date = st.text_input("Effective date", placeholder="DD/MM/YYYY hoặc YYYY", key=f"dca7b_{ticker}_effective")
    c4, c5 = st.columns(2)
    with c4:
        as_of_date = st.text_input("As-of date", placeholder="DD/MM/YYYY hoặc YYYY", key=f"dca7b_{ticker}_asof")
    with c5:
        page_section = st.text_input("Page / Section", key=f"dca7b_{ticker}_page_section")
    return SourceMeta(
        title=source_title,
        source_type=source_type,
        source_url_or_file="",
        source_grade=source_grade,
        publication_date=publication_date,
        effective_date=effective_date,
        as_of_date=as_of_date,
        page_or_section=page_section,
        record_type=record_type,
    )


def _render_source_register(ticker: str) -> None:
    sources = pd.DataFrame(list_sources(ticker))
    if not sources.empty:
        st.markdown("**Source Register**")
        preferred = [
            "id", "record_type", "title", "source_type", "source_grade", "publication_date", "effective_date",
            "as_of_date", "page_or_section", "source_url_or_file", "parser_status", "updated_at",
        ]
        cols = [c for c in preferred if c in sources.columns]
        render_static_table(sources[cols], height=320, sort_key=f"dca7b_{ticker}_sources")


def _render_ingest_controls(ticker: str) -> None:
    st.markdown("### Nạp nguồn cấu trúc chính thức")
    st.caption(
        "Phase 7B chỉ tự parse dữ liệu có cấu trúc JSON/CSV/HTML. PDF/unstructured source được giữ làm provenance nhưng không được đoán giá trị; phần research/extraction sâu thuộc Phase 7C."
    )
    meta_base = _source_meta_from_ui(ticker)

    upload = st.file_uploader(
        "Tải structured official source",
        type=["csv", "json", "jsonl", "html", "htm", "pdf"],
        key=f"dca7b_{ticker}_upload",
    )
    if st.button("📥 Nạp file vào Candidate Data", use_container_width=True, key=f"dca7b_{ticker}_ingest_file"):
        if upload is None:
            st.warning("Chưa chọn file.")
        else:
            meta = SourceMeta(**{**meta_base.__dict__, "source_url_or_file": upload.name})
            try:
                rows = parse_structured_bytes(upload.getvalue(), upload.name, meta.record_type)
                result = ingest_structured_rows(ticker, meta.record_type, rows, meta, note="User uploaded structured official source")
                st.success(
                    f"Đã nạp {result['raw_count']} raw rows → {result['candidate_count']} candidates; "
                    f"duplicate {result['duplicate_count']}; conflicts {result['conflict_count']}."
                )
            except Exception as exc:
                register_source(ticker, meta, parser_status=f"Not parsed in Phase 7B: {exc}")
                st.warning(str(exc))

    url = st.text_input("Official structured URL", placeholder="https://...csv / .json / HTML table", key=f"dca7b_{ticker}_url")
    if st.button("🌐 Đăng ký + cập nhật URL", use_container_width=True, key=f"dca7b_{ticker}_ingest_url"):
        if not url.strip():
            st.warning("Chưa nhập URL.")
        else:
            meta = SourceMeta(**{**meta_base.__dict__, "source_url_or_file": url.strip()})
            register_source(ticker, meta)
            try:
                rows = fetch_structured_source(meta)
                result = ingest_structured_rows(ticker, meta.record_type, rows, meta, note="Official structured URL ingest")
                st.success(
                    f"Đã cập nhật URL: {result['raw_count']} raw rows → {result['candidate_count']} candidates; "
                    f"duplicate {result['duplicate_count']}; conflicts {result['conflict_count']}."
                )
            except Exception as exc:
                register_source(ticker, meta, parser_status=f"Refresh error / unstructured source: {exc}")
                st.warning(f"Nguồn đã được lưu provenance nhưng chưa parse thành candidate: {exc}")

    if st.button("🔄 Cập nhật dữ liệu quản trị", type="primary", use_container_width=True, key=f"dca7b_{ticker}_refresh_all"):
        with st.spinner("Đang refresh các structured official sources đã đăng ký + local source folder..."):
            result = refresh_registered_sources(ticker)
        if result.get("error_count"):
            st.warning(
                f"Refresh xong với {result['error_count']} lỗi/nguồn không cấu trúc. Candidates mới: {result['candidate_count']}; "
                f"duplicates: {result['duplicate_count']}; conflicts: {result['conflict_count']}."
            )
            for msg in result.get("messages", [])[:12]:
                st.caption(msg)
        else:
            st.success(
                f"Refresh xong. Candidates mới: {result['candidate_count']}; duplicates: {result['duplicate_count']}; "
                f"conflicts: {result['conflict_count']}."
            )


def _render_candidate_review(ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
    st.markdown("### Candidate Data → Analyst Review → Apply")
    frame = candidate_review_frame(ticker)
    if frame.empty:
        st.info("Chưa có Candidate Data mới.")
        return payload
    edited = sortable_data_editor(
        frame,
        key=f"dca7b_{ticker}_candidate_review",
        hide_index=True,
        use_container_width=True,
        height=380,
        num_rows="fixed",
        disabled=[c for c in frame.columns if c != "Apply?"],
        column_config={"Apply?": st.column_config.CheckboxColumn("Apply?", default=False)},
    )
    selected: list[int] = []
    if isinstance(edited, pd.DataFrame) and "Apply?" in edited.columns:
        selected = [int(x) for x in edited.loc[edited["Apply?"] == True, "Candidate ID"].tolist()]
    st.caption(
        "Apply chỉ ghi các record dữ liệu vào roster/career/compensation/ownership/insider/event tables. "
        "Không thay Q33–Q38, OO/LT/HH, Lion/Hyena hoặc kết luận cuối của analyst."
    )
    if st.button("✅ Apply các candidates đã chọn", use_container_width=True, key=f"dca7b_{ticker}_apply_candidates"):
        if not selected:
            st.warning("Chưa chọn candidate.")
        else:
            updated, result = apply_candidate_ids(ticker, payload, selected)
            save_record(ticker, updated, str(updated.get("company_name") or ""))
            st.success(f"Đã apply {result['applied']} candidate; bỏ qua {result['skipped']}. Analyst conclusions giữ nguyên.")
            st.rerun()
    return payload


def _render_conflicts_and_review_queue(ticker: str) -> None:
    conflicts = pd.DataFrame(list_conflicts(ticker, "Needs analyst review"))
    if not conflicts.empty:
        st.markdown("### ⚠ Data Conflict / Identity Review")
        cols = [c for c in ["id", "conflict_type", "record_type", "record_key", "details", "status", "created_at"] if c in conflicts.columns]
        render_static_table(conflicts[cols], height=300, sort_key=f"dca7b_{ticker}_conflicts")
        st.caption("Possible identity matches không được tự merge. Conflicting disclosures được giữ song song cho đến khi analyst xử lý.")

    queue = pd.DataFrame(list_review_queue(ticker, "Open"))
    if not queue.empty:
        st.markdown("### Management Change Review Queue")
        cols = [c for c in ["id", "event_date", "event_type", "manager", "questions_to_review", "reason", "status"] if c in queue.columns]
        render_static_table(queue[cols], height=300, sort_key=f"dca7b_{ticker}_review_queue")
        ids = [int(x) for x in queue["id"].tolist()]
        review_id = st.selectbox("Review item", ids, key=f"dca7b_{ticker}_review_id")
        if st.button("✅ Đã review management event", use_container_width=True, key=f"dca7b_{ticker}_review_done"):
            resolve_review_item(int(review_id), "Reviewed")
            st.success("Đã đóng review item. Không có Q33–Q38 nào bị tự thay đổi.")
            st.rerun()


def _render_refresh_history(ticker: str) -> None:
    history = pd.DataFrame(latest_refresh_runs(ticker, 20))
    if not history.empty:
        with st.expander("Refresh Run Audit", expanded=False):
            cols = [
                c for c in [
                    "id", "started_at", "completed_at", "source_count", "raw_count", "candidate_count", "duplicate_count",
                    "conflict_count", "error_count", "parser_version", "note",
                ] if c in history.columns
            ]
            render_static_table(history[cols], height=300, sort_key=f"dca7b_{ticker}_refresh_history")


def render_structured_management_bridge(ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    st.markdown("## 🧱 Phase 7B — Structured Management Data Bridge")
    st.caption(
        "Primary disclosure first | Raw → Candidate → Confirmed | event/as-of data | registered ≠ executed | "
        "actual shares ≠ options ≠ RSU ≠ ESOP | no automatic management classification."
    )

    with st.expander("🔒 Phase 7B data boundary", expanded=True):
        st.markdown(
            """
- **Source priority:** Annual/Governance reports, AGM/Board documents, regulator/exchange disclosures, insider disclosures và official IR/company releases trước secondary structured sources.
- **Không silent overwrite:** mọi structured record đi qua `Raw → Candidate → Analyst Apply`.
- **Không fake TTM:** Chương 7 dùng publication/effective/as-of dates. Rolling 12M insider activity nếu có sau này cũng không được gọi là TTM financial data.
- **Conflict-safe:** nguồn mâu thuẫn được giữ và tạo conflict item; tên người gần giống chỉ tạo possible identity match, không auto-merge.
- **Q37:** aggregate compensation không được phân bổ giả; Actual Shares/Options/RSU/ESOP tách riêng.
- **Q38:** Registered Shares khác Executed Shares. Giao dịch không sinh BUY/SELL signal.
- **Phase 7B không nghiên cứu PDF/unstructured text bằng AI.** Phần đó thuộc Phase 7C.
            """
        )

    status = bridge_status_frame(safe)
    if not status.empty:
        st.markdown("### Structured Data Status")
        render_static_table(status, height=300, sort_key=f"dca7b_{safe}_status")
    warnings = staleness_warnings(safe)
    if warnings:
        st.warning("Staleness review:\n\n- " + "\n- ".join(warnings[:12]))

    with st.container(border=True):
        _render_ingest_controls(safe)
    _render_source_register(safe)
    with st.container(border=True):
        payload = _render_candidate_review(safe, payload)
    _render_conflicts_and_review_queue(safe)
    _render_refresh_history(safe)
    return payload


__all__ = ["render_structured_management_bridge"]
