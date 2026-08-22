from __future__ import annotations

"""Phase 4A UI: governed AI suggestion inbox, with no model/network execution."""

import json

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.ai_research_assistant import (
    AI_RUN_TYPES,
    decide_ai_suggestion,
    list_ai_runs,
    list_ai_suggestions,
    record_ai_run,
)
from ..services.evidence_workspace import list_sources


RUN_TYPE_LABELS = {
    "evidence_extraction": "Trích xuất evidence",
    "research_gap": "Phát hiện research gap",
    "contradiction_scan": "Tìm bằng chứng phản bác",
    "delta_review": "So sánh kỳ mới/kỳ cũ",
}


def _example_payload(source_id: int | None) -> str:
    if source_id is None:
        payload = [{
            "suggestion_type": "research_gap",
            "question_id": "Q01",
            "rationale": "Chưa có nguồn active để trả lời câu hỏi.",
            "confidence": 3,
            "materiality": 4,
        }]
    else:
        payload = [{
            "suggestion_type": "evidence_candidate",
            "source_id": source_id,
            "question_id": "Q10",
            "evidence_type": "fact",
            "relationship": "supporting",
            "direction": "supports",
            "locator_text": "Trang 83, mục Khách hàng",
            "excerpt": "Trích nguyên văn hoặc số liệu chính xác từ nguồn.",
            "rationale": "Giải thích vì sao bằng chứng liên quan tới câu hỏi.",
            "confidence": 3,
            "materiality": 4,
        }]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _render_run_ingestion(repo, company_ref_id: int, review, actor: str, sources: list[dict]) -> None:
    locked = review is None or review.get("status") == "completed"
    with st.expander("➕ Ghi nhận một AI run có kiểm soát", expanded=False):
        st.caption(
            "Phase 4A nhận JSON output từ một model/external runner và đóng dấu hash. "
            "App chưa tự gọi model; prompt chỉ được lưu SHA-256, không lưu nguyên văn."
        )
        source_options = [int(item["id"]) for item in sources]
        source_labels = {
            int(item["id"]): f"#{item['id']} · {item['title']} · {item.get('document_date') or 'không ngày'}"
            for item in sources
        }
        left, right = st.columns(2)
        run_type = left.selectbox(
            "Loại run", AI_RUN_TYPES, format_func=lambda value: RUN_TYPE_LABELS[value],
            key=f"ai_run_type_{company_ref_id}", disabled=locked,
        )
        provider = right.text_input("Provider *", value="external", key=f"ai_provider_{company_ref_id}", disabled=locked)
        left, right = st.columns(2)
        model_name = left.text_input("Model *", key=f"ai_model_{company_ref_id}", disabled=locked)
        model_version = right.text_input("Model version", key=f"ai_model_version_{company_ref_id}", disabled=locked)
        prompt_version = st.text_input("Prompt version *", value="phase4a-v1", key=f"ai_prompt_version_{company_ref_id}", disabled=locked)
        prompt_text = st.text_area(
            "Prompt đã dùng * (chỉ hash được lưu)", key=f"ai_prompt_{company_ref_id}",
            disabled=locked, height=100,
        )
        selected_sources = st.multiselect(
            "Source manifest", source_options, format_func=lambda value: source_labels[value],
            key=f"ai_sources_{company_ref_id}", disabled=locked,
        )
        default_source = selected_sources[0] if selected_sources else (source_options[0] if source_options else None)
        output_json = st.text_area(
            "AI suggestions JSON *", value=_example_payload(default_source),
            key=f"ai_output_{company_ref_id}", disabled=locked, height=300,
        )
        if st.button(
            "Ghi nhận AI run", type="primary", use_container_width=True,
            key=f"record_ai_run_{company_ref_id}", disabled=locked,
        ):
            try:
                parsed = json.loads(output_json)
                run_id = record_ai_run(
                    repo,
                    company_ref_id=company_ref_id,
                    review_id=int(review["id"]),
                    run_type=run_type,
                    provider=provider,
                    model_name=model_name,
                    model_version=model_version,
                    prompt_version=prompt_version,
                    prompt_text=prompt_text,
                    source_ids=selected_sources,
                    suggestions=parsed,
                    actor=actor,
                )
                st.success(f"Đã ghi AI run #{run_id}; chưa có assessment nào bị thay đổi.")
                st.rerun()
            except (json.JSONDecodeError, ValidationError) as exc:
                st.error(f"Không thể ghi AI run: {exc}")


def _render_suggestion_inbox(repo, review, actor: str) -> None:
    if review is None:
        st.info("Hãy tạo/chọn review trước khi dùng AI Research Assistant.")
        return
    review_id = int(review["id"])
    rows = list_ai_suggestions(repo, review_id)
    pending = [item for item in rows if item.get("decision_id") is None]
    decided = [item for item in rows if item.get("decision_id") is not None]

    cols = st.columns(3)
    cols[0].metric("Suggestions", len(rows))
    cols[1].metric("Chờ analyst", len(pending))
    cols[2].metric("Đã quyết định", len(decided))

    if not pending:
        st.info("Không có AI suggestion nào đang chờ analyst.")
    else:
        ids = [int(item["id"]) for item in pending]
        selected_id = st.selectbox(
            "Suggestion cần duyệt", ids,
            format_func=lambda value: next(
                f"#{item['id']} · {item['question_id']} · {item['suggestion_type']}"
                for item in pending if int(item["id"]) == value
            ),
            key=f"ai_pending_{review_id}",
        )
        item = next(row for row in pending if int(row["id"]) == selected_id)
        st.markdown(f"**{item['question_id']} · {item['suggestion_type']}**")
        st.write(item["rationale"])
        if item.get("source_id"):
            st.caption(
                f"Source #{item['source_id']} · {item.get('source_title') or '—'} · "
                f"Locator: {item.get('locator_text') or '—'}"
            )
            st.code(item.get("excerpt") or "", language=None)
        st.caption(
            f"Model: {item['provider']}/{item['model_name']} · Prompt: {item['prompt_version']} · "
            f"Confidence {item['confidence']}/5 · Materiality {item['materiality']}/5"
        )
        reason = st.text_area("Lý do quyết định *", key=f"ai_decision_reason_{selected_id}")
        accept, reject = st.columns(2)
        locked = review.get("status") == "completed"
        if accept.button(
            "Chấp nhận vào Evidence", type="primary", use_container_width=True,
            key=f"accept_ai_{selected_id}", disabled=locked or not reason.strip(),
        ):
            try:
                result = decide_ai_suggestion(
                    repo, selected_id, decision="accepted", reason=reason, actor=actor
                )
                if result["created_evidence_id"]:
                    st.success(
                        f"Đã tạo Evidence #{result['created_evidence_id']} ở trạng thái unverified; "
                        "analyst assessment vẫn không đổi."
                    )
                else:
                    st.success("Đã xác nhận research gap; analyst assessment vẫn không đổi.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
        if reject.button(
            "Từ chối suggestion", use_container_width=True,
            key=f"reject_ai_{selected_id}", disabled=locked or not reason.strip(),
        ):
            try:
                decide_ai_suggestion(repo, selected_id, decision="rejected", reason=reason, actor=actor)
                st.success("Đã từ chối suggestion và giữ audit trail.")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))

    if decided:
        with st.expander("Lịch sử quyết định", expanded=False):
            columns = [
                "id", "question_id", "suggestion_type", "source_title", "decision",
                "decision_reason", "created_evidence_id", "decided_by", "decided_at",
            ]
            st.dataframe(
                pd.DataFrame(decided)[[column for column in columns if column in decided[0]]],
                use_container_width=True, hide_index=True,
            )


def render_ai_research_assistant(repo, company_ref_id: int, review, actor: str) -> None:
    st.markdown("### 🤖 AI Research Assistant — Phase 4A")
    st.warning(
        "AI chỉ đề xuất. Mọi evidence phải có source + locator + excerpt và chỉ được đưa vào workspace "
        "sau khi analyst duyệt. AI không được ghi đè câu trả lời, assessment hoặc kết luận đầu tư."
    )
    if review is None:
        st.info("Chưa có review đang chọn.")
        return
    sources = list_sources(repo, company_ref_id)
    runs = list_ai_runs(repo, int(review["id"]))
    if runs:
        with st.expander("AI run audit", expanded=False):
            columns = [
                "id", "run_type", "provider", "model_name", "model_version", "prompt_version",
                "suggestion_count", "pending_count", "input_hash", "output_hash", "created_at",
            ]
            st.dataframe(
                pd.DataFrame(runs)[[column for column in columns if column in runs[0]]],
                use_container_width=True, hide_index=True,
            )
    _render_run_ingestion(repo, company_ref_id, review, actor, sources)
    st.markdown("#### Analyst approval queue")
    _render_suggestion_inbox(repo, review, actor)


__all__ = ["render_ai_research_assistant"]
