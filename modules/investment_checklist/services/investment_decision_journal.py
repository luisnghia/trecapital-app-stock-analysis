from __future__ import annotations

"""Phase 7 governed investment memo and decision journal.

The module stores analyst-authored research products only.  It never writes Q01-Q59,
never calls an AI provider, and never infers or emits a trading decision by itself.
"""

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from ..repositories.sqlite_repository import ValidationError


PILLAR_TYPES = ("business", "moat", "management", "financial", "valuation", "catalyst", "risk", "other")
PILLAR_STATUSES = ("supported", "mixed", "contradicted", "research_gap")
RISK_CATEGORIES = ("business", "financial", "management", "valuation", "industry", "regulatory", "governance", "execution", "other")
RISK_STATUSES = ("open", "monitoring", "mitigated", "realized", "closed")
INVESTMENT_DECISIONS = ("pass", "watch", "buy", "add", "hold", "trim", "sell")
CAPITAL_DECISIONS = ("buy", "add", "hold", "trim", "sell")
THESIS_STATUSES = ("intact", "weakened", "broken", "realized", "unknown")
OUTCOME_LABELS = ("pending", "positive", "negative", "mixed", "unknown")

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, *, label: str, required: bool = False, limit: int = 12000) -> str:
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


def _months(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Thời hạn phải nằm trong khoảng 1–120 tháng.") from exc
    if not 1 <= result <= 120:
        raise ValidationError("Thời hạn phải nằm trong khoảng 1–120 tháng.")
    return result


def _optional_float(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải là số.") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValidationError(f"{label} phải là số hữu hạn.")
    return result


def normalize_journal_key(value: Any, *, label: str) -> str:
    raw = _text(value, label=label, required=True, limit=80).casefold()
    key = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    if not _KEY_RE.fullmatch(key):
        raise ValidationError(f"{label} cần 2–80 ký tự a-z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang.")
    return key


def _editable_review(repo, c, review_id: int, company_ref_id: int | None = None) -> dict[str, Any]:
    review = repo.get_review(int(review_id), conn=c)
    if not review:
        raise ValidationError("Review không tồn tại.")
    if review["status"] == "completed":
        raise ValidationError("Review đã finalize; Investment Memo & Decision Journal là read-only.")
    if company_ref_id is not None and int(review["company_ref_id"]) != int(company_ref_id):
        raise ValidationError("Dữ liệu quyết định không thuộc đúng doanh nghiệp của review.")
    return review


def _ensure_unsigned(c, review_id: int) -> None:
    if c.execute("SELECT id FROM investment_decisions WHERE review_id=?", (int(review_id),)).fetchone():
        raise ValidationError("Review đã có quyết định bất biến; memo, pillar và risk register đã được niêm phong.")


def _evidence(repo, c, evidence_id: int | None, company_ref_id: int, label: str = "Evidence") -> dict[str, Any] | None:
    if evidence_id in (None, "", 0, "0"):
        return None
    row = repo._d(c.execute("SELECT * FROM research_evidence WHERE id=?", (int(evidence_id),)).fetchone())
    if not row or int(row["company_ref_id"]) != int(company_ref_id):
        raise ValidationError(f"{label} không thuộc doanh nghiệp đang phân tích.")
    return row


def _latest_rows(repo, c, table: str, key_column: str, review_id: int, order: str) -> list[dict[str, Any]]:
    sql = (
        f"SELECT x.* FROM {table} x WHERE x.review_id=? AND NOT EXISTS("
        f"SELECT 1 FROM {table} n WHERE n.review_id=x.review_id AND n.{key_column}=x.{key_column} "
        "AND n.version_no>x.version_no) " + order
    )
    return [dict(row) for row in c.execute(sql, (int(review_id),))]


def save_investment_memo(
    repo, *, company_ref_id: int, review_id: int, title: str, thesis_summary: str,
    variant_perception: str, business_quality: str, valuation_summary: str,
    catalysts: str, invalidation_conditions: str, time_horizon_months: int,
    memo_key: str = "primary", source_evidence_id: int | None = None,
    change_reason: str = "", actor: str = "analyst",
) -> int:
    key = normalize_journal_key(memo_key, label="Memo key")
    values = {
        "title": _text(title, label="Tiêu đề memo", required=True, limit=500),
        "thesis_summary": _text(thesis_summary, label="Investment thesis", required=True),
        "variant_perception": _text(variant_perception, label="Variant perception", required=True),
        "business_quality": _text(business_quality, label="Chất lượng doanh nghiệp", required=True),
        "valuation_summary": _text(valuation_summary, label="Tóm tắt định giá", required=True),
        "catalysts": _text(catalysts, label="Catalyst", required=True),
        "invalidation_conditions": _text(invalidation_conditions, label="Điều kiện bác bỏ thesis", required=True),
    }
    months = _months(time_horizon_months)
    reason = _text(change_reason, label="Lý do tạo version mới", limit=2000)
    actor = _text(actor, label="Analyst", required=True, limit=200)
    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _ensure_unsigned(c, review_id)
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        previous = repo._d(c.execute(
            "SELECT * FROM investment_memo_versions WHERE review_id=? AND memo_key=? "
            "ORDER BY version_no DESC,id DESC LIMIT 1", (int(review_id), key),
        ).fetchone())
        if previous and not reason:
            raise ValidationError("Lý do tạo version memo mới là bắt buộc.")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "memo_key": key,
            "version_no": int(previous["version_no"]) + 1 if previous else 1, **values,
            "time_horizon_months": months,
            "source_evidence_id": int(evidence["id"]) if evidence else None,
            "change_reason": reason or None,
            "supersedes_memo_id": int(previous["id"]) if previous else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO investment_memo_versions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM investment_memo_versions WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="investment_memo", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_investment_memos(repo, review_id: int, *, conn=None, latest_only: bool = True) -> list[dict[str, Any]]:
    def query(c):
        if latest_only:
            return _latest_rows(repo, c, "investment_memo_versions", "memo_key", review_id,
                                "ORDER BY x.memo_key,x.version_no DESC")
        return [dict(row) for row in c.execute(
            "SELECT * FROM investment_memo_versions WHERE review_id=? ORDER BY memo_key,version_no DESC,id DESC",
            (int(review_id),),
        )]
    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def save_thesis_pillar(
    repo, *, company_ref_id: int, review_id: int, pillar_key: str, pillar_type: str,
    statement_text: str, status: str, falsification_test: str, confidence: int,
    materiality: int, supporting_evidence_id: int | None = None,
    contradicting_evidence_id: int | None = None, change_reason: str = "",
    actor: str = "analyst",
) -> int:
    key = normalize_journal_key(pillar_key, label="Pillar key")
    pillar_type = _choice(pillar_type, PILLAR_TYPES, "Loại pillar")
    status = _choice(status, PILLAR_STATUSES, "Trạng thái pillar")
    statement = _text(statement_text, label="Nội dung pillar", required=True)
    falsification = _text(falsification_test, label="Falsification test", required=True)
    confidence = _score(confidence, "Độ tin cậy")
    materiality = _score(materiality, "Mức độ trọng yếu")
    reason = _text(change_reason, label="Lý do tạo version mới", limit=2000)
    actor = _text(actor, label="Analyst", required=True, limit=200)
    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _ensure_unsigned(c, review_id)
        support = _evidence(repo, c, supporting_evidence_id, company_ref_id, "Supporting evidence")
        contradict = _evidence(repo, c, contradicting_evidence_id, company_ref_id, "Contradicting evidence")
        if status in {"supported", "mixed"} and not support:
            raise ValidationError("Pillar supported/mixed bắt buộc có supporting evidence.")
        if status in {"contradicted", "mixed"} and not contradict:
            raise ValidationError("Pillar contradicted/mixed bắt buộc có contradicting evidence.")
        previous = repo._d(c.execute(
            "SELECT * FROM investment_thesis_pillars WHERE review_id=? AND pillar_key=? "
            "ORDER BY version_no DESC,id DESC LIMIT 1", (int(review_id), key),
        ).fetchone())
        if previous and not reason:
            raise ValidationError("Lý do tạo version pillar mới là bắt buộc.")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "pillar_key": key,
            "version_no": int(previous["version_no"]) + 1 if previous else 1,
            "pillar_type": pillar_type, "statement_text": statement, "status": status,
            "supporting_evidence_id": int(support["id"]) if support else None,
            "contradicting_evidence_id": int(contradict["id"]) if contradict else None,
            "falsification_test": falsification, "confidence": confidence, "materiality": materiality,
            "change_reason": reason or None,
            "supersedes_pillar_id": int(previous["id"]) if previous else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO investment_thesis_pillars({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM investment_thesis_pillars WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="investment_thesis_pillar", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_thesis_pillars(repo, review_id: int, *, conn=None, latest_only: bool = True) -> list[dict[str, Any]]:
    def query(c):
        if latest_only:
            return _latest_rows(repo, c, "investment_thesis_pillars", "pillar_key", review_id,
                                "ORDER BY x.materiality DESC,x.pillar_key")
        return [dict(row) for row in c.execute(
            "SELECT * FROM investment_thesis_pillars WHERE review_id=? ORDER BY pillar_key,version_no DESC,id DESC",
            (int(review_id),),
        )]
    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def save_risk_register_item(
    repo, *, company_ref_id: int, review_id: int, risk_key: str, risk_category: str,
    statement_text: str, probability: int, impact: int, resilience: int, mitigation: str,
    early_warning: str, status: str, source_evidence_id: int | None = None,
    monitoring_rule_id: int | None = None, change_reason: str = "", actor: str = "analyst",
) -> int:
    key = normalize_journal_key(risk_key, label="Risk key")
    category = _choice(risk_category, RISK_CATEGORIES, "Nhóm rủi ro")
    status = _choice(status, RISK_STATUSES, "Trạng thái rủi ro")
    statement = _text(statement_text, label="Nội dung rủi ro", required=True)
    probability = _score(probability, "Xác suất")
    impact = _score(impact, "Tác động")
    resilience = _score(resilience, "Khả năng chống chịu")
    mitigation = _text(mitigation, label="Biện pháp giảm thiểu", required=True)
    early_warning = _text(early_warning, label="Chỉ báo cảnh báo sớm", required=True)
    reason = _text(change_reason, label="Lý do tạo version mới", limit=2000)
    actor = _text(actor, label="Analyst", required=True, limit=200)
    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _ensure_unsigned(c, review_id)
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        rule = None
        if monitoring_rule_id not in (None, "", 0, "0"):
            rule = repo._d(c.execute("SELECT * FROM monitoring_rules WHERE id=?", (int(monitoring_rule_id),)).fetchone())
            if not rule or int(rule["company_ref_id"]) != int(company_ref_id) or int(rule["review_id"]) != int(review_id):
                raise ValidationError("Monitoring rule không thuộc review hiện tại.")
        previous = repo._d(c.execute(
            "SELECT * FROM investment_risk_register WHERE review_id=? AND risk_key=? "
            "ORDER BY version_no DESC,id DESC LIMIT 1", (int(review_id), key),
        ).fetchone())
        if previous and not reason:
            raise ValidationError("Lý do tạo version risk mới là bắt buộc.")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "risk_key": key,
            "version_no": int(previous["version_no"]) + 1 if previous else 1,
            "risk_category": category, "statement_text": statement, "probability": probability,
            "impact": impact, "resilience": resilience, "mitigation": mitigation,
            "early_warning": early_warning, "status": status,
            "source_evidence_id": int(evidence["id"]) if evidence else None,
            "monitoring_rule_id": int(rule["id"]) if rule else None,
            "change_reason": reason or None,
            "supersedes_risk_id": int(previous["id"]) if previous else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO investment_risk_register({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM investment_risk_register WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="investment_risk", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_risk_register(repo, review_id: int, *, conn=None, latest_only: bool = True) -> list[dict[str, Any]]:
    def query(c):
        if latest_only:
            rows = _latest_rows(repo, c, "investment_risk_register", "risk_key", review_id,
                                "ORDER BY (x.probability*x.impact) DESC,x.risk_key")
        else:
            rows = [dict(row) for row in c.execute(
                "SELECT * FROM investment_risk_register WHERE review_id=? ORDER BY risk_key,version_no DESC,id DESC",
                (int(review_id),),
            )]
        for row in rows:
            row["risk_score"] = int(row["probability"]) * int(row["impact"])
            row["residual_score"] = row["risk_score"] * (6 - int(row["resilience"])) / 5
        return rows
    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def _research_snapshot(repo, c, review_id: int) -> dict[str, Any]:
    memos = list_investment_memos(repo, review_id, conn=c)
    pillars = list_thesis_pillars(repo, review_id, conn=c)
    risks = list_risk_register(repo, review_id, conn=c)
    return {
        "schema": "investment-decision-research-v1",
        "review_id": int(review_id),
        "review_metrics": repo.review_metrics(review_id, conn=c),
        "memos": memos,
        "thesis_pillars": pillars,
        "risk_register": risks,
    }


def record_investment_decision(
    repo, *, company_ref_id: int, review_id: int, decision: str, decision_reason: str,
    time_horizon_months: int, primary_invalidation: str, market_price: float | None = None,
    intrinsic_low: float | None = None, intrinsic_base: float | None = None,
    intrinsic_high: float | None = None, target_position_pct: float | None = None,
    max_position_pct: float | None = None, acknowledged_gaps: bool = False,
    analyst_confirmed: bool = False, actor: str = "analyst",
) -> int:
    decision = _choice(decision, INVESTMENT_DECISIONS, "Quyết định")
    reason = _text(decision_reason, label="Lý do quyết định", required=True)
    invalidation = _text(primary_invalidation, label="Điều kiện vô hiệu hóa chính", required=True)
    months = _months(time_horizon_months)
    market_price = _optional_float(market_price, "Giá thị trường")
    intrinsic_low = _optional_float(intrinsic_low, "Giá trị nội tại thấp")
    intrinsic_base = _optional_float(intrinsic_base, "Giá trị nội tại cơ sở")
    intrinsic_high = _optional_float(intrinsic_high, "Giá trị nội tại cao")
    target = _optional_float(target_position_pct, "Tỷ trọng mục tiêu")
    maximum = _optional_float(max_position_pct, "Tỷ trọng tối đa")
    actor = _text(actor, label="Analyst", required=True, limit=200)
    if not acknowledged_gaps:
        raise ValidationError("Analyst phải xác nhận đã đọc các research gap/contradiction còn mở.")
    if not analyst_confirmed:
        raise ValidationError("Quyết định chỉ được lưu sau xác nhận trực tiếp của analyst.")
    if target is not None and not 0 <= target <= 100:
        raise ValidationError("Tỷ trọng mục tiêu phải nằm trong khoảng 0–100%.")
    if maximum is not None and not 0 <= maximum <= 100:
        raise ValidationError("Tỷ trọng tối đa phải nằm trong khoảng 0–100%.")
    if target is not None and maximum is not None and target > maximum:
        raise ValidationError("Tỷ trọng mục tiêu không được lớn hơn tỷ trọng tối đa.")
    if decision in CAPITAL_DECISIONS:
        if market_price is None or market_price <= 0:
            raise ValidationError("Quyết định có sử dụng vốn cần giá thị trường dương.")
        if None in {intrinsic_low, intrinsic_base, intrinsic_high}:
            raise ValidationError("Quyết định có sử dụng vốn cần đủ ba kịch bản giá trị nội tại.")
        if not (0 < intrinsic_low <= intrinsic_base <= intrinsic_high):
            raise ValidationError("Kịch bản định giá phải thỏa 0 < low ≤ base ≤ high.")
    elif any(value is not None for value in (intrinsic_low, intrinsic_base, intrinsic_high)):
        if None in {intrinsic_low, intrinsic_base, intrinsic_high} or not (0 < intrinsic_low <= intrinsic_base <= intrinsic_high):
            raise ValidationError("Nếu nhập định giá, cần đủ kịch bản 0 < low ≤ base ≤ high.")

    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _ensure_unsigned(c, review_id)
        snapshot = _research_snapshot(repo, c, review_id)
        if not snapshot["memos"]:
            raise ValidationError("Cần ít nhất một memo trước khi ghi quyết định.")
        if not snapshot["thesis_pillars"]:
            raise ValidationError("Cần ít nhất một thesis pillar trước khi ghi quyết định.")
        if not snapshot["risk_register"]:
            raise ValidationError("Cần ít nhất một risk register item trước khi ghi quyết định.")
        memo = next((row for row in snapshot["memos"] if row["memo_key"] == "primary"), snapshot["memos"][0])
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        snapshot_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        mos = None
        if intrinsic_base is not None and market_price is not None and intrinsic_base > 0:
            mos = (intrinsic_base - market_price) / intrinsic_base
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "memo_id": int(memo["id"]),
            "decision": decision, "decision_reason": reason, "market_price": market_price,
            "intrinsic_low": intrinsic_low, "intrinsic_base": intrinsic_base, "intrinsic_high": intrinsic_high,
            "mos_base": mos, "target_position_pct": target, "max_position_pct": maximum,
            "time_horizon_months": months, "primary_invalidation": invalidation,
            "acknowledged_gaps": 1, "analyst_confirmed": 1,
            "memo_snapshot_json": snapshot_json, "memo_snapshot_hash": snapshot_hash,
            "decided_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO investment_decisions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM investment_decisions WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="analyst_sign", entity_type="investment_decision", entity_id=row_id,
                    after={k: v for k, v in created.items() if k != "memo_snapshot_json"})
        return row_id


def list_investment_decisions(repo, company_ref_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = (
        "SELECT d.*,r.as_of_date,r.status AS review_status,r.review_type FROM investment_decisions d "
        "JOIN research_reviews r ON r.id=d.review_id WHERE d.company_ref_id=? "
        "ORDER BY r.as_of_date DESC,d.id DESC"
    )
    def query(c):
        return [dict(row) for row in c.execute(sql, (int(company_ref_id),))]
    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def add_decision_outcome_review(
    repo, *, decision_id: int, company_ref_id: int, review_id: int, as_of_date,
    thesis_status: str, outcome_label: str, process_grade: int, outcome_summary: str,
    lessons_learned: str, market_price: float | None = None,
    source_evidence_id: int | None = None, actor: str = "analyst",
) -> int:
    thesis_status = _choice(thesis_status, THESIS_STATUSES, "Trạng thái thesis")
    outcome_label = _choice(outcome_label, OUTCOME_LABELS, "Kết quả")
    grade = _score(process_grade, "Process grade")
    summary = _text(outcome_summary, label="Tóm tắt outcome", required=True)
    lessons = _text(lessons_learned, label="Bài học quy trình", required=True)
    price = _optional_float(market_price, "Giá thị trường")
    if price is not None and price <= 0:
        raise ValidationError("Giá thị trường phải dương.")
    actor = _text(actor, label="Analyst", required=True, limit=200)
    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        decision = repo._d(c.execute("SELECT * FROM investment_decisions WHERE id=?", (int(decision_id),)).fetchone())
        if not decision or int(decision["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Quyết định gốc không thuộc doanh nghiệp đang phân tích.")
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        if (thesis_status != "unknown" or outcome_label not in {"pending", "unknown"}) and not evidence:
            raise ValidationError("Đánh giá outcome xác định bắt buộc có exact evidence.")
        fields = {
            "decision_id": int(decision_id), "company_ref_id": int(company_ref_id),
            "review_id": int(review_id), "as_of_date": repo._date(as_of_date), "market_price": price,
            "thesis_status": thesis_status, "outcome_label": outcome_label, "process_grade": grade,
            "outcome_summary": summary, "lessons_learned": lessons,
            "source_evidence_id": int(evidence["id"]) if evidence else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO decision_outcome_reviews({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM decision_outcome_reviews WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="create", entity_type="decision_outcome_review", entity_id=row_id, after=created)
        return row_id


def list_decision_outcomes(repo, company_ref_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = (
        "SELECT o.*,d.decision AS original_decision,d.created_at AS decision_created_at "
        "FROM decision_outcome_reviews o JOIN investment_decisions d ON d.id=o.decision_id "
        "WHERE o.company_ref_id=? ORDER BY o.as_of_date DESC,o.id DESC"
    )
    def query(c):
        return [dict(row) for row in c.execute(sql, (int(company_ref_id),))]
    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def decision_journal_bundle(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    def build(c):
        review = repo.get_review(review_id, conn=c)
        if not review:
            raise ValidationError("Review không tồn tại.")
        memos = list_investment_memos(repo, review_id, conn=c)
        pillars = list_thesis_pillars(repo, review_id, conn=c)
        risks = list_risk_register(repo, review_id, conn=c)
        decision = repo._d(c.execute("SELECT * FROM investment_decisions WHERE review_id=?", (int(review_id),)).fetchone())
        outcomes = list_decision_outcomes(repo, int(review["company_ref_id"]), conn=c)
        return {
            "memos": memos, "thesis_pillars": pillars, "risk_register": risks,
            "decision": decision, "outcomes": outcomes,
            "summary": {
                "memo_versions": len(memos), "pillars": len(pillars), "research_gaps": sum(p["status"] == "research_gap" for p in pillars),
                "contradicted": sum(p["status"] in {"mixed", "contradicted"} for p in pillars),
                "open_risks": sum(r["status"] in {"open", "monitoring", "realized"} for r in risks),
                "signed": bool(decision),
            },
        }
    if conn is not None:
        return build(conn)
    with repo._conn() as c:
        return build(c)


def snapshot_decision_journal_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    def build(c):
        bundle = decision_journal_bundle(repo, review_id, conn=c)
        decision_id = int(bundle["decision"]["id"]) if bundle["decision"] else None
        bundle["outcomes"] = [
            row for row in bundle["outcomes"]
            if int(row["review_id"]) == int(review_id)
            or (decision_id is not None and int(row["decision_id"]) == decision_id)
        ]
        return {"schema": "investment-memo-decision-journal-v1", **bundle}

    if conn is not None:
        return build(conn)
    with repo._conn() as c:
        return build(c)


__all__ = [
    "CAPITAL_DECISIONS", "INVESTMENT_DECISIONS", "OUTCOME_LABELS", "PILLAR_STATUSES",
    "PILLAR_TYPES", "RISK_CATEGORIES", "RISK_STATUSES", "THESIS_STATUSES",
    "add_decision_outcome_review", "decision_journal_bundle", "list_decision_outcomes",
    "list_investment_decisions", "list_investment_memos", "list_risk_register",
    "list_thesis_pillars", "normalize_journal_key", "record_investment_decision",
    "save_investment_memo", "save_risk_register_item", "save_thesis_pillar",
    "snapshot_decision_journal_for_review",
]
