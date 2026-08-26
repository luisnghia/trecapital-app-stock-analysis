from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.topdown_data_update import (
    decide_driver_suggestion,
    get_update_run_bundle,
    latest_accepted_driver_outlook,
    list_pending_driver_suggestions,
    list_update_runs,
    load_source_registry,
    run_latest_data_update,
    source_coverage_rows,
)


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, "")).strip()


def _score_label(value) -> str:
    if value is None:
        return "Research gap"
    score = int(value)
    return {
        -2: "-2 · Giảm mạnh",
        -1: "-1 · Giảm",
        0: "0 · Trung tính/ít đổi",
        1: "+1 · Tăng",
        2: "+2 · Tăng mạnh",
    }[score]


def _render_registry(registry: dict) -> None:
    coverage = source_coverage_rows(registry)
    automatic = sum(row["Cơ chế"] == "Tự động khi bấm Cập nhật" for row in coverage)
    optional = sum(row["Cơ chế"] == "Tự động khi có API key" for row in coverage)
    gaps = len(coverage) - automatic - optional
    c1, c2, c3 = st.columns(3)
    c1.metric("Driver có API không cần key", automatic)
    c2.metric("Driver API key tùy chọn", optional)
    c3.metric("Driver cần evidence/analyst", gaps)
    with st.expander("Source Registry — đủ 26 Portfolio Drivers", expanded=False):
        st.dataframe(
            pd.DataFrame(coverage),
            use_container_width=True,
            hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("URL")},
        )


def _render_run(repo, run_id: int) -> None:
    bundle = get_update_run_bundle(repo, run_id)
    if not bundle:
        return
    run = bundle["run"]
    cols = st.columns(4)
    cols[0].metric("Run", f"#{run['id']}")
    cols[1].metric("Trạng thái", run["status"])
    cols[2].metric("Nguồn thành công", run["success_count"])
    cols[3].metric("Nguồn lỗi/bỏ qua", run["failure_count"])
    st.caption(
        f"Bắt đầu: {run['started_at']} · Hoàn tất: {run.get('completed_at') or 'đang chạy'} · "
        f"Registry SHA-256: {run['source_registry_hash'][:16]}…"
    )
    errors = run.get("detail", {}).get("errors", [])
    if errors:
        with st.expander(f"Research gaps/lỗi nguồn ({len(errors)})", expanded=False):
            st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)
    observations = bundle["observations"]
    if observations:
        view = pd.DataFrame(
            [
                {
                    "Driver": row["driver_id"],
                    "Nguồn": row["source_code"],
                    "Series": row["series_code"],
                    "Kỳ dữ liệu": row["period_label"],
                    "Giá trị": row["value_numeric"],
                    "Kỳ trước": row["previous_value_numeric"],
                    "Thay đổi": row["delta_numeric"],
                    "Đơn vị": row["unit"],
                    "Độ mới": row["freshness_status"],
                    "Truy xuất lúc": row["retrieved_at"],
                    "URL": row["source_url"],
                }
                for row in observations
            ]
        )
        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("URL nguồn")},
        )


def _render_decision_queue(repo, review, actor: str) -> None:
    pending = list_pending_driver_suggestions(repo, int(review["id"]))
    if not pending:
        st.info("Không có driver suggestion đang chờ quyết định.")
        return
    labels = {
        int(row["id"]): (
            f"#{row['id']} · {row['driver_id']} · {row['period_label']} · "
            f"{row['value_numeric']:g} {row['unit']} · {_score_label(row['suggested_score'])}"
        )
        for row in pending
    }
    with st.form(f"phase9_decision_{review['id']}"):
        suggestion_id = st.selectbox(
            "Suggestion cần xử lý",
            list(labels),
            format_func=lambda value: labels[value],
        )
        selected = next(row for row in pending if int(row["id"]) == int(suggestion_id))
        st.caption(selected["rationale"])
        if selected.get("data_gap_reason"):
            st.warning(selected["data_gap_reason"])
        decision = st.radio(
            "Quyết định",
            ["accept", "reject"],
            horizontal=True,
            format_func=lambda value: "Chấp nhận/điều chỉnh điểm" if value == "accept" else "Từ chối",
        )
        default_score = int(selected["suggested_score"]) if selected["suggested_score"] is not None else 0
        applied_score = st.select_slider(
            "Điểm driver áp dụng",
            options=[-2, -1, 0, 1, 2],
            value=default_score,
            format_func=_score_label,
            disabled=decision == "reject",
        )
        reason = st.text_area("Lý do quyết định *")
        confirmed = st.checkbox(
            "Tôi đã kiểm tra nguồn/kỳ dữ liệu; điểm này chỉ cập nhật Portfolio Driver, không phải lệnh mua/bán.",
            disabled=decision == "reject",
        )
        submitted = st.form_submit_button("Lưu quyết định", type="primary", use_container_width=True)
    if submitted:
        try:
            decide_driver_suggestion(
                repo,
                suggestion_id=int(suggestion_id),
                decision=decision,
                decision_reason=reason,
                actor=actor,
                applied_score=int(applied_score) if decision == "accept" else None,
                analyst_confirmed=bool(confirmed) if decision == "accept" else False,
            )
            st.success("Đã lưu quyết định Phase 9.")
            st.rerun(scope="fragment")
        except ValidationError as exc:
            st.error(str(exc))


def render_topdown_data_update(repo, company_ref_id: int, review, actor: str) -> None:
    st.markdown("### 🔄 Latest Data Update — Phase 9")
    st.markdown(
        "<div class='principle'><b>Nguyên tắc:</b> app chỉ gọi nguồn khi người dùng bấm "
        "<b>Cập nhật dữ liệu mới nhất</b>. Không polling, không cron, không realtime. Dữ liệu nguồn tạo "
        "suggestion; analyst phải accept/reject trước khi áp dụng vào 26 Portfolio Drivers.</div>",
        unsafe_allow_html=True,
    )
    registry = load_source_registry()
    _render_registry(registry)
    if not review:
        st.info("Tạo hoặc chọn review trước khi cập nhật dữ liệu Phase 9.")
        return

    entries = [entry for entry in registry["driver_sources"] if entry.get("adapter")]
    driver_names = {entry["driver_id"]: entry["driver_name"] for entry in entries}
    no_key_ids = [
        entry["driver_id"]
        for entry in entries
        if entry["mode"] in {"automatic", "automatic_proxy"}
    ]
    optional_ids = [entry["driver_id"] for entry in entries if entry["mode"] == "automatic_optional_key"]
    keys_available = {
        "interest_rates": bool(_secret("FRED_API_KEY")),
        "risk_aversion": bool(_secret("FRED_API_KEY")),
        "commodity_prices": bool(_secret("EIA_API_KEY")),
    }
    default_ids = no_key_ids + [driver_id for driver_id in optional_ids if keys_available.get(driver_id)]
    selected_ids = st.multiselect(
        "Driver sẽ tải khi bấm Cập nhật",
        [entry["driver_id"] for entry in entries],
        default=default_ids,
        format_func=lambda driver_id: f"{driver_names[driver_id]} ({driver_id})",
        disabled=review["status"] == "completed",
    )
    if optional_ids:
        st.caption(
            "Nguồn tùy chọn: FRED_API_KEY "
            f"{'đã có' if _secret('FRED_API_KEY') else 'chưa có'} · EIA_API_KEY "
            f"{'đã có' if _secret('EIA_API_KEY') else 'chưa có'}. Không có key thì app vẫn chạy bằng nguồn miễn phí."
        )
    if review["status"] == "completed":
        st.warning("Review đã completed: Phase 9 chỉ đọc, không gọi nguồn hoặc ghi quyết định mới.")
    clicked = st.button(
        "🔄 Cập nhật dữ liệu mới nhất",
        type="primary",
        use_container_width=True,
        disabled=review["status"] == "completed" or not selected_ids,
    )
    if clicked:
        try:
            with st.spinner("Đang lấy đúng quan sát mới nhất từ các nguồn đã chọn…"):
                run_id = run_latest_data_update(
                    repo,
                    company_ref_id=company_ref_id,
                    review_id=int(review["id"]),
                    driver_ids=selected_ids,
                    actor=actor,
                    api_keys={"FRED_API_KEY": _secret("FRED_API_KEY"), "EIA_API_KEY": _secret("EIA_API_KEY")},
                )
            st.session_state[f"phase9_latest_run_{review['id']}"] = run_id
            st.success(f"Đã hoàn tất Update Run #{run_id}.")
        except (ValidationError, ValueError) as exc:
            st.error(str(exc))

    runs = list_update_runs(repo, int(review["id"]))
    if runs:
        run_ids = [int(row["id"]) for row in runs]
        desired = st.session_state.get(f"phase9_latest_run_{review['id']}")
        index = run_ids.index(desired) if desired in run_ids else 0
        selected_run = st.selectbox(
            "Lịch sử Update Run",
            run_ids,
            index=index,
            format_func=lambda value: (
                f"Run #{value} · {next(row for row in runs if int(row['id']) == value)['status']} · "
                f"{next(row for row in runs if int(row['id']) == value)['started_at']}"
            ),
        )
        _render_run(repo, selected_run)
    else:
        st.info("Chưa có Update Run. App chưa gọi bất kỳ nguồn nào trong review này.")

    st.divider()
    st.markdown("#### Analyst approval queue")
    if review["status"] != "completed":
        _render_decision_queue(repo, review, actor)

    accepted = latest_accepted_driver_outlook(repo, int(review["id"]))
    st.markdown("#### Driver đã được analyst chấp nhận")
    if not accepted:
        st.caption("Chưa có driver nào được chấp nhận.")
        return
    accepted_df = pd.DataFrame(
        [
            {"Driver": driver_names.get(driver_id, driver_id), "Driver ID": driver_id, "Điểm áp dụng": score}
            for driver_id, score in accepted.items()
        ]
    )
    st.dataframe(accepted_df, use_container_width=True, hide_index=True)
    if st.button(
        "Áp dụng các điểm đã duyệt vào phiên Fisher Top-down",
        use_container_width=True,
        disabled=review["status"] == "completed",
    ):
        current = dict(st.session_state.get("topdown_trien_vong", {}))
        current.update(accepted)
        st.session_state["topdown_trien_vong"] = current
        st.session_state["topdown_phase9_applied_review_id"] = int(review["id"])
        st.session_state["topdown_phase9_applied_count"] = len(accepted)
        st.success(f"Đã áp dụng {len(accepted)} driver vào phiên Top-down hiện tại.")
    st.page_link("pages/06_Phan_tich_TopDown_Nganh.py", label="Mở Fisher Top-Down theo ngành", icon="🧭")


__all__ = ["render_topdown_data_update"]
