from __future__ import annotations

"""Phase 6 governed monitoring and delta-review workflow.

Monitoring records are evidence-backed analyst work products.  They never write Q01-Q59
assessments; the Analyst Workspace remains the only assessment writer.
"""

from datetime import datetime, timezone
import json
import re
import uuid
from typing import Any

from ..repositories.sqlite_repository import ValidationError


CADENCES = ("continuous", "weekly", "monthly", "quarterly", "annual", "event")
TRIGGER_TYPES = ("periodic", "metric_threshold", "filing", "guidance", "management", "industry", "thesis")
COMPARISON_OPERATORS = ("none", "lt", "lte", "gt", "gte", "abs_change_pct", "delta")
OBSERVATION_STATUSES = ("triggered", "clear", "unknown", "research_gap")
CHANGE_TYPES = ("new_evidence", "metric_threshold", "guidance", "management", "industry", "thesis", "periodic_review")
PROPOSED_ACTIONS = ("carry_forward", "revise", "research_gap", "no_change")
DECISIONS = ("carry_forward", "revise", "research_gap", "dismiss")

_RULE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, *, label: str, required: bool = False, limit: int = 8000) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValidationError(f"{label} là bắt buộc.")
    if len(result) > limit:
        raise ValidationError(f"{label} không được vượt quá {limit:,} ký tự.")
    return result


def _choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    result = _text(value, label=label, required=True, limit=100)
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


def _optional_float(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải là số.") from exc


def normalize_rule_key(value: Any) -> str:
    raw = _text(value, label="Rule key", required=True, limit=80).casefold()
    key = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    if not _RULE_KEY_RE.fullmatch(key):
        raise ValidationError("Rule key cần 2–80 ký tự a-z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang.")
    return key


def _editable_review(repo, c, review_id: int, company_ref_id: int | None = None) -> dict[str, Any]:
    review = repo.get_review(int(review_id), conn=c)
    if not review:
        raise ValidationError("Review không tồn tại.")
    if review["status"] == "completed":
        raise ValidationError("Review đã finalize; Monitoring & Delta Review là read-only.")
    if company_ref_id is not None and int(review["company_ref_id"]) != int(company_ref_id):
        raise ValidationError("Dữ liệu monitoring không thuộc đúng doanh nghiệp của review.")
    return review


def _question(repo, c, question_id: str) -> dict[str, Any]:
    qid = str(question_id or "").strip().upper()
    row = repo._d(c.execute("SELECT * FROM checklist_questions WHERE question_id=? AND active=1", (qid,)).fetchone())
    if not row:
        raise ValidationError("Question ID phải thuộc Q01–Q59 đang hoạt động.")
    return row


def _evidence(repo, c, evidence_id: int | None, company_ref_id: int) -> dict[str, Any] | None:
    if evidence_id in (None, "", 0, "0"):
        return None
    row = repo._d(c.execute("SELECT * FROM research_evidence WHERE id=?", (int(evidence_id),)).fetchone())
    if not row or int(row["company_ref_id"]) != int(company_ref_id):
        raise ValidationError("Evidence không thuộc doanh nghiệp đang phân tích.")
    return row


def save_monitoring_rule(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    question_id: str,
    title: str,
    description: str,
    cadence: str,
    trigger_type: str,
    rule_key: str | None = None,
    metric_key: str = "",
    comparison_operator: str = "none",
    threshold_value: float | None = None,
    threshold_unit: str = "",
    materiality: int = 3,
    active: bool = True,
    source_evidence_id: int | None = None,
    change_reason: str = "",
    actor: str = "analyst",
) -> int:
    title = _text(title, label="Tiêu đề rule", required=True, limit=500)
    description = _text(description, label="Nội dung theo dõi", required=True)
    cadence = _choice(cadence, CADENCES, "Tần suất")
    trigger_type = _choice(trigger_type, TRIGGER_TYPES, "Loại trigger")
    comparison_operator = _choice(comparison_operator, COMPARISON_OPERATORS, "Toán tử")
    metric_key = _text(metric_key, label="Metric key", limit=120)
    threshold_value = _optional_float(threshold_value, "Ngưỡng")
    threshold_unit = _text(threshold_unit, label="Đơn vị ngưỡng", limit=60)
    materiality = _score(materiality, "Mức độ trọng yếu")
    change_reason = _text(change_reason, label="Lý do tạo version mới", limit=2000)
    key = normalize_rule_key(rule_key or f"rule-{uuid.uuid4().hex[:12]}")
    if trigger_type == "metric_threshold":
        if not metric_key or threshold_value is None or comparison_operator == "none":
            raise ValidationError("Metric threshold cần metric key, toán tử và giá trị ngưỡng.")
    elif comparison_operator != "none" or threshold_value is not None:
        raise ValidationError("Chỉ metric threshold mới được cấu hình toán tử/giá trị ngưỡng.")

    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        question = _question(repo, c, question_id)
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        previous = repo._d(c.execute(
            "SELECT * FROM monitoring_rules WHERE review_id=? AND rule_key=? ORDER BY version_no DESC,id DESC LIMIT 1",
            (review_id, key),
        ).fetchone())
        if previous and not change_reason:
            raise ValidationError("Lý do tạo version monitoring rule mới là bắt buộc.")
        if previous and previous["question_id"] != question["question_id"]:
            raise ValidationError("Không được đổi Question ID giữa các version của rule.")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "rule_key": key,
            "version_no": int(previous["version_no"]) + 1 if previous else 1,
            "question_id": question["question_id"], "title": title, "description": description,
            "cadence": cadence, "trigger_type": trigger_type, "metric_key": metric_key or None,
            "comparison_operator": comparison_operator, "threshold_value": threshold_value,
            "threshold_unit": threshold_unit or None, "materiality": materiality,
            "active": int(bool(active)), "source_evidence_id": int(evidence["id"]) if evidence else None,
            "change_reason": change_reason or None,
            "supersedes_rule_id": int(previous["id"]) if previous else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO monitoring_rules({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM monitoring_rules WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="monitoring_rule", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_monitoring_rules(repo, review_id: int, *, conn=None, latest_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT r.* FROM monitoring_rules r WHERE r.review_id=?"
    if latest_only:
        sql += " AND NOT EXISTS(SELECT 1 FROM monitoring_rules n WHERE n.review_id=r.review_id AND n.rule_key=r.rule_key AND n.version_no>r.version_no)"
    sql += " ORDER BY r.active DESC,r.materiality DESC,r.question_id,r.title"

    def query(c):
        return [dict(row) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def add_monitoring_observation(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    rule_id: int,
    observed_at,
    as_of_date,
    observation_status: str,
    summary: str,
    observed_value: float | None = None,
    observed_unit: str = "",
    source_evidence_id: int | None = None,
    confidence: int = 3,
    materiality: int = 3,
    actor: str = "analyst",
) -> int:
    observation_status = _choice(observation_status, OBSERVATION_STATUSES, "Trạng thái quan sát")
    summary = _text(summary, label="Tóm tắt quan sát", required=True)
    observed_value = _optional_float(observed_value, "Giá trị quan sát")
    observed_unit = _text(observed_unit, label="Đơn vị", limit=60)
    confidence = _score(confidence, "Độ tin cậy")
    materiality = _score(materiality, "Mức độ trọng yếu")
    observed_at = repo._date(observed_at)
    as_of_date = repo._date(as_of_date)

    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        rule = repo._d(c.execute(
            "SELECT * FROM monitoring_rules WHERE id=? AND review_id=?", (int(rule_id), review_id)
        ).fetchone())
        if not rule or int(rule["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Monitoring rule không thuộc review hiện tại.")
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        if observation_status in {"triggered", "clear"} and not evidence:
            raise ValidationError("Triggered/clear observation bắt buộc có exact evidence.")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "rule_id": int(rule_id),
            "question_id": rule["question_id"], "observed_at": observed_at, "as_of_date": as_of_date,
            "observation_status": observation_status, "observed_value": observed_value,
            "observed_unit": observed_unit or None, "summary": summary,
            "source_evidence_id": int(evidence["id"]) if evidence else None,
            "confidence": confidence, "materiality": materiality, "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO monitoring_observations({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM monitoring_observations WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="create", entity_type="monitoring_observation", entity_id=row_id, after=created)
        return row_id


def list_monitoring_observations(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = """SELECT o.*,r.title AS rule_title FROM monitoring_observations o
    JOIN monitoring_rules r ON r.id=o.rule_id WHERE o.review_id=?
    ORDER BY o.observed_at DESC,o.id DESC"""

    def query(c):
        return [dict(row) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def create_delta_item(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    question_id: str,
    change_type: str,
    proposed_action: str,
    rationale: str,
    observation_id: int | None = None,
    source_evidence_id: int | None = None,
    confidence: int = 3,
    materiality: int = 3,
    actor: str = "analyst",
) -> int:
    change_type = _choice(change_type, CHANGE_TYPES, "Loại thay đổi")
    proposed_action = _choice(proposed_action, PROPOSED_ACTIONS, "Hành động đề xuất")
    rationale = _text(rationale, label="Rationale", required=True)
    confidence = _score(confidence, "Độ tin cậy")
    materiality = _score(materiality, "Mức độ trọng yếu")

    with repo._conn() as c:
        review = _editable_review(repo, c, review_id, company_ref_id)
        if review["review_type"] != "delta" or not review.get("prior_review_id"):
            raise ValidationError("Delta item chỉ được tạo trong delta review có prior completed review.")
        prior = repo.get_review(int(review["prior_review_id"]), conn=c)
        if not prior or prior["status"] != "completed":
            raise ValidationError("Prior review của delta review phải ở trạng thái completed.")
        question = _question(repo, c, question_id)
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        observation = None
        if observation_id:
            observation = repo._d(c.execute(
                "SELECT * FROM monitoring_observations WHERE id=? AND review_id=?",
                (int(observation_id), review_id),
            ).fetchone())
            if not observation or observation["question_id"] != question["question_id"]:
                raise ValidationError("Observation phải thuộc cùng delta review và Question ID.")
        baseline = repo._d(c.execute(
            "SELECT * FROM analyst_assessments WHERE review_id=? AND question_id=? ORDER BY version_no DESC,id DESC LIMIT 1",
            (prior["id"], question["question_id"]),
        ).fetchone())
        duplicate = c.execute(
            "SELECT id FROM delta_review_items WHERE review_id=? AND question_id=? AND COALESCE(observation_id,0)=COALESCE(?,0)",
            (review_id, question["question_id"], int(observation_id) if observation_id else None),
        ).fetchone()
        if duplicate:
            raise ValidationError(f"Delta item đã tồn tại (#{duplicate['id']}).")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id),
            "prior_review_id": int(prior["id"]), "question_id": question["question_id"],
            "observation_id": int(observation_id) if observation_id else None,
            "change_type": change_type, "proposed_action": proposed_action, "rationale": rationale,
            "baseline_assessment_id": int(baseline["id"]) if baseline else None,
            "source_evidence_id": int(evidence["id"]) if evidence else None,
            "confidence": confidence, "materiality": materiality, "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO delta_review_items({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM delta_review_items WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="create", entity_type="delta_review_item", entity_id=row_id, after=created)
        return row_id


def record_delta_decision(
    repo,
    *,
    delta_item_id: int,
    decision: str,
    decision_reason: str,
    resulting_assessment_id: int | None = None,
    actor: str = "analyst",
) -> int:
    decision = _choice(decision, DECISIONS, "Quyết định")
    decision_reason = _text(decision_reason, label="Lý do quyết định", required=True, limit=3000)
    with repo._conn() as c:
        item = repo._d(c.execute("SELECT * FROM delta_review_items WHERE id=?", (int(delta_item_id),)).fetchone())
        if not item:
            raise ValidationError("Delta item không tồn tại.")
        _editable_review(repo, c, int(item["review_id"]), int(item["company_ref_id"]))
        if c.execute("SELECT id FROM delta_review_decisions WHERE delta_item_id=?", (delta_item_id,)).fetchone():
            raise ValidationError("Delta item đã có quyết định bất biến.")
        assessment = None
        if resulting_assessment_id:
            assessment = repo._d(c.execute(
                "SELECT * FROM analyst_assessments WHERE id=? AND review_id=? AND question_id=?",
                (int(resulting_assessment_id), item["review_id"], item["question_id"]),
            ).fetchone())
            if not assessment:
                raise ValidationError("Assessment kết quả phải thuộc cùng delta review và Question ID.")
        if decision != "dismiss" and not assessment:
            raise ValidationError("Hãy cập nhật Analyst Workspace trước, rồi liên kết assessment kết quả để đóng delta item.")
        if decision == "carry_forward" and not bool(assessment.get("analyst_confirmed")):
            raise ValidationError("Carry-forward cần assessment được analyst xác nhận unchanged.")
        if decision == "research_gap" and assessment.get("status") != "research_gap":
            raise ValidationError("Quyết định research gap phải liên kết assessment status=research_gap.")
        if decision == "revise" and assessment.get("status") not in {"answered", "needs_review"}:
            raise ValidationError("Quyết định revise phải liên kết assessment answered/needs_review.")
        fields = {
            "delta_item_id": int(delta_item_id), "company_ref_id": int(item["company_ref_id"]),
            "review_id": int(item["review_id"]), "question_id": item["question_id"],
            "decision": decision, "decision_reason": decision_reason,
            "resulting_assessment_id": int(assessment["id"]) if assessment else None,
            "decided_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO delta_review_decisions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM delta_review_decisions WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=item["company_ref_id"], review_id=item["review_id"], actor=actor,
                    action="decide", entity_type="delta_review_item", entity_id=delta_item_id,
                    before=item, after=created)
        return row_id


def list_delta_items(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = """SELECT i.*,d.id AS decision_id,d.decision,d.decision_reason,d.resulting_assessment_id,
    d.decided_by,d.created_at AS decided_at FROM delta_review_items i
    LEFT JOIN delta_review_decisions d ON d.delta_item_id=i.id
    WHERE i.review_id=? ORDER BY (d.id IS NULL) DESC,i.materiality DESC,i.id DESC"""

    def query(c):
        return [dict(row) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def monitoring_delta_bundle(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    def build(c):
        rules = list_monitoring_rules(repo, review_id, conn=c)
        observations = list_monitoring_observations(repo, review_id, conn=c)
        items = list_delta_items(repo, review_id, conn=c)
        summary = {
            "active_rules": sum(bool(row["active"]) for row in rules),
            "triggered_observations": sum(row["observation_status"] == "triggered" for row in observations),
            "open_delta_items": sum(not row.get("decision_id") for row in items),
            "closed_delta_items": sum(bool(row.get("decision_id")) for row in items),
            "research_gaps": sum(row["observation_status"] in {"unknown", "research_gap"} for row in observations),
        }
        return {"rules": rules, "observations": observations, "delta_items": items, "summary": summary}

    if conn is not None:
        return build(conn)
    with repo._conn() as c:
        return build(c)


def snapshot_monitoring_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    bundle = monitoring_delta_bundle(repo, review_id, conn=conn)
    return {"schema": "monitoring-delta-review-v1", **bundle}


__all__ = [
    "CADENCES", "CHANGE_TYPES", "COMPARISON_OPERATORS", "DECISIONS", "OBSERVATION_STATUSES",
    "PROPOSED_ACTIONS", "TRIGGER_TYPES", "add_monitoring_observation", "create_delta_item",
    "list_delta_items", "list_monitoring_observations", "list_monitoring_rules",
    "monitoring_delta_bundle", "normalize_rule_key", "record_delta_decision",
    "save_monitoring_rule", "snapshot_monitoring_for_review",
]
