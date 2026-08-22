from __future__ import annotations

from ..formula_assumptions import EVALUATION_RULES, FORMULA_ROWS, GLOSSARY, SOURCE_NOTES
from ..source_policy import SourcePolicyDataProvider
from ..services.formulas import inventory_metrics
from ..services.portfolio_extensions import ensure_extension_schema
from ..services.review_admin import delete_review_manually, review_delete_preview
from . import page as _page
from .analytical_hub_v2 import render_analytical_hub_v2
from .portfolio_extensions import render_wrapped_table
from .watchlist_v2 import render_watchlist_toggle_v2, render_watchlist_v2
from .evidence_workspace import render_evidence_workspace
from .ai_research_assistant import render_ai_research_assistant
from .industry_overlay import render_industry_overlay


SECTIONS = [
    "🏠 Research Home",
    "🧮 Analytical Tools",
    "🧠 Analyst Workspace Q01–Q59",
    "🔎 Research Evidence",
    "🤖 AI Research Assistant",
    "🏭 Industry & Moat",
    "⭐ Watchlist",
    "🕘 Snapshot & History",
    "📐 Công thức & giả định",
]


def _fmt_current(value, kind="money"):
    if value is None or _page.pd.isna(value):
        return "—"
    value = float(value)
    if kind == "pct":
        return f"{value * 100:,.1f}%"
    if kind == "ratio":
        return f"{value:,.1f}x"
    if kind == "price":
        return f"{value:,.0f} đ/cp"
    if kind == "days":
        return f"{value:,.0f} ngày"
    return f"{value:,.0f} tỷ"


def _render_formula_assumptions_wrapped(integration, host):
    st = _page.st
    st.markdown("#### Công thức & giả định")
    st.markdown(
        "<div class='principle'><b>Nguyên tắc Trecapital:</b> công thức phải bám tài liệu nguồn; "
        "giả định nào bộ nguồn không khóa cứng phải được ghi rõ; dữ liệu thiếu không được tự điền 0; "
        "công thức và Data Layer phải đồng bộ giữa các module.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("##### Tóm tắt công thức đang dùng")
    render_wrapped_table(_page.pd.DataFrame(FORMULA_ROWS), css_class="core-formula-table")

    pre = integration.get_inventory_prefill()
    st.markdown("##### Audit số liệu hiệu lực hiện tại")
    if pre is None:
        st.info("Chưa có dữ liệu hiệu lực để thay số vào công thức. App không tự bịa số liệu.")
    else:
        metrics = inventory_metrics(
            tev=pre.tev,
            ebit=pre.ebit,
            ebitda=pre.ebitda,
            normalized_earnings=pre.normalized_earnings,
            total_debt=pre.total_debt,
            interest_expense=pre.interest_expense,
            fcf_current=pre.fcf_current,
            market_cap=pre.market_cap,
            dividend_per_share=pre.dividend_per_share,
            market_price=pre.market_price,
            target_price=pre.target_price,
        )
        audit_rows = [
            {"Chỉ tiêu": "TEV", "Số liệu": _fmt_current(pre.tev), "Công thức / cách đọc": "Market Cap + Interest-bearing Debt − Cash − Short-term Investments. Thiếu Debt ⇒ Unknown, không tự thay bằng 0."},
            {"Chỉ tiêu": "TEV/EBIT", "Số liệu": _fmt_current(metrics.get("tev_ebit"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.ebit)}"},
            {"Chỉ tiêu": "TEV/EBITDA", "Số liệu": _fmt_current(metrics.get("tev_ebitda"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.ebitda)}"},
            {"Chỉ tiêu": "TEV/Normalized Earnings", "Số liệu": _fmt_current(metrics.get("tev_normalized_earnings"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.normalized_earnings)}"},
            {"Chỉ tiêu": "Pre-tax Earnings Yield", "Số liệu": _fmt_current(metrics.get("pretax_earnings_yield"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.ebit)} ÷ {_fmt_current(pre.tev)} — nghịch đảo TEV/EBIT theo Table 1.2."},
            {"Chỉ tiêu": "Debt/EBITDA", "Số liệu": _fmt_current(metrics.get("debt_ebitda"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.total_debt)} ÷ {_fmt_current(pre.ebitda)}"},
            {"Chỉ tiêu": "EBIT/Interest", "Số liệu": _fmt_current(metrics.get("ebit_interest"), "ratio"), "Công thức / cách đọc": f"{_fmt_current(pre.ebit)} ÷ {_fmt_current(pre.interest_expense)}"},
            {"Chỉ tiêu": "FCF Yield EV", "Số liệu": _fmt_current(metrics.get("fcf_yield_ev"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.fcf_current)} ÷ {_fmt_current(pre.tev)}"},
            {"Chỉ tiêu": "FCF Yield Market", "Số liệu": _fmt_current(metrics.get("fcf_yield_market"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.fcf_current)} ÷ {_fmt_current(pre.market_cap)}"},
            {"Chỉ tiêu": "Dividend Yield", "Số liệu": _fmt_current(metrics.get("dividend_yield"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.dividend_per_share, 'price')} ÷ {_fmt_current(pre.market_price, 'price')}"},
            {"Chỉ tiêu": "Stock Price vs Target", "Số liệu": _fmt_current(metrics.get("price_vs_target"), "pct"), "Công thức / cách đọc": f"{_fmt_current(pre.market_price, 'price')} ÷ {_fmt_current(pre.target_price, 'price')}"},
            {"Chỉ tiêu": "MOS", "Số liệu": _fmt_current(pre.mos, "pct"), "Công thức / cách đọc": "(Target − Market Price) ÷ Target; nhận đồng bộ từ Module 2."},
            {"Chỉ tiêu": "CCC", "Số liệu": _fmt_current(pre.ccc_days, "days"), "Công thức / cách đọc": "DIO + DSO − DPO; proxy dùng số dư bình quân khi đủ dữ liệu."},
        ]
        render_wrapped_table(_page.pd.DataFrame(audit_rows), css_class="formula-audit-table")
        for note in getattr(pre, "source_notes", ()) or ():
            st.warning(note) if str(note).startswith("CẢNH BÁO") else st.caption("• " + str(note))

    st.markdown("##### Giả định/nguyên tắc đánh giá")
    for rule in EVALUATION_RULES:
        st.markdown(f"- {rule}")

    st.markdown("##### Thuật ngữ & từ viết tắt")
    render_wrapped_table(_page.pd.DataFrame(GLOSSARY), css_class="formula-glossary-table")

    st.markdown("##### Nguồn và phạm vi")
    for note in SOURCE_NOTES:
        st.caption("• " + note)
    st.caption(
        f"Overlay ngành hiệu lực: {host.company.company_type}. Công thức là tài liệu vận hành của Checklist; "
        "thay đổi công thức phải đi cùng regression test và audit trail."
    )


def _render_delete_review_popover(repo, selected_review, actor, state_key):
    st = _page.st
    with st.popover("🗑️ Xóa review", use_container_width=True, disabled=selected_review is None):
        if selected_review is None:
            st.caption("Chưa có review để xóa.")
            return
        preview = review_delete_preview(repo, selected_review["id"])
        counts = preview["counts"]
        st.warning(
            f"Xóa REVIEW #{selected_review['id']} ({selected_review['as_of_date']} · {selected_review['status']}) sẽ xóa "
            f"{counts['analyst_assessments']} assessment, {counts['screening_assessments']} screening version, "
            f"{counts['evidence_links']} evidence link, "
            f"{counts.get('peer_snapshots', 0)} peer snapshot, "
            f"{counts.get('ai_runs', 0)} AI run/{counts.get('ai_suggestions', 0)} suggestion, "
            f"{counts['inventory_snapshots']} inventory snapshot và {counts['immutable_snapshots']} immutable snapshot gắn với review này. "
            "Các review sau sẽ được nối lại về prior review trước đó. Audit tombstone vẫn được giữ."
        )
        reason = st.text_area("Lý do xóa review *", key=f"delete_reason_{selected_review['id']}")
        token = preview["confirmation_token"]
        confirm = st.text_input(f"Nhập đúng: {token}", key=f"delete_confirm_{selected_review['id']}")
        if st.button(
            "Xóa vĩnh viễn review đã chọn",
            type="primary",
            use_container_width=True,
            key=f"delete_review_{selected_review['id']}",
            disabled=not reason.strip() or confirm.strip() != token,
        ):
            try:
                delete_review_manually(repo, selected_review["id"], actor=actor, reason=reason, confirmation_text=confirm)
                st.session_state.pop(state_key, None)
                st.session_state["checklist_last_admin_message"] = f"Đã xóa REVIEW #{selected_review['id']} và dữ liệu review liên quan."
                st.rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))


def render_investment_checklist(host, *, repo=None, data_provider=None, theme=None):
    """Integrated preview: Phase 1C + Phase 2 + persistent Watchlist + analyst correction overlays."""
    st = _page.st
    if theme:
        theme.inject_module_css()
    else:
        st.markdown(_page.FALLBACK_CSS, unsafe_allow_html=True)

    if data_provider is not None and not isinstance(data_provider, SourcePolicyDataProvider):
        data_provider = SourcePolicyDataProvider(data_provider, host.company.company_type)

    repo = repo or _page.build_repository(host)
    ensure_extension_schema(repo)
    integration = _page.ChecklistIntegrationService(repo, host, data_provider)
    cid, company = _page._company_cached(integration, host)
    actor = host.analyst.user_id

    st.markdown('<div class="checklist-module">', unsafe_allow_html=True)
    st.subheader("Investment Research & Checklist System")
    st.caption(
        "Integrated Preview — Core Research + Analytical Tools + Evidence + governed AI provider/approval queue; "
        "analyst giữ quyền quyết định cuối cùng."
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

    reviews = repo.list_reviews(cid)
    review = None
    left, create_col, delete_col, watch_col = st.columns([2.0, 0.9, 0.9, 1.25])
    state = f"checklist_review_{company['host_company_key']}"
    if reviews:
        ids = [r["id"] for r in reviews]
        desired = st.session_state.get(state)
        index = ids.index(desired) if desired in ids else 0
        rid = left.selectbox(
            "Review",
            ids,
            index=index,
            format_func=lambda x: _page._review_label(next(r for r in reviews if r["id"] == x)),
            key=f"review_select_{cid}",
        )
        st.session_state[state] = rid
        review = next(r for r in reviews if r["id"] == rid)
    else:
        left.info("Chưa có review cho mã này.")

    with create_col.popover("➕ Tạo review", use_container_width=True):
        asof = st.date_input("As-of date", value=_page.date.today(), key=f"new_review_date_{cid}")
        rtype = st.selectbox("Loại review", ["full", "screening", "delta"], key=f"new_review_type_{cid}")
        review_reason = st.text_area("Lý do tạo review *", key=f"new_review_reason_{cid}")
        if st.button("Tạo review", use_container_width=True, key=f"create_review_{cid}", disabled=not review_reason.strip()):
            try:
                rid = repo.create_review(cid, asof, rtype, actor, review_reason=review_reason)
                st.session_state[state] = rid
                st.rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))

    with delete_col:
        _render_delete_review_popover(repo, review, actor, state)
    with watch_col:
        render_watchlist_toggle_v2(repo, cid, company["ticker"], actor=actor, data_provider=data_provider)

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
        "Khu vực checklist",
        SECTIONS,
        index=default_index,
        horizontal=True,
        label_visibility="collapsed",
        key="checklist_section_global",
    )
    if section == "🏠 Research Home":
        _page._render_home(repo, cid, review)
    elif section == "🧮 Analytical Tools":
        render_analytical_hub_v2(repo, integration, cid, review, actor, data_provider, host.company.company_type)
    elif section == "🧠 Analyst Workspace Q01–Q59":
        _page._render_workspace(repo, cid, review, actor)
    elif section == "🔎 Research Evidence":
        render_evidence_workspace(repo, cid, review, actor)
    elif section == "🤖 AI Research Assistant":
        render_ai_research_assistant(repo, cid, review, actor)
    elif section == "🏭 Industry & Moat":
        render_industry_overlay(integration, host, data_provider)
    elif section == "⭐ Watchlist":
        render_watchlist_v2(repo, cid, company["ticker"], actor=actor, data_provider=data_provider)
    elif section == "🕘 Snapshot & History":
        _page._render_history(repo, cid, review, actor)
    else:
        _render_formula_assumptions_wrapped(integration, host)

    st.markdown("</div>", unsafe_allow_html=True)


__all__ = ["render_investment_checklist"]
