from __future__ import annotations

"""Streamlit UI for Phase 9J analyst-owned Chapters 7–9 management synthesis."""

from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter7 import load_record as load_chapter7_record
from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record
from modules.deep_company_analysis.chapter9_store import load_record as load_chapter9_record
from modules.deep_company_analysis.chapter9_synthesis import build_management_handoff
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


def render_management_synthesis_workspace(ticker: str, company_name: str = "") -> None:
    """Render synthesis against saved Chapter 7–9 records only.

    Using saved source records avoids capturing a baseline against unsaved in-memory edits from the
    Chapter 9 page. The analyst can save Chapter 9 first, then save/finalize the synthesis.
    """
    chapter7_payload = load_chapter7_record(ticker)
    chapter8_payload = load_chapter8_record(ticker, company_name)
    chapter9_payload = load_chapter9_record(ticker, company_name)
    handoff = build_management_handoff(chapter7_payload, chapter8_payload, chapter9_payload)
    workspace = load_workspace(ticker, company_name)
    drift = source_drift_status(workspace, handoff)
    summary = synthesis_workspace_summary(workspace, handoff)

    st.markdown("### Phase 9J — Analyst-Owned Management Synthesis Workspace")
    st.caption(SYNTHESIS_WORKSPACE_BOUNDARY)
    st.caption(
        "Nguồn dùng để tổng hợp là các Chapter 7–9 workspace đã lưu. Nếu vừa sửa Q33–Q52, hãy lưu chapter tương ứng trước khi chấp nhận baseline mới."
    )

    with st.expander("📖 Giải thích Phase 9J", expanded=False):
        st.markdown(
            """
- **Management Synthesis:** kết luận tổng hợp do analyst tự viết sau khi đọc Chapters 7–9; AI không tự soạn ô kết luận cuối.
- **Source Fingerprint:** mã băm của Q33–Q52 question ledger, manager roster, evidence, research gaps, chapter readiness và manager-lineage warnings.
- **Source Drift:** báo rằng nghiên cứu nền đã thay đổi kể từ lần lưu synthesis gần nhất. App chỉ cảnh báo, không tự sửa hoặc hạ trạng thái kết luận.
- **Snapshot:** bản chụp bất biến của synthesis và source baseline tại thời điểm analyst lưu.
- **Finalized:** trạng thái do analyst chọn. Source drift sau đó không tự đổi Finalized thành Draft; analyst phải review và quyết định.
            """
        )

    if drift["status"].startswith("Changed"):
        changed = ", ".join(drift["changed_sections"]) or "source package"
        st.warning(f"🟡 {drift['status']} | thay đổi: {changed}")
    elif drift["status"].startswith("Unchanged"):
        st.success(f"🟢 {drift['status']}")
    else:
        st.info(f"🔵 {drift['status']}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Workspace", summary["workspace_status"])
    c2.metric("Analyst confidence", summary["analyst_confidence"])
    c3.metric("Text sections", f"{summary['completed_text_sections']}/{summary['total_text_sections']}")
    c4.metric("Evidence rows", int(handoff.get("evidence_rows") or 0))
    c5.metric("Open research gaps", int(handoff.get("research_gaps_open") or 0))
    st.caption(f"Current research handoff: {handoff.get('handoff_state', '')}")

    with st.expander("Read-only source handoff used by Phase 9J", expanded=False):
        st.markdown("**Chapter readiness**")
        _render_table(handoff["chapter_readiness"], 300)
        st.markdown("**Q33–Q52 analyst-owned question ledger**")
        _render_table(handoff["question_ledger"], 520)
        if not handoff["lineage_warning_table"].empty:
            st.markdown("**Manager lineage warnings**")
            _render_table(handoff["lineage_warning_table"], 320)

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

    b1, b2 = st.columns(2)
    with b1:
        if st.button("💾 Lưu Management Synthesis + source baseline", use_container_width=True, key=f"dca9j_{ticker}_save"):
            captured = capture_source_baseline(workspace, handoff, mark_reviewed=True)
            save_workspace(ticker, captured, company_name)
            st.success("Đã lưu synthesis và baseline Q33–Q52 hiện tại. Không thay đổi bất kỳ source chapter hay investment conclusion nào.")
    with b2:
        if st.button("📸 Lưu snapshot Management Synthesis", use_container_width=True, key=f"dca9j_{ticker}_snapshot"):
            captured = capture_source_baseline(workspace, handoff, mark_reviewed=True)
            snapshot_id = create_snapshot(ticker, captured)
            st.success(f"Đã lưu immutable synthesis snapshot #{snapshot_id}.")

    snapshots = pd.DataFrame(list_snapshots(ticker, 20))
    if snapshots.empty:
        return
    st.markdown("**Management Synthesis Snapshot History**")
    _render_table(snapshots, 300)
    ids = [int(value) for value in snapshots["id"].tolist()]
    snapshot_id = st.selectbox("Preview synthesis snapshot (read-only)", ids, key=f"dca9j_{ticker}_preview")
    snapshot = load_snapshot(snapshot_id)
    if isinstance(snapshot, dict):
        snapshot_drift = source_drift_status(snapshot, handoff)
        p1, p2, p3 = st.columns(3)
        p1.metric("Snapshot status", snapshot.get("workspace_status") or "Draft")
        p2.metric("Confidence", snapshot.get("analyst_confidence") or "Unknown")
        p3.metric("Vs current source", "Changed" if snapshot_drift["changed"] else "Current")
        st.caption(
            f"Snapshot source freshness: {snapshot_drift['status']}. Preview không restore/ghi đè current synthesis."
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
            }
        ])
        _render_table(preview, 360)


__all__ = ["render_management_synthesis_workspace"]
