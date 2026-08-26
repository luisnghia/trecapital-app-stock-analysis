from __future__ import annotations

"""Phase 6 Streamlit workspace for monitoring rules, observations and delta decisions."""

from datetime import date

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.monitoring_delta_review import (
    CADENCES,
    CHANGE_TYPES,
    COMPARISON_OPERATORS,
    DECISIONS,
    OBSERVATION_STATUSES,
    PROPOSED_ACTIONS,
    TRIGGER_TYPES,
    add_monitoring_observation,
    create_delta_item,
    monitoring_delta_bundle,
    record_delta_decision,
    save_monitoring_rule,
)


LABELS = {
    "continuous": "Liên tục", "weekly": "Hàng tuần", "monthly": "Hàng tháng",
    "quarterly": "Hàng quý", "annual": "Hàng năm", "event": "Theo sự kiện",
    "periodic": "Review định kỳ", "metric_threshold": "Ngưỡng chỉ tiêu", "filing": "Công bố mới",
    "guidance": "Guidance", "management": "Management", "industry": "Ngành/moat", "thesis": "Investment thesis",
    "none": "Không áp dụng", "lt": "<", "lte": "≤", "gt": ">", "gte": "≥",
    "abs_change_pct": "|Δ| %", "delta": "Δ tuyệt đối", "triggered": "Đã kích hoạt",
    "clear": "Không kích hoạt", "unknown": "Unknown", "research_gap": "Research gap",
    "new_evidence": "Bằng chứng mới", "metric_threshold": "Vượt ngưỡng", "periodic_review": "Review định kỳ",
    "carry_forward": "Giữ nguyên có xác nhận", "revise": "Sửa assessment", "no_change": "Không thay đổi",
    "dismiss": "Loại khỏi queue",
}


def _label(value: str) -> str:
    return LABELS.get(value, value)


def _evidence_rows(repo, company_ref_id: int) -> list[dict]:
    with repo._conn() as c:
        return [dict(row) for row in c.execute(
            """SELECT e.id,e.evidence_type,e.excerpt,e.verification_status,s.title AS source_title
            FROM research_evidence e JOIN research_sources s ON s.id=e.source_id
            WHERE e.company_ref_id=? AND s.status='active'
            AND NOT EXISTS(SELECT 1 FROM research_evidence n WHERE n.source_id=e.source_id
              AND n.evidence_key=e.evidence_key AND n.version_no>e.version_no)
            ORDER BY e.id DESC LIMIT 300""",
            (company_ref_id,),
        )]


def _evidence_picker(label: str, rows: list[dict], *, key: str) -> int | None:
    options = [0] + [int(row["id"]) for row in rows]
    by_id = {int(row["id"]): row for row in rows}

    def display(value: int) -> str:
        if value == 0:
            return "— Chưa liên kết —"
        row = by_id[value]
        excerpt = str(row.get("excerpt") or "").replace("\n", " ")
        return f"#{value} · {row['evidence_type']} · {excerpt[:110]}"

    selected = st.selectbox(label, options, format_func=display, key=key)
    return None if selected == 0 else int(selected)


def _df(rows: list[dict], *, empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def _render_dashboard(review, bundle: dict) -> None:
    summary = bundle["summary"]
    cols = st.columns(5)
    cols[0].metric("Rule đang hoạt động", summary["active_rules"])
    cols[1].metric("Trigger", summary["triggered_observations"])
    cols[2].metric("Delta đang mở", summary["open_delta_items"])
    cols[3].metric("Delta đã đóng", summary["closed_delta_items"])
    cols[4].metric("Unknown/gap", summary["research_gaps"])
    if review["review_type"] != "delta":
        st.info("Monitoring dùng được trong review hiện tại. Để xử lý thay đổi so với kỳ trước, hãy tạo review loại delta.")
    elif not review.get("prior_review_id"):
        st.warning("Delta review chưa có prior completed review; queue sẽ bị khóa để tránh so sánh sai baseline.")
    st.markdown("##### Trigger gần nhất")
    triggered = [row for row in bundle["observations"] if row["observation_status"] == "triggered"]
    _df(triggered[:20], empty="Chưa có trigger.")
    st.markdown("##### Delta queue đang mở")
    _df([row for row in bundle["delta_items"] if not row.get("decision_id")], empty="Không có delta item đang mở.")


def _render_rules(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    rules = bundle["rules"]
    _df(rules, empty="Chưa có monitoring rule.")
    if review["status"] == "completed":
        return
    with st.form(f"monitoring_rule_{review['id']}"):
        st.markdown("##### Tạo rule / append version")
        existing = {str(row["rule_key"]): row for row in rules}
        selected = st.selectbox("Rule", ["__new__"] + list(existing), format_func=lambda v: "Rule mới" if v == "__new__" else f"{v} · {existing[v]['title']}")
        current = existing.get(selected, {})
        questions = repo.list_questions()
        qids = [row["question_id"] for row in questions]
        default_q = current.get("question_id", "Q01")
        question_id = st.selectbox("Question ID", qids, index=qids.index(default_q) if default_q in qids else 0,
                                   disabled=selected != "__new__")
        rule_key = st.text_input("Rule key", value="" if selected == "__new__" else selected,
                                 disabled=selected != "__new__", placeholder="vd: quarterly-roic")
        title = st.text_input("Tiêu đề *", value=str(current.get("title") or ""))
        description = st.text_area("Nội dung theo dõi *", value=str(current.get("description") or ""))
        c1, c2, c3 = st.columns(3)
        cadence = c1.selectbox("Tần suất", CADENCES, index=CADENCES.index(current.get("cadence", "quarterly")), format_func=_label)
        trigger_type = c2.selectbox("Loại trigger", TRIGGER_TYPES, index=TRIGGER_TYPES.index(current.get("trigger_type", "periodic")), format_func=_label)
        materiality = c3.slider("Materiality", 1, 5, int(current.get("materiality") or 3))
        c1, c2, c3 = st.columns(3)
        metric_key = c1.text_input("Metric key", value=str(current.get("metric_key") or ""))
        op = c2.selectbox("Toán tử", COMPARISON_OPERATORS,
                          index=COMPARISON_OPERATORS.index(current.get("comparison_operator", "none")), format_func=_label)
        threshold = c3.number_input("Ngưỡng", value=current.get("threshold_value"), step=0.1)
        c1, c2 = st.columns([1, 2])
        unit = c1.text_input("Đơn vị", value=str(current.get("threshold_unit") or ""))
        active = c1.checkbox("Đang hoạt động", value=bool(current.get("active", 1)))
        with c2:
            evidence_id = _evidence_picker("Exact evidence", evidence, key=f"rule_evidence_{review['id']}")
            reason = st.text_input("Lý do version mới *", disabled=selected == "__new__")
        submitted = st.form_submit_button("Lưu monitoring rule", type="primary", use_container_width=True)
    if submitted:
        try:
            save_monitoring_rule(
                repo, company_ref_id=company_ref_id, review_id=review["id"], question_id=question_id,
                title=title, description=description, cadence=cadence, trigger_type=trigger_type,
                rule_key=rule_key if selected == "__new__" else selected, metric_key=metric_key,
                comparison_operator=op, threshold_value=threshold, threshold_unit=unit,
                materiality=materiality, active=active, source_evidence_id=evidence_id,
                change_reason=reason, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def _render_observations(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    observations = bundle["observations"]
    _df(observations, empty="Chưa có observation.")
    rules = [row for row in bundle["rules"] if row["active"]]
    if review["status"] == "completed" or not rules:
        if not rules:
            st.info("Cần ít nhất một monitoring rule đang hoạt động.")
        return
    by_id = {int(row["id"]): row for row in rules}
    with st.form(f"monitoring_observation_{review['id']}"):
        rule_id = st.selectbox("Rule", list(by_id), format_func=lambda value: f"{by_id[value]['question_id']} · {by_id[value]['title']}")
        c1, c2, c3 = st.columns(3)
        observed_at = c1.date_input("Ngày quan sát", value=date.today())
        as_of_date = c2.date_input("Kỳ dữ liệu", value=date.today())
        status = c3.selectbox("Trạng thái", OBSERVATION_STATUSES, format_func=_label)
        c1, c2 = st.columns(2)
        value = c1.number_input("Giá trị", value=None, step=0.1)
        unit = c2.text_input("Đơn vị")
        summary = st.text_area("Tóm tắt quan sát *")
        evidence_id = _evidence_picker("Exact evidence * khi triggered/clear", evidence, key=f"obs_evidence_{review['id']}")
        c1, c2 = st.columns(2)
        confidence = c1.slider("Confidence", 1, 5, 3)
        materiality = c2.slider("Materiality", 1, 5, int(by_id[rule_id]["materiality"]))
        submitted = st.form_submit_button("Lưu observation", type="primary", use_container_width=True)
    if submitted:
        try:
            add_monitoring_observation(
                repo, company_ref_id=company_ref_id, review_id=review["id"], rule_id=rule_id,
                observed_at=observed_at, as_of_date=as_of_date, observation_status=status,
                summary=summary, observed_value=value, observed_unit=unit,
                source_evidence_id=evidence_id, confidence=confidence, materiality=materiality, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def _render_delta_queue(repo, company_ref_id: int, review, actor: str, evidence: list[dict], bundle: dict) -> None:
    items = bundle["delta_items"]
    _df(items, empty="Chưa có delta item.")
    if review["status"] == "completed":
        return
    if review["review_type"] != "delta" or not review.get("prior_review_id"):
        st.warning("Khu vực này chỉ mở cho delta review có prior completed review.")
        return
    questions = repo.list_questions()
    qids = [row["question_id"] for row in questions]
    observations = bundle["observations"]
    obs_by_id = {int(row["id"]): row for row in observations}
    with st.form(f"delta_item_{review['id']}"):
        st.markdown("##### Tạo delta item")
        question_id = st.selectbox("Question ID", qids)
        matching = [0] + [oid for oid, row in obs_by_id.items() if row["question_id"] == question_id]
        observation_id = st.selectbox("Observation", matching, format_func=lambda value: "— Không liên kết —" if value == 0 else f"#{value} · {obs_by_id[value]['summary'][:100]}")
        c1, c2 = st.columns(2)
        change_type = c1.selectbox("Loại thay đổi", CHANGE_TYPES, format_func=_label)
        action = c2.selectbox("Hành động đề xuất", PROPOSED_ACTIONS, format_func=_label)
        rationale = st.text_area("Rationale *")
        evidence_id = _evidence_picker("Exact evidence", evidence, key=f"delta_evidence_{review['id']}")
        c1, c2 = st.columns(2)
        confidence = c1.slider("Confidence", 1, 5, 3)
        materiality = c2.slider("Materiality", 1, 5, 3)
        create = st.form_submit_button("Đưa vào delta queue", type="primary", use_container_width=True)
    if create:
        try:
            create_delta_item(
                repo, company_ref_id=company_ref_id, review_id=review["id"], question_id=question_id,
                change_type=change_type, proposed_action=action, rationale=rationale,
                observation_id=observation_id or None, source_evidence_id=evidence_id,
                confidence=confidence, materiality=materiality, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))

    open_items = [row for row in items if not row.get("decision_id")]
    if not open_items:
        return
    item_by_id = {int(row["id"]): row for row in open_items}
    with st.form(f"delta_decision_{review['id']}"):
        st.markdown("##### Đóng delta item sau khi cập nhật Analyst Workspace")
        item_id = st.selectbox("Delta item", list(item_by_id), format_func=lambda value: f"#{value} · {item_by_id[value]['question_id']} · {item_by_id[value]['rationale'][:90]}")
        item = item_by_id[item_id]
        decision = st.selectbox("Quyết định", DECISIONS, format_func=_label)
        with repo._conn() as c:
            assessments = [dict(row) for row in c.execute(
                "SELECT * FROM analyst_assessments WHERE review_id=? AND question_id=? ORDER BY version_no DESC,id DESC",
                (review["id"], item["question_id"]),
            )]
        by_assessment = {int(row["id"]): row for row in assessments}
        assessment_id = st.selectbox(
            "Assessment kết quả", [0] + list(by_assessment),
            format_func=lambda value: "— Chỉ dùng khi dismiss —" if value == 0 else f"#{value} · {by_assessment[value]['status']} · v{by_assessment[value]['version_no']}",
        )
        reason = st.text_area("Lý do quyết định *")
        decide = st.form_submit_button("Ghi quyết định bất biến", type="primary", use_container_width=True)
    if decide:
        try:
            record_delta_decision(
                repo, delta_item_id=item_id, decision=decision, decision_reason=reason,
                resulting_assessment_id=assessment_id or None, actor=actor,
            )
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))


def render_monitoring_delta_review(repo, company_ref_id: int, review, actor: str) -> None:
    st.markdown("### 📡 Monitoring & Delta Review — Phase 6")
    st.caption(
        "Rule → observation có evidence → delta queue → analyst cập nhật Q01–Q59 → quyết định bất biến. "
        "Phase 6 không tự ghi assessment."
    )
    if not review:
        st.info("Tạo hoặc chọn review để bắt đầu Monitoring & Delta Review.")
        return
    if review["status"] == "completed":
        st.warning("Review đã completed: Phase 6 chỉ đọc và đã được khóa trong immutable snapshot.")
    bundle = monitoring_delta_bundle(repo, int(review["id"]))
    evidence = _evidence_rows(repo, company_ref_id)
    view = st.radio(
        "Phase 6 view", ["Dashboard", "Monitoring Rules", "Observations", "Delta Queue"],
        horizontal=True, label_visibility="collapsed", key=f"phase6_view_{review['id']}",
    )
    if view == "Dashboard":
        _render_dashboard(review, bundle)
    elif view == "Monitoring Rules":
        _render_rules(repo, company_ref_id, review, actor, evidence, bundle)
    elif view == "Observations":
        _render_observations(repo, company_ref_id, review, actor, evidence, bundle)
    else:
        _render_delta_queue(repo, company_ref_id, review, actor, evidence, bundle)


__all__ = ["render_monitoring_delta_review"]
