from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter7 import create_snapshot, save_record
from modules.deep_company_analysis.chapter7_closure import (
    CLOSURE_BOUNDARY,
    FINAL_CHECKLIST_COLUMNS,
    FINAL_CHECKLIST_STATUS_OPTIONS,
    RESIDUAL_UNKNOWN_COLUMNS,
    RESIDUAL_UNKNOWN_STATUS_OPTIONS,
    career_coverage_audit,
    chapter7_completion_status,
    compensation_ownership_reconciliation,
    default_final_checklist_rows,
    insider_context_audit,
    source_coverage_matrix,
)
from modules.deep_company_analysis.chapter7_data_bridge import (
    list_conflicts,
    list_review_queue,
    list_sources,
    resolve_conflict,
    resolve_review_item,
)
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.where(pd.notna(value), None).to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _editable_table(
    rows: Any,
    columns: list[str],
    *,
    key: str,
    height: int,
    column_config: dict[str, Any] | None = None,
    disabled: list[str] | None = None,
) -> list[dict[str, Any]]:
    frame = pd.DataFrame(_records(rows))
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[columns]
    edited = sortable_data_editor(
        frame,
        key=key,
        hide_index=True,
        use_container_width=True,
        height=height,
        num_rows="dynamic",
        column_config=column_config or {},
        disabled=disabled or [],
    )
    return edited.where(pd.notna(edited), None).to_dict("records") if isinstance(edited, pd.DataFrame) else frame.to_dict("records")


def _lion_dimension_audit(payload: dict[str, Any]) -> pd.DataFrame:
    rows = _records(payload.get("lion_hyena_matrix"))
    out: list[dict[str, Any]] = []
    for row in rows:
        lion = str(row.get("Lion Evidence") or "").strip()
        hyena = str(row.get("Hyena Evidence") or "").strip()
        direction = str(row.get("Evidence Direction") or "Unknown")
        source = str(row.get("Source") or "").strip()
        out.append(
            {
                "Dimension": row.get("Dimension"),
                "Lion Evidence?": "Yes" if lion else "No",
                "Hyena Evidence?": "Yes" if hyena else "No",
                "Direction": direction,
                "Source?": "Yes" if source else "No",
                "Closure": "Reviewed" if direction != "Unknown" or lion or hyena else "Unknown — analyst resolve/accept",
            }
        )
    return pd.DataFrame(out)


def _q33_q34_summary(payload: dict[str, Any]) -> pd.DataFrame:
    q33 = payload.get("q33") or {}
    q34 = payload.get("q34") or {}
    profiles = _records(payload.get("management_profiles"))
    transitions = _records(payload.get("outside_transitions"))
    return pd.DataFrame(
        [
            {
                "Question": "Q33",
                "Research Status": (payload.get("question_status") or {}).get("Q33", "Unknown"),
                "Analyst Classification": q33.get("analyst_classification", "Unknown"),
                "Rows / Evidence Context": len(profiles),
                "Analyst Conclusion": q33.get("conclusion", ""),
                "Boundary": "Founder ≠ automatic OO1; outsider ≠ automatic negative",
            },
            {
                "Question": "Q34",
                "Research Status": (payload.get("question_status") or {}).get("Q34", "Unknown"),
                "Analyst Classification": q34.get("overall_assessment", "Unknown"),
                "Rows / Evidence Context": len(transitions),
                "Analyst Conclusion": q34.get("conclusion", ""),
                "Boundary": "Learn-before-change is evidence, not a mechanical score",
            },
        ]
    )


def _normalize_residual_acceptance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        status = str(item.get("Status") or "Open")
        accepted = bool(item.get("Accepted By Analyst"))
        if status == "Accepted Residual Unknown" and accepted and not str(item.get("Accepted At") or "").strip():
            item["Accepted At"] = _now()
        if status != "Accepted Residual Unknown" and status not in {"Resolved", "N/A"}:
            item["Accepted By Analyst"] = False
            if status == "Open":
                item["Accepted At"] = ""
        out.append(item)
    return out


def render_chapter7_final_closure(ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
    safe = str(ticker or "").upper().strip()
    open_conflicts = list_conflicts(safe, "Needs analyst review")
    open_reviews = list_review_queue(safe, "Open")

    st.markdown("## 🔒 Phase 7D — Chapter 7 Final Source Closure & Completion Gate")
    st.caption(CLOSURE_BOUNDARY)
    st.info(
        "Completion = research/source completeness only. A manager can have serious concerns and Chapter 7 can still be Complete if the evidence, counter-evidence, residual unknowns and analyst conclusion have been fully reviewed."
    )

    with st.expander("Source Coverage Overview — Q33 đến Q38", expanded=True):
        coverage = source_coverage_matrix(payload, open_conflicts)
        render_static_table(coverage, height=min(390, 110 + 32 * len(coverage)), sort_key=f"dca7d_{safe}_coverage")
        st.caption("Coverage = độ đầy đủ bằng chứng. Không phải Management Quality score và không tự thay analyst conclusion.")

    with st.expander("Q33–Q34 Closure — Classification & Outside Management", expanded=False):
        render_static_table(_q33_q34_summary(payload), height=220, sort_key=f"dca7d_{safe}_q33q34")
        st.caption("Q34 = N/A phải có analyst rationale; outsider không tự động bị đánh giá tiêu cực.")

    with st.expander("Q35 Closure — Table 7.1 Seven-Dimension Audit", expanded=True):
        lion_audit = _lion_dimension_audit(payload)
        if not lion_audit.empty:
            render_static_table(lion_audit, height=min(390, 110 + 34 * len(lion_audit)), sort_key=f"dca7d_{safe}_lion_audit")
        st.caption("Đúng 7 dimensions; không cộng điểm, không weighting, không % Lion/Hyena.")

    with st.expander("Q36 Closure — Career Coverage Audit", expanded=False):
        render_static_table(career_coverage_audit(payload), height=330, sort_key=f"dca7d_{safe}_career")
        st.caption("Potential career gap ≠ unemployment/problem. Nếu nguồn không giải thích, giữ Unknown.")

    with st.expander("Q37 Closure — Compensation & Ownership Reconciliation", expanded=False):
        render_static_table(compensation_ownership_reconciliation(payload), height=390, sort_key=f"dca7d_{safe}_comp_owner")
        st.caption("Actual Shares, Options, RSU/Restricted và ESOP/Unvested Awards tiếp tục tách riêng; aggregate compensation không được phân bổ giả.")

    with st.expander("Q38 Closure — Insider Transaction Context Audit", expanded=False):
        render_static_table(insider_context_audit(payload), height=310, sort_key=f"dca7d_{safe}_insider")
        st.caption("Registered ≠ Executed. Grant/vesting/ESOP ≠ open-market purchase. Không có conviction score hoặc Buy/Sell signal.")

    with st.expander("Chapter 7 Source-Locked Key Points Checklist — 7K01 đến 7K17", expanded=True):
        checklist = payload.get("chapter7_final_checklist") or default_final_checklist_rows()
        payload["chapter7_final_checklist"] = _editable_table(
            checklist,
            FINAL_CHECKLIST_COLUMNS,
            key=f"dca7d_{safe}_checklist",
            height=560,
            disabled=["ID", "Question", "Source-Locked Requirement"],
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=list(FINAL_CHECKLIST_STATUS_OPTIONS)),
            },
        )
        st.caption("Gate chỉ pass khi 7K01–7K17 đều Covered/N/A. Evidence weak/Unknown phải được research tiếp hoặc phản ánh bằng residual-unknown workflow phù hợp.")

    with st.expander("Residual Unknown Acceptance", expanded=True):
        st.caption(
            "Dùng khi đã research nhưng disclosure không tồn tại/không đủ. Không dùng để bỏ qua việc nghiên cứu. Accepted Residual Unknown phải là quyết định explicit của analyst."
        )
        residual = _editable_table(
            payload.get("chapter7_residual_unknowns") or [],
            RESIDUAL_UNKNOWN_COLUMNS,
            key=f"dca7d_{safe}_residual",
            height=360,
            disabled=["Accepted At"],
            column_config={
                "Question": st.column_config.SelectboxColumn("Question", options=["Q33", "Q34", "Q35", "Q36", "Q37", "Q38", "All"]),
                "Status": st.column_config.SelectboxColumn("Status", options=list(RESIDUAL_UNKNOWN_STATUS_OPTIONS)),
                "Accepted By Analyst": st.column_config.CheckboxColumn("Accepted By Analyst"),
            },
        )
        payload["chapter7_residual_unknowns"] = _normalize_residual_acceptance(residual)

    with st.expander("Source Conflicts & Management Change Review Gate", expanded=True):
        if open_conflicts:
            conflict_frame = pd.DataFrame(open_conflicts)
            visible = [c for c in ["id", "conflict_type", "record_type", "record_key", "details", "status", "created_at"] if c in conflict_frame.columns]
            render_static_table(conflict_frame[visible], height=min(360, 100 + 32 * len(conflict_frame)), sort_key=f"dca7d_{safe}_conflicts")
            selected_conflicts = st.multiselect(
                "Conflict IDs đã analyst review",
                options=[int(row["id"]) for row in open_conflicts],
                key=f"dca7d_{safe}_conflict_ids",
            )
            conflict_resolution = st.selectbox(
                "Kết quả xử lý conflict",
                ["Resolved", "Accepted residual uncertainty"],
                key=f"dca7d_{safe}_conflict_resolution",
            )
            if st.button("✓ Ghi nhận xử lý source conflict", key=f"dca7d_{safe}_resolve_conflicts", disabled=not selected_conflicts):
                for conflict_id in selected_conflicts:
                    resolve_conflict(int(conflict_id), conflict_resolution)
                st.success("Đã ghi nhận xử lý conflict. Không có analyst conclusion nào bị tự thay đổi.")
                st.rerun()
        else:
            st.success("Không còn source/data conflict ở trạng thái Needs analyst review.")

        if open_reviews:
            review_frame = pd.DataFrame(open_reviews)
            visible = [c for c in ["id", "event_date", "event_type", "manager", "questions_to_review", "reason", "status"] if c in review_frame.columns]
            render_static_table(review_frame[visible], height=min(360, 100 + 32 * len(review_frame)), sort_key=f"dca7d_{safe}_review_queue")
            selected_reviews = st.multiselect(
                "Management event review IDs đã analyst xử lý",
                options=[int(row["id"]) for row in open_reviews],
                key=f"dca7d_{safe}_review_ids",
            )
            review_resolution = st.selectbox(
                "Kết quả review",
                ["Reviewed — updated assessment", "Reviewed — confirmed unchanged"],
                key=f"dca7d_{safe}_review_resolution",
            )
            if st.button("✓ Hoàn tất management change review", key=f"dca7d_{safe}_resolve_reviews", disabled=not selected_reviews):
                for review_id in selected_reviews:
                    resolve_review_item(int(review_id), review_resolution)
                payload["chapter7_last_management_review_at"] = _now()
                payload["chapter7_last_management_review_result"] = review_resolution
                save_record(safe, payload, str(payload.get("company_name") or ""))
                st.success("Đã review management event. Previous assessment không được auto-carry-forward; analyst đã explicit chọn update/confirm unchanged.")
                st.rerun()
        else:
            st.success("Không còn management event review item ở trạng thái Open.")

    with st.expander("Final Analyst Dossier & Completion Gate", expanded=True):
        dossier = pd.DataFrame([
            {"Field": "Management Classification", "Analyst Value": payload.get("final_management_classification", "Unknown")},
            {"Field": "Execution uncertainty", "Analyst Value": payload.get("execution_uncertainty", "Unknown")},
            {"Field": "Management-business fit", "Analyst Value": payload.get("management_business_fit", "Unknown")},
            {"Field": "Compensation alignment", "Analyst Value": payload.get("compensation_alignment", "Unknown")},
            {"Field": "Ownership alignment", "Analyst Value": payload.get("ownership_alignment", "Unknown")},
            {"Field": "Insider behavior", "Analyst Value": payload.get("insider_behavior", "Unknown")},
        ])
        render_static_table(dossier, height=290, sort_key=f"dca7d_{safe}_dossier")
        payload["chapter7_completion_note"] = st.text_area(
            "Completion note / residual uncertainty accepted by analyst",
            value=str(payload.get("chapter7_completion_note") or ""),
            key=f"dca7d_{safe}_completion_note",
        )

        status = chapter7_completion_status(payload, open_conflicts=open_conflicts, open_review_items=open_reviews)
        if status["blockers"]:
            st.warning("Chapter 7 chưa thể khóa Final:\n\n- " + "\n- ".join(status["blockers"]))
        else:
            st.success("Không còn hard blocker. Analyst có thể xác nhận Chapter 7 Complete / Source-Closed.")
        for warning in status["warnings"]:
            st.info(warning)

        st.caption(f"Completion status: **{status['status']}**")
        if status["status"] == "Complete — Review Required":
            st.error("Có management/source event mới cần review. Chapter 7 không tự carry-forward kết luận cũ.")

        prior_confirmed = bool(payload.get("chapter7_complete_confirmed"))
        if status["ready"]:
            confirmed = st.checkbox(
                "✅ Analyst xác nhận Chapter 7 Complete / Source-Closed",
                value=prior_confirmed,
                key=f"dca7d_{safe}_complete_confirmed",
            )
            payload["chapter7_complete_confirmed"] = bool(confirmed)
            if confirmed and not prior_confirmed:
                payload["chapter7_completion_as_of"] = _now()
                payload["chapter7_completion_version"] = int(payload.get("chapter7_completion_version") or 0) + 1
                payload["chapter7_closure_source_snapshot"] = list_sources(safe)
                payload["chapter7_closure_conflict_snapshot"] = list_conflicts(safe, None)
                payload["chapter7_closure_review_snapshot"] = list_review_queue(safe, None)
                save_record(safe, payload, str(payload.get("company_name") or ""))
                snapshot_id = create_snapshot(safe, payload)
                st.success(f"Chapter 7 đã được analyst xác nhận Complete / Source-Closed. Snapshot #{snapshot_id} đã được khóa cho version hiện tại.")
                st.rerun()
        else:
            st.checkbox(
                "✅ Analyst xác nhận Chapter 7 Complete / Source-Closed",
                value=prior_confirmed,
                disabled=True,
                key=f"dca7d_{safe}_complete_disabled",
            )

        st.caption("Đây là Chapter 7 research/source-completion gate, KHÔNG phải Investment Research Gate và không truyền trực tiếp sang MOS, fair value, portfolio sizing hay BUY/HOLD/SELL.")

    return payload


__all__ = ["render_chapter7_final_closure"]
