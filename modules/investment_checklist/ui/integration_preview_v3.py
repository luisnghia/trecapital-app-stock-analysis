from __future__ import annotations

import pandas as pd
import streamlit as st

from ..source_policy import SourcePolicyDataProvider
from ..services.integration_service import ChecklistIntegrationService, build_repository
from ..services.portfolio_extensions import ensure_extension_schema, is_watchlisted, set_watchlist
from ..services.review_admin import delete_review_manually, review_delete_preview
from ..services.watchlist_v2 import refresh_watchlist_cagrs_if_changed
from . import page as _page
from .evidence_workspace import render_evidence_workspace
from .ai_research_assistant import render_ai_research_assistant
from .industry_overlay import render_industry_overlay
from .integration_preview import SECTIONS
from .management_intelligence import render_management_intelligence
from .monitoring_delta_review import render_monitoring_delta_review
from .investment_decision_journal import render_investment_decision_journal
from .performance_v3 import (
    render_analytical_fast,
    render_formula_assumptions_v3,
    render_home_fast,
    render_watchlist_fast,
    render_workspace_fast,
)


def _review_cache_key(company_ref_id: int) -> str:
    return f"_checklist_reviews_fast_{company_ref_id}"


def _reviews_cached(repo, company_ref_id: int):
    key = _review_cache_key(company_ref_id)
    rows = st.session_state.get(key)
    if rows is None:
        rows = repo.list_reviews(company_ref_id)
        st.session_state[key] = rows
    return rows


def _invalidate_reviews(company_ref_id: int) -> None:
    st.session_state.pop(_review_cache_key(company_ref_id), None)


def _watch_key(company_ref_id: int) -> str:
    return f"_checklist_watch_state_fast_{company_ref_id}"


def _watchlisted_cached(repo, company_ref_id: int) -> bool:
    key = _watch_key(company_ref_id)
    if key not in st.session_state:
        st.session_state[key] = bool(is_watchlisted(repo, company_ref_id))
    return bool(st.session_state[key])


def _fragment_rerun() -> None:
    try:
        st.rerun(scope="fragment")
    except (TypeError, ValueError):
        st.rerun()


def _render_watch_toggle(repo, company_ref_id: int, ticker: str, actor: str, data_provider) -> None:
    active = _watchlisted_cached(repo, company_ref_id)
    label = "★ Đang trong Watchlist — bấm để bỏ" if active else "☆ Đưa doanh nghiệp vào Watchlist"
    if st.button(label, key=f"watch_fast_{company_ref_id}", use_container_width=True):
        set_watchlist(repo, company_ref_id, active=not active, actor=actor, provider=data_provider)
        st.session_state[_watch_key(company_ref_id)] = not active
        if not active:
            # Populate the current-financial cache immediately. Watchlist no longer depends on reviews.
            refresh_watchlist_cagrs_if_changed(repo, company_ref_id, provider=data_provider, actor=actor)
        st.session_state["checklist_last_admin_message"] = (
            f"{'Đã thêm' if not active else 'Đã bỏ'} {ticker} {'vào' if not active else 'khỏi'} Watchlist."
        )
        _fragment_rerun()


def _render_delete_review(repo, selected_review, actor: str, state_key: str, company_ref_id: int) -> None:
    with st.popover("🗑️ Xóa review", use_container_width=True, disabled=selected_review is None):
        if selected_review is None:
            st.caption("Chưa có review để xóa.")
            return
        preview_key = f"_delete_review_preview_{int(selected_review['id'])}"
        preview = st.session_state.get(preview_key)
        if preview is None:
            st.caption(
                "Bản xem trước phạm vi xóa chỉ được tải khi cần, để chuyển khu vực Checklist không phải chạy "
                "hàng loạt COUNT trên Supabase."
            )
            if st.button(
                "Tải phạm vi xóa review",
                use_container_width=True,
                key=f"load_delete_preview_{int(selected_review['id'])}",
            ):
                preview = review_delete_preview(repo, selected_review["id"])
                st.session_state[preview_key] = preview
        if preview is None:
            return
        counts = preview["counts"]
        st.warning(
            f"Xóa REVIEW #{selected_review['id']} ({selected_review['as_of_date']} · {selected_review['status']}) sẽ xóa "
            f"{counts['analyst_assessments']} assessment, {counts['screening_assessments']} screening version, "
            f"{counts['evidence_links']} evidence link, "
            f"{counts.get('peer_snapshots', 0)} peer snapshot, "
            f"{counts.get('ai_runs', 0)} AI run/{counts.get('ai_suggestions', 0)} suggestion, "
            f"{counts.get('management_people', 0)} management profile version/"
            f"{counts.get('management_timeline', 0)} timeline event/"
            f"{counts.get('management_track_records', 0)} track record/"
            f"{counts.get('management_signals', 0)} signal, "
            f"{counts.get('monitoring_rules', 0)} monitoring rule/{counts.get('monitoring_observations', 0)} observation/"
            f"{counts.get('delta_items', 0)} delta item/{counts.get('delta_decisions', 0)} decision, "
            f"{counts.get('investment_memos', 0)} memo/{counts.get('thesis_pillars', 0)} thesis pillar/"
            f"{counts.get('investment_risks', 0)} risk/{counts.get('investment_decisions', 0)} signed decision/"
            f"{counts.get('decision_outcomes', 0)} outcome review, "
            f"{counts['inventory_snapshots']} inventory snapshot và {counts['immutable_snapshots']} immutable snapshot gắn với review này. "
            "Audit tombstone vẫn được giữ."
        )
        reason = st.text_area("Lý do xóa review *", key=f"delete_reason_fast_{selected_review['id']}")
        token = preview["confirmation_token"]
        confirm = st.text_input(f"Nhập đúng: {token}", key=f"delete_confirm_fast_{selected_review['id']}")
        if st.button(
            "Xóa vĩnh viễn review đã chọn",
            type="primary",
            use_container_width=True,
            key=f"delete_review_fast_{selected_review['id']}",
            disabled=not reason.strip() or confirm.strip() != token,
        ):
            try:
                delete_review_manually(
                    repo, selected_review["id"], actor=actor, reason=reason, confirmation_text=confirm
                )
                st.session_state.pop(state_key, None)
                st.session_state.pop(preview_key, None)
                _invalidate_reviews(company_ref_id)
                st.session_state["checklist_last_admin_message"] = f"Đã xóa REVIEW #{selected_review['id']}."
                _fragment_rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))


def _render_history_fast(repo, company_ref_id: int, review, actor: str) -> None:
    st.markdown("#### Snapshot & History")
    reviews = _reviews_cached(repo, company_ref_id)
    if reviews:
        st.markdown("##### Lịch sử toàn bộ review")
        st.dataframe(pd.DataFrame(reviews), use_container_width=True, hide_index=True)
    if not review:
        st.info("Chưa có review.")
        return

    metrics = repo.review_metrics(review["id"])
    cols = st.columns(3)
    cols[0].metric("Answered", metrics["answered"])
    cols[1].metric("Research gaps", metrics["research_gaps"])
    cols[2].metric("Completion", f"{metrics['research_completion'] * 100:.1f}%")

    if review["status"] != "completed":
        finalize_reason = st.text_area(
            "Lý do chốt/finalize review *", key=f"final_reason_fast_{review['id']}",
            help="Bắt buộc và được lưu cùng review để audit lịch sử.",
        )
        ok = st.checkbox("Tôi hiểu review sẽ bị khóa sau khi finalize.", key=f"fin_fast_{review['id']}")
        if st.button(
            "🔒 Finalize & Create Immutable Snapshot", type="primary",
            disabled=not ok or not finalize_reason.strip(), key=f"final_fast_{review['id']}",
        ):
            try:
                repo.finalize_review(review["id"], actor=actor, finalize_reason=finalize_reason)
                _invalidate_reviews(company_ref_id)
                _fragment_rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))

    snaps = repo.list_snapshots(company_ref_id)
    if snaps:
        st.dataframe(pd.DataFrame(snaps), use_container_width=True, hide_index=True)
        sid = st.selectbox(
            "View as-of snapshot", [s["id"] for s in snaps],
            format_func=lambda x: f"Snapshot #{x} — {next(s for s in snaps if s['id'] == x)['as_of_date']}",
        )
        with st.expander("Raw immutable payload (audit)"):
            st.json(repo.get_snapshot(sid)["payload"])
    else:
        st.info("Chưa có snapshot.")

    with st.expander("Audit log"):
        logs = repo.list_audit_logs(company_ref_id, 200)
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True) if logs else st.caption("Chưa có log.")
    with st.expander("Integration sync log"):
        logs = repo.list_sync_logs(company_ref_id, 100)
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True) if logs else st.caption("Chưa có sync log.")


@st.fragment
def render_investment_checklist(host, *, repo=None, data_provider=None, theme=None) -> None:
    """Fragment-isolated Checklist: internal navigation does not rerun the Trecapital page pipeline."""
    if theme:
        theme.inject_module_css()
    else:
        st.markdown(_page.FALLBACK_CSS, unsafe_allow_html=True)

    if data_provider is not None and not isinstance(data_provider, SourcePolicyDataProvider):
        data_provider = SourcePolicyDataProvider(data_provider, host.company.company_type)

    repo = repo or build_repository(host)
    ensure_extension_schema(repo)
    integration = ChecklistIntegrationService(repo, host, data_provider)
    company_ref_id, company = _page._company_cached(integration, host)
    actor = host.analyst.user_id

    st.markdown('<div class="checklist-module">', unsafe_allow_html=True)
    st.subheader("Investment Research & Checklist System")
    st.caption(
        "Fast Interactive Preview — internal navigation chạy trong Streamlit Fragment; Trecapital Data Layer không tải lại khi đổi Question/tool."
    )
    st.markdown(f"**{company['ticker']} — {company['company_name']}** · {company['industry_name'] or 'Chưa gán ngành'}")
    st.markdown(
        '<div class="principle"><b>Single Source of Truth:</b> dữ liệu tài chính tự động chỉ đến từ Trecapital Data Layer. '
        'Analyst correction là overlay có version/reason, không sửa dữ liệu gốc. Completed review vẫn bất biến.</div>',
        unsafe_allow_html=True,
    )

    admin_message = st.session_state.pop("checklist_last_admin_message", None)
    if admin_message:
        st.success(admin_message)

    reviews = _reviews_cached(repo, company_ref_id)
    review = None
    left, create_col, delete_col, watch_col = st.columns([2.0, 0.9, 0.9, 1.25])
    state = f"checklist_review_{company['host_company_key']}"
    if reviews:
        ids = [r["id"] for r in reviews]
        desired = st.session_state.get(state)
        index = ids.index(desired) if desired in ids else 0
        rid = left.selectbox(
            "Review", ids, index=index,
            format_func=lambda x: _page._review_label(next(r for r in reviews if r["id"] == x)),
            key=f"review_select_fast_{company_ref_id}",
        )
        st.session_state[state] = rid
        review = next(r for r in reviews if r["id"] == rid)
    else:
        left.info("Chưa có review cho mã này.")

    with create_col.popover("➕ Tạo review", use_container_width=True):
        asof = st.date_input("As-of date", value=_page.date.today(), key=f"new_review_date_fast_{company_ref_id}")
        rtype = st.selectbox("Loại review", ["full", "screening", "delta"], key=f"new_review_type_fast_{company_ref_id}")
        reason = st.text_area("Lý do tạo review *", key=f"new_review_reason_fast_{company_ref_id}")
        if st.button("Tạo review", use_container_width=True, key=f"create_review_fast_{company_ref_id}", disabled=not reason.strip()):
            try:
                rid = repo.create_review(company_ref_id, asof, rtype, actor, review_reason=reason)
                st.session_state[state] = rid
                _invalidate_reviews(company_ref_id)
                _fragment_rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))

    with delete_col:
        _render_delete_review(repo, review, actor, state, company_ref_id)
    with watch_col:
        _render_watch_toggle(repo, company_ref_id, company["ticker"], actor, data_provider)

    if review:
        st.caption(
            f"Review #{review['id']} · {review['as_of_date']} · {review['review_type']} · {review['status']} · "
            f"Lý do: {review.get('review_reason') or 'Legacy — chưa ghi lý do'}"
        )
        if review["status"] == "completed":
            st.markdown('<span class="locked">🔒 Completed — read only</span>', unsafe_allow_html=True)

    desired_section = st.session_state.get("checklist_section_global")
    default_index = SECTIONS.index(desired_section) if desired_section in SECTIONS else 0
    section = st.radio(
        "Khu vực checklist", SECTIONS, index=default_index, horizontal=True,
        label_visibility="collapsed", key="checklist_section_global",
    )

    if section == "🏠 Research Home":
        render_home_fast(repo, company_ref_id, review, reviews=reviews)
    elif section == "🧮 Analytical Tools":
        render_analytical_fast(repo, integration, company_ref_id, review, actor, data_provider, host.company.company_type)
    elif section == "🧠 Analyst Workspace Q01–Q59":
        render_workspace_fast(repo, company_ref_id, review, actor)
    elif section == "🔎 Research Evidence":
        render_evidence_workspace(repo, company_ref_id, review, actor)
    elif section == "🤖 AI Research Assistant":
        render_ai_research_assistant(repo, company_ref_id, review, actor)
    elif section == "👥 Management & Human Intel":
        render_management_intelligence(repo, company_ref_id, review, actor)
    elif section == "📡 Monitoring & Delta Review":
        render_monitoring_delta_review(repo, company_ref_id, review, actor)
    elif section == "📝 Investment Memo & Decision":
        render_investment_decision_journal(repo, company_ref_id, review, actor)
    elif section == "🏭 Industry & Moat":
        render_industry_overlay(
            integration,
            host,
            data_provider,
            repo=repo,
            company_ref_id=company_ref_id,
            review=review,
            actor=actor,
        )
    elif section == "⭐ Watchlist":
        render_watchlist_fast(repo, company_ref_id, company["ticker"], actor=actor, data_provider=data_provider)
    elif section == "🕘 Snapshot & History":
        _render_history_fast(repo, company_ref_id, review, actor)
    else:
        render_formula_assumptions_v3(integration, host)

    st.markdown("</div>", unsafe_allow_html=True)


__all__ = ["render_investment_checklist"]
