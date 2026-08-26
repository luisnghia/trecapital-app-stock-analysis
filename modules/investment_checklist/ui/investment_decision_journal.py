from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.investment_decision_journal import (
    INVESTMENT_DECISIONS,
    OUTCOME_LABELS,
    PILLAR_STATUSES,
    PILLAR_TYPES,
    RISK_CATEGORIES,
    RISK_STATUSES,
    THESIS_STATUSES,
    add_decision_outcome_review,
    decision_journal_bundle,
    list_investment_decisions,
    record_investment_decision,
    save_investment_memo,
    save_risk_register_item,
    save_thesis_pillar,
)


_LABELS = {
    "pass": "Pass — không đầu tư", "watch": "Watch — tiếp tục theo dõi", "buy": "Buy",
    "add": "Add", "hold": "Hold", "trim": "Trim", "sell": "Sell",
    "supported": "Được hỗ trợ", "mixed": "Bằng chứng trái chiều", "contradicted": "Bị phản chứng",
    "research_gap": "Research gap", "open": "Mở", "monitoring": "Đang theo dõi",
    "mitigated": "Đã giảm thiểu", "realized": "Đã xảy ra/hiện thực hóa", "closed": "Đóng",
    "intact": "Thesis còn nguyên", "weakened": "Thesis suy yếu", "broken": "Thesis bị phá vỡ",
    "unknown": "Chưa đủ dữ liệu", "pending": "Đang chờ", "positive": "Tích cực",
    "negative": "Tiêu cực", "mixed": "Trái chiều",
}


def _label(value: str) -> str:
    return _LABELS.get(value, value.replace("_", " ").title())


def _df(rows: list[dict], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def _evidence_rows(repo, company_ref_id: int) -> list[dict]:
    with repo._conn() as c:
        return [dict(row) for row in c.execute(
            """SELECT e.id,e.evidence_type,e.excerpt,e.verification_status,s.title AS source_title
            FROM research_evidence e JOIN research_sources s ON s.id=e.source_id
            WHERE e.company_ref_id=? AND s.status='active'
            AND NOT EXISTS(SELECT 1 FROM research_evidence n WHERE n.source_id=e.source_id
              AND n.evidence_key=e.evidence_key AND n.version_no>e.version_no)
            ORDER BY e.id DESC LIMIT 300""", (int(company_ref_id),),
        )]


def _evidence_picker(label: str, rows: list[dict], *, key: str, current: int | None = None) -> int | None:
    by_id = {int(row["id"]): row for row in rows}
    options = [0] + list(by_id)
    index = options.index(int(current)) if current and int(current) in options else 0

    def display(value: int) -> str:
        if value == 0:
            return "— Chưa liên kết —"
        row = by_id[value]
        excerpt = str(row.get("excerpt") or "").replace("\n", " ")
        return f"#{value} · {row['evidence_type']} · {excerpt[:110]}"

    selected = st.selectbox(label, options, index=index, format_func=display, key=key)
    return None if selected == 0 else int(selected)


def _render_dashboard(bundle: dict) -> None:
    summary = bundle["summary"]
    cols = st.columns(5)
    cols[0].metric("Memo hiện hành", summary["memo_versions"])
    cols[1].metric("Thesis pillar", summary["pillars"])
    cols[2].metric("Gap/phản chứng", summary["research_gaps"] + summary["contradicted"])
    cols[3].metric("Rủi ro mở", summary["open_risks"])
    cols[4].metric("Analyst đã ký", "Có" if summary["signed"] else "Chưa")
    st.markdown("##### Thesis pillars hiện hành")
    _df(bundle["thesis_pillars"], "Chưa có thesis pillar.")
    st.markdown("##### Risk register hiện hành")
    _df(bundle["risk_register"], "Chưa có risk register item.")


def _render_memo(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    memos = bundle["memos"]
    _df(memos, "Chưa có investment memo.")
    if review["status"] == "completed" or bundle["decision"]:
        return
    by_key = {row["memo_key"]: row for row in memos}
    with st.form(f"phase7_memo_{review['id']}"):
        selected = st.selectbox("Memo", ["__new__"] + list(by_key),
                                format_func=lambda value: "Memo mới" if value == "__new__" else f"{value} · v{by_key[value]['version_no']}")
        current = by_key.get(selected, {})
        key = st.text_input("Memo key", value="primary" if selected == "__new__" else selected,
                            disabled=selected != "__new__")
        title = st.text_input("Tiêu đề *", value=str(current.get("title") or ""))
        thesis = st.text_area("Investment thesis *", value=str(current.get("thesis_summary") or ""))
        variant = st.text_area("Variant perception *", value=str(current.get("variant_perception") or ""))
        quality = st.text_area("Chất lượng doanh nghiệp *", value=str(current.get("business_quality") or ""))
        valuation = st.text_area("Tóm tắt định giá *", value=str(current.get("valuation_summary") or ""))
        catalysts = st.text_area("Catalyst *", value=str(current.get("catalysts") or ""))
        invalidation = st.text_area("Điều kiện bác bỏ thesis *", value=str(current.get("invalidation_conditions") or ""))
        c1, c2 = st.columns(2)
        months = c1.number_input("Thời hạn (tháng)", min_value=1, max_value=120,
                                 value=int(current.get("time_horizon_months") or 36))
        with c2:
            evidence_id = _evidence_picker("Evidence tổng hợp", evidence, key=f"memo_ev_{review['id']}",
                                           current=current.get("source_evidence_id"))
        reason = st.text_input("Lý do version mới *", disabled=selected == "__new__")
        submitted = st.form_submit_button("Lưu memo version", type="primary", use_container_width=True)
    if submitted:
        try:
            save_investment_memo(
                repo, company_ref_id=company_ref_id, review_id=review["id"], memo_key=key,
                title=title, thesis_summary=thesis, variant_perception=variant,
                business_quality=quality, valuation_summary=valuation, catalysts=catalysts,
                invalidation_conditions=invalidation, time_horizon_months=months,
                source_evidence_id=evidence_id, change_reason=reason, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def _render_pillars(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    pillars = bundle["thesis_pillars"]
    _df(pillars, "Chưa có thesis pillar.")
    if review["status"] == "completed" or bundle["decision"]:
        return
    by_key = {row["pillar_key"]: row for row in pillars}
    with st.form(f"phase7_pillar_{review['id']}"):
        selected = st.selectbox("Pillar", ["__new__"] + list(by_key),
                                format_func=lambda value: "Pillar mới" if value == "__new__" else f"{value} · v{by_key[value]['version_no']}")
        current = by_key.get(selected, {})
        key = st.text_input("Pillar key", value="" if selected == "__new__" else selected,
                            disabled=selected != "__new__", placeholder="vd: cost-advantage")
        c1, c2 = st.columns(2)
        pillar_type = c1.selectbox("Nhóm", PILLAR_TYPES, index=PILLAR_TYPES.index(current.get("pillar_type", "business")), format_func=_label)
        status = c2.selectbox("Trạng thái", PILLAR_STATUSES, index=PILLAR_STATUSES.index(current.get("status", "research_gap")), format_func=_label)
        statement = st.text_area("Luận điểm *", value=str(current.get("statement_text") or ""))
        falsification = st.text_area("Falsification test *", value=str(current.get("falsification_test") or ""),
                                     help="Quan sát nào sẽ chứng minh luận điểm này sai?")
        c1, c2 = st.columns(2)
        with c1:
            support = _evidence_picker("Supporting evidence", evidence, key=f"pillar_support_{review['id']}", current=current.get("supporting_evidence_id"))
        with c2:
            contradict = _evidence_picker("Contradicting evidence", evidence, key=f"pillar_contra_{review['id']}", current=current.get("contradicting_evidence_id"))
        c1, c2 = st.columns(2)
        confidence = c1.slider("Confidence", 1, 5, int(current.get("confidence") or 3))
        materiality = c2.slider("Materiality", 1, 5, int(current.get("materiality") or 3))
        reason = st.text_input("Lý do version mới *", disabled=selected == "__new__")
        submitted = st.form_submit_button("Lưu thesis pillar", type="primary", use_container_width=True)
    if submitted:
        try:
            save_thesis_pillar(
                repo, company_ref_id=company_ref_id, review_id=review["id"], pillar_key=key,
                pillar_type=pillar_type, statement_text=statement, status=status,
                falsification_test=falsification, confidence=confidence, materiality=materiality,
                supporting_evidence_id=support, contradicting_evidence_id=contradict,
                change_reason=reason, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def _render_risks(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    risks = bundle["risk_register"]
    _df(risks, "Chưa có risk register item.")
    if review["status"] == "completed" or bundle["decision"]:
        return
    by_key = {row["risk_key"]: row for row in risks}
    with repo._conn() as c:
        rules = [dict(row) for row in c.execute(
            "SELECT * FROM monitoring_rules WHERE review_id=? AND active=1 AND NOT EXISTS("
            "SELECT 1 FROM monitoring_rules n WHERE n.review_id=monitoring_rules.review_id "
            "AND n.rule_key=monitoring_rules.rule_key AND n.version_no>monitoring_rules.version_no) "
            "ORDER BY materiality DESC,title", (int(review["id"]),),
        )]
    rule_by_id = {int(row["id"]): row for row in rules}
    with st.form(f"phase7_risk_{review['id']}"):
        selected = st.selectbox("Risk", ["__new__"] + list(by_key),
                                format_func=lambda value: "Risk mới" if value == "__new__" else f"{value} · v{by_key[value]['version_no']}")
        current = by_key.get(selected, {})
        key = st.text_input("Risk key", value="" if selected == "__new__" else selected,
                            disabled=selected != "__new__", placeholder="vd: urea-spread-collapse")
        c1, c2 = st.columns(2)
        category = c1.selectbox("Nhóm", RISK_CATEGORIES, index=RISK_CATEGORIES.index(current.get("risk_category", "business")), format_func=_label)
        status = c2.selectbox("Trạng thái", RISK_STATUSES, index=RISK_STATUSES.index(current.get("status", "open")), format_func=_label)
        statement = st.text_area("Nội dung rủi ro *", value=str(current.get("statement_text") or ""))
        c1, c2, c3 = st.columns(3)
        probability = c1.slider("Xác suất", 1, 5, int(current.get("probability") or 3))
        impact = c2.slider("Tác động", 1, 5, int(current.get("impact") or 3))
        resilience = c3.slider("Khả năng chống chịu", 1, 5, int(current.get("resilience") or 3))
        mitigation = st.text_area("Biện pháp giảm thiểu *", value=str(current.get("mitigation") or ""))
        early_warning = st.text_area("Chỉ báo cảnh báo sớm *", value=str(current.get("early_warning") or ""))
        evidence_id = _evidence_picker("Exact evidence", evidence, key=f"risk_ev_{review['id']}", current=current.get("source_evidence_id"))
        rule_options = [0] + list(rule_by_id)
        current_rule = int(current.get("monitoring_rule_id") or 0)
        rule_index = rule_options.index(current_rule) if current_rule in rule_options else 0
        rule_id = st.selectbox("Monitoring rule", rule_options, index=rule_index,
                               format_func=lambda value: "— Chưa liên kết —" if value == 0 else f"#{value} · {rule_by_id[value]['title']}")
        reason = st.text_input("Lý do version mới *", disabled=selected == "__new__")
        submitted = st.form_submit_button("Lưu risk register", type="primary", use_container_width=True)
    if submitted:
        try:
            save_risk_register_item(
                repo, company_ref_id=company_ref_id, review_id=review["id"], risk_key=key,
                risk_category=category, statement_text=statement, probability=probability,
                impact=impact, resilience=resilience, mitigation=mitigation,
                early_warning=early_warning, status=status, source_evidence_id=evidence_id,
                monitoring_rule_id=rule_id or None, change_reason=reason, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def _render_decision(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    decision = bundle["decision"]
    if decision:
        st.success("Quyết định đã được analyst ký và là bất biến. Memo/pillar/risk của review này đã được niêm phong.")
        display = {key: value for key, value in decision.items() if key != "memo_snapshot_json"}
        st.dataframe(pd.DataFrame([display]), use_container_width=True, hide_index=True)
        with st.expander("Snapshot đã ký"):
            st.json(decision["memo_snapshot_json"])
    elif review["status"] == "completed":
        st.info("Review completed không có quyết định được ký trong Phase 7.")
    else:
        ready = bool(bundle["memos"] and bundle["thesis_pillars"] and bundle["risk_register"])
        if not ready:
            st.warning("Cần ít nhất 1 memo, 1 thesis pillar và 1 risk register item trước khi ký quyết định.")
        with st.form(f"phase7_decision_{review['id']}"):
            st.markdown("##### Analyst decision signature")
            choice = st.selectbox("Quyết định", INVESTMENT_DECISIONS, format_func=_label)
            reason = st.text_area("Lý do quyết định *")
            invalidation = st.text_area("Điều kiện vô hiệu hóa chính *")
            months = st.number_input("Thời hạn (tháng)", min_value=1, max_value=120, value=36)
            c1, c2, c3, c4 = st.columns(4)
            market = c1.number_input("Giá thị trường", min_value=0.0, value=None, step=100.0)
            low = c2.number_input("Intrinsic low", min_value=0.0, value=None, step=100.0)
            base = c3.number_input("Intrinsic base", min_value=0.0, value=None, step=100.0)
            high = c4.number_input("Intrinsic high", min_value=0.0, value=None, step=100.0)
            c1, c2 = st.columns(2)
            target = c1.number_input("Tỷ trọng mục tiêu (%)", min_value=0.0, max_value=100.0, value=None, step=0.5)
            maximum = c2.number_input("Tỷ trọng tối đa (%)", min_value=0.0, max_value=100.0, value=None, step=0.5)
            acknowledge = st.checkbox("Tôi đã đọc các research gap và bằng chứng phản chứng còn mở.")
            confirm = st.checkbox("Tôi là analyst và trực tiếp xác nhận quyết định này; app không đề xuất BUY/SELL.")
            submitted = st.form_submit_button("Ký quyết định bất biến", type="primary", use_container_width=True,
                                              disabled=not ready or not acknowledge or not confirm)
        if submitted:
            try:
                record_investment_decision(
                    repo, company_ref_id=company_ref_id, review_id=review["id"], decision=choice,
                    decision_reason=reason, time_horizon_months=months, primary_invalidation=invalidation,
                    market_price=market, intrinsic_low=low, intrinsic_base=base, intrinsic_high=high,
                    target_position_pct=target, max_position_pct=maximum,
                    acknowledged_gaps=acknowledge, analyst_confirmed=confirm, actor=actor,
                )
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))

    st.markdown("##### Post-decision review")
    _df(bundle["outcomes"], "Chưa có post-decision review.")
    if review["status"] == "completed":
        return
    decisions = list_investment_decisions(repo, company_ref_id)
    if not decisions:
        st.info("Chưa có quyết định lịch sử để đánh giá outcome.")
        return
    by_id = {int(row["id"]): row for row in decisions}
    with st.form(f"phase7_outcome_{review['id']}"):
        decision_id = st.selectbox("Quyết định gốc", list(by_id),
                                   format_func=lambda value: f"#{value} · {by_id[value]['as_of_date']} · {_label(by_id[value]['decision'])}")
        c1, c2, c3 = st.columns(3)
        as_of = c1.date_input("Ngày đánh giá", value=date.today())
        thesis_status = c2.selectbox("Trạng thái thesis", THESIS_STATUSES, format_func=_label)
        outcome = c3.selectbox("Outcome", OUTCOME_LABELS, format_func=_label)
        c1, c2 = st.columns(2)
        grade = c1.slider("Process grade", 1, 5, 3)
        price = c2.number_input("Giá thị trường", min_value=0.0, value=None, step=100.0)
        summary = st.text_area("Tóm tắt outcome *")
        lessons = st.text_area("Bài học quy trình *")
        evidence_id = _evidence_picker("Exact evidence", evidence, key=f"outcome_ev_{review['id']}")
        submitted = st.form_submit_button("Lưu post-decision review", type="primary", use_container_width=True)
    if submitted:
        try:
            add_decision_outcome_review(
                repo, decision_id=decision_id, company_ref_id=company_ref_id, review_id=review["id"],
                as_of_date=as_of, thesis_status=thesis_status, outcome_label=outcome,
                process_grade=grade, outcome_summary=summary, lessons_learned=lessons,
                market_price=price, source_evidence_id=evidence_id, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def render_investment_decision_journal(repo, company_ref_id: int, review, actor: str) -> None:
    st.markdown("### 📝 Investment Memo & Decision Journal — Phase 7")
    st.caption(
        "Memo có version → thesis/falsification → risk register → analyst ký quyết định → post-decision review. "
        "App không tự phát BUY/SELL và không ghi vào Q01–Q59."
    )
    if not review:
        st.info("Tạo hoặc chọn review để bắt đầu Investment Memo & Decision Journal.")
        return
    if review["status"] == "completed":
        st.warning("Review đã completed: Phase 7 chỉ đọc và đã được khóa trong immutable snapshot.")
    bundle = decision_journal_bundle(repo, int(review["id"]))
    evidence = _evidence_rows(repo, company_ref_id)
    view = st.radio(
        "Phase 7 view", ["Dashboard", "Investment Memo", "Thesis Pillars", "Risk Register", "Decision Journal"],
        horizontal=True, label_visibility="collapsed", key=f"phase7_view_{review['id']}",
    )
    if view == "Dashboard":
        _render_dashboard(bundle)
    elif view == "Investment Memo":
        _render_memo(repo, company_ref_id, review, actor, evidence, bundle)
    elif view == "Thesis Pillars":
        _render_pillars(repo, company_ref_id, review, actor, evidence, bundle)
    elif view == "Risk Register":
        _render_risks(repo, company_ref_id, review, actor, evidence, bundle)
    else:
        _render_decision(repo, company_ref_id, review, actor, evidence, bundle)


__all__ = ["render_investment_decision_journal"]
