from __future__ import annotations

"""Chapter 9 unified Streamlit analyst workspace for Q48-Q52 plus Phase 9J synthesis handoff.

The UI wires the tested Phase 9A-9J layers into the existing Deep Company Analysis workspace.
Research creates candidates; only the analyst can promote evidence, close known-unknown gaps,
change Research Status/Confidence, write conclusions, and write the cross-chapter management
synthesis. Research-completion readiness and source fingerprints never create a management score,
character classification, MOS/Research Gate change, or BUY/HOLD/SELL.
"""

from typing import Any

import pandas as pd
import streamlit as st

import module1_dashboard as m1
import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract
from modules.deep_company_analysis.chapter7 import load_record as load_chapter7_record
from modules.deep_company_analysis.chapter9_completion import (
    RESEARCH_COMPLETION_BOUNDARY,
    append_completion_log,
    build_dimension_closure,
    build_question_completion,
    completion_snapshot,
)
from modules.deep_company_analysis.chapter9_research import CANDIDATE_COLUMNS, Chapter9ResearchAgent
from modules.deep_company_analysis.chapter9_store import (
    create_snapshot,
    list_snapshots,
    load_record,
    load_snapshot,
    save_record,
)
from modules.deep_company_analysis.chapter9_synthesis_ui import render_management_synthesis_workspace
from modules.deep_company_analysis.chapter9_workspace import (
    WORKSPACE_EVIDENCE_COLUMNS,
    merge_research_gaps,
    promote_selected_candidates,
    validate_candidate_for_promotion,
    workspace_snapshot,
)
from modules.deep_company_analysis.table_format import (
    render_static_table,
    sortable_data_editor,
    static_table_html,
)


RESEARCH_GAP_WORKSPACE_COLUMNS = [
    "Question",
    "Dimension Key",
    "Manager ID",
    "Manager",
    "Research Gap",
    "Materiality",
    "Next Action",
    "Status",
    "Analyst Note",
]


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _rows_frame(rows: Any, columns: list[str]) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
    elif isinstance(rows, list):
        frame = pd.DataFrame([dict(item) for item in rows if isinstance(item, dict)])
    else:
        frame = pd.DataFrame()
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _editor(
    label: str,
    rows: Any,
    columns: list[str],
    key: str,
    *,
    height: int = 340,
    disabled: list[str] | None = None,
    column_config: dict[str, Any] | None = None,
    dynamic: bool = True,
) -> list[dict[str, Any]]:
    st.markdown(f"**{label}**")
    frame = _rows_frame(rows, columns)
    edited = sortable_data_editor(
        frame,
        key=key,
        hide_index=True,
        use_container_width=True,
        height=height,
        num_rows="dynamic" if dynamic else "fixed",
        disabled=disabled or [],
        column_config=column_config or {},
    )
    return edited.to_dict("records") if isinstance(edited, pd.DataFrame) else frame.to_dict("records")


def _source_dimension_frame() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dim in contract.all_dimensions():
        rows.append(
            {
                "Question": dim.question,
                "Dimension Key": dim.key,
                "Dimension": dim.label,
                "Source Origin": dim.origin,
                "Source Pages": ", ".join(str(page) for page in dim.source_pages),
                "Evidence Targets": " | ".join(dim.evidence_targets),
                "Red Flags / Counter-Evidence Cues": " | ".join(dim.red_flags),
                "Supporting / Counter-Signals": " | ".join(dim.counter_signals),
                "Source Note": dim.analyst_note,
            }
        )
    return pd.DataFrame(rows)


def _render_source_lock() -> None:
    with st.expander(
        "🔒 Source-lock Chương 9 — Assessing the Quality of Management: Positive and Negative Traits",
        expanded=True,
    ):
        st.markdown(
            """
- Q48–Q52 bám theo **Michael Shearn — The Investment Checklist — Chapter 9** và giữ nguyên **26 source dimensions** của Phase 9B.
- **Chapter 7 manager master** là nguồn duy nhất cho Manager ID/role. Chương 9 không tạo manager thay thế.
- Q48 và Q52 là **CEO-specific**; candidate chỉ được promote khi khớp đúng CEO/Tổng Giám đốc đã xác nhận ở Chapter 7.
- Phase 9D chỉ tạo **Candidate — analyst verify**. Search snippet không phải fact; original source text được ưu tiên.
- `Unknown` / `Research Gap` là kết quả hợp lệ khi chưa đủ bằng chứng. Không suy đoán để lấp chỗ trống.
- Direction cue chỉ giúp sắp xếp research; **không phải kết luận positive/negative trait**.
- Phase 9G chỉ kiểm tra **research completion/source coverage**; không tự đóng câu hỏi hoặc biến coverage thành Management Quality Score.
- Phase 9J chỉ lưu **analyst-owned cross-chapter synthesis + source fingerprint**; source drift không tự sửa conclusion/status.
- Chương 9 **không tạo Management Quality Score, character classification, MOS/Research Gate change hoặc BUY/HOLD/SELL**.
            """
        )
        st.caption(contract.Q52_FINANCING_CONTEXT_EXCEPTION)


def _render_research_summary(payload: dict[str, Any]) -> None:
    snap = workspace_snapshot(payload)
    with st.container(border=True):
        st.markdown("### Research-completeness summary")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Answered", f"{snap['answered']}/{snap['question_count']}")
        c2.metric("Partial", snap["partial"])
        c3.metric("Unknown", snap["unknown"])
        c4.metric("Promoted evidence", snap["promoted_evidence"])
        c5.metric("Open gaps", snap["open_research_gaps"])
        st.caption(
            "Coverage summary only — không phải điểm chất lượng quản lý, không tạo investment signal."
        )


def _render_manager_context(chapter7_payload: dict[str, Any], ticker: str) -> bridge.Chapter9ContextResult:
    context = bridge.build_context(chapter7_payload)
    st.markdown("### Phase 9C — Manager Context Bridge")
    st.caption(context.note)
    if context.manager_reference.empty:
        st.warning("Chapter 7 manager master chưa có dữ liệu. Q48–Q52 giữ trạng thái unassigned/Unknown.")
    else:
        render_static_table(
            context.manager_reference,
            height=240,
            sort_key=f"dca9_{ticker}_manager_reference",
        )

    if not context.gaps.empty:
        st.markdown("**Manager / CEO scope gaps**")
        render_static_table(context.gaps, height=260, sort_key=f"dca9_{ticker}_scope_gaps")

    with st.expander("26 source dimensions × Chapter 7 manager scope", expanded=False):
        render_static_table(
            context.dimension_scope,
            height=520,
            sort_key=f"dca9_{ticker}_dimension_scope",
        )
    return context


def _render_research(
    ticker: str,
    company_name: str,
    chapter7_payload: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    st.markdown("### Phase 9D–9E — Evidence Research Assistant → Analyst Promotion")
    state_key = f"dca9_research_result_{ticker}"
    c1, c2 = st.columns([1, 2])
    with c1:
        run_research = st.button(
            "🔎 Tự nghiên cứu Q48–Q52",
            use_container_width=True,
            key=f"dca9_{ticker}_research",
        )
    with c2:
        st.caption(
            "Tìm nguồn official/company + web tập trung. Kết quả chỉ là candidate; analyst phải mở nguồn, đọc và tick Select trước khi Promote."
        )

    if run_research:
        with st.spinner(f"Đang nghiên cứu {ticker} — Q48 đến Q52..."):
            result = Chapter9ResearchAgent(m1.RAW_DIR / "chapter9_phase9g_v68").search(
                ticker,
                company_name,
                chapter7_payload=chapter7_payload,
                max_results_per_query=2,
                max_official_documents=18,
            )
        st.session_state[state_key] = {
            "candidates": result.candidates.to_dict("records"),
            "quality": result.quality.to_dict("records"),
            "gaps": result.gaps.to_dict("records"),
            "manager_reference": result.manager_reference.to_dict("records"),
            "dimension_scope": result.dimension_scope.to_dict("records"),
            "source_attempts": result.source_attempts.to_dict("records"),
            "raw_paths": list(result.raw_paths),
            "note": result.note,
        }
        append_completion_log(ticker, "research_run", {"candidate_rows": len(result.candidates), "gap_rows": len(result.gaps)})

    research = st.session_state.get(state_key)
    if not isinstance(research, dict):
        st.info(
            "Chưa có research run trong session này. Analyst vẫn có thể nhập evidence/gaps thủ công và lưu workspace."
        )
        return payload

    quality = pd.DataFrame(research.get("quality") or [])
    if not quality.empty:
        st.markdown("**Dimension coverage / source quality — coverage only**")
        render_static_table(quality, height=420, sort_key=f"dca9_{ticker}_quality")

    candidates = _rows_frame(research.get("candidates"), CANDIDATE_COLUMNS)
    if not candidates.empty:
        st.markdown("**Evidence Candidates — mở nguồn và kiểm tra trước khi tick Promote**")
        candidates["Select"] = candidates["Select"].fillna(False).astype(bool)
        edited = sortable_data_editor(
            candidates,
            key=f"dca9_{ticker}_candidate_editor",
            hide_index=True,
            use_container_width=True,
            height=540,
            num_rows="fixed",
            disabled=[column for column in CANDIDATE_COLUMNS if column != "Select"],
            column_config={
                "Select": st.column_config.CheckboxColumn("Promote?"),
                "Source URL / File": st.column_config.LinkColumn("Mở nguồn", display_text="Open source"),
            },
        )
        if isinstance(edited, pd.DataFrame):
            research["candidates"] = edited.to_dict("records")
            st.session_state[state_key] = research
        else:
            edited = candidates

        if st.button(
            "✅ Promote evidence đã chọn",
            use_container_width=True,
            key=f"dca9_{ticker}_promote",
        ):
            selected = edited[edited["Select"].fillna(False).astype(bool)] if isinstance(edited, pd.DataFrame) else pd.DataFrame()
            validation_failures: list[str] = []
            for _, row in selected.iterrows():
                valid, reason = validate_candidate_for_promotion(row.to_dict(), chapter7_payload)
                if not valid:
                    validation_failures.append(
                        f"{row.get('Question', '')}/{row.get('Dimension Key', '')}: {reason}"
                    )
            payload, added = promote_selected_candidates(
                payload,
                edited,
                chapter7_payload=chapter7_payload,
            )
            save_record(ticker, payload, company_name)
            append_completion_log(ticker, "promote_candidates", {"selected": len(selected), "added": added, "rejected": len(validation_failures)})
            if added:
                st.success(
                    f"Đã promote {added} evidence. Analyst Assessment/Confidence/Research Status không bị ghi đè."
                )
            else:
                st.warning("Không có candidate hợp lệ mới để promote.")
            if validation_failures:
                st.warning("Candidate bị bỏ qua:\n\n- " + "\n- ".join(validation_failures[:12]))
    else:
        st.info("Research run chưa tìm thấy candidate đủ điều kiện; giữ Unknown/Research Gap thay vì suy đoán.")

    gaps = pd.DataFrame(research.get("gaps") or [])
    if not gaps.empty:
        st.markdown("**Research Gaps do assistant phát hiện**")
        render_static_table(gaps, height=380, sort_key=f"dca9_{ticker}_research_gaps_preview")
        if st.button(
            "➕ Đưa Research Gaps vào analyst workspace",
            use_container_width=True,
            key=f"dca9_{ticker}_merge_gaps",
        ):
            payload, added = merge_research_gaps(payload, gaps)
            save_record(ticker, payload, company_name)
            append_completion_log(ticker, "merge_research_gaps", {"added": added})
            st.success(f"Đã thêm {added} research gap mới; Analyst Note hiện có được giữ nguyên.")

    attempts = pd.DataFrame(research.get("source_attempts") or [])
    if not attempts.empty:
        with st.expander("Source attempt log", expanded=False):
            render_static_table(attempts, height=300, sort_key=f"dca9_{ticker}_attempts")
    note = str(research.get("note") or "")
    if note:
        with st.expander("Research run note", expanded=False):
            st.caption(note)
    return payload


def _render_question_status(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Analyst Status & Conclusions — Q48 đến Q52")
    for question in ch9.QUESTION_KEYS:
        title = ch9.QUESTION_TITLES[question]
        page = ch9.QUESTION_SOURCE_PAGES[question]
        with st.expander(f"{question} — {title} | source p.{page}", expanded=question == "Q48"):
            c1, c2 = st.columns(2)
            statuses = list(ch9.QUESTION_STATUS_OPTIONS)
            confidences = list(ch9.CONFIDENCE_OPTIONS)
            current_status = str(payload["question_status"].get(question) or "Unknown")
            current_conf = str(payload["confidence"].get(question) or "Unknown")
            with c1:
                payload["question_status"][question] = st.selectbox(
                    "Research status",
                    statuses,
                    index=statuses.index(current_status) if current_status in statuses else 0,
                    key=f"dca9_{ticker}_{question}_status",
                )
            with c2:
                payload["confidence"][question] = st.selectbox(
                    "Analyst confidence",
                    confidences,
                    index=confidences.index(current_conf) if current_conf in confidences else 0,
                    key=f"dca9_{ticker}_{question}_confidence",
                )
            current = str(payload["analyst_assessment"].get(question) or "")
            payload["analyst_assessment"][question] = st.text_area(
                "Analyst Assessment / Conclusion",
                value="" if current == "Unknown" else current,
                key=f"dca9_{ticker}_{question}_assessment",
                help="Đây là kết luận của analyst. Research Assistant không được ghi vào ô này.",
            ) or "Unknown"


def _render_source_locked_tables(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Source-Locked Analyst Tables")
    payload["q48_passion_research"] = _editor(
        "Q48 — 6 Passion Research Prompts",
        payload.get("q48_passion_research"),
        ch9.Q48_PASSION_COLUMNS,
        f"dca9_{ticker}_q48_passion",
        height=430,
        dynamic=False,
    )

    with st.expander("26 source dimensions — read-only contract", expanded=False):
        source_dimensions = _source_dimension_frame()
        render_static_table(source_dimensions, height=560, sort_key=f"dca9_{ticker}_source_dimensions")
        st.caption(
            "Red flags/counter-signals là research cues từ source contract; không được tự động coi là đúng với doanh nghiệp đang phân tích."
        )


def _render_evidence_gaps_events(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Evidence Matrix, Research Gaps & Behavior Events")
    payload["evidence"] = _editor(
        "Promoted / Manual Evidence Matrix",
        payload.get("evidence"),
        WORKSPACE_EVIDENCE_COLUMNS,
        f"dca9_{ticker}_evidence",
        height=470,
        column_config={
            "Source URL / File": st.column_config.LinkColumn("Source URL / File", display_text="Open source"),
            "Direction": st.column_config.SelectboxColumn(
                "Direction",
                options=list(ch9.EVIDENCE_DIRECTION_OPTIONS),
            ),
        },
    )
    payload["research_gaps"] = _editor(
        "Research Gap Workflow",
        payload.get("research_gaps"),
        RESEARCH_GAP_WORKSPACE_COLUMNS,
        f"dca9_{ticker}_gaps",
        height=400,
    )
    payload["behavior_events"] = _editor(
        "Dated Management / Behavior Events",
        payload.get("behavior_events"),
        ch9.BEHAVIOR_EVENT_COLUMNS,
        f"dca9_{ticker}_events",
        height=430,
    )


def _render_completion_gate(ticker: str, payload: dict[str, Any], chapter7_payload: dict[str, Any]) -> None:
    st.markdown("### Phase 9G — Research Completion Gate & Source Coverage Closure")
    st.caption(RESEARCH_COMPLETION_BOUNDARY)

    with st.expander("📖 Giải thích thuật ngữ Phase 9G", expanded=False):
        st.markdown(
            """
- **Research Completion Gate:** trạng thái quy trình cho biết hồ sơ nghiên cứu đã đủ điều kiện để analyst đóng Q48–Q52 hay chưa; **không phải Research Gate đầu tư**.
- **Source Dimension:** một khía cạnh nghiên cứu bám trực tiếp source contract Chương 9; tổng cộng 26 dimensions.
- **Source Lineage:** đường dẫn/tệp nguồn đi kèm đoạn evidence/reference đủ để kiểm tra lại bằng chứng.
- **Verified Evidence:** evidence đã được analyst promote/xác minh; số lượng evidence không tự tạo kết luận.
- **Known Unknown:** khoảng trống đã nghiên cứu nhưng chưa có bằng chứng đủ tin cậy; analyst có thể chủ động đóng gap và giữ nó trong audit trail thay vì bịa dữ liệu.
- **Closure Status:** trạng thái hoàn thành nghiên cứu của dimension, không phải đánh giá tích cực/tiêu cực về ban điều hành.
            """
        )

    dimensions = build_dimension_closure(payload, chapter7_payload)
    questions = build_question_completion(payload, chapter7_payload)
    snap = completion_snapshot(payload, chapter7_payload)
    gate = snap["research_completion_gate"]

    if gate.startswith("Ready"):
        st.success(f"🟢 {gate}")
    elif gate.startswith("Review"):
        st.warning(f"🟡 {gate}")
    else:
        st.error(f"🔴 {gate}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Closed dimensions", f"{snap['closed_dimensions']}/{snap['source_dimension_count']}")
    c2.metric("Review dimensions", snap["review_dimensions"])
    c3.metric("Open dimensions", snap["open_dimensions"])
    c4.metric("Blocked dimensions", snap["blocked_dimensions"])
    c5.metric("Ready questions", f"{snap['ready_questions']}/{len(ch9.QUESTION_KEYS)}")
    st.caption(
        "Các số trên chỉ là tally về độ hoàn tất nghiên cứu. 26/26 không có nghĩa management tốt và không phải Buy Signal."
    )

    st.markdown("**Q48–Q52 completion checks**")
    questions_html = static_table_html(questions, height=360)
    if questions_html:
        st.html(questions_html)
    with st.expander("26 source-dimension closure checks", expanded=False):
        dimensions_html = static_table_html(dimensions, height=620)
        if dimensions_html:
            st.html(dimensions_html)
        st.caption(
            "Một dimension chỉ đóng khi có verified evidence + source lineage, hoặc analyst chủ động đóng research gap như known unknown. Empty search result không tự đóng dimension."
        )

    if st.button("🔄 Ghi log kiểm tra Research Completion Gate", use_container_width=True, key=f"dca9_{ticker}_completion_log"):
        append_completion_log(
            ticker,
            "completion_gate_check",
            {
                "gate": gate,
                "closed_dimensions": snap["closed_dimensions"],
                "review_dimensions": snap["review_dimensions"],
                "open_dimensions": snap["open_dimensions"],
                "blocked_dimensions": snap["blocked_dimensions"],
                "ready_questions": snap["ready_questions"],
            },
        )
        st.success("Đã ghi diagnostic log Phase 9G vào data_cache/logs/deep_company_analysis_chapter9.log.")


def _render_snapshot_history(ticker: str) -> None:
    snapshots = pd.DataFrame(list_snapshots(ticker, 20))
    if snapshots.empty:
        return
    st.markdown("### Snapshot History")
    render_static_table(snapshots, height=300, sort_key=f"dca9_{ticker}_snapshots")
    ids = [int(value) for value in snapshots["id"].tolist()]
    selected_id = st.selectbox(
        "Preview snapshot (read-only)",
        ids,
        key=f"dca9_{ticker}_snapshot_preview_id",
    )
    snapshot_payload = load_snapshot(selected_id)
    if isinstance(snapshot_payload, dict):
        snap = workspace_snapshot(snapshot_payload)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Answered", f"{snap['answered']}/{snap['question_count']}")
        c2.metric("Partial", snap["partial"])
        c3.metric("Promoted evidence", snap["promoted_evidence"])
        c4.metric("Open gaps", snap["open_research_gaps"])
        st.caption("Preview only — snapshot không tự restore/ghi đè current workspace.")


def render_chapter9_tab(default_ticker: str = "DGC") -> None:
    ticker = _safe_ticker(
        st.text_input(
            "Mã cổ phiếu",
            value=_safe_ticker(default_ticker) or "DGC",
            key="dca_ch9_ticker",
        )
    ) or "DGC"
    payload = load_record(ticker)
    payload["ticker"] = ticker
    chapter7_payload = load_chapter7_record(ticker)

    st.title("🧠 Chương 9 — Phẩm chất tích cực & tiêu cực của Ban điều hành")
    st.caption(
        "Assessing the Quality of Management—Positive and Negative Traits | Q48–Q52 | Phase 9A–9J"
    )
    _render_source_lock()

    payload["company_name"] = st.text_input(
        "Tên doanh nghiệp",
        value=str(payload.get("company_name") or chapter7_payload.get("company_name") or ""),
        key=f"dca9_{ticker}_company_name",
    )
    company_name = str(payload.get("company_name") or "")

    _render_research_summary(payload)
    with st.container(border=True):
        _render_manager_context(chapter7_payload, ticker)
    with st.container(border=True):
        payload = _render_research(ticker, company_name, chapter7_payload, payload)
    with st.container(border=True):
        _render_question_status(ticker, payload)
    with st.container(border=True):
        _render_source_locked_tables(ticker, payload)
    with st.container(border=True):
        _render_evidence_gaps_events(ticker, payload)
    with st.container(border=True):
        _render_completion_gate(ticker, payload, chapter7_payload)

    warnings = ch9.research_gap_warnings(payload)
    if warnings:
        st.warning("Research completeness:\n\n- " + "\n- ".join(warnings))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Lưu Chapter 9 workspace", use_container_width=True, key=f"dca9_{ticker}_save"):
            save_record(ticker, payload, company_name)
            append_completion_log(ticker, "workspace_save", completion_snapshot(payload, chapter7_payload))
            st.success("Đã lưu Chapter 9. Research Assistant không ghi đè Analyst Assessment.")
    with c2:
        if st.button("📸 Lưu snapshot Chapter 9", use_container_width=True, key=f"dca9_{ticker}_snapshot"):
            snapshot_id = create_snapshot(ticker, payload)
            append_completion_log(ticker, "snapshot_save", {"snapshot_id": snapshot_id})
            st.success(f"Đã lưu snapshot #{snapshot_id}.")

    with st.container(border=True):
        render_management_synthesis_workspace(ticker, company_name)

    _render_snapshot_history(ticker)


__all__ = ["render_chapter9_tab"]
