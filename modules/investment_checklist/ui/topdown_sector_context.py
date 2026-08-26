from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.evidence_workspace import list_latest_evidence
from ..services.topdown_sector_context import (
    list_topdown_sector_snapshots,
    save_topdown_sector_snapshot,
    snapshot_is_stale,
)


_STATUS_LABELS = {
    "unverified": "Unverified — benchmark chưa được kiểm chứng",
    "historical_source": "Historical source — có nguồn gốc nhưng không phải benchmark hiện hành",
    "analyst_verified": "Analyst verified — có exact evidence đã xác minh",
}


def _summary_table(payload: dict) -> pd.DataFrame:
    ranking_by_code = {row["sector_code"]: row for row in payload.get("ranking", [])}
    rows = []
    for weight in payload.get("weights", []):
        rank = ranking_by_code.get(weight["sector_code"], {})
        rows.append(
            {
                "Hạng": rank.get("rank"),
                "Mã ngành": weight["sector_code"],
                "Ngành": weight["sector_name"],
                "Điểm": weight["sector_score"],
                "Benchmark %": weight["benchmark_weight_pct"],
                "Đề xuất %": weight["proposed_weight_pct"],
                "Lệch điểm %": weight["tilt_pct"],
                "Tín hiệu ngành": weight["signal"],
            }
        )
    return pd.DataFrame(rows).sort_values("Hạng") if rows else pd.DataFrame()


def _render_saved(snapshots: list[dict]) -> None:
    st.markdown("##### Snapshot đã lưu trong review")
    if not snapshots:
        st.info("Review này chưa có Fisher Top-down/Sector snapshot.")
        return
    latest = snapshots[0]
    status = latest["benchmark_status"]
    cols = st.columns(5)
    cols[0].metric("Version", f"v{latest['version_no']}")
    cols[1].metric("Ngành", latest["selected_sector_code"])
    cols[2].metric("Điểm ngành", f"{latest['sector_score']:.1f}")
    cols[3].metric("Benchmark", f"{latest['benchmark_weight_pct']:.1f}%")
    cols[4].metric("Context weight", f"{latest['proposed_weight_pct']:.1f}%")
    if status != "analyst_verified":
        st.warning(
            "Benchmark của snapshot mới nhất chưa đạt analyst_verified; không được dùng tỷ trọng này như dữ liệu đã kiểm chứng."
        )
    if snapshot_is_stale(latest):
        st.warning("Snapshot mới nhất đã vượt time horizon và được xem là stale.")
    table = pd.DataFrame(
        [
            {
                "Version": row["version_no"],
                "As-of": row["as_of_date"],
                "Ngành": f"{row['selected_sector_code']} — {row['selected_sector_name']}",
                "Pha chu kỳ": row["cycle_phase"],
                "Benchmark status": row["benchmark_status"],
                "Research gaps": len(row["research_gaps"]),
                "SHA-256": row["payload_hash"][:12] + "…",
                "Hash valid": row["payload_hash_valid"],
                "Lý do": row["change_reason"],
            }
            for row in snapshots
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
    selected_id = st.selectbox(
        "Xem payload snapshot",
        [row["id"] for row in snapshots],
        format_func=lambda value: f"Snapshot #{value} · v{next(r for r in snapshots if r['id'] == value)['version_no']}",
        key="topdown_saved_snapshot_view",
    )
    with st.expander("Raw governed payload (audit)"):
        st.json(next(row for row in snapshots if row["id"] == selected_id)["payload"])


def render_topdown_sector_context(repo, company_ref_id: int, review, actor: str) -> None:
    st.markdown("### 🧭 Fisher Top-down & Sector Context — Phase 8")
    st.markdown(
        "<div class='principle'><b>Guardrail:</b> đây là bằng chứng bối cảnh ngành–vĩ mô. "
        "Module không tự ghi Q01–Q59, không thay kết luận Industry & Moat và không tạo lệnh mua/bán.</div>",
        unsafe_allow_html=True,
    )
    if not review:
        st.info("Tạo hoặc chọn review trước khi lưu sector context.")
        st.page_link("pages/06_Phan_tich_TopDown_Nganh.py", label="Mở Fisher Top-Down theo ngành", icon="🧭")
        return

    snapshots = list_topdown_sector_snapshots(repo, int(review["id"]))
    _render_saved(snapshots)
    st.divider()
    payload = st.session_state.get("topdown_governed_snapshot_payload")
    if not payload:
        st.info(
            "Chưa có kết quả Top-down trong phiên này. Mở page Fisher Top-Down, rà driver/benchmark rồi quay lại Checklist."
        )
        st.page_link("pages/06_Phan_tich_TopDown_Nganh.py", label="Mở Fisher Top-Down theo ngành", icon="🧭")
        return

    st.markdown("##### Kết quả đang chờ analyst xác nhận")
    benchmark = payload.get("benchmark", {})
    cols = st.columns(4)
    cols[0].metric("Methodology", payload.get("methodology_version", "—"))
    cols[1].metric("Pha chu kỳ", payload.get("cycle_phase", "—"))
    cols[2].metric("Benchmark", benchmark.get("id", "—"))
    cols[3].metric("Số ngành", len(payload.get("ranking", [])))
    if benchmark.get("requires_update"):
        st.error(
            "Benchmark đang là giá trị khởi tạo. Snapshot vẫn có thể lưu để audit, nhưng phải giữ Unverified cho đến khi gắn exact evidence."
        )
    st.dataframe(_summary_table(payload), use_container_width=True, hide_index=True)

    disabled = review.get("status") == "completed"
    if disabled:
        st.warning("Review đã completed: workspace Phase 8 chỉ đọc.")
        return

    ranking = payload.get("ranking", [])
    codes = [row["sector_code"] for row in ranking]
    labels = {row["sector_code"]: row["sector_name"] for row in ranking}
    with st.form(f"save_topdown_sector_{review['id']}"):
        selected_sector_code = st.selectbox(
            "Ngành gán cho doanh nghiệp *",
            codes,
            format_func=lambda code: f"{code} — {labels.get(code, code)}",
        )
        c1, c2 = st.columns(2)
        as_of = c1.date_input("As-of date *", value=date.fromisoformat(str(review["as_of_date"])[:10]))
        horizon_months = c2.number_input("Time horizon (tháng) *", min_value=1, max_value=36, value=12)
        default_status = "unverified" if benchmark.get("requires_update", True) else "historical_source"
        benchmark_status = st.selectbox(
            "Trạng thái benchmark *",
            list(_STATUS_LABELS),
            index=list(_STATUS_LABELS).index(default_status),
            format_func=lambda value: _STATUS_LABELS[value],
        )
        evidence_id = None
        if benchmark_status == "analyst_verified":
            evidence = [
                row
                for row in list_latest_evidence(repo, company_ref_id)
                if row.get("verification_status") == "verified"
            ]
            if evidence:
                evidence_id = st.selectbox(
                    "Exact benchmark evidence *",
                    [row["id"] for row in evidence],
                    format_func=lambda value: (
                        f"Evidence #{value} — "
                        f"{next(row for row in evidence if row['id'] == value)['source_title']}"
                    ),
                )
            else:
                st.error("Chưa có exact evidence ở trạng thái verified cho benchmark.")
        gaps_text = st.text_area(
            "Research gaps (mỗi dòng một mục)",
            value=(
                "Cập nhật tỷ trọng benchmark từ nguồn chính thống."
                if benchmark.get("requires_update")
                else "Kiểm tra tính phù hợp của benchmark lịch sử với kỳ hiện tại."
            ),
        )
        reason = st.text_area("Lý do lưu/version snapshot *")
        confirmed = st.checkbox(
            "Tôi xác nhận sector context chỉ là bằng chứng; analyst vẫn tự quyết định assessment và investment decision."
        )
        submitted = st.form_submit_button(
            "Lưu governed sector snapshot",
            type="primary",
            use_container_width=True,
            disabled=benchmark_status == "analyst_verified" and evidence_id is None,
        )
    if submitted:
        try:
            snapshot_id = save_topdown_sector_snapshot(
                repo,
                company_ref_id=company_ref_id,
                review_id=int(review["id"]),
                payload=payload,
                selected_sector_code=selected_sector_code,
                as_of_date=as_of,
                horizon_months=int(horizon_months),
                benchmark_status=benchmark_status,
                benchmark_source_evidence_id=evidence_id,
                research_gaps=[line.strip() for line in gaps_text.splitlines() if line.strip()],
                analyst_confirmed=confirmed,
                change_reason=reason,
                actor=actor,
            )
            st.success(f"Đã lưu Fisher Top-down/Sector Snapshot #{snapshot_id}.")
            st.rerun(scope="fragment")
        except (ValidationError, ValueError) as exc:
            st.error(str(exc))


__all__ = ["render_topdown_sector_context"]
