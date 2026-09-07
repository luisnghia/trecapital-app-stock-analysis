from __future__ import annotations

"""Phase 9K read-only consolidated-report renderer for saved analyst management synthesis."""

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter9_synthesis_review import (
    build_re_review_checklist,
    build_source_review_state,
)
from modules.deep_company_analysis.chapter9_synthesis_store import load_workspace
from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    SYNTHESIS_WORKSPACE_BOUNDARY,
    build_synthesis_report_frame,
)
from modules.deep_company_analysis.table_format import static_table_html


def _render_table(frame: pd.DataFrame, height: int) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.caption("Chưa có dữ liệu.")
        return
    html = static_table_html(frame, height=height)
    if html:
        st.html(html)


def render_saved_management_synthesis_report(
    ticker: str,
    company_name: str,
    handoff: dict,
) -> None:
    """Render saved analyst synthesis and freshness state; never writes or re-baselines data."""
    workspace = load_workspace(ticker, company_name)
    review = build_source_review_state(workspace, handoff)
    report_frame = build_synthesis_report_frame(workspace, handoff)

    st.markdown("## ✍️ Final Analyst Management Synthesis — Chapters 7–9")
    st.caption(SYNTHESIS_WORKSPACE_BOUNDARY)

    if review["report_label"] == "Needs Re-review":
        st.warning(
            "🟡 Needs Re-review — kết luận analyst vẫn được giữ nguyên nhưng Q33–Q52 source research đã thay đổi kể từ baseline được analyst duyệt gần nhất."
        )
    elif review["report_label"] == "Current":
        st.success("🟢 Current — saved analyst synthesis đang khớp baseline Q33–Q52 đã được analyst duyệt.")
    else:
        st.info("🔵 No baseline — Management Synthesis chưa có baseline Q33–Q52 đã được analyst duyệt.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Synthesis status", workspace.get("workspace_status") or "Draft")
    c2.metric("Analyst confidence", workspace.get("analyst_confidence") or "Unknown")
    c3.metric("Source freshness", review["report_label"])
    c4.metric("Changed source sections", len(review["changed_sections"]) if review["needs_re_review"] else 0)

    if not str(workspace.get("final_management_synthesis") or "").strip():
        st.info("Analyst chưa nhập Final Analyst Management Synthesis. Báo cáo không tự sinh kết luận thay thế.")

    _render_table(report_frame, 560)

    if review["needs_re_review"]:
        st.markdown("### ⚠ Source Re-review Required")
        _render_table(build_re_review_checklist(workspace, handoff), 420)
        st.caption(
            "Để cập nhật trạng thái về Current, analyst phải vào Chapter 9 → Phase 9K, tự rà soát các source section thay đổi và bấm xác nhận Re-review. Báo cáo này read-only và không tự chấp nhận baseline mới."
        )

    if workspace.get("last_re_review_at"):
        st.caption(
            f"Last explicit re-review: {workspace.get('last_re_review_at')} | note: {workspace.get('last_re_review_note') or ''}"
        )
    st.caption(
        "Source freshness chỉ phản ánh việc baseline nghiên cứu còn khớp hay cần rà soát lại; không phải Management Quality Score, không thay MOS, investment Research Gate hoặc BUY/HOLD/SELL."
    )


__all__ = ["render_saved_management_synthesis_report"]
