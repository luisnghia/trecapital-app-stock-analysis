from . import page as _page
from ..formula_assumptions import EVALUATION_RULES, FORMULA_ROWS, GLOSSARY, SOURCE_NOTES
from ..source_policy import SourcePolicyDataProvider
from ..services.formulas import inventory_metrics
from ..services.review_admin import delete_review_manually, review_delete_preview
from .evidence_workspace import render_evidence_workspace
from .quant_tools import render_quantitative_tools


SECTIONS = [
    "🏠 Research Home",
    "📋 Table 1.1",
    "📊 Table 1.2",
    "🧠 Analyst Workspace Q01–Q59",
    "🔎 Research Evidence",
    "🧮 Analytical Tools",
    "🕘 Snapshot & History",
    "📐 Công thức & giả định",
]


def _ttm_first_period_sort_date(period, current_as_of=None):
    """Sort Table 1.2 with TTM/T12M as the absolute first row."""
    text = str(period or "").strip()
    upper = text.upper()
    if "TTM" in upper or "T12M" in upper:
        return _page.pd.Timestamp.max.normalize()
    if text.isdigit() and len(text) == 4:
        text = f"{text}-12-31"
    dt = _page.pd.to_datetime(text, errors="coerce")
    return dt if _page.pd.notna(dt) else _page.pd.Timestamp.min


_page._period_sort_date = _ttm_first_period_sort_date


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


def _render_formula_assumptions(integration, host):
    st = _page.st
    st.markdown("#### Công thức & giả định")
    st.markdown(
        "<div class='principle'><b>Nguyên tắc Trecapital:</b> công thức phải bám tài liệu nguồn; "
        "giả định nào bộ nguồn không khóa cứng phải được ghi rõ; dữ liệu thiếu không được tự điền 0; "
        "công thức và Data Layer phải đồng bộ giữa các module.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("##### Tóm tắt công thức đang dùng")
    formula_df = _page.pd.DataFrame(FORMULA_ROWS)
    st.dataframe(formula_df, use_container_width=True, hide_index=True, height=560)

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
            {"Chỉ tiêu": "TEV", "Số liệu": _fmt_current(pre.tev), "Cách đọc": "Market Cap + Debt − Cash − Short-term Investments; thiếu Debt ⇒ để trống."},
            {"Chỉ tiêu": "TEV/EBIT", "Số liệu": _fmt_current(metrics.get("tev_ebit"), "ratio"), "Cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.ebit)}"},
            {"Chỉ tiêu": "TEV/EBITDA", "Số liệu": _fmt_current(metrics.get("tev_ebitda"), "ratio"), "Cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.ebitda)}"},
            {"Chỉ tiêu": "TEV/Normalized Earnings", "Số liệu": _fmt_current(metrics.get("tev_normalized_earnings"), "ratio"), "Cách đọc": f"{_fmt_current(pre.tev)} ÷ {_fmt_current(pre.normalized_earnings)}"},
            {"Chỉ tiêu": "Pre-tax Earnings Yield", "Số liệu": _fmt_current(metrics.get("pretax_earnings_yield"), "pct"), "Cách đọc": f"{_fmt_current(pre.ebit)} ÷ {_fmt_current(pre.tev)} — nghịch đảo TEV/EBIT theo Bảng 1.2 Shearn"},
            {"Chỉ tiêu": "Debt/EBITDA", "Số liệu": _fmt_current(metrics.get("debt_ebitda"), "ratio"), "Cách đọc": f"{_fmt_current(pre.total_debt)} ÷ {_fmt_current(pre.ebitda)}"},
            {"Chỉ tiêu": "EBIT/Interest", "Số liệu": _fmt_current(metrics.get("ebit_interest"), "ratio"), "Cách đọc": f"{_fmt_current(pre.ebit)} ÷ {_fmt_current(pre.interest_expense)}"},
            {"Chỉ tiêu": "FCF Yield EV", "Số liệu": _fmt_current(metrics.get("fcf_yield_ev"), "pct"), "Cách đọc": f"{_fmt_current(pre.fcf_current)} ÷ {_fmt_current(pre.tev)}"},
            {"Chỉ tiêu": "FCF Yield Market", "Số liệu": _fmt_current(metrics.get("fcf_yield_market"), "pct"), "Cách đọc": f"{_fmt_current(pre.fcf_current)} ÷ {_fmt_current(pre.market_cap)}"},
            {"Chỉ tiêu": "Dividend Yield", "Số liệu": _fmt_current(metrics.get("dividend_yield"), "pct"), "Cách đọc": f"{_fmt_current(pre.dividend_per_share, 'price')} ÷ {_fmt_current(pre.market_price, 'price')}"},
            {"Chỉ tiêu": "Stock Price vs Target", "Số liệu": _fmt_current(metrics.get("price_vs_target"), "pct"), "Cách đọc": f"{_fmt_current(pre.market_price, 'price')} ÷ {_fmt_current(pre.target_price, 'price')}"},
            {"Chỉ tiêu": "MOS", "Số liệu": _fmt_current(pre.mos, "pct"), "Cách đọc": "(Target − Market Price) ÷ Target; nhận đồng bộ từ Module 2."},
            {"Chỉ tiêu": "CCC", "Số liệu": _fmt_current(pre.ccc_days, "days"), "Cách đọc": "DIO + DSO − DPO; proxy dùng số dư bình quân khi đủ dữ liệu."},
        ]
        st.dataframe(_page.pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
        for note in getattr(pre, "source_notes", ()) or ():
            st.warning(note) if str(note).startswith("CẢNH BÁO") else st.caption("• " + str(note))

    st.markdown("##### Giả định/nguyên tắc đánh giá")
    for rule in EVALUATION_RULES:
        st.markdown(f"- {rule}")

    st.markdown("##### Thuật ngữ & từ viết tắt")
    st.dataframe(_page.pd.DataFrame(GLOSSARY), use_container_width=True, hide_index=True)

    st.markdown("##### Nguồn và phạm vi")
    for note in SOURCE_NOTES:
        st.caption("• " + note)
    st.caption(
        f"Overlay ngành hiệu lực: {host.company.company_type}. "
        "Công thức này là tài liệu vận hành của Checklist; thay đổi công thức phải đi cùng test và audit trail."
    )


def _render_delete_review_popover(repo, reviews, selected_review, actor, state_key):
    st = _page.st
    disabled = selected_review is None
    with st.popover("🗑️ Xóa review", use_container_width=True, disabled=disabled):
        if selected_review is None:
            st.caption("Chưa có review để xóa.")
            return
        preview = review_delete_preview(repo, selected_review["id"])
        counts = preview["counts"]
        st.warning(
            f"Xóa REVIEW #{selected_review['id']} ({selected_review['as_of_date']} · {selected_review['status']}) sẽ xóa "
            f"{counts['analyst_assessments']} assessment, {counts['screening_assessments']} screening version, "
            f"{counts['evidence_links']} evidence link, "
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
                delete_review_manually(
                    repo,
                    selected_review["id"],
                    actor=actor,
                    reason=reason,
                    confirmation_text=confirm,
                )
                st.session_state.pop(state_key, None)
                st.session_state["checklist_last_admin_message"] = f"Đã xóa REVIEW #{selected_review['id']} và dữ liệu review liên quan."
                st.rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))


def render_investment_checklist(host, *, repo=None, data_provider=None, theme=None):
    """Phase 2 UI: Phase 1C core + source policy + quantitative analytical tools."""
    st = _page.st
    if theme:
        theme.inject_module_css()
    else:
        st.markdown(_page.FALLBACK_CSS, unsafe_allow_html=True)

    if data_provider is not None and not isinstance(data_provider, SourcePolicyDataProvider):
        data_provider = SourcePolicyDataProvider(data_provider, host.company.company_type)

    repo = repo or _page.build_repository(host)
    integration = _page.ChecklistIntegrationService(repo, host, data_provider)
    cid, company = _page._company_cached(integration, host)
    actor = host.analyst.user_id

    st.markdown('<div class="checklist-module">', unsafe_allow_html=True)
    st.subheader("Investment Research & Checklist System")
    st.caption("Phase 2 — Core Research System + Quantitative Analytical Tools. Không AI; tool cung cấp evidence, analyst giữ quyền kết luận.")
    st.markdown(f"**{company['ticker']} — {company['company_name']}** · {company['industry_name'] or 'Chưa gán ngành'}")
    st.markdown(
        '<div class="principle"><b>Nguyên tắc:</b> Analyst tự trả lời, tự đánh giá; Unknown khác Neutral; '
        'mọi thay đổi được lưu version; completed review là read-only. Quantitative Tools chỉ consume Trecapital Data Layer và '
        'không tự ghi assessment. Xóa review là thao tác admin có lý do + xác nhận + audit tombstone.</div>',
        unsafe_allow_html=True,
    )

    admin_message = st.session_state.pop("checklist_last_admin_message", None)
    if admin_message:
        st.success(admin_message)

    reviews = repo.list_reviews(cid)
    review = None
    left, create_col, delete_col = st.columns([2.2, 1.0, 1.0])
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
        review_reason = st.text_area(
            "Lý do tạo review *",
            key=f"new_review_reason_{cid}",
            help="Bắt buộc: ví dụ cập nhật BCTC quý mới, thay đổi thesis, sự kiện trọng yếu hoặc review định kỳ.",
        )
        if st.button("Tạo review", use_container_width=True, key=f"create_review_{cid}", disabled=not review_reason.strip()):
            try:
                rid = repo.create_review(cid, asof, rtype, actor, review_reason=review_reason)
                st.session_state[state] = rid
                st.rerun()
            except _page.ValidationError as exc:
                st.error(str(exc))

    with delete_col:
        _render_delete_review_popover(repo, reviews, review, actor, state)

    if review:
        st.caption(
            f"Review #{review['id']} · {review['as_of_date']} · {review['review_type']} · {review['status']} · "
            f"Lý do: {review.get('review_reason') or 'Legacy — chưa ghi lý do'}"
        )
        if review["status"] == "completed":
            st.markdown('<span class="locked">🔒 Completed — read only</span>', unsafe_allow_html=True)

    section = st.radio(
        "Khu vực checklist",
        SECTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key=f"checklist_section_{cid}",
    )
    if section == SECTIONS[0]:
        _page._render_home(repo, cid, review)
    elif section == SECTIONS[1]:
        _page._render_table11(repo, cid, review, actor)
    elif section == SECTIONS[2]:
        _page._render_table12(repo, integration, cid, review, actor)
    elif section == SECTIONS[3]:
        _page._render_workspace(repo, cid, review, actor)
    elif section == SECTIONS[4]:
        render_evidence_workspace(repo, cid, review, actor)
    elif section == SECTIONS[5]:
        render_quantitative_tools(data_provider, company_type=host.company.company_type)
    elif section == SECTIONS[6]:
        _page._render_history(repo, cid, review, actor)
    else:
        _render_formula_assumptions(integration, host)

    st.markdown("</div>", unsafe_allow_html=True)


__all__ = ["render_investment_checklist"]
