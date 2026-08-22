from __future__ import annotations

from datetime import date
import time
from typing import Any

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.evidence_workspace import list_latest_evidence
from ..services.management_intelligence import (
    APPOINTMENT_TYPES,
    CORROBORATION_STATUSES,
    DEFAULT_TRACK_QUESTIONS,
    HORIZONS,
    HUMAN_SOURCE_CATEGORIES,
    MANAGEMENT_DIMENSIONS,
    MANAGEMENT_QUESTION_IDS,
    SIGNAL_STATUSES,
    TIMELINE_EVENT_TYPES,
    TRACK_RECORD_TYPES,
    TRACK_RESULT_STATUSES,
    VERIFICATION_STATUSES,
    add_timeline_event,
    list_management_signals,
    list_people,
    list_timeline_events,
    list_track_records,
    management_research_bundle,
    save_management_signal,
    save_person_version,
    save_track_record,
)


APPOINTMENT_LABELS = {
    "founder": "Nhà sáng lập", "internal": "Thăng tiến nội bộ",
    "external": "Tuyển từ bên ngoài", "unknown": "Chưa xác định",
}
TIMELINE_LABELS = {
    "joined": "Gia nhập", "promoted": "Thăng chức", "appointed": "Bổ nhiệm",
    "role_changed": "Đổi vai trò", "departed": "Rời đi", "board_change": "Thay đổi HĐQT",
    "ownership_change": "Thay đổi sở hữu", "compensation_change": "Thay đổi lương thưởng",
    "insider_trade": "Giao dịch nội bộ", "other": "Khác",
}
TRACK_LABELS = {
    "compensation_ownership": "Lương thưởng & sở hữu",
    "insider_transaction": "Giao dịch cổ phiếu nội bộ",
    "guidance": "Guidance CEO/CFO",
    "capital_allocation": "Phân bổ vốn",
    "buyback": "Mua lại cổ phiếu",
    "ma_decision": "Quyết định M&A",
    "ma_outcome": "Hậu kiểm M&A",
    "integrity": "Moment of integrity",
    "communication": "Giao tiếp & nhất quán",
    "human_intelligence": "Human Intelligence",
}
SOURCE_CATEGORY_LABELS = {
    "company": "Doanh nghiệp / tài liệu chính thức", "customer": "Khách hàng",
    "competitor": "Đối thủ", "supplier": "Nhà cung cấp", "employee": "Nhân viên/cựu nhân viên",
    "industry_insider": "Người trong ngành", "academic": "Giảng viên/chuyên gia học thuật",
    "headhunter": "Headhunter", "regulator": "Cơ quan quản lý", "other": "Nguồn khác",
}
SIGNAL_LABELS = {
    "supported": "Có bằng chứng ủng hộ", "contradicted": "Có bằng chứng phản bác",
    "mixed": "Bằng chứng trái chiều", "research_gap": "Research gap",
    "not_reviewed": "Chưa nghiên cứu",
}


def _management_cache_key(review_id: int) -> str:
    return f"_management_bundle_fast_{int(review_id)}"


def _invalidate_management_cache(review_id: int) -> None:
    st.session_state.pop(_management_cache_key(review_id), None)


def _management_bundle_cached(repo, review_id: int, *, ttl_seconds: float = 30.0) -> dict[str, Any]:
    key = _management_cache_key(review_id)
    cached = st.session_state.get(key)
    now = time.monotonic()
    if isinstance(cached, dict) and now - float(cached.get("loaded_at", 0.0)) <= ttl_seconds:
        return cached["bundle"]
    bundle = management_research_bundle(repo, int(review_id))
    st.session_state[key] = {"loaded_at": now, "bundle": bundle}
    return bundle


def _evidence_options(company_ref_id: int) -> tuple[list[int], dict[int, str]]:
    cache_key = f"_management_evidence_fast_{int(company_ref_id)}"
    cached = st.session_state.get(cache_key)
    now = time.monotonic()
    if isinstance(cached, dict) and now - float(cached.get("loaded_at", 0.0)) <= 30.0:
        rows = cached["rows"]
    else:
        rows = list_latest_evidence(st.session_state["_management_repo"], company_ref_id)
        st.session_state[cache_key] = {"loaded_at": now, "rows": rows}
    labels = {0: "— Chưa gắn evidence (không tính evidence coverage) —"}
    for row in rows:
        excerpt = str(row.get("excerpt") or "").replace("\n", " ")
        labels[int(row["id"])] = (
            f"Evidence #{row['id']} · {row.get('source_title') or 'Nguồn'} · {excerpt[:90]}"
        )
    return [0] + [int(row["id"]) for row in rows], labels


def _evidence_select(label: str, company_ref_id: int, *, key: str) -> int | None:
    options, labels = _evidence_options(company_ref_id)
    selected = st.selectbox(label, options, format_func=lambda value: labels[value], key=key)
    return None if selected == 0 else int(selected)


def _render_coverage(review_id: int, *, signals: list[dict[str, Any]] | None = None) -> None:
    if signals is None:
        signals = list_management_signals(st.session_state["_management_repo"], review_id)
    by_question: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        by_question.setdefault(signal["question_id"], []).append(signal)
    rows = []
    for qid in MANAGEMENT_QUESTION_IDS:
        items = by_question.get(qid, [])
        researched = [item for item in items if item["signal_status"] not in {"research_gap", "not_reviewed"}]
        evidence_count = sum(bool(item.get("source_evidence_id")) for item in researched)
        rows.append({
            "Q": qid,
            "Nội dung": MANAGEMENT_DIMENSIONS[qid],
            "Trạng thái structured research": ", ".join(sorted({SIGNAL_LABELS[item["signal_status"]] for item in items})) if items else "Research gap",
            "Subjects": len({item["subject_key"] for item in items}),
            "Evidence-backed": evidence_count,
            "Final assessment": "Analyst Workspace",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=610)


def _render_people_and_timeline(
    repo,
    company_ref_id: int,
    review: dict[str, Any],
    actor: str,
    *,
    people: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, Any]] | None = None,
) -> None:
    review_id = int(review["id"])
    locked = review["status"] == "completed"
    people = list_people(repo, review_id) if people is None else people
    st.markdown("##### Hồ sơ lãnh đạo chủ chốt")
    if people:
        frame = pd.DataFrame([{
            "Person key": row["person_key"], "Họ tên": row["full_name"],
            "Chức danh": row["current_title"], "Nguồn bổ nhiệm": APPOINTMENT_LABELS[row["appointment_type"]],
            "Bắt đầu": row.get("start_date") or "—", "Kết thúc": row.get("end_date") or "—",
            "Key manager": "Có" if row["is_key_manager"] else "Không",
            "Sở hữu": "—" if row.get("ownership_pct") is None else f"{row['ownership_pct']:.2f}%",
            "Evidence": row.get("source_evidence_id") or "—", "Version": row["version_no"],
        } for row in people])
        st.dataframe(frame, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có hồ sơ management. Nên bắt đầu với tối đa 5 lãnh đạo chủ chốt.")

    with st.expander("➕ Thêm/cập nhật hồ sơ manager", expanded=not people and not locked):
        with st.form(f"management_person_form_{review_id}"):
            left, right = st.columns(2)
            person_key = left.text_input("Person key *", help="Khóa ổn định, ví dụ: nguyen-van-a")
            full_name = right.text_input("Họ tên *")
            current_title = left.text_input("Chức danh hiện tại *")
            appointment_type = right.selectbox(
                "Nguồn bổ nhiệm", APPOINTMENT_TYPES, format_func=lambda value: APPOINTMENT_LABELS[value]
            )
            start_date = left.text_input("Ngày bắt đầu (YYYY-MM-DD)")
            end_date = right.text_input("Ngày kết thúc (nếu có)")
            is_key = left.checkbox("Lãnh đạo chủ chốt", value=True)
            ownership = right.number_input("Tỷ lệ sở hữu (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.01)
            compensation = st.text_area("Lương thưởng/sở hữu và cơ chế khuyến khích")
            verification = left.selectbox("Trạng thái xác minh", VERIFICATION_STATUSES)
            evidence_id = _evidence_select("Evidence chính xác", company_ref_id, key=f"person_evidence_{review_id}")
            change_reason = st.text_area("Lý do tạo version mới (bắt buộc nếu person key đã tồn tại)")
            submitted = st.form_submit_button("Lưu hồ sơ append-only", disabled=locked, use_container_width=True)
        if submitted:
            try:
                save_person_version(
                    repo, company_ref_id=company_ref_id, review_id=review_id, person_key=person_key,
                    full_name=full_name, current_title=current_title, appointment_type=appointment_type,
                    start_date=start_date or None, end_date=end_date or None, is_key_manager=is_key,
                    ownership_pct=ownership, compensation_note=compensation,
                    source_evidence_id=evidence_id, verification_status=verification,
                    change_reason=change_reason, actor=actor,
                )
                _invalidate_management_cache(review_id)
                st.success("Đã lưu version hồ sơ manager.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))

    st.markdown("##### Table 8.1 — Management Tenure Timeline")
    st.caption(
        "Dựng chronology tối thiểu 5–10 năm cho nhóm lãnh đạo chủ chốt. Turnover là tín hiệu cần điều tra, "
        "không phải kết luận tự động về chất lượng management."
    )
    timeline = list_timeline_events(repo, review_id) if timeline is None else timeline
    if timeline:
        st.dataframe(pd.DataFrame([{
            "Ngày": row["event_date"], "Person key": row["person_key"],
            "Sự kiện": TIMELINE_LABELS[row["event_type"]], "Tổ chức": row["organization"],
            "Vai trò": row["role_title"], "External hire": "Có" if row["external_hire"] else "Không",
            "Evidence": row.get("source_evidence_id") or "—", "Tóm tắt": row["event_summary"],
        } for row in timeline]), use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có timeline event.")

    with st.expander("➕ Thêm timeline event"):
        with st.form(f"management_timeline_form_{review_id}"):
            left, right = st.columns(2)
            person_key = left.text_input("Person key *", key=f"timeline_person_{review_id}")
            event_date = right.date_input("Ngày sự kiện *", value=date.today(), key=f"timeline_date_{review_id}")
            event_type = left.selectbox(
                "Loại sự kiện", TIMELINE_EVENT_TYPES, format_func=lambda value: TIMELINE_LABELS[value]
            )
            external = right.checkbox("Tuyển từ bên ngoài")
            organization = left.text_input("Tổ chức *")
            role_title = right.text_input("Chức danh *", key=f"timeline_role_{review_id}")
            summary = st.text_area("Mô tả sự kiện và bối cảnh *")
            confidence = left.slider("Độ tin cậy", 1, 5, 3)
            evidence_id = _evidence_select("Evidence chính xác", company_ref_id, key=f"timeline_evidence_{review_id}")
            submitted = st.form_submit_button("Lưu timeline event", disabled=locked, use_container_width=True)
        if submitted:
            try:
                add_timeline_event(
                    repo, company_ref_id=company_ref_id, review_id=review_id, person_key=person_key,
                    event_date=event_date, event_type=event_type, organization=organization,
                    role_title=role_title, event_summary=summary, external_hire=external,
                    source_evidence_id=evidence_id, confidence=confidence, actor=actor,
                )
                _invalidate_management_cache(review_id)
                st.success("Đã lưu timeline event.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


def _render_signals(
    repo,
    company_ref_id: int,
    review: dict[str, Any],
    actor: str,
    *,
    signals: list[dict[str, Any]] | None = None,
) -> None:
    review_id = int(review["id"])
    locked = review["status"] == "completed"
    st.markdown("##### Table 7.1 — Lion vs Hyena & Management Character Matrix")
    st.warning(
        "Lion/Hyena là khung định tính để kiểm tra hành vi xây tổ chức dài hạn, chia sẻ credit, phát triển người kế cận "
        "và hành xử khi khó khăn. Không gắn nhãn một con người từ vài phát biểu; ưu tiên hành động quan sát được qua nhiều chu kỳ."
    )
    signals = list_management_signals(repo, review_id) if signals is None else signals
    if signals:
        st.dataframe(pd.DataFrame([{
            "Q": row["question_id"], "Dimension": MANAGEMENT_DIMENSIONS[row["question_id"]],
            "Subject": row["subject_key"], "Status": SIGNAL_LABELS[row["signal_status"]],
            "Signal -2..+2": row.get("signal_score"), "Confidence": row["confidence"],
            "Materiality": row["materiality"], "Evidence": row.get("source_evidence_id") or "—",
            "Rationale": row["rationale"], "Version": row["version_no"],
        } for row in signals]), use_container_width=True, hide_index=True, height=520)
    else:
        st.info("Chưa có structured management signal; toàn bộ 22 câu đang là Research gap.")

    with st.expander("➕ Ghi structured signal cho Q33–Q52/Q58–Q59", expanded=not signals and not locked):
        with st.form(f"management_signal_form_{review_id}"):
            question_id = st.selectbox(
                "Câu hỏi *", MANAGEMENT_QUESTION_IDS,
                format_func=lambda value: f"{value} — {MANAGEMENT_DIMENSIONS[value]}",
            )
            subject_key = st.text_input("Subject key *", value="management-team")
            left, right = st.columns(2)
            signal_status = left.selectbox(
                "Trạng thái", SIGNAL_STATUSES, format_func=lambda value: SIGNAL_LABELS[value]
            )
            score = right.selectbox("Signal score", [None, -2, -1, 0, 1, 2], index=0)
            confidence = left.slider("Độ tin cậy", 1, 5, 3, key=f"signal_conf_{review_id}")
            materiality = right.slider("Mức độ trọng yếu", 1, 5, 3, key=f"signal_mat_{review_id}")
            rationale = st.text_area("Rationale dựa trên hành động/bằng chứng *")
            evidence_id = _evidence_select("Evidence chính xác", company_ref_id, key=f"signal_evidence_{review_id}")
            change_reason = st.text_area("Lý do thay đổi score (bắt buộc nếu score thay đổi)")
            submitted = st.form_submit_button("Lưu signal append-only", disabled=locked, use_container_width=True)
        if submitted:
            try:
                save_management_signal(
                    repo, company_ref_id=company_ref_id, review_id=review_id,
                    question_id=question_id, subject_key=subject_key, signal_status=signal_status,
                    rationale=rationale, signal_score=score, confidence=confidence,
                    materiality=materiality, source_evidence_id=evidence_id,
                    change_reason=change_reason, actor=actor,
                )
                _invalidate_management_cache(review_id)
                st.success("Đã lưu structured management signal. Final assessment chưa bị thay đổi.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


def _render_track_records(
    repo,
    company_ref_id: int,
    review: dict[str, Any],
    actor: str,
    *,
    records: list[dict[str, Any]] | None = None,
) -> None:
    review_id = int(review["id"])
    locked = review["status"] == "completed"
    st.markdown("##### Guidance, Capital Allocation, M&A & Human Intelligence")
    st.caption(
        "Hậu kiểm guidance và M&A theo mốc hiện tại/1/3/5 năm. Human Intelligence cần phân loại nguồn và kiểm chứng chéo; "
        "nguồn đơn lẻ không được tự động trở thành kết luận."
    )
    records = list_track_records(repo, review_id) if records is None else records
    if records:
        st.dataframe(pd.DataFrame([{
            "Loại": TRACK_LABELS[row["record_type"]], "Ngày": row.get("event_date") or "—",
            "Subject": row["subject_key"], "Tiêu đề": row["title"],
            "Nội dung": "🔒 Nội dung bảo mật" if row["confidential"] else row["statement_text"],
            "Horizon": row["horizon"], "Kết quả": row["result_status"],
            "Nguồn": SOURCE_CATEGORY_LABELS[row["source_category"]],
            "Corroboration": row["corroboration_status"], "Q": ", ".join(row["question_ids"]),
            "Evidence": row.get("source_evidence_id") or "—", "Version": row["version_no"],
        } for row in records]), use_container_width=True, hide_index=True, height=520)
    else:
        st.info("Chưa có management track record.")

    with st.expander("➕ Thêm track record / Human Intelligence"):
        record_type = st.selectbox(
            "Loại record", TRACK_RECORD_TYPES, format_func=lambda value: TRACK_LABELS[value],
            key=f"management_track_type_{review_id}",
        )
        with st.form(f"management_track_form_{review_id}_{record_type}"):
            defaults = list(DEFAULT_TRACK_QUESTIONS[record_type])
            question_ids = st.multiselect(
                "Liên kết câu hỏi management *", MANAGEMENT_QUESTION_IDS, default=defaults,
                format_func=lambda value: f"{value} — {MANAGEMENT_DIMENSIONS[value]}",
                key=f"track_questions_{review_id}_{record_type}",
            )
            left, right = st.columns(2)
            subject_key = left.text_input("Subject key *", value="management-team", key=f"track_subject_{review_id}")
            event_date = right.date_input("Ngày sự kiện", value=date.today(), key=f"track_date_{review_id}")
            title = st.text_input("Tiêu đề *", key=f"track_title_{review_id}")
            statement = st.text_area("Sự kiện / phát biểu / quyết định *")
            expected = st.text_area("Kết quả kỳ vọng / rationale ban đầu")
            actual = st.text_area("Kết quả thực tế / hậu kiểm")
            result_status = left.selectbox("Kết quả", TRACK_RESULT_STATUSES, index=TRACK_RESULT_STATUSES.index("unknown"))
            horizon = right.selectbox("Mốc hậu kiểm", HORIZONS)
            source_category = left.selectbox(
                "Nhóm nguồn", HUMAN_SOURCE_CATEGORIES,
                format_func=lambda value: SOURCE_CATEGORY_LABELS[value],
            )
            corroboration = right.selectbox("Kiểm chứng chéo", CORROBORATION_STATUSES)
            credibility = left.slider("Độ tin cậy nguồn", 1, 5, 3, key=f"track_cred_{review_id}")
            confidential = right.checkbox("Nội dung Human Intelligence bảo mật")
            evidence_id = _evidence_select("Evidence chính xác", company_ref_id, key=f"track_evidence_{review_id}")
            submitted = st.form_submit_button("Lưu track record append-only", disabled=locked, use_container_width=True)
        if submitted:
            try:
                save_track_record(
                    repo, company_ref_id=company_ref_id, review_id=review_id,
                    record_type=record_type, title=title, statement_text=statement,
                    question_ids=question_ids, subject_key=subject_key, event_date=event_date,
                    expected_outcome=expected, actual_outcome=actual, result_status=result_status,
                    horizon=horizon, source_category=source_category, credibility=credibility,
                    corroboration_status=corroboration, confidential=confidential,
                    source_evidence_id=evidence_id, actor=actor,
                )
                _invalidate_management_cache(review_id)
                st.success("Đã lưu management track record. Không có final assessment nào bị ghi tự động.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


def render_management_intelligence(
    repo,
    company_ref_id: int,
    review: dict[str, Any] | None,
    actor: str,
) -> None:
    st.markdown("### 👥 Management & Human Intelligence — Phase 5")
    st.info(
        "Workspace này tổ chức bằng chứng cho Q33–Q52 và Q58–Q59. Structured signal không phải final assessment, "
        "không tự gắn nhãn Lion/Hyena và không ghi đè câu trả lời của analyst."
    )
    if not review:
        st.warning("Hãy tạo/chọn một review trước khi nghiên cứu management.")
        return

    st.session_state["_management_repo"] = repo
    review_id = int(review["id"])
    bundle = _management_bundle_cached(repo, review_id)
    summary = bundle["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Management coverage", f"{summary['coverage_pct'] * 100:.1f}%", f"{len(summary['covered_questions'])}/22 câu")
    c2.metric("Evidence coverage", f"{summary['evidence_coverage_pct'] * 100:.1f}%", f"{len(summary['evidence_backed_questions'])}/22 câu")
    c3.metric("Key managers", summary["key_manager_count"], f"{summary['timeline_event_count']} timeline event")
    c4.metric("Track records", summary["track_record_count"], f"{summary['human_intelligence_count']} Human Intel")
    if summary["key_manager_count"] < 5:
        st.warning("Table 8.1 chưa đủ 5 lãnh đạo chủ chốt; tiếp tục bổ sung hồ sơ/timeline 5–10 năm.")
    if summary["research_gaps"]:
        st.caption("Research gaps: " + ", ".join(summary["research_gaps"]))
    if review["status"] == "completed":
        st.warning("Review đã completed: toàn bộ Phase 5 chỉ đọc và đã được khóa trong immutable snapshot.")

    section = st.radio(
        "Management workspace",
        ["Coverage Q33–Q52/Q58–Q59", "People & Tenure", "Lion/Hyena & Signals", "Track Record & Human Intel"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"management_section_{company_ref_id}_{review_id}",
    )
    if section == "Coverage Q33–Q52/Q58–Q59":
        _render_coverage(review_id, signals=bundle["signals"])
    elif section == "People & Tenure":
        _render_people_and_timeline(
            repo, company_ref_id, review, actor,
            people=bundle["people"], timeline=bundle["timeline"],
        )
    elif section == "Lion/Hyena & Signals":
        _render_signals(repo, company_ref_id, review, actor, signals=bundle["signals"])
    else:
        _render_track_records(repo, company_ref_id, review, actor, records=bundle["track_records"])


__all__ = ["render_management_intelligence"]
