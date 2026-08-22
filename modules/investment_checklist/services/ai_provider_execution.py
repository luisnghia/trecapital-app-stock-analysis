from __future__ import annotations

"""Phase 4B provider execution for the governed AI suggestion inbox.

External HTTP calls happen outside database transactions.  Provider output is constrained by a
strict JSON schema, then revalidated against immutable source content before it is recorded.
"""

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Protocol
import uuid

import httpx

from ..repositories.sqlite_repository import ValidationError
from .ai_research_assistant import (
    AI_RUN_TYPES,
    MAX_SUGGESTIONS_PER_RUN,
    record_ai_run,
    record_ai_run_failure,
)
from .source_content import get_source_content


OPENAI_PROVIDER = "openai-responses"
OPENAI_MODEL_IDS = ("gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.6-sol")
DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"
PHASE4B_PROMPT_VERSION = "phase4b-openai-structured-v1"
MAX_PROVIDER_SOURCE_CHARS = 800_000
MAX_PROVIDER_CONTENTS = 12
DEFAULT_MAX_SUGGESTIONS = 30
DEFAULT_MAX_OUTPUT_TOKENS = 8_000
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


RUN_TYPE_INSTRUCTIONS = {
    "evidence_extraction": "Find material facts, metrics, and quotes that directly help answer the scoped questions.",
    "research_gap": "Identify material questions that the supplied documents do not answer adequately.",
    "contradiction_scan": "Prioritize statements or metrics that contradict, weaken, or qualify a possible thesis.",
    "delta_review": "Identify material changes between periods represented in the supplied documents.",
}


class AIProvider(Protocol):
    def generate(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
        reasoning_effort: str,
        safety_identifier: str,
        metadata: dict[str, str],
    ) -> "ProviderResult": ...


@dataclass(frozen=True)
class ProviderResult:
    suggestions: list[dict[str, Any]]
    model_version: str
    metadata: dict[str, Any]


class ProviderExecutionError(RuntimeError):
    def __init__(self, message: str, *, metadata: dict[str, Any] | None = None):
        super().__init__(message)
        self.metadata = dict(metadata or {})


def _safe_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message") or payload.get("message")
    except Exception:
        message = None
    return str(message or f"HTTP {response.status_code}").strip()[:1200]


def _response_text(payload: dict[str, Any]) -> str:
    refusals: list[str] = []
    texts: list[str] = []
    for output in payload.get("output") or []:
        if output.get("type") != "message":
            continue
        for content in output.get("content") or []:
            if content.get("type") == "refusal":
                refusals.append(str(content.get("refusal") or "Provider refused the request."))
            elif content.get("type") == "output_text":
                texts.append(str(content.get("text") or ""))
    if refusals:
        raise ProviderExecutionError("OpenAI từ chối yêu cầu: " + " ".join(refusals)[:1000])
    text = "\n".join(item for item in texts if item).strip()
    if not text:
        raise ProviderExecutionError("OpenAI không trả về structured output.")
    return text


class OpenAIResponsesProvider:
    """Minimal server-side Responses API client with bounded retries and request-id audit."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 120.0,
        max_attempts: int = 3,
        http_client: httpx.Client | None = None,
    ):
        key = str(api_key or "").strip()
        if not key:
            raise ValidationError("OPENAI_API_KEY chưa được cấu hình ở server secrets.")
        self.api_key = key
        self.timeout_seconds = min(max(float(timeout_seconds), 10.0), 300.0)
        self.max_attempts = min(max(int(max_attempts), 1), 3)
        self.http_client = http_client

    def generate(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        response_schema: dict[str, Any],
        max_output_tokens: int,
        reasoning_effort: str,
        safety_identifier: str,
        metadata: dict[str, str],
    ) -> ProviderResult:
        client_request_id = str(uuid.uuid4())
        request_body = {
            "model": model,
            "instructions": instructions,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": input_text}]}],
            "max_output_tokens": int(max_output_tokens),
            "reasoning": {"effort": reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "investment_research_suggestions",
                    "strict": True,
                    "schema": response_schema,
                }
            },
            "store": False,
            "safety_identifier": safety_identifier[:64],
            "metadata": {str(key)[:64]: str(value)[:512] for key, value in metadata.items()},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Client-Request-Id": client_request_id,
            "User-Agent": "Trecapital-Investment-Checklist/23.85",
        }
        started = time.monotonic()
        request_id = None
        response: httpx.Response | None = None
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds)
        owns_client = self.http_client is None
        try:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = client.post(
                        "https://api.openai.com/v1/responses",
                        headers=headers,
                        json=request_body,
                        timeout=self.timeout_seconds,
                    )
                    request_id = response.headers.get("x-request-id") or request_id
                    if response.status_code < 400:
                        break
                    if response.status_code not in RETRYABLE_STATUS_CODES or attempt >= self.max_attempts:
                        raise ProviderExecutionError(
                            f"OpenAI API lỗi: {_safe_error_message(response)}",
                            metadata={
                                "provider_request_id": request_id,
                                "client_request_id": client_request_id,
                                "attempt_count": attempt,
                                "latency_ms": int((time.monotonic() - started) * 1000),
                            },
                        )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt >= self.max_attempts:
                        raise ProviderExecutionError(
                            f"Không thể kết nối OpenAI sau {attempt} lần thử: {type(exc).__name__}",
                            metadata={
                                "provider_request_id": request_id,
                                "client_request_id": client_request_id,
                                "attempt_count": attempt,
                                "latency_ms": int((time.monotonic() - started) * 1000),
                            },
                        ) from exc
                time.sleep(float(attempt))
            if response is None:
                raise ProviderExecutionError("OpenAI API không trả về response.")
            try:
                payload = response.json()
            except Exception as exc:
                raise ProviderExecutionError(
                    "OpenAI trả về response không phải JSON.",
                    metadata={
                        "provider_request_id": request_id,
                        "client_request_id": client_request_id,
                        "attempt_count": attempt,
                        "latency_ms": int((time.monotonic() - started) * 1000),
                    },
                ) from exc
            status = str(payload.get("status") or "")
            usage = payload.get("usage") or {}
            response_metadata = {
                "provider_request_id": request_id,
                "provider_response_id": payload.get("id"),
                "client_request_id": client_request_id,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "latency_ms": int((time.monotonic() - started) * 1000),
                "attempt_count": attempt,
                "service_tier": payload.get("service_tier"),
            }
            if status != "completed":
                detail = payload.get("error") or payload.get("incomplete_details") or status or "unknown"
                raise ProviderExecutionError(
                    f"OpenAI run chưa hoàn tất: {str(detail)[:1000]}",
                    metadata=response_metadata,
                )
            try:
                structured = json.loads(_response_text(payload))
            except ProviderExecutionError as exc:
                raise ProviderExecutionError(str(exc), metadata=response_metadata) from exc
            except json.JSONDecodeError as exc:
                raise ProviderExecutionError(
                    "Structured output của OpenAI không parse được JSON.", metadata=response_metadata
                ) from exc
            suggestions = structured.get("suggestions") if isinstance(structured, dict) else None
            if not isinstance(suggestions, list):
                raise ProviderExecutionError(
                    "Structured output thiếu mảng suggestions.", metadata=response_metadata
                )
            return ProviderResult(
                suggestions=suggestions,
                model_version=str(payload.get("model") or model),
                metadata=response_metadata,
            )
        finally:
            if owns_client:
                client.close()


def _suggestion_schema(max_suggestions: int) -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    nullable_integer = {"type": ["integer", "null"]}
    item = {
        "type": "object",
        "properties": {
            "suggestion_type": {"type": "string", "enum": ["evidence_candidate", "contradiction", "research_gap"]},
            "source_id": nullable_integer,
            "source_content_id": nullable_integer,
            "question_id": {"type": "string"},
            "evidence_type": {"type": ["string", "null"], "enum": ["fact", "quote", "metric", "observation", "contradiction", "risk", None]},
            "relationship": {"type": ["string", "null"], "enum": ["primary", "supporting", "context", "contradicts", None]},
            "direction": {"type": ["string", "null"], "enum": ["supports", "contradicts", "context", None]},
            "locator_text": nullable_string,
            "excerpt": nullable_string,
            "rationale": {"type": "string"},
            "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
            "materiality": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": [
            "suggestion_type", "source_id", "source_content_id", "question_id", "evidence_type",
            "relationship", "direction", "locator_text", "excerpt", "rationale", "confidence", "materiality",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "suggestions": {"type": "array", "items": item, "maxItems": max_suggestions},
        },
        "required": ["suggestions"],
        "additionalProperties": False,
    }


def _prepare_run_package(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    run_type: str,
    source_content_ids: list[int] | tuple[int, ...],
    question_ids: list[str] | tuple[str, ...] | None,
    max_suggestions: int,
) -> dict[str, Any]:
    if run_type not in AI_RUN_TYPES:
        raise ValidationError("Loại AI run không hợp lệ.")
    content_ids = [int(value) for value in source_content_ids]
    if not content_ids:
        raise ValidationError("Phase 4B cần ít nhất một content version đã lưu.")
    if len(content_ids) > MAX_PROVIDER_CONTENTS:
        raise ValidationError(f"Mỗi run chỉ được tối đa {MAX_PROVIDER_CONTENTS} content versions.")
    if len(set(content_ids)) != len(content_ids):
        raise ValidationError("Content manifest bị trùng.")
    max_suggestions = int(max_suggestions)
    if not 1 <= max_suggestions <= min(50, MAX_SUGGESTIONS_PER_RUN):
        raise ValidationError("Số suggestion tối đa phải nằm trong khoảng 1–50.")

    with repo._conn() as c:
        review = repo.get_review(int(review_id), conn=c)
        if not review or int(review["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Review không thuộc doanh nghiệp đang phân tích.")
        if review["status"] == "completed":
            raise ValidationError("Review đã finalize; provider execution bị khóa.")
        question_rows = [dict(row) for row in c.execute(
            "SELECT question_id,question_no,group_name,question_vi,guidance FROM checklist_questions WHERE active=1 ORDER BY question_no"
        )]
        if question_ids:
            scoped = {str(value).strip().upper() for value in question_ids}
            question_rows = [row for row in question_rows if row["question_id"] in scoped]
            if not question_rows or len(question_rows) != len(scoped):
                raise ValidationError("Question scope chứa Q không hợp lệ.")
        contents: list[dict[str, Any]] = []
        source_ids: list[int] = []
        seen_sources: set[int] = set()
        for content_id in content_ids:
            content = get_source_content(repo, content_id, conn=c)
            if not content or int(content["company_ref_id"]) != int(company_ref_id):
                raise ValidationError(f"Content #{content_id} không thuộc doanh nghiệp đang phân tích.")
            if content["source_status"] != "active":
                raise ValidationError(f"Source của Content #{content_id} đã archived.")
            source_id = int(content["source_id"])
            if source_id in seen_sources:
                raise ValidationError("Mỗi source chỉ được chọn một content version trong một AI run.")
            latest = c.execute(
                "SELECT id FROM research_source_contents WHERE source_id=? ORDER BY version_no DESC,id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not latest or int(latest["id"]) != content_id:
                raise ValidationError(f"Content #{content_id} không phải version mới nhất của Source #{source_id}.")
            seen_sources.add(source_id)
            source_ids.append(source_id)
            contents.append(content)

    total_chars = sum(int(item["char_count"]) for item in contents)
    if total_chars > MAX_PROVIDER_SOURCE_CHARS:
        raise ValidationError(
            f"Tổng nội dung {total_chars:,} ký tự vượt budget {MAX_PROVIDER_SOURCE_CHARS:,}; "
            "hãy giới hạn phạm vi trang hoặc chia thành nhiều run."
        )
    prompt_basis = {
        "prompt_version": PHASE4B_PROMPT_VERSION,
        "run_type": run_type,
        "run_instruction": RUN_TYPE_INSTRUCTIONS[run_type],
        "questions": question_rows,
        "governance": {
            "suggestions_only": True,
            "no_assessment_write": True,
            "verbatim_excerpt_required": True,
            "research_gap_has_no_source": True,
        },
    }
    instructions = (
        "You are a governed investment-research extraction engine. Return suggestions only, never an "
        "investment recommendation, score, or analyst assessment. For evidence_candidate and contradiction, "
        "source_id and source_content_id must match the supplied document, locator_text must identify the page/"
        "paragraph/line marker, and excerpt must be copied verbatim from that document. If evidence is absent, "
        "use research_gap with all citation fields null. Do not infer a quote, number, or event that is not present. "
        + RUN_TYPE_INSTRUCTIONS[run_type]
    )
    document_blocks = []
    for item in contents:
        document_blocks.append(
            "\n".join([
                f"<<<SOURCE source_id={item['source_id']} source_content_id={item['id']} "
                f"content_hash={item['content_hash']} title={json.dumps(item['source_title'], ensure_ascii=False)}>>>",
                item["content_text"],
                "<<<END SOURCE>>>",
            ])
        )
    input_text = (
        "RUN CONFIG:\n" + json.dumps(
            {"run_type": run_type, "max_suggestions": max_suggestions}, ensure_ascii=False, sort_keys=True
        ) + "\n\nQUESTION CATALOG:\n" + json.dumps(question_rows, ensure_ascii=False, sort_keys=True) +
        "\n\nSOURCE DOCUMENTS:\n" + "\n\n".join(document_blocks)
    )
    return {
        "source_ids": source_ids,
        "source_content_ids": content_ids,
        "prompt_text": json.dumps(prompt_basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "instructions": instructions,
        "input_text": input_text,
        "response_schema": _suggestion_schema(max_suggestions),
        "total_source_chars": total_chars,
        "question_count": len(question_rows),
    }


def execute_provider_run(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    run_type: str,
    source_content_ids: list[int] | tuple[int, ...],
    actor: str,
    api_key: str,
    model_name: str = DEFAULT_OPENAI_MODEL,
    question_ids: list[str] | tuple[str, ...] | None = None,
    max_suggestions: int = DEFAULT_MAX_SUGGESTIONS,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    reasoning_effort: str = "low",
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    if model_name not in OPENAI_MODEL_IDS:
        raise ValidationError("Model OpenAI không nằm trong allowlist Phase 4B.")
    if reasoning_effort not in {"none", "low", "medium", "high"}:
        raise ValidationError("Reasoning effort không hợp lệ.")
    max_output_tokens = int(max_output_tokens)
    if not 1_000 <= max_output_tokens <= 16_000:
        raise ValidationError("Max output tokens phải nằm trong khoảng 1.000–16.000.")
    actor = str(actor or "analyst").strip()
    if not actor:
        raise ValidationError("Người chạy AI là bắt buộc.")
    package = _prepare_run_package(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        run_type=run_type,
        source_content_ids=source_content_ids,
        question_ids=question_ids,
        max_suggestions=max_suggestions,
    )
    provider_client = provider or OpenAIResponsesProvider(api_key)
    safe_actor = hashlib.sha256(actor.encode("utf-8")).hexdigest()[:32]
    provider_metadata: dict[str, Any] = {}
    try:
        result = provider_client.generate(
            model=model_name,
            instructions=package["instructions"],
            input_text=package["input_text"],
            response_schema=package["response_schema"],
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            safety_identifier=safe_actor,
            metadata={
                "workflow": "investment-checklist-phase4b",
                "run_type": run_type,
                "review_id": str(review_id),
            },
        )
        provider_metadata = result.metadata
        run_id = record_ai_run(
            repo,
            company_ref_id=company_ref_id,
            review_id=review_id,
            run_type=run_type,
            provider=OPENAI_PROVIDER,
            model_name=model_name,
            model_version=result.model_version,
            prompt_version=PHASE4B_PROMPT_VERSION,
            prompt_text=package["prompt_text"],
            source_ids=package["source_ids"],
            source_content_ids=package["source_content_ids"],
            suggestions=result.suggestions,
            provider_metadata=provider_metadata,
            actor=actor,
            allow_empty=True,
        )
        return {
            "run_id": run_id,
            "suggestion_count": len(result.suggestions),
            "total_source_chars": package["total_source_chars"],
            "question_count": package["question_count"],
            "provider_metadata": provider_metadata,
        }
    except Exception as exc:
        if isinstance(exc, ProviderExecutionError):
            provider_metadata = exc.metadata
        failure_id = record_ai_run_failure(
            repo,
            company_ref_id=company_ref_id,
            review_id=review_id,
            run_type=run_type,
            provider=OPENAI_PROVIDER,
            model_name=model_name,
            prompt_version=PHASE4B_PROMPT_VERSION,
            prompt_text=package["prompt_text"],
            source_ids=package["source_ids"],
            source_content_ids=package["source_content_ids"],
            error_text=str(exc),
            actor=actor,
            provider_metadata=provider_metadata,
        )
        if isinstance(exc, ValidationError):
            raise ValidationError(f"{exc} (Failed run #{failure_id})") from exc
        if isinstance(exc, ProviderExecutionError):
            raise ProviderExecutionError(
                f"{exc} (Failed run #{failure_id})", metadata=provider_metadata
            ) from exc
        raise ProviderExecutionError(f"Provider execution thất bại (Failed run #{failure_id}): {exc}") from exc


__all__ = [
    "AIProvider", "DEFAULT_MAX_OUTPUT_TOKENS", "DEFAULT_MAX_SUGGESTIONS", "DEFAULT_OPENAI_MODEL",
    "MAX_PROVIDER_SOURCE_CHARS", "OPENAI_MODEL_IDS", "OPENAI_PROVIDER", "PHASE4B_PROMPT_VERSION",
    "OpenAIResponsesProvider", "ProviderExecutionError", "ProviderResult", "execute_provider_run",
]
