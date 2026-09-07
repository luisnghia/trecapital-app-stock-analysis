from __future__ import annotations

"""Streamlit UI for analyst-owned Chapters 7–9 management synthesis, re-review and history."""

from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter7 import load_record as load_chapter7_record
from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record
from modules.deep_company_analysis.chapter9_completion import append_completion_log
from modules.deep_company_analysis.chapter9_store import load_record as load_chapter9_record
from modules.deep_company_analysis.chapter9_synthesis import build_management_handoff
from modules.deep_company_analysis.chapter9_synthesis_history import (
    SYNTHESIS_HISTORY_BOUNDARY,
    build_version_lineage,
    compare_synthesis_versions,
    synthesis_history_summary,
)
from modules.deep_company_analysis.chapter9_synthesis_review import (
    accept_current_source_after_re_review,
    build_re_review_checklist,
    build_source_review_state,
)
from modules.deep_company_analysis.chapter9_synthesis_store import (
    create_snapshot,
    list_snapshots,
    load_snapshot,
    load_workspace,
    save_workspace,
)
from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    ANALYST_CONFIDENCE_OPTIONS,
    SYNTHESIS_WORKSPACE_BOUNDARY,
    WORKSPACE_STATUS_OPTIONS,
    capture_source_baseline,
    source_drift_status,
    synthesis_workspace_summary,
)
from modules.deep_company_analysis.table_format import static_table_html


def _render_table(frame: pd.DataFrame, height: int = 360) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.caption("Chưa có dữ liệu.")
        return
    html = static_table_html(frame, height=height)
    if html:
        st.html(html)


def _select(label: str, value: Any, options: tuple[str, ...], key: str) -> str:
    choices = list(options)
    current = str(value or choices[0])
    return str(st.selectbox(label, choices, index=choices.index(current) if current in choices else 0, key=key))


def _snapshot_records(snapshot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in snapshot_rows:
        try:
            snapshot_id = int(row.get("id"))
        except Exception:
            continue
        payload = load_snapshot(snapshot_id)
        if not isinstance(payload, dict):
            continue
        records.append(
            {
                "snapshot_id": snapshot_id,
                "created_at": row.get("created_at", ""),
                "schema_version": row.get("schema_version", payload.get("schema_version", "")),
                "payload": payload,
            }
        )
    return records


def _render_synthesis_history(
    ticker: str,
    current_saved_workspace: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
) -> None:
    records = _snapshot_records(snapshot_rows)
    if not records:
        return

    st.markdown("#### Phase 9L — Analyst Synthesis History & Delta Review")
    st.caption(SYNTHESIS_HISTORY_BOUNDARY)
    with st.expander("📖 Giải thích Phase 9L", expanded=False):
        st.markdown(
            """
- **Version Lineage:** chuỗi các immutable Management Synthesis snapshot đã lưu theo thời gian.
- **Snapshot:** bản chụp bất biến; Phase 9L chỉ đọc để so sánh, không restore hay ghi đè current workspace.
- **Delta:** thay đổi cấu trúc giữa hai phiên bản analyst-owned: `Added`, `Removed`, `Changed`, `Unchanged`.
- **Source Baseline:** fingerprint Q33–Q52 đã được lưu trong chính phiên bản đó. Phase 9L không dùng dữ liệu hôm nay để dựng lại source freshness trong quá khứ.
- **Re-review Lineage:** thời điểm, memo và source sections của lần analyst explicit re-review đã được lưu trong từng version.
- **Changed không có nghĩa management tốt lên/xấu đi:** đây chỉ là thay đổi của hồ sơ/kết luận analyst theo thời gian.
            """
        )

    lineage = build_version_lineage(records)
    st.markdown("**Immutable Management Synthesis Version Lineage**")
    _render_table(lineage, 420)

    ids = [int(record["snapshot_id"]) for record in records]
    left_col, right_col = st.columns(2)
    with left_col:
        before_id = int(
            st.selectbox(
                "Before version",
                ids,
                format_func=lambda value: f"Snapshot #{value}",
                key=f"dca9l_{ticker}_before",
            )
        )
    after_options = ["Current saved workspace"] + [f"Snapshot #{value}" for value in ids]
    with right_col:
        after_choice = str(
            st.selectbox(
                "After version",
                after_options,
                key=f"dca9l_{ticker}_after",
            )
        )

    before_payload = load_snapshot(before_id) or {}
    before_label = f"Snapshot #{before_id}"
    if after_choice == "Current saved workspace":
        after_payload = current_saved_workspace
        after_label = "Current saved workspace"
    else:
        try:
            after_id = int(after_choice.split("#", 1)[1])
        except Exception:
            after_id = before_id
        after_payload = load_snapshot(after_id) or {}
        after_label = f"Snapshot #{after_id}"

    delta = compare_synthesis_versions(
        before_payload,
        after_payload,
        before_label=before_label,
        after_label=after_label,
    )
    history = synthesis_history_summary(before_payload, after_payload)

    if history["changed_fields"]:
        st.warning(
            f"🟡 {history['changed_fields']}/{history['tracked_fields']} tracked fields changed between the selected versions. This is a record delta, not a management-quality judgment."
        )
    else:
        st.success("🟢 Không có thay đổi trong các tracked analyst-synthesis fields giữa hai version đã chọn.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Changed fields", history["changed_fields"])
    m2.metric("Added", history["added_fields"])
    m3.metric("Removed", history["removed_fields"])
    m4.metric("Modified", history["modified_fields"])
    m5.metric("Source baseline", "Changed" if history["source_baseline_changed"] else "Unchanged")

    changed_only = st.checkbox(
        "Chỉ hiển thị fields có thay đổi",
        value=True,
        key=f"dca9l_{ticker}_changed_only",
    )
    display_delta = delta[delta["Delta"] != "Unchanged"].reset_index(drop=True) if changed_only else delta
    st.markdown("**Analyst Synthesis Field Delta**")
    _render_table(display_delta, 520)
    if changed_only and display_delta.empty:
        st.caption("Không có field thay đổi; bỏ chọn bộ lọc để xem toàn bộ tracked fields.")

    st.caption(
        "Historical source freshness is not reconstructed. Phase 9L displays only the baseline fingerprint/re-review metadata actually stored in each version."
    )
    if st.button(
        "🧾 Ghi log Synthesis Delta Review",
        use_container_width=True,
        key=f"dca9l_{ticker}_log_delta",
    ):
        append_completion_log(
            ticker,
            "phase9l_synthesis_delta_view",
            {
                "before": before_label,
                "after": after_label,
                "changed_fields": history["changed_fields"],
                "source_baseline_changed": history["source_baseline_changed"],
                "status_changed": history["status_changed"],
                "confidence_changed": history["confidence_changed"],
                "final_synthesis_changed": history["final_synthesis_changed"],
            },
        )
        st.success("Đã ghi log Phase 9L delta review. Không thay đổi workspace, snapshot hoặc investment conclusion.")


def render_management_synthesis_workspace(ticker: str, company_name: str = "") -> None:
    """Render synthesis against saved Chapter 7–9 records only.

    Phase 9K deliberately separates ordinary synthesis saving from accepting a changed source
    baseline. Phase 9L adds a read-only comparison of immutable synthesis versions; it never
    restores/overwrites a workspace or interprets a text delta as management quality.
    """
    chapter7_payload = load_chapter7_record(ticker)
    chapter8_payload = load_chapter8_record(ticker, company_name)
    chapter9_payload = load_chapter9_record(ticker, company_name)
    handoff = build_management_handoff(chapter7_payload, chapter8_payload, chapter9_payload)
    workspace = load_workspace(ticker, company_name)
    drift = source_drift_status(workspace, handoff)
    review_state = build_source_review_state(workspace, handoff)
    summary = synthesis_workspace_summary(workspace, handoff)

    st.markdown("### Phase 9J–9L — Analyst-Owned Management Synthesis + Re-review + History")
    st.caption(SYNTHESIS_WORKSPACE_BOUNDARY)
    st.caption(
        "Nguồn dùng để tổng hợp là các Chapter 7–9 workspace đã lưu. Nếu vừa sửa Q33–Q52, hãy lưu chapter tương ứng trước. Khi source drift xuất hiện, nút Save bình thường KHÔNG tự chấp nhận baseline mới."
    )

    with st.expander("📖 Giải thích Phase 9J–9K", expanded=False):
        st.markdown(
            """
- **Management Synthesis:** kết luận tổng hợp do analyst tự viết sau khi đọc Chapters 7–9; AI không tự soạn ô kết luận cuối.
- **Source Fingerprint:** mã băm của Q33–Q52 question ledger, manager roster, evidence, research gaps, chapter readiness và manager-lineage warnings.
- **Source Drift:** báo rằng nghiên cứu nền đã thay đổi kể từ baseline analyst đã duyệt gần nhất.
- **Needs Re-review:** kết luận đang được hiển thị nhưng nguồn nền đã thay đổi; app không tự sửa, hạ trạng thái hoặc vô hiệu hóa kết luận.
- **Explicit Re-review:** analyst xem checklist phần thay đổi, ghi review memo, tick xác nhận và chủ động chấp nhận Q33–Q52 hiện tại làm baseline mới.
- **Snapshot:** bản chụp bất biến. Snapshot không tự chấp nhận source drift.
            """
        )

    if review_state["report_label"] == "Needs Re-review":
        changed = ", ".join(review_state["changed_sections"]) or "source package"
        st.warning(f"🟡 {review_state['state']} | thay đổi: {changed}")
    elif review_state["report_label"] == "Current":
        st.success(f"🟢 {review_state['state']}")
    else:
        st.info(f"🔵 {review_state['state']}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Workspace", summary["workspace_status"])
    c2.metric("Analyst confidence", summary["analyst_confidence"])
    c3.metric("Source freshness", review_state["report_label"])
    c4.metric("Evidence rows", int(handoff.get("evidence_rows") or 0))
    c5.metric("Open research gaps", int(handoff.get("research_gaps_open") or 0))
    st.caption(f"Current research handoff: {handoff.get('handoff_state', '')}")

    with st.expander("Read-only source handoff used by synthesis", expanded=False):
        st.markdown("**Chapter readiness**")
        _render_table(handoff["chapter_readiness"], 300)
        st.markdown("**Q33–Q52 analyst-owned question ledger**")
        _render_table(handoff["question_ledger"], 520)
        if not handoff["lineage_warning_table"].empty:
            st.markdown("**Manager lineage warnings**")
            _render_table(handoff["lineage_warning_table"], 320)

    if review_state["needs_re_review"]:
        st.markdown("#### Phase 9K — Source Re-review Checklist")
        st.caption(
            "Changed chỉ có nghĩa source package thay đổi. Analyst phải xem dữ liệu nền; app không suy luận management tốt/xấu từ thay đổi này."
        )
        _render_table(build_re_review_checklist(workspace, handoff), 420)

    c1, c2 = st.columns(2)
    with c1:
        workspace["workspace_status"] = _select(
            "Synthesis status",
            workspace.get("workspace_status"),
            WORKSPACE_STATUS_OPTIONS,
            f"dca9j_{ticker}_status",
        )
    with c2:
        workspace["analyst_confidence"] = _select(
            "Analyst confidence",
            workspace.get("analyst_confidence"),
            ANALYST_CONFIDENCE_OPTIONS,
            f"dca9j_{ticker}_confidence",
        )

    workspace["chapter7_background_takeaway"] = st.text_area(
        "Chapter 7 — Background / Classification Takeaway",
        value=str(workspace.get("chapter7_background_takeaway") or ""),
        key=f"dca9j_{ticker}_ch7_takeaway",
        help="Analyst viết; app không tự copy/biến classification thành điểm số.",
    )
    workspace["chapter8_operating_takeaway"] = st.text_area(
        "Chapter 8 — Operating Competence Takeaway",
        value=str(workspace.get("chapter8_operating_takeaway") or ""),
        key=f"dca9j_{ticker}_ch8_takeaway",
    )
    workspace["chapter9_traits_takeaway"] = st.text_area(
        "Chapter 9 — Positive / Negative Traits Takeaway",
        value=str(workspace.get("chapter9_traits_takeaway") or ""),
        key=f"dca9j_{ticker}_ch9_takeaway",
    )
    workspace["management_strengths"] = st.text_area(
        "Management strengths — analyst synthesis",
        value=str(workspace.get("management_strengths") or ""),
        key=f"dca9j_{ticker}_strengths",
    )
    workspace["management_concerns"] = st.text_area(
        "Management concerns — analyst synthesis",
        value=str(workspace.get("management_concerns") or ""),
        key=f"dca9j_{ticker}_concerns",
    )
    workspace["management_unknowns"] = st.text_area(
        "Material management unknowns",
        value=str(workspace.get("management_unknowns") or ""),
        key=f"dca9j_{ticker}_unknowns",
    )
    workspace["evidence_that_would_change_view"] = st.text_area(
        "Evidence that would change my management view",
        value=str(workspace.get("evidence_that_would_change_view") or ""),
        key=f"dca9j_{ticker}_change_view",
    )
    workspace["final_management_synthesis"] = st.text_area(
        "Final Analyst Management Synthesis",
        value=str(workspace.get("final_management_synthesis") or ""),
        key=f"dca9j_{ticker}_final_synthesis",
        height=180,
        help="Ô này hoàn toàn analyst-owned. Không có AI auto-write hoặc auto-score.",
    )
    workspace["analyst_note"] = st.text_area(
        "Analyst note / review memo",
        value=str(workspace.get("analyst_note") or ""),
        key=f"dca9j_{ticker}_note",
    )

    has_baseline = bool(str(workspace.get("source_fingerprint") or "").strip())
    b1, b2 = st.columns(2)
    with b1:
        save_label = "💾 Lưu Management Synthesis"
        if not has_baseline:
            save_label = "💾 Lưu Management Synthesis + baseline đầu tiên"
        elif review_state["needs_re_review"]:
            save_label = "💾 Lưu Synthesis — giữ nguyên baseline cũ"
        if st.button(save_label, use_container_width=True, key=f"dca9j_{ticker}_save"):
            to_save = workspace
            if not has_baseline:
                to_save = capture_source_baseline(workspace, handoff, mark_reviewed=True)
            save_workspace(ticker, to_save, company_name)
            append_completion_log(
                ticker,
                "phase9k_synthesis_save",
                {
                    "initial_baseline_captured": not has_baseline,
                    "source_drift_preserved": bool(has_baseline and review_state["needs_re_review"]),
                    "workspace_status": workspace.get("workspace_status"),
                },
            )
            if has_baseline and review_state["needs_re_review"]:
                st.success("Đã lưu nội dung analyst nhưng GIỮ baseline cũ. Source vẫn ở trạng thái Needs Re-review cho đến khi analyst xác nhận riêng.")
            else:
                st.success("Đã lưu Management Synthesis. Không thay đổi source chapter hay investment conclusion.")
    with b2:
        if st.button("📸 Lưu snapshot Management Synthesis", use_container_width=True, key=f"dca9j_{ticker}_snapshot"):
            snapshot_id = create_snapshot(ticker, workspace)
            append_completion_log(ticker, "phase9k_synthesis_snapshot", {"snapshot_id": snapshot_id, "source_drift": review_state["needs_re_review"]})
            st.success(f"Đã lưu immutable synthesis snapshot #{snapshot_id}. Snapshot không tự chấp nhận source drift.")

    if review_state["needs_re_review"]:
        with st.container(border=True):
            st.markdown("#### ✅ Explicit Re-review Acceptance")
            re_review_note = st.text_area(
                "Re-review memo — nêu phần đã kiểm tra và lý do chấp nhận baseline mới",
                value="",
                key=f"dca9k_{ticker}_rereview_note",
            )
            confirmed = st.checkbox(
                "Tôi xác nhận đã rà soát các source section thay đổi và chấp nhận Q33–Q52 hiện tại làm baseline mới.",
                value=False,
                key=f"dca9k_{ticker}_rereview_confirm",
            )
            if st.button(
                "✅ Xác nhận Re-review & chấp nhận baseline mới",
                use_container_width=True,
                disabled=not confirmed,
                key=f"dca9k_{ticker}_rereview_accept",
            ):
                accepted = accept_current_source_after_re_review(
                    workspace,
                    handoff,
                    analyst_review_note=re_review_note,
                )
                save_workspace(ticker, accepted, company_name)
                snapshot_id = create_snapshot(ticker, accepted)
                append_completion_log(
                    ticker,
                    "phase9k_source_rereview_accept",
                    {
                        "changed_sections": review_state["changed_sections"],
                        "snapshot_id": snapshot_id,
                        "workspace_status_preserved": accepted.get("workspace_status"),
                    },
                )
                st.success(
                    f"Đã chấp nhận baseline mới sau re-review và lưu audit snapshot #{snapshot_id}. Workspace status, confidence và analyst text được giữ nguyên."
                )

    if workspace.get("last_re_review_at"):
        st.caption(
            f"Last explicit re-review: {workspace.get('last_re_review_at')} | sections: {', '.join(workspace.get('last_re_review_sections') or []) or 'none'} | note: {workspace.get('last_re_review_note') or ''}"
        )

    snapshot_rows = list_snapshots(ticker, 50)
    snapshots = pd.DataFrame(snapshot_rows)
    if snapshots.empty:
        return
    st.markdown("**Management Synthesis Snapshot History**")
    _render_table(snapshots, 300)
    ids = [int(value) for value in snapshots["id"].tolist()]
    snapshot_id = st.selectbox("Preview synthesis snapshot (read-only)", ids, key=f"dca9j_{ticker}_preview")
    snapshot = load_snapshot(snapshot_id)
    if isinstance(snapshot, dict):
        snapshot_review = build_source_review_state(snapshot, handoff)
        p1, p2, p3 = st.columns(3)
        p1.metric("Snapshot status", snapshot.get("workspace_status") or "Draft")
        p2.metric("Confidence", snapshot.get("analyst_confidence") or "Unknown")
        p3.metric("Vs current source", snapshot_review["report_label"])
        st.caption(
            f"Snapshot source freshness: {snapshot_review['state']}. Preview không restore/ghi đè current synthesis."
        )
        preview = pd.DataFrame([
            {
                "Final Analyst Management Synthesis": snapshot.get("final_management_synthesis", ""),
                "Management Strengths": snapshot.get("management_strengths", ""),
                "Management Concerns": snapshot.get("management_concerns", ""),
                "Management Unknowns": snapshot.get("management_unknowns", ""),
                "Evidence That Would Change View": snapshot.get("evidence_that_would_change_view", ""),
                "Source Captured At": snapshot.get("source_captured_at", ""),
                "Analyst Reviewed At": snapshot.get("analyst_reviewed_at", ""),
                "Last Re-review At": snapshot.get("last_re_review_at", ""),
                "Last Re-review Note": snapshot.get("last_re_review_note", ""),
            }
        ])
        _render_table(preview, 380)

    current_saved_workspace = load_workspace(ticker, company_name)
    _render_synthesis_history(ticker, current_saved_workspace, snapshot_rows)


__all__ = ["render_management_synthesis_workspace"]
