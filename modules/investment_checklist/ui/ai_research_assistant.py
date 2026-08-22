from __future__ import annotations

"""Phase 4B UI: source ingestion, governed provider execution and analyst approval."""

import json
import os

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
from ..services.ai_provider_execution import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_SUGGESTIONS,
    DEFAULT_OPENAI_MODEL,
    MAX_PROVIDER_SOURCE_CHARS,
    OPENAI_MODEL_IDS,
    ProviderExecutionError,
    execute_provider_run,
)
from ..services.evidence_workspace import list_sources
from ..services.source_content import (
    SUPPORTED_SOURCE_EXTENSIONS,
    create_source_content_version,
    extract_document_text,
    list_source_contents,
)


RUN_TYPE_LABELS = {
    "evidence_extraction": "Trích xuất evidence",
    "research_gap": "Phát hiện research gap",
    "contradiction_scan": "Tìm bằng chứng phản bác",
    "delta_review": "So sánh kỳ mới/kỳ cũ",
}


MODEL_LABELS = {
    "gpt-5.6-terra": "GPT-5.6 Terra — cân bằng chất lượng/chi phí",
    "gpt-5.6-luna": "GPT-5.6 Luna — tiết kiệm chi phí",
    "gpt-5.6-sol": "GPT-5.6 Sol — chất lượng cao nhất",
}


def _server_secret(name: str) -> str | None:
    value = str(os.getenv(name, "") or "").strip()
    if value:
        return value
    try:
        if not st.secrets.load_if_toml_exists():
            return None
        secrets = st.secrets.to_dict()
    except Exception:
        return None
    value = str(secrets.get(name, "") or "").strip()
    return value or None


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


def _content_label(item: dict) -> str:
    return (
        f"Content #{item['id']} · Source #{item['source_id']} · v{item['version_no']} · "
        f"{int(item['char_count']):,} ký tự · {item.get('source_title') or '—'}"
    )


def _latest_contents(rows: list[dict]) -> list[dict]:
    latest: dict[int, dict] = {}
    for row in rows:
        source_id = int(row["source_id"])
        if source_id not in latest:
            latest[source_id] = row
    return list(latest.values())


def _render_source_content_ingestion(
    repo, company_ref_id: int, actor: str, sources: list[dict]
) -> list[dict]:
    contents = list_source_contents(repo, company_ref_id)
    with st.expander("1️⃣ Nạp nội dung nguồn để AI đọc", expanded=not contents):
        st.caption(
            "Binary upload không được lưu. App chỉ lưu text đã trích xuất, locator markers và SHA-256 "
            "trong Supabase; mỗi lần sửa tạo version mới, không ghi đè."
        )
        if not sources:
            st.info("Hãy tạo Source metadata trong Research Evidence trước.")
        else:
            source_ids = [int(item["id"]) for item in sources]
            labels = {int(item["id"]): f"#{item['id']} · {item['title']}" for item in sources}
            source_id = st.selectbox(
                "Source nhận nội dung", source_ids, format_func=lambda value: labels[value],
                key=f"ai_content_source_{company_ref_id}",
            )
            uploaded = st.file_uploader(
                "PDF/DOCX/TXT/MD/CSV/JSON",
                type=[suffix.lstrip(".") for suffix in SUPPORTED_SOURCE_EXTENSIONS],
                key=f"ai_content_upload_{company_ref_id}",
            )
            pdf_pages = st.text_input(
                "Phạm vi trang PDF (để trống = toàn bộ)",
                placeholder="Ví dụ: 1-40,83,94-110",
                key=f"ai_pdf_pages_{company_ref_id}",
                help="Giới hạn đúng phần cần nghiên cứu giúp giảm token và tránh gửi nội dung không liên quan.",
            )
            pasted = st.text_area(
                "Hoặc dán nội dung text", height=140,
                key=f"ai_content_paste_{company_ref_id}",
                help="Nếu vừa tải file vừa dán text, app ưu tiên file.",
            )
            scope_label = st.text_input(
                "Mô tả phạm vi", placeholder="Ví dụ: BCTN 2025 — chương Khách hàng và Quản trị rủi ro",
                key=f"ai_content_scope_{company_ref_id}",
            )
            if st.button(
                "Lưu content version", type="primary", use_container_width=True,
                key=f"save_ai_content_{company_ref_id}", disabled=uploaded is None and not pasted.strip(),
            ):
                try:
                    if uploaded is not None:
                        extracted = extract_document_text(
                            uploaded.name, uploaded.getvalue(), pdf_pages=pdf_pages,
                        )
                        content_text = extracted["content_text"]
                        content_type = extracted["content_type"]
                        locator_scheme = extracted["locator_scheme"]
                        original_filename = extracted["original_filename"]
                        final_scope = scope_label.strip() or extracted["scope_label"]
                    else:
                        content_text = pasted
                        content_type = "text/plain"
                        locator_scheme = "analyst_supplied"
                        original_filename = ""
                        final_scope = scope_label.strip() or "Analyst supplied text"
                    content_id = create_source_content_version(
                        repo,
                        company_ref_id=company_ref_id,
                        source_id=source_id,
                        content_text=content_text,
                        content_type=content_type,
                        locator_scheme=locator_scheme,
                        original_filename=original_filename,
                        scope_label=final_scope,
                        actor=actor,
                    )
                    st.success(f"Đã lưu Content #{content_id}; binary file không được lưu.")
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
        if contents:
            st.markdown("##### Content versions đã lưu")
            frame = pd.DataFrame(contents).rename(columns={
                "id": "Content ID", "source_id": "Source ID", "version_no": "Version",
                "source_title": "Nguồn", "original_filename": "Tệp", "scope_label": "Phạm vi",
                "locator_scheme": "Locator", "char_count": "Ký tự", "content_hash": "SHA-256",
                "created_by": "Người tạo", "created_at": "Thời gian",
            })
            columns = [
                "Content ID", "Source ID", "Version", "Nguồn", "Tệp", "Phạm vi", "Locator",
                "Ký tự", "SHA-256", "Người tạo", "Thời gian",
            ]
            st.dataframe(frame[columns], use_container_width=True, hide_index=True, height=300)
    return contents


def _render_provider_execution(
    repo,
    company_ref_id: int,
    review,
    actor: str,
    contents: list[dict],
) -> None:
    api_key = _server_secret("OPENAI_API_KEY")
    locked = review is None or review.get("status") == "completed"
    latest = _latest_contents(contents)
    with st.expander("2️⃣ Chạy OpenAI provider có kiểm soát", expanded=True):
        if api_key:
            st.success("OpenAI provider: sẵn sàng — API key chỉ tồn tại ở server secrets.")
        else:
            st.warning(
                "Chưa có OPENAI_API_KEY trong Streamlit Secrets. App vẫn cho nạp nguồn và duyệt run cũ, "
                "nhưng chưa thể gọi model thật."
            )
        if locked:
            st.info("Review completed hoặc chưa được chọn; provider execution đang bị khóa.")
        if not latest:
            st.info("Chưa có content version để gửi cho model.")

        content_ids = [int(item["id"]) for item in latest]
        labels = {int(item["id"]): _content_label(item) for item in latest}
        selected_contents = st.multiselect(
            "Content manifest *", content_ids, format_func=lambda value: labels[value],
            key=f"phase4b_contents_{company_ref_id}", disabled=locked,
        )
        selected_rows = [item for item in latest if int(item["id"]) in selected_contents]
        total_chars = sum(int(item["char_count"]) for item in selected_rows)
        estimated_tokens = round(total_chars / 4)
        st.caption(
            f"Input nguồn: {total_chars:,}/{MAX_PROVIDER_SOURCE_CHARS:,} ký tự · "
            f"ước tính khoảng {estimated_tokens:,} tokens (ước tính thô; usage thực được lưu sau run)."
        )
        if total_chars > MAX_PROVIDER_SOURCE_CHARS:
            st.error("Vượt input budget; hãy giới hạn phạm vi trang hoặc chia thành nhiều run.")

        left, right = st.columns(2)
        run_type = left.selectbox(
            "Loại run", AI_RUN_TYPES, format_func=lambda value: RUN_TYPE_LABELS[value],
            key=f"phase4b_run_type_{company_ref_id}", disabled=locked,
        )
        default_model = _server_secret("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        if default_model not in OPENAI_MODEL_IDS:
            default_model = DEFAULT_OPENAI_MODEL
        model_name = right.selectbox(
            "Model", OPENAI_MODEL_IDS, index=OPENAI_MODEL_IDS.index(default_model),
            format_func=lambda value: MODEL_LABELS[value],
            key=f"phase4b_model_{company_ref_id}", disabled=locked,
        )
        questions = repo.list_questions()
        groups = list(dict.fromkeys(str(item["group_name"]) for item in questions))
        scope = st.selectbox(
            "Phạm vi câu hỏi", ["Tất cả Q01–Q59", *groups],
            key=f"phase4b_question_scope_{company_ref_id}", disabled=locked,
        )
        question_ids = None if scope == "Tất cả Q01–Q59" else [
            item["question_id"] for item in questions if item["group_name"] == scope
        ]
        c1, c2, c3 = st.columns(3)
        max_suggestions = c1.slider(
            "Tối đa suggestions", 1, 50, DEFAULT_MAX_SUGGESTIONS,
            key=f"phase4b_max_suggestions_{company_ref_id}", disabled=locked,
        )
        max_output_tokens = c2.selectbox(
            "Max output tokens", [2_000, 4_000, DEFAULT_MAX_OUTPUT_TOKENS, 12_000, 16_000],
            index=2, key=f"phase4b_max_tokens_{company_ref_id}", disabled=locked,
        )
        reasoning_effort = c3.selectbox(
            "Reasoning", ["none", "low", "medium", "high"], index=1,
            key=f"phase4b_reasoning_{company_ref_id}", disabled=locked,
        )
        confirmed = st.checkbox(
            "Tôi xác nhận gửi các content đã chọn tới OpenAI; AI chỉ tạo suggestion và không được tự ghi assessment.",
            key=f"phase4b_confirm_{company_ref_id}", disabled=locked or not api_key,
        )
        disabled = (
            locked or not api_key or not selected_contents or not confirmed or
            total_chars > MAX_PROVIDER_SOURCE_CHARS
        )
        if st.button(
            "🤖 Chạy provider và đưa vào approval queue", type="primary", use_container_width=True,
            key=f"phase4b_execute_{company_ref_id}", disabled=disabled,
        ):
            try:
                with st.spinner("Đang gọi model, kiểm tra structured output và đối chiếu trích dẫn..."):
                    result = execute_provider_run(
                        repo,
                        company_ref_id=company_ref_id,
                        review_id=int(review["id"]),
                        run_type=run_type,
                        source_content_ids=selected_contents,
                        actor=actor,
                        api_key=api_key,
                        model_name=model_name,
                        question_ids=question_ids,
                        max_suggestions=max_suggestions,
                        max_output_tokens=max_output_tokens,
                        reasoning_effort=reasoning_effort,
                    )
                usage = result.get("provider_metadata") or {}
                st.success(
                    f"Đã ghi AI run #{result['run_id']} với {result['suggestion_count']} suggestions; "
                    f"usage {usage.get('total_tokens') or '—'} tokens. Assessment không thay đổi."
                )
                st.rerun()
            except (ValidationError, ProviderExecutionError) as exc:
                st.error(str(exc))


def _render_run_ingestion(repo, company_ref_id: int, review, actor: str, sources: list[dict]) -> None:
    locked = review is None or review.get("status") == "completed"
    with st.expander("Tương thích Phase 4A — nhập JSON từ external runner", expanded=False):
        st.caption(
            "Luồng dự phòng nhận JSON output từ một external runner và đóng dấu hash. "
            "Prompt chỉ được lưu SHA-256, không lưu nguyên văn."
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
    st.markdown("### 🤖 AI Research Assistant — Phase 4B")
    st.warning(
        "AI chỉ đề xuất. Mọi evidence phải có source + locator + excerpt và chỉ được đưa vào workspace "
        "sau khi analyst duyệt. AI không được ghi đè câu trả lời, assessment hoặc kết luận đầu tư."
    )
    if review is None:
        st.info("Chưa có review đang chọn.")
        return
    sources = list_sources(repo, company_ref_id)
    runs = list_ai_runs(repo, int(review["id"]))
    contents = _render_source_content_ingestion(repo, company_ref_id, actor, sources)
    _render_provider_execution(repo, company_ref_id, review, actor, contents)
    if runs:
        with st.expander("AI run audit", expanded=False):
            columns = [
                "id", "status", "run_type", "provider", "model_name", "model_version", "prompt_version",
                "suggestion_count", "pending_count", "input_tokens", "output_tokens", "total_tokens",
                "latency_ms", "attempt_count", "provider_request_id", "provider_response_id",
                "input_hash", "output_hash", "error_text", "created_at",
            ]
            st.dataframe(
                pd.DataFrame(runs)[[column for column in columns if column in runs[0]]],
                use_container_width=True, hide_index=True,
            )
    _render_run_ingestion(repo, company_ref_id, review, actor, sources)
    st.markdown("#### Analyst approval queue")
    _render_suggestion_inbox(repo, review, actor)


__all__ = ["render_ai_research_assistant"]
