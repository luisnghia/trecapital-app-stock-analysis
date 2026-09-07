from __future__ import annotations

"""Phase 9K–9L read-only consolidated-report renderer for saved analyst management synthesis."""

from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter9_synthesis_history import (
    SYNTHESIS_HISTORY_BOUNDARY,
    build_version_lineage,
    compare_synthesis_versions,
    synthesis_history_summary,
)
from modules.deep_company_analysis.chapter9_synthesis_review import (
    build_re_review_checklist,
    build_source_review_state,
)
from modules.deep_company_analysis.chapter9_synthesis_store import (
    list_snapshots,
    load_snapshot,
    load_workspace,
)
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


def _render_version_lineage(ticker: str, workspace: dict[str, Any]) -> None:
    snapshot_rows = list_snapshots(ticker, 50)
    records = _snapshot_records(snapshot_rows)
    if not records:
        st.caption("Chưa có Management Synthesis snapshot để lập version lineage.")
        return

    st.markdown("### 🕘 Phase 9L — Management Synthesis Version Lineage")
    st.caption(SYNTHESIS_HISTORY_BOUNDARY)
    st.caption(
        "Version lineage dùng metadata đã lưu trong từng immutable snapshot. Báo cáo không dựng lại historical source freshness bằng dữ liệu hiện tại."
    )
    _render_table(build_version_lineage(records), 420)

    latest = max(records, key=lambda item: int(item.get("snapshot_id") or 0))
    latest_id = int(latest["snapshot_id"])
    latest_payload = latest["payload"]
    delta = compare_synthesis_versions(
        latest_payload,
        workspace,
        before_label=f"Latest snapshot #{latest_id}",
        after_label="Current saved workspace",
    )
    summary = synthesis_history_summary(latest_payload, workspace)
    changed = delta[delta["Delta"] != "Unchanged"].reset_index(drop=True)

    if summary["changed_fields"]:
        st.warning(
            f"🟡 Current saved workspace khác latest immutable snapshot #{latest_id} tại {summary['changed_fields']} tracked fields. Đây là record delta, không phải đánh giá management tốt/xấu."
        )
        _render_table(changed, 460)
    else:
        st.success(f"🟢 Current saved workspace khớp latest immutable snapshot #{latest_id} trên toàn bộ tracked synthesis fields.")


def render_saved_management_synthesis_report(
    ticker: str,
    company_name: str,
    handoff: dict,
) -> None:
    """Render saved analyst synthesis, freshness and version lineage; never writes or re-baselines data."""
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

    _render_version_lineage(ticker, workspace)

    st.caption(
        "Source freshness và version delta chỉ phản ánh baseline/research record có thay đổi hay không; không phải Management Quality Score, không thay MOS, investment Research Gate hoặc BUY/HOLD/SELL."
    )


__all__ = ["render_saved_management_synthesis_report"]
