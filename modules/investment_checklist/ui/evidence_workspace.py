from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.evidence_workspace import (
    EVIDENCE_DIRECTIONS,
    EVIDENCE_TYPES,
    LINK_RELATIONSHIPS,
    SOURCE_TYPES,
    SOURCE_TYPE_LABELS,
    VERIFICATION_STATUSES,
    archive_source,
    create_evidence_version,
    create_source,
    evidence_coverage,
    evidence_summary,
    export_evidence_json,
    link_evidence_to_question,
    list_latest_evidence,
    list_review_evidence,
    list_sources,
    unlink_evidence_from_question,
)


EVIDENCE_SECTIONS = ("Coverage", "Nguồn", "Bằng chứng", "Liên kết Q01–Q59")
VERIFICATION_LABELS = {
    "unverified": "Chưa xác minh",
    "verified": "Đã xác minh",
    "disputed": "Có tranh luận / mâu thuẫn",
    "stale": "Đã cũ",
}
DIRECTION_LABELS = {
    "supports": "Ủng hộ thesis/nhận định",
    "contradicts": "Phản bác / mâu thuẫn",
    "context": "Bối cảnh trung tính",
}
RELATIONSHIP_LABELS = {
    "primary": "Bằng chứng chính",
    "supporting": "Bằng chứng bổ trợ",
    "context": "Bối cảnh",
    "contradicts": "Bằng chứng phản bác",
}


def _notify(message: str) -> None:
    st.session_state["evidence_workspace_message"] = message


def _invalidate_review_evidence(review_id: int) -> None:
    st.session_state.pop(f"_evidence_links_fast_{int(review_id)}", None)


def _rerun() -> None:
    try:
        st.rerun(scope="fragment")
    except (TypeError, ValueError):
        st.rerun()


def _source_label(source: dict) -> str:
    prefix = SOURCE_TYPE_LABELS.get(source.get("source_type"), source.get("source_type") or "Nguồn")
    date_text = source.get("document_date") or "không rõ ngày"
    return f"#{source['id']} · {prefix} · {date_text} · {source['title']}"


def _evidence_label(evidence: dict) -> str:
    excerpt = str(evidence.get("excerpt") or "").replace("\n", " ")
    if len(excerpt) > 90:
        excerpt = excerpt[:87] + "..."
    return f"E#{evidence['id']} · v{evidence['version_no']} · {evidence['source_title']} · {excerpt}"


def _render_summary(repo, review: dict | None) -> None:
    if not review:
        st.info("Tạo hoặc chọn review để theo dõi coverage và liên kết bằng chứng với Q01–Q59.")
        return
    summary = evidence_summary(repo, review["id"])
    cols = st.columns(5)
    cols[0].metric("Câu có evidence", f"{summary['covered_questions']}/59")
    cols[1].metric("Coverage", f"{summary['coverage_ratio'] * 100:.1f}%")
    cols[2].metric("Câu có verified", summary["verified_questions"])
    cols[3].metric("Active links", summary["active_links"])
    cols[4].metric("Mâu thuẫn", summary["contradictions"])


def _render_coverage(repo, review: dict | None) -> None:
    if not review:
        st.info("Chưa có review để tính coverage.")
        return
    rows = evidence_coverage(repo, review["id"])
    frame = pd.DataFrame(rows).rename(columns={
        "question_id": "Q",
        "group_name": "Nhóm",
        "question_vi": "Câu hỏi",
        "evidence_count": "Evidence",
        "verified_count": "Verified",
        "contradiction_count": "Mâu thuẫn",
        "max_materiality": "Trọng yếu cao nhất",
    })
    view = st.radio(
        "Lọc coverage", ("Tất cả Q01–Q59", "Chưa có evidence", "Có mâu thuẫn"),
        horizontal=True, key=f"evidence_coverage_filter_{review['id']}",
    )
    if view == "Chưa có evidence":
        frame = frame[frame["Evidence"] == 0]
    elif view == "Có mâu thuẫn":
        frame = frame[frame["Mâu thuẫn"] > 0]
    st.dataframe(
        frame[["Q", "Nhóm", "Câu hỏi", "Evidence", "Verified", "Mâu thuẫn", "Trọng yếu cao nhất"]],
        use_container_width=True, hide_index=True, height=520,
    )

    linked = list_review_evidence(repo, review["id"])
    if linked:
        st.markdown("##### Evidence package đang gắn với review")
        linked_df = pd.DataFrame(linked).rename(columns={
            "question_id": "Q", "source_title": "Nguồn", "excerpt": "Trích đoạn / sự kiện",
            "locator_text": "Vị trí", "verification_status": "Xác minh", "direction": "Chiều",
            "relationship": "Vai trò", "materiality": "Trọng yếu", "version_no": "Version",
        })
        st.dataframe(
            linked_df[["Q", "Nguồn", "Trích đoạn / sự kiện", "Vị trí", "Xác minh", "Chiều", "Vai trò", "Trọng yếu", "Version"]],
            use_container_width=True, hide_index=True, height=420,
        )
        st.download_button(
            "⬇️ Xuất Evidence Package JSON",
            data=export_evidence_json(repo, review["id"]),
            file_name=f"evidence_review_{review['id']}.json",
            mime="application/json",
            key=f"download_evidence_{review['id']}",
        )
    else:
        st.caption("Review chưa có evidence link.")


def _render_sources(repo, company_ref_id: int, actor: str) -> None:
    with st.form(f"create_source_{company_ref_id}", clear_on_submit=True):
        st.markdown("##### Thêm nguồn")
        c1, c2 = st.columns(2)
        source_type = c1.selectbox(
            "Loại nguồn", SOURCE_TYPES, format_func=lambda x: SOURCE_TYPE_LABELS[x],
        )
        reliability = c2.selectbox(
            "Độ tin cậy nguồn", [1, 2, 3, 4, 5], index=2,
            help="1 = rất thấp; 3 = cần đối chiếu; 5 = nguồn gốc/chính thức đã kiểm chứng.",
        )
        title = st.text_input("Tiêu đề nguồn *", max_chars=500)
        c3, c4 = st.columns(2)
        publisher = c3.text_input("Đơn vị phát hành", max_chars=300)
        url = c4.text_input("URL", max_chars=2000)
        c5, c6 = st.columns(2)
        document_date = c5.date_input("Ngày tài liệu", value=None)
        accessed_at = c6.date_input("Ngày truy cập", value=date.today())
        notes = st.text_area("Ghi chú nguồn", height=90)
        submitted = st.form_submit_button("Lưu nguồn", type="primary")
    if submitted:
        try:
            source_id = create_source(
                repo, company_ref_id=company_ref_id, source_type=source_type, title=title,
                publisher=publisher, url=url, document_date=document_date, accessed_at=accessed_at,
                reliability=reliability, notes=notes, actor=actor,
            )
            _notify(f"Đã tạo Source #{source_id}.")
            _rerun()
        except ValidationError as exc:
            st.error(str(exc))

    sources = list_sources(repo, company_ref_id, include_archived=True)
    if not sources:
        st.info("Chưa có nguồn.")
        return
    st.markdown("##### Danh mục nguồn")
    frame = pd.DataFrame(sources).rename(columns={
        "id": "Source ID", "source_type": "Loại", "title": "Tiêu đề", "publisher": "Nhà phát hành",
        "document_date": "Ngày tài liệu", "accessed_at": "Ngày truy cập", "reliability": "Tin cậy",
        "status": "Trạng thái", "url": "URL", "notes": "Ghi chú",
    })
    st.dataframe(
        frame[["Source ID", "Loại", "Tiêu đề", "Nhà phát hành", "Ngày tài liệu", "Ngày truy cập", "Tin cậy", "Trạng thái", "URL", "Ghi chú"]],
        use_container_width=True, hide_index=True, height=420,
    )
    active = [source for source in sources if source["status"] == "active"]
    if active:
        with st.expander("Lưu trữ nguồn không còn sử dụng"):
            source_id = st.selectbox("Nguồn", [s["id"] for s in active], format_func=lambda x: _source_label(next(s for s in active if s["id"] == x)))
            reason = st.text_input("Lý do lưu trữ *", key=f"archive_source_reason_{company_ref_id}")
            if st.button("Lưu trữ nguồn", disabled=not reason.strip(), key=f"archive_source_{company_ref_id}"):
                try:
                    archive_source(repo, source_id, reason=reason, actor=actor)
                    _notify(f"Đã lưu trữ Source #{source_id}; evidence lịch sử vẫn được giữ.")
                    _rerun()
                except ValidationError as exc:
                    st.error(str(exc))


def _render_evidence(repo, company_ref_id: int, actor: str) -> None:
    sources = list_sources(repo, company_ref_id)
    if not sources:
        st.info("Hãy tạo ít nhất một nguồn trước khi ghi bằng chứng.")
        return

    with st.form(f"create_evidence_{company_ref_id}", clear_on_submit=True):
        st.markdown("##### Ghi bằng chứng mới")
        source_id = st.selectbox(
            "Nguồn *", [s["id"] for s in sources],
            format_func=lambda x: _source_label(next(s for s in sources if s["id"] == x)),
        )
        c1, c2, c3 = st.columns(3)
        evidence_type = c1.selectbox("Loại bằng chứng", EVIDENCE_TYPES)
        verification = c2.selectbox("Xác minh", VERIFICATION_STATUSES, format_func=lambda x: VERIFICATION_LABELS[x])
        direction = c3.selectbox("Chiều bằng chứng", EVIDENCE_DIRECTIONS, format_func=lambda x: DIRECTION_LABELS[x])
        excerpt = st.text_area(
            "Trích đoạn / sự kiện / số liệu *", height=150,
            help="Ghi đoạn ngắn đủ để kiểm chứng; không dùng ô này để chép toàn bộ tài liệu.",
        )
        c4, c5, c6 = st.columns([1.8, 1, 1])
        locator = c4.text_input("Vị trí", placeholder="Ví dụ: trang 83, mục 4.2, đoạn 3")
        evidence_date = c5.date_input("Ngày evidence", value=None)
        confidence = c6.selectbox("Độ tin cậy", [1, 2, 3, 4, 5], index=2)
        note = st.text_area("Ghi chú của analyst", height=100)
        submitted = st.form_submit_button("Lưu evidence", type="primary")
    if submitted:
        try:
            evidence_id = create_evidence_version(
                repo, company_ref_id=company_ref_id, source_id=source_id,
                evidence_type=evidence_type, excerpt=excerpt, locator_text=locator,
                analyst_note=note, evidence_date=evidence_date, verification_status=verification,
                direction=direction, confidence=confidence, actor=actor,
            )
            _notify(f"Đã tạo Evidence #{evidence_id}.")
            _rerun()
        except ValidationError as exc:
            st.error(str(exc))

    evidence = list_latest_evidence(repo, company_ref_id)
    if not evidence:
        return
    st.markdown("##### Evidence mới nhất theo từng evidence key")
    frame = pd.DataFrame(evidence).rename(columns={
        "id": "Evidence ID", "source_title": "Nguồn", "version_no": "Version", "evidence_type": "Loại",
        "excerpt": "Trích đoạn / sự kiện", "locator_text": "Vị trí", "verification_status": "Xác minh",
        "direction": "Chiều", "confidence": "Tin cậy", "evidence_date": "Ngày evidence",
    })
    st.dataframe(
        frame[["Evidence ID", "Nguồn", "Version", "Loại", "Trích đoạn / sự kiện", "Vị trí", "Xác minh", "Chiều", "Tin cậy", "Ngày evidence"]],
        use_container_width=True, hide_index=True, height=430,
    )

    with st.expander("Tạo version sửa đổi — không ghi đè evidence cũ"):
        selected_id = st.selectbox(
            "Evidence cần sửa", [e["id"] for e in evidence],
            format_func=lambda x: _evidence_label(next(e for e in evidence if e["id"] == x)),
            key=f"version_evidence_select_{company_ref_id}",
        )
        selected = next(e for e in evidence if e["id"] == selected_id)
        new_excerpt = st.text_area("Trích đoạn / sự kiện mới *", value=selected["excerpt"], key=f"version_excerpt_{selected_id}")
        new_locator = st.text_input("Vị trí mới", value=selected.get("locator_text") or "", key=f"version_locator_{selected_id}")
        new_note = st.text_area("Ghi chú analyst mới", value=selected.get("analyst_note") or "", key=f"version_note_{selected_id}")
        c1, c2, c3 = st.columns(3)
        new_verification = c1.selectbox(
            "Xác minh mới", VERIFICATION_STATUSES,
            index=VERIFICATION_STATUSES.index(selected["verification_status"]),
            format_func=lambda x: VERIFICATION_LABELS[x], key=f"version_verify_{selected_id}",
        )
        new_direction = c2.selectbox(
            "Chiều mới", EVIDENCE_DIRECTIONS, index=EVIDENCE_DIRECTIONS.index(selected["direction"]),
            format_func=lambda x: DIRECTION_LABELS[x], key=f"version_direction_{selected_id}",
        )
        new_confidence = c3.selectbox(
            "Tin cậy mới", [1, 2, 3, 4, 5], index=int(selected["confidence"]) - 1,
            key=f"version_confidence_{selected_id}",
        )
        reason = st.text_input("Lý do tạo version mới *", key=f"version_reason_{selected_id}")
        if st.button("Tạo evidence version mới", disabled=not reason.strip(), key=f"version_evidence_{selected_id}"):
            try:
                new_id = create_evidence_version(
                    repo, company_ref_id=company_ref_id, source_id=selected["source_id"],
                    evidence_type=selected["evidence_type"], excerpt=new_excerpt, locator_text=new_locator,
                    analyst_note=new_note, evidence_date=selected.get("evidence_date"),
                    verification_status=new_verification, direction=new_direction, confidence=new_confidence,
                    evidence_key=selected["evidence_key"], change_reason=reason, actor=actor,
                )
                _notify(f"Đã tạo Evidence #{new_id}, version {int(selected['version_no']) + 1}; version cũ được giữ nguyên.")
                _rerun()
            except ValidationError as exc:
                st.error(str(exc))


def _render_links(repo, company_ref_id: int, review: dict | None, actor: str) -> None:
    if not review:
        st.info("Chưa có review để liên kết evidence với Q01–Q59.")
        return
    evidence = list_latest_evidence(repo, company_ref_id)
    if not evidence:
        st.info("Chưa có evidence để liên kết.")
        return
    questions = repo.list_questions()
    q_by_id = {q["question_id"]: q for q in questions}
    locked = review["status"] == "completed"
    if locked:
        st.warning("Review đã finalize: evidence links là read-only. Tạo review mới để cập nhật bằng chứng.")
    else:
        st.markdown("##### Gắn evidence vào một hoặc nhiều câu hỏi")
        evidence_id = st.selectbox(
            "Evidence", [e["id"] for e in evidence],
            format_func=lambda x: _evidence_label(next(e for e in evidence if e["id"] == x)),
            key=f"link_evidence_select_{review['id']}",
        )
        qids = st.multiselect(
            "Câu hỏi Q01–Q59 *", [q["question_id"] for q in questions],
            format_func=lambda x: f"{x} — {q_by_id[x]['question_vi']}",
            key=f"link_questions_{review['id']}",
        )
        c1, c2 = st.columns(2)
        relationship = c1.selectbox(
            "Vai trò", LINK_RELATIONSHIPS, format_func=lambda x: RELATIONSHIP_LABELS[x],
            key=f"link_relationship_{review['id']}",
        )
        materiality = c2.selectbox("Mức độ trọng yếu", [1, 2, 3, 4, 5], index=2, key=f"link_materiality_{review['id']}")
        note = st.text_area("Ghi chú liên kết", key=f"link_note_{review['id']}")
        if st.button(
            "Tạo evidence links", type="primary", disabled=not qids,
            key=f"create_evidence_links_{review['id']}",
        ):
            created = 0
            errors = []
            for qid in qids:
                try:
                    link_evidence_to_question(
                        repo, review_id=review["id"], question_id=qid, evidence_id=evidence_id,
                        relationship=relationship, materiality=materiality, link_note=note, actor=actor,
                    )
                    created += 1
                except ValidationError as exc:
                    errors.append(f"{qid}: {exc}")
            if errors:
                st.warning("; ".join(errors))
            if created:
                _invalidate_review_evidence(review["id"])
                _notify(f"Đã tạo {created} evidence link cho Review #{review['id']}.")
                _rerun()

    links = list_review_evidence(repo, review["id"])
    if not links:
        st.caption("Review chưa có evidence link.")
        return
    st.markdown("##### Evidence links hiện tại")
    frame = pd.DataFrame(links).rename(columns={
        "link_id": "Link ID", "question_id": "Q", "source_title": "Nguồn",
        "excerpt": "Trích đoạn / sự kiện", "relationship": "Vai trò", "materiality": "Trọng yếu",
        "verification_status": "Xác minh", "direction": "Chiều", "version_no": "Evidence version",
    })
    st.dataframe(
        frame[["Link ID", "Q", "Nguồn", "Trích đoạn / sự kiện", "Vai trò", "Trọng yếu", "Xác minh", "Chiều", "Evidence version"]],
        use_container_width=True, hide_index=True, height=420,
    )
    if not locked:
        with st.expander("Bỏ một evidence link"):
            link_id = st.selectbox(
                "Link", [row["link_id"] for row in links],
                format_func=lambda x: f"Link #{x} · {next(row for row in links if row['link_id'] == x)['question_id']}",
                key=f"unlink_select_{review['id']}",
            )
            reason = st.text_input("Lý do bỏ liên kết *", key=f"unlink_reason_{review['id']}")
            if st.button("Bỏ liên kết", disabled=not reason.strip(), key=f"unlink_button_{review['id']}"):
                try:
                    unlink_evidence_from_question(repo, link_id, reason=reason, actor=actor)
                    _invalidate_review_evidence(review["id"])
                    _notify(f"Đã bỏ Link #{link_id}; audit history được giữ.")
                    _rerun()
                except ValidationError as exc:
                    st.error(str(exc))


def render_evidence_workspace(repo, company_ref_id: int, review: dict | None, actor: str) -> None:
    st.markdown("#### 🔎 Research Evidence Workspace")
    st.markdown(
        '<div class="principle"><b>Evidence-first:</b> mỗi nhận định phải truy ngược được về nguồn, vị trí và version. '
        'Evidence có thể ủng hộ, phản bác hoặc chỉ cung cấp bối cảnh; analyst vẫn là người đưa ra assessment cuối cùng.</div>',
        unsafe_allow_html=True,
    )
    message = st.session_state.pop("evidence_workspace_message", None)
    if message:
        st.success(message)
    _render_summary(repo, review)
    selected = st.radio(
        "Evidence workspace", EVIDENCE_SECTIONS, horizontal=True, label_visibility="collapsed",
        key=f"evidence_section_{company_ref_id}",
    )
    if selected == "Coverage":
        _render_coverage(repo, review)
    elif selected == "Nguồn":
        _render_sources(repo, company_ref_id, actor)
    elif selected == "Bằng chứng":
        _render_evidence(repo, company_ref_id, actor)
    else:
        _render_links(repo, company_ref_id, review, actor)


__all__ = ["render_evidence_workspace"]
