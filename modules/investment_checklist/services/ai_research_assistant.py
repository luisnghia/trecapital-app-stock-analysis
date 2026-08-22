from __future__ import annotations

"""Governed AI research inbox for Phase 4A.

This module records model output as immutable suggestions. It never writes an analyst assessment.
Only an explicit analyst decision may promote a cited suggestion into the existing Evidence
Workspace, and that promotion remains unverified until the analyst verifies it separately.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from ..repositories.sqlite_repository import ValidationError
from .evidence_workspace import (
    EVIDENCE_DIRECTIONS,
    EVIDENCE_TYPES,
    LINK_RELATIONSHIPS,
    create_evidence_version,
    link_evidence_to_question,
)


AI_RUN_TYPES = ("evidence_extraction", "research_gap", "contradiction_scan", "delta_review")
AI_SUGGESTION_TYPES = ("evidence_candidate", "contradiction", "research_gap")
AI_DECISIONS = ("accepted", "rejected")
MAX_SUGGESTIONS_PER_RUN = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, *, label: str, required: bool = False, max_length: int = 5000) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValidationError(f"{label} là bắt buộc.")
    if len(result) > max_length:
        raise ValidationError(f"{label} không được vượt quá {max_length:,} ký tự.")
    return result


def _choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    result = _text(value, label=label, required=True, max_length=100)
    if result not in allowed:
        raise ValidationError(f"{label} không hợp lệ: {result}")
    return result


def _score(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải nằm trong khoảng 1–5.") from exc
    if result not in {1, 2, 3, 4, 5}:
        raise ValidationError(f"{label} phải nằm trong khoảng 1–5.")
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _editable_review(repo, c, company_ref_id: int, review_id: int) -> dict[str, Any]:
    review = repo.get_review(review_id, conn=c)
    if not review:
        raise ValidationError("Review không tồn tại.")
    if int(review["company_ref_id"]) != int(company_ref_id):
        raise ValidationError("AI run không thuộc đúng doanh nghiệp của review.")
    if review["status"] == "completed":
        raise ValidationError("Review đã finalize; AI Research Assistant là read-only.")
    return review


def _normalize_suggestion(raw: Any, *, sources: dict[int, dict[str, Any]], valid_questions: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError("Mỗi AI suggestion phải là một JSON object.")
    suggestion_type = _choice(raw.get("suggestion_type"), AI_SUGGESTION_TYPES, "Loại suggestion")
    question_id = _text(raw.get("question_id"), label="Question ID", required=True, max_length=10).upper()
    if question_id not in valid_questions:
        raise ValidationError(f"Question ID không hợp lệ: {question_id}")

    rationale = _text(raw.get("rationale"), label="Lý do đề xuất", required=True, max_length=5000)
    confidence = _score(raw.get("confidence"), "Độ tin cậy AI")
    materiality = _score(raw.get("materiality"), "Mức độ trọng yếu")
    source_id_raw = raw.get("source_id")

    if suggestion_type == "research_gap":
        if source_id_raw not in (None, ""):
            raise ValidationError("Research gap không được gắn nguồn giả; hãy dùng evidence candidate nếu đã có nguồn.")
        return {
            "suggestion_type": suggestion_type,
            "source_id": None,
            "source_hash_at_run": None,
            "question_id": question_id,
            "evidence_type": None,
            "relationship": None,
            "direction": None,
            "locator_text": None,
            "excerpt": None,
            "rationale": rationale,
            "confidence": confidence,
            "materiality": materiality,
        }

    try:
        source_id = int(source_id_raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Evidence/contradiction suggestion bắt buộc có source_id.") from exc
    source = sources.get(source_id)
    if not source:
        raise ValidationError(f"Source #{source_id} không nằm trong source manifest của AI run.")
    locator_text = _text(raw.get("locator_text"), label="Vị trí trích dẫn", required=True, max_length=500)
    excerpt = _text(raw.get("excerpt"), label="Trích đoạn", required=True, max_length=5000)

    if suggestion_type == "contradiction":
        evidence_type = "contradiction"
        relationship = "contradicts"
        direction = "contradicts"
    else:
        evidence_type = _choice(raw.get("evidence_type", "observation"), EVIDENCE_TYPES, "Loại evidence")
        relationship = _choice(raw.get("relationship", "supporting"), LINK_RELATIONSHIPS, "Vai trò evidence")
        direction = _choice(raw.get("direction", "context"), EVIDENCE_DIRECTIONS, "Chiều evidence")

    return {
        "suggestion_type": suggestion_type,
        "source_id": source_id,
        "source_hash_at_run": source["source_hash"],
        "question_id": question_id,
        "evidence_type": evidence_type,
        "relationship": relationship,
        "direction": direction,
        "locator_text": locator_text,
        "excerpt": excerpt,
        "rationale": rationale,
        "confidence": confidence,
        "materiality": materiality,
    }


def record_ai_run(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    run_type: str,
    provider: str,
    model_name: str,
    prompt_version: str,
    prompt_text: str,
    source_ids: list[int] | tuple[int, ...],
    suggestions: list[dict[str, Any]],
    actor: str = "analyst",
    model_version: str = "",
) -> int:
    """Record a completed external/model run and immutable, hash-addressed suggestions."""
    run_type = _choice(run_type, AI_RUN_TYPES, "Loại AI run")
    provider = _text(provider, label="AI provider", required=True, max_length=200)
    model_name = _text(model_name, label="Tên model", required=True, max_length=200)
    model_version = _text(model_version, label="Model version", max_length=200)
    prompt_version = _text(prompt_version, label="Prompt version", required=True, max_length=200)
    prompt_text = _text(prompt_text, label="Prompt", required=True, max_length=50_000)
    actor = _text(actor, label="Người tạo run", required=True, max_length=200)
    if not isinstance(suggestions, list) or not suggestions:
        raise ValidationError("AI run phải có ít nhất một suggestion.")
    if len(suggestions) > MAX_SUGGESTIONS_PER_RUN:
        raise ValidationError(f"Mỗi AI run chỉ được tối đa {MAX_SUGGESTIONS_PER_RUN} suggestions.")
    try:
        requested_sources = sorted({int(value) for value in source_ids})
    except (TypeError, ValueError) as exc:
        raise ValidationError("Source manifest chứa source_id không hợp lệ.") from exc

    with repo._conn() as c:
        _editable_review(repo, c, company_ref_id, review_id)
        valid_questions = {str(row["question_id"]) for row in c.execute(
            "SELECT question_id FROM checklist_questions WHERE active=1"
        )}
        sources: dict[int, dict[str, Any]] = {}
        for source_id in requested_sources:
            row = repo._d(c.execute("SELECT * FROM research_sources WHERE id=?", (source_id,)).fetchone())
            if not row or int(row["company_ref_id"]) != int(company_ref_id):
                raise ValidationError(f"Source #{source_id} không thuộc doanh nghiệp đang phân tích.")
            if row["status"] != "active":
                raise ValidationError(f"Source #{source_id} đã archived và không được đưa vào AI run mới.")
            sources[source_id] = row

        normalized = [
            _normalize_suggestion(item, sources=sources, valid_questions=valid_questions)
            for item in suggestions
        ]
        manifest = [
            {
                "source_id": source_id,
                "source_hash": sources[source_id]["source_hash"],
                "title": sources[source_id]["title"],
                "document_date": sources[source_id].get("document_date"),
            }
            for source_id in requested_sources
        ]
        prompt_hash = _hash(prompt_text)
        manifest_hash = _hash(manifest)
        input_hash = _hash({
            "run_type": run_type,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "source_manifest_hash": manifest_hash,
        })
        output_hash = _hash(normalized)
        now = _now()
        fields = {
            "company_ref_id": company_ref_id,
            "review_id": review_id,
            "run_type": run_type,
            "status": "completed",
            "provider": provider,
            "model_name": model_name,
            "model_version": model_version or None,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "source_manifest_json": _canonical_json(manifest),
            "source_manifest_hash": manifest_hash,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "requested_by": actor,
            "created_at": now,
            "completed_at": now,
            "error_text": None,
        }
        cur = c.execute(
            f"INSERT INTO ai_research_runs({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        run_id = int(cur.lastrowid)
        for index, item in enumerate(normalized, 1):
            suggestion = {
                "run_id": run_id,
                "company_ref_id": company_ref_id,
                "review_id": review_id,
                "suggestion_no": index,
                **item,
                "payload_hash": _hash(item),
                "created_at": now,
            }
            c.execute(
                f"INSERT INTO ai_research_suggestions({','.join(suggestion)}) VALUES({','.join('?' for _ in suggestion)})",
                tuple(suggestion.values()),
            )
        repo._audit(
            c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
            action="record_completed_run", entity_type="ai_research_run", entity_id=run_id,
            after={
                "run_type": run_type,
                "provider": provider,
                "model_name": model_name,
                "prompt_version": prompt_version,
                "source_manifest_hash": manifest_hash,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "suggestion_count": len(normalized),
            },
        )
        return run_id


def list_ai_runs(repo, review_id: int) -> list[dict[str, Any]]:
    with repo._conn() as c:
        rows = c.execute(
            """SELECT r.*,
            (SELECT COUNT(*) FROM ai_research_suggestions s WHERE s.run_id=r.id) suggestion_count,
            (SELECT COUNT(*) FROM ai_research_suggestions s LEFT JOIN ai_suggestion_decisions d ON d.suggestion_id=s.id
             WHERE s.run_id=r.id AND d.id IS NULL) pending_count
            FROM ai_research_runs r WHERE r.review_id=? ORDER BY r.id DESC""",
            (review_id,),
        )
        return [dict(row) for row in rows]


def list_ai_suggestions(repo, review_id: int, *, pending_only: bool = False) -> list[dict[str, Any]]:
    sql = """SELECT s.*,src.title source_title,d.id decision_id,d.decision,d.decision_reason,
    d.created_evidence_id,d.created_link_id,d.decided_by,d.created_at decided_at,
    r.provider,r.model_name,r.prompt_version,r.output_hash run_output_hash
    FROM ai_research_suggestions s
    JOIN ai_research_runs r ON r.id=s.run_id
    LEFT JOIN research_sources src ON src.id=s.source_id
    LEFT JOIN ai_suggestion_decisions d ON d.suggestion_id=s.id
    WHERE s.review_id=?"""
    if pending_only:
        sql += " AND d.id IS NULL"
    sql += " ORDER BY s.run_id DESC,s.suggestion_no"
    with repo._conn() as c:
        return [dict(row) for row in c.execute(sql, (review_id,))]


def decide_ai_suggestion(
    repo,
    suggestion_id: int,
    *,
    decision: str,
    reason: str,
    actor: str = "analyst",
) -> dict[str, Any]:
    """Accept/reject one suggestion; accepted cited items are atomically promoted to evidence."""
    decision = _choice(decision, AI_DECISIONS, "Quyết định")
    reason = _text(reason, label="Lý do quyết định", required=True, max_length=3000)
    actor = _text(actor, label="Người quyết định", required=True, max_length=200)

    with repo._conn() as c:
        suggestion = repo._d(c.execute(
            "SELECT * FROM ai_research_suggestions WHERE id=?", (int(suggestion_id),)
        ).fetchone())
        if not suggestion:
            raise ValidationError("AI suggestion không tồn tại.")
        review = _editable_review(repo, c, int(suggestion["company_ref_id"]), int(suggestion["review_id"]))
        existing = c.execute(
            "SELECT id FROM ai_suggestion_decisions WHERE suggestion_id=?", (int(suggestion_id),)
        ).fetchone()
        if existing:
            raise ValidationError("AI suggestion đã được analyst quyết định và không thể ghi đè.")

        evidence_id = None
        link_id = None
        if decision == "accepted" and suggestion["suggestion_type"] != "research_gap":
            source = repo._d(c.execute(
                "SELECT * FROM research_sources WHERE id=?", (suggestion["source_id"],)
            ).fetchone())
            if not source or source["status"] != "active":
                raise ValidationError("Nguồn của AI suggestion không còn active; cần chạy lại AI research.")
            if source["source_hash"] != suggestion["source_hash_at_run"]:
                raise ValidationError("Nguồn đã thay đổi từ lúc AI chạy; cần chạy lại để tránh citation drift.")
            evidence_id = create_evidence_version(
                repo,
                company_ref_id=int(suggestion["company_ref_id"]),
                source_id=int(suggestion["source_id"]),
                evidence_type=suggestion["evidence_type"],
                excerpt=suggestion["excerpt"],
                locator_text=suggestion["locator_text"],
                analyst_note=f"AI suggestion #{suggestion_id} được analyst chấp nhận: {reason}",
                verification_status="unverified",
                direction=suggestion["direction"],
                confidence=int(suggestion["confidence"]),
                actor=actor,
                conn=c,
            )
            link_id = link_evidence_to_question(
                repo,
                review_id=int(suggestion["review_id"]),
                question_id=suggestion["question_id"],
                evidence_id=evidence_id,
                relationship=suggestion["relationship"],
                materiality=int(suggestion["materiality"]),
                link_note=f"Promoted từ AI suggestion #{suggestion_id}; analyst reason: {reason}",
                actor=actor,
                conn=c,
            )

        fields = {
            "suggestion_id": int(suggestion_id),
            "decision": decision,
            "decision_reason": reason,
            "created_evidence_id": evidence_id,
            "created_link_id": link_id,
            "decided_by": actor,
            "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO ai_suggestion_decisions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        decision_id = int(cur.lastrowid)
        result = {"decision_id": decision_id, **fields}
        repo._audit(
            c, company_ref_id=review["company_ref_id"], review_id=review["id"], actor=actor,
            action=decision, entity_type="ai_suggestion_decision", entity_id=decision_id,
            before={"suggestion_id": int(suggestion_id), "payload_hash": suggestion["payload_hash"]},
            after=result,
        )
        return result


def snapshot_ai_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    def build(c):
        runs = [dict(row) for row in c.execute(
            "SELECT * FROM ai_research_runs WHERE review_id=? ORDER BY id", (review_id,)
        )]
        for run in runs:
            run["source_manifest"] = json.loads(run.pop("source_manifest_json"))
        suggestions = [dict(row) for row in c.execute(
            "SELECT * FROM ai_research_suggestions WHERE review_id=? ORDER BY run_id,suggestion_no", (review_id,)
        )]
        suggestion_ids = [int(item["id"]) for item in suggestions]
        decisions: list[dict[str, Any]] = []
        if suggestion_ids:
            marks = ",".join("?" for _ in suggestion_ids)
            decisions = [dict(row) for row in c.execute(
                f"SELECT * FROM ai_suggestion_decisions WHERE suggestion_id IN ({marks}) ORDER BY id",
                tuple(suggestion_ids),
            )]
        return {
            "schema": "ai-research-assistant-v1",
            "governance": "AI suggestions only; analyst decisions are required; no automatic assessment writes.",
            "runs": runs,
            "suggestions": suggestions,
            "decisions": decisions,
        }

    if conn is not None:
        return build(conn)
    with repo._conn() as c:
        return build(c)


__all__ = [
    "AI_DECISIONS", "AI_RUN_TYPES", "AI_SUGGESTION_TYPES", "MAX_SUGGESTIONS_PER_RUN",
    "decide_ai_suggestion", "list_ai_runs", "list_ai_suggestions", "record_ai_run",
    "snapshot_ai_for_review",
]
