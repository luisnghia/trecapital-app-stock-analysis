from __future__ import annotations

"""Phase 5 structured management and human-intelligence research.

The workspace stores evidence-backed research records and analyst signals.  It never writes the
final Q01-Q59 assessment: the Analyst Workspace remains the only place that can do that.
"""

from datetime import datetime, timezone
import json
import re
import uuid
from typing import Any

from ..repositories.sqlite_repository import ValidationError


MANAGEMENT_QUESTION_IDS = tuple(
    [f"Q{number:02d}" for number in range(33, 53)] + ["Q58", "Q59"]
)
MANAGEMENT_QUESTION_SET = frozenset(MANAGEMENT_QUESTION_IDS)

MANAGEMENT_DIMENSIONS = {
    "Q33": "Loại nhà quản lý",
    "Q34": "Tác động của lãnh đạo tuyển từ bên ngoài",
    "Q35": "Lion / Hyena - xây tổ chức hay tối ưu lợi ích ngắn hạn",
    "Q36": "Con đường thăng tiến và kinh nghiệm",
    "Q37": "Lương thưởng và sở hữu",
    "Q38": "Giao dịch cổ phiếu của lãnh đạo",
    "Q39": "Định hướng vì các stakeholder",
    "Q40": "Năng lực cải thiện vận hành hằng ngày",
    "Q41": "Chất lượng guidance CEO/CFO",
    "Q42": "Mức độ tập trung / phân quyền",
    "Q43": "Cách đối xử với nhân viên",
    "Q44": "Năng lực tuyển và giữ người giỏi",
    "Q45": "Kỷ luật chi phí",
    "Q46": "Kỷ luật phân bổ vốn",
    "Q47": "Kỷ luật mua lại cổ phiếu",
    "Q48": "Yêu doanh nghiệp hay chủ yếu vì tiền",
    "Q49": "Moment of integrity",
    "Q50": "Nhất quán giữa giao tiếp và hành động",
    "Q51": "Tư duy độc lập",
    "Q52": "Mức độ tự quảng bá",
    "Q58": "Quy trình ra quyết định M&A",
    "Q59": "Thành tích M&A 1/3/5 năm",
}

APPOINTMENT_TYPES = ("founder", "internal", "external", "unknown")
VERIFICATION_STATUSES = ("unverified", "verified", "disputed", "stale")
TIMELINE_EVENT_TYPES = (
    "joined", "promoted", "appointed", "role_changed", "departed", "board_change",
    "ownership_change", "compensation_change", "insider_trade", "other",
)
TRACK_RECORD_TYPES = (
    "compensation_ownership", "insider_transaction", "guidance", "capital_allocation",
    "buyback", "ma_decision", "ma_outcome", "integrity", "communication",
    "human_intelligence",
)
TRACK_RESULT_STATUSES = (
    "pending", "met", "partly_met", "missed", "value_created", "neutral",
    "value_destroyed", "verified", "disputed", "unknown",
)
HORIZONS = ("current", "1y", "3y", "5y", "other")
HUMAN_SOURCE_CATEGORIES = (
    "company", "customer", "competitor", "supplier", "employee", "industry_insider",
    "academic", "headhunter", "regulator", "other",
)
CORROBORATION_STATUSES = ("single_source", "corroborated", "contradicted", "not_applicable")
SIGNAL_STATUSES = ("supported", "contradicted", "mixed", "research_gap", "not_reviewed")

DEFAULT_TRACK_QUESTIONS = {
    "compensation_ownership": ("Q37",),
    "insider_transaction": ("Q38",),
    "guidance": ("Q41", "Q50"),
    "capital_allocation": ("Q46",),
    "buyback": ("Q47",),
    "ma_decision": ("Q58",),
    "ma_outcome": ("Q59",),
    "integrity": ("Q49",),
    "communication": ("Q50", "Q52"),
    "human_intelligence": MANAGEMENT_QUESTION_IDS,
}

_PERSON_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, *, label: str, required: bool = False, limit: int = 5000) -> str:
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


def _score(value: Any, label: str, *, low: int = 1, high: int = 5) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải nằm trong khoảng {low}–{high}.") from exc
    if not low <= result <= high:
        raise ValidationError(f"{label} phải nằm trong khoảng {low}–{high}.")
    return result


def _optional_float(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải là số.") from exc


def _date(repo, value: Any, label: str, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise ValidationError(f"{label} là bắt buộc.")
        return None
    return repo._date(value)


def normalize_person_key(value: Any) -> str:
    raw = _text(value, label="Person key", required=True, limit=80).casefold()
    key = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    if not _PERSON_KEY_RE.fullmatch(key):
        raise ValidationError("Person key cần 2–80 ký tự a-z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang.")
    return key


def _editable_review(repo, c, review_id: int, company_ref_id: int | None = None) -> dict[str, Any]:
    review = repo.get_review(int(review_id), conn=c)
    if not review:
        raise ValidationError("Review không tồn tại.")
    if review["status"] == "completed":
        raise ValidationError("Review đã finalize; Management & Human Intelligence là read-only.")
    if company_ref_id is not None and int(review["company_ref_id"]) != int(company_ref_id):
        raise ValidationError("Dữ liệu management không thuộc đúng doanh nghiệp của review.")
    return review


def _evidence(repo, c, evidence_id: int | None, company_ref_id: int) -> dict[str, Any] | None:
    if evidence_id in (None, "", 0, "0"):
        return None
    row = repo._d(c.execute("SELECT * FROM research_evidence WHERE id=?", (int(evidence_id),)).fetchone())
    if not row or int(row["company_ref_id"]) != int(company_ref_id):
        raise ValidationError("Evidence không thuộc doanh nghiệp đang phân tích.")
    return row


def _question_ids(values: Any, *, record_type: str | None = None) -> tuple[str, ...]:
    if values in (None, ""):
        values = DEFAULT_TRACK_QUESTIONS.get(str(record_type), ())
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    result: list[str] = []
    for value in values or ():
        qid = str(value).strip().upper()
        if qid not in MANAGEMENT_QUESTION_SET:
            raise ValidationError(f"{qid} không thuộc phạm vi management Q33–Q52/Q58–Q59.")
        if qid not in result:
            result.append(qid)
    if not result:
        raise ValidationError("Cần liên kết ít nhất một câu hỏi management.")
    allowed = set(DEFAULT_TRACK_QUESTIONS.get(str(record_type), MANAGEMENT_QUESTION_IDS))
    if record_type != "human_intelligence" and not set(result).issubset(allowed):
        raise ValidationError(f"Record {record_type} chỉ được liên kết: {', '.join(sorted(allowed))}.")
    return tuple(result)


def save_person_version(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    person_key: str,
    full_name: str,
    current_title: str,
    appointment_type: str = "unknown",
    start_date=None,
    end_date=None,
    is_key_manager: bool = True,
    ownership_pct: float | None = None,
    compensation_note: str = "",
    source_evidence_id: int | None = None,
    verification_status: str = "unverified",
    change_reason: str = "",
    actor: str = "analyst",
) -> int:
    key = normalize_person_key(person_key)
    full_name = _text(full_name, label="Tên manager", required=True, limit=300)
    current_title = _text(current_title, label="Chức danh", required=True, limit=300)
    appointment_type = _choice(appointment_type, APPOINTMENT_TYPES, "Nguồn bổ nhiệm")
    start_date = _date(repo, start_date, "Ngày bắt đầu")
    end_date = _date(repo, end_date, "Ngày kết thúc")
    ownership_pct = _optional_float(ownership_pct, "Tỷ lệ sở hữu")
    if ownership_pct is not None and not 0 <= ownership_pct <= 100:
        raise ValidationError("Tỷ lệ sở hữu phải nằm trong khoảng 0–100%.")
    compensation_note = _text(compensation_note, label="Ghi chú lương thưởng", limit=5000)
    verification_status = _choice(verification_status, VERIFICATION_STATUSES, "Trạng thái xác minh")
    change_reason = _text(change_reason, label="Lý do thay đổi", limit=2000)

    with repo._conn() as c:
        review = _editable_review(repo, c, review_id, company_ref_id)
        evidence = _evidence(repo, c, source_evidence_id, company_ref_id)
        previous = repo._d(c.execute(
            "SELECT * FROM management_people_versions WHERE review_id=? AND person_key=? ORDER BY version_no DESC,id DESC LIMIT 1",
            (review_id, key),
        ).fetchone())
        if previous and not change_reason:
            raise ValidationError("Lý do tạo version hồ sơ manager mới là bắt buộc.")
        version_no = int(previous["version_no"]) + 1 if previous else 1
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "person_key": key,
            "version_no": version_no, "full_name": full_name, "current_title": current_title,
            "appointment_type": appointment_type, "start_date": start_date, "end_date": end_date,
            "is_key_manager": int(bool(is_key_manager)), "ownership_pct": ownership_pct,
            "compensation_note": compensation_note or None,
            "source_evidence_id": int(evidence["id"]) if evidence else None,
            "verification_status": verification_status, "change_reason": change_reason or None,
            "supersedes_version_id": int(previous["id"]) if previous else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO management_people_versions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM management_people_versions WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="management_person", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_people(repo, review_id: int, *, conn=None, latest_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM management_people_versions WHERE review_id=?"
    if latest_only:
        sql += " AND NOT EXISTS(SELECT 1 FROM management_people_versions n WHERE n.review_id=management_people_versions.review_id AND n.person_key=management_people_versions.person_key AND n.version_no>management_people_versions.version_no)"
    sql += " ORDER BY is_key_manager DESC,full_name,version_no DESC"

    def query(c):
        return [dict(row) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def add_timeline_event(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    person_key: str,
    event_date,
    event_type: str,
    organization: str,
    role_title: str,
    event_summary: str,
    end_date=None,
    external_hire: bool = False,
    source_evidence_id: int | None = None,
    confidence: int = 3,
    supersedes_event_id: int | None = None,
    change_reason: str = "",
    actor: str = "analyst",
) -> int:
    key = normalize_person_key(person_key)
    event_date = _date(repo, event_date, "Ngày sự kiện", required=True)
    end_date = _date(repo, end_date, "Ngày kết thúc")
    event_type = _choice(event_type, TIMELINE_EVENT_TYPES, "Loại sự kiện")
    organization = _text(organization, label="Tổ chức", required=True, limit=300)
    role_title = _text(role_title, label="Chức danh", required=True, limit=300)
    event_summary = _text(event_summary, label="Mô tả sự kiện", required=True, limit=5000)
    confidence = _score(confidence, "Độ tin cậy")
    change_reason = _text(change_reason, label="Lý do correction", limit=2000)
    if supersedes_event_id and not change_reason:
        raise ValidationError("Lý do correction timeline là bắt buộc.")

    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _evidence(repo, c, source_evidence_id, company_ref_id)
        previous = None
        if supersedes_event_id:
            previous = repo._d(c.execute(
                "SELECT * FROM management_timeline_events WHERE id=? AND review_id=?",
                (int(supersedes_event_id), review_id),
            ).fetchone())
            if not previous:
                raise ValidationError("Timeline event cần correction không tồn tại trong review.")
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "person_key": key,
            "event_date": event_date, "end_date": end_date, "event_type": event_type,
            "organization": organization, "role_title": role_title, "event_summary": event_summary,
            "external_hire": int(bool(external_hire)),
            "source_evidence_id": int(source_evidence_id) if source_evidence_id else None,
            "confidence": confidence, "supersedes_event_id": int(supersedes_event_id) if supersedes_event_id else None,
            "change_reason": change_reason or None, "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO management_timeline_events({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM management_timeline_events WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="create_correction" if previous else "create", entity_type="management_timeline_event",
                    entity_id=row_id, before=previous, after=created)
        return row_id


def list_timeline_events(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = """SELECT e.* FROM management_timeline_events e
    WHERE e.review_id=? AND NOT EXISTS(
        SELECT 1 FROM management_timeline_events n WHERE n.supersedes_event_id=e.id
    ) ORDER BY e.event_date DESC,e.id DESC"""

    def query(c):
        return [dict(row) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def save_track_record(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    record_type: str,
    title: str,
    statement_text: str,
    question_ids: Any = None,
    subject_key: str = "management-team",
    event_date=None,
    period_label: str = "",
    expected_outcome: str = "",
    actual_outcome: str = "",
    result_status: str = "unknown",
    horizon: str = "current",
    amount_value: float | None = None,
    currency: str = "VND",
    source_category: str = "company",
    credibility: int = 3,
    corroboration_status: str = "not_applicable",
    confidential: bool = False,
    source_evidence_id: int | None = None,
    record_key: str | None = None,
    change_reason: str = "",
    actor: str = "analyst",
) -> int:
    record_type = _choice(record_type, TRACK_RECORD_TYPES, "Loại track record")
    title = _text(title, label="Tiêu đề", required=True, limit=500)
    statement_text = _text(statement_text, label="Sự kiện / phát biểu / quyết định", required=True, limit=8000)
    qids = _question_ids(question_ids, record_type=record_type)
    subject_key = normalize_person_key(subject_key)
    event_date = _date(repo, event_date, "Ngày sự kiện")
    period_label = _text(period_label, label="Kỳ đánh giá", limit=200)
    expected_outcome = _text(expected_outcome, label="Kết quả kỳ vọng", limit=5000)
    actual_outcome = _text(actual_outcome, label="Kết quả thực tế", limit=5000)
    result_status = _choice(result_status, TRACK_RESULT_STATUSES, "Kết quả")
    horizon = _choice(horizon, HORIZONS, "Mốc hậu kiểm")
    amount_value = _optional_float(amount_value, "Giá trị giao dịch")
    currency = _text(currency, label="Đơn vị tiền", required=True, limit=20).upper()
    source_category = _choice(source_category, HUMAN_SOURCE_CATEGORIES, "Nhóm nguồn Human Intelligence")
    credibility = _score(credibility, "Độ tin cậy nguồn")
    corroboration_status = _choice(corroboration_status, CORROBORATION_STATUSES, "Trạng thái kiểm chứng chéo")
    change_reason = _text(change_reason, label="Lý do tạo version mới", limit=2000)
    key = str(record_key or uuid.uuid4())

    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _evidence(repo, c, source_evidence_id, company_ref_id)
        previous = None
        if record_key:
            previous = repo._d(c.execute(
                "SELECT * FROM management_track_records WHERE review_id=? AND record_key=? ORDER BY version_no DESC,id DESC LIMIT 1",
                (review_id, key),
            ).fetchone())
            if not previous:
                raise ValidationError("Record key cần tạo version mới không tồn tại.")
            if not change_reason:
                raise ValidationError("Lý do tạo version track record mới là bắt buộc.")
            if previous["record_type"] != record_type:
                raise ValidationError("Không được đổi loại track record giữa các version.")
        version_no = int(previous["version_no"]) + 1 if previous else 1
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "record_key": key,
            "version_no": version_no, "record_type": record_type, "subject_key": subject_key,
            "event_date": event_date, "period_label": period_label or None, "title": title,
            "statement_text": statement_text, "expected_outcome": expected_outcome or None,
            "actual_outcome": actual_outcome or None, "result_status": result_status, "horizon": horizon,
            "amount_value": amount_value, "currency": currency, "source_category": source_category,
            "credibility": credibility, "corroboration_status": corroboration_status,
            "confidential": int(bool(confidential)),
            "source_evidence_id": int(source_evidence_id) if source_evidence_id else None,
            "question_ids_json": json.dumps(qids, ensure_ascii=False),
            "change_reason": change_reason or None,
            "supersedes_record_id": int(previous["id"]) if previous else None,
            "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO management_track_records({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM management_track_records WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="management_track_record", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_track_records(repo, review_id: int, *, conn=None, record_type: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [review_id]
    sql = """SELECT r.* FROM management_track_records r WHERE r.review_id=?
    AND NOT EXISTS(SELECT 1 FROM management_track_records n WHERE n.review_id=r.review_id AND n.record_key=r.record_key AND n.version_no>r.version_no)"""
    if record_type:
        sql += " AND r.record_type=?"
        params.append(_choice(record_type, TRACK_RECORD_TYPES, "Loại track record"))
    sql += " ORDER BY COALESCE(r.event_date,r.created_at) DESC,r.id DESC"

    def query(c):
        rows = [dict(row) for row in c.execute(sql, tuple(params))]
        for row in rows:
            row["question_ids"] = json.loads(row.pop("question_ids_json"))
        return rows

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def save_management_signal(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    question_id: str,
    subject_key: str,
    signal_status: str,
    rationale: str,
    signal_score: int | None = None,
    confidence: int = 3,
    materiality: int = 3,
    source_evidence_id: int | None = None,
    change_reason: str = "",
    actor: str = "analyst",
) -> int:
    qid = str(question_id or "").strip().upper()
    if qid not in MANAGEMENT_QUESTION_SET:
        raise ValidationError("Question ID không thuộc Q33–Q52/Q58–Q59.")
    subject_key = normalize_person_key(subject_key)
    signal_status = _choice(signal_status, SIGNAL_STATUSES, "Trạng thái tín hiệu")
    rationale = _text(rationale, label="Rationale", required=True, limit=8000)
    confidence = _score(confidence, "Độ tin cậy")
    materiality = _score(materiality, "Mức độ trọng yếu")
    change_reason = _text(change_reason, label="Lý do thay đổi", limit=2000)
    if signal_status in {"research_gap", "not_reviewed"}:
        if signal_score is not None:
            raise ValidationError("Research gap/not reviewed không được gán điểm; Unknown khác Neutral.")
    elif signal_score not in {-2, -1, 0, 1, 2}:
        raise ValidationError("Signal score -2..+2 là bắt buộc cho tín hiệu đã nghiên cứu.")

    with repo._conn() as c:
        _editable_review(repo, c, review_id, company_ref_id)
        _evidence(repo, c, source_evidence_id, company_ref_id)
        previous = repo._d(c.execute(
            """SELECT * FROM management_question_signals WHERE review_id=? AND question_id=? AND subject_key=?
            ORDER BY version_no DESC,id DESC LIMIT 1""",
            (review_id, qid, subject_key),
        ).fetchone())
        if previous and previous.get("signal_score") != signal_score and not change_reason:
            raise ValidationError("Lý do thay đổi signal score là bắt buộc.")
        version_no = int(previous["version_no"]) + 1 if previous else 1
        fields = {
            "company_ref_id": int(company_ref_id), "review_id": int(review_id), "question_id": qid,
            "subject_key": subject_key, "version_no": version_no, "signal_status": signal_status,
            "signal_score": signal_score, "confidence": confidence, "materiality": materiality,
            "rationale": rationale,
            "source_evidence_id": int(source_evidence_id) if source_evidence_id else None,
            "change_reason": change_reason or None, "created_by": actor, "created_at": _now(),
        }
        cur = c.execute(
            f"INSERT INTO management_question_signals({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        row_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM management_question_signals WHERE id=?", (row_id,)).fetchone())
        repo._audit(c, company_ref_id=company_ref_id, review_id=review_id, actor=actor,
                    action="append_version", entity_type="management_question_signal", entity_id=row_id,
                    before=previous, after=created)
        return row_id


def list_management_signals(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = """SELECT s.* FROM management_question_signals s WHERE s.review_id=? AND NOT EXISTS(
        SELECT 1 FROM management_question_signals n
        WHERE n.review_id=s.review_id AND n.question_id=s.question_id AND n.subject_key=s.subject_key
          AND n.version_no>s.version_no
    ) ORDER BY CAST(SUBSTR(s.question_id,2) AS INTEGER),s.subject_key"""

    def query(c):
        return [dict(row) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return query(conn)
    with repo._conn() as c:
        return query(c)


def _management_summary_from_rows(
    people: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    records: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    covered = sorted({row["question_id"] for row in signals if row["signal_status"] not in {"research_gap", "not_reviewed"}})
    evidence_backed = sorted({
        row["question_id"] for row in signals
        if row["signal_status"] not in {"research_gap", "not_reviewed"} and row.get("source_evidence_id")
    })
    gaps = sorted(MANAGEMENT_QUESTION_SET - set(covered), key=lambda value: int(value[1:]))
    return {
        "question_total": len(MANAGEMENT_QUESTION_IDS), "covered_questions": covered,
        "evidence_backed_questions": evidence_backed, "research_gaps": gaps,
        "coverage_pct": len(covered) / len(MANAGEMENT_QUESTION_IDS),
        "evidence_coverage_pct": len(evidence_backed) / len(MANAGEMENT_QUESTION_IDS),
        "key_manager_count": sum(bool(row["is_key_manager"]) for row in people),
        "people_count": len(people), "timeline_event_count": len(timeline),
        "track_record_count": len(records), "signal_count": len(signals),
        "human_intelligence_count": sum(row["record_type"] == "human_intelligence" for row in records),
    }


def management_research_bundle(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    """Load all Phase 5 read models through one pooled connection.

    The four SELECTs remain deliberately separate and auditable, but keeping them inside a single
    connection removes repeated Supabase/PgBouncer checkout latency.  The returned rows are also
    reused by the selected sub-view instead of immediately querying the same table again.
    """
    def build(c):
        people = list_people(repo, review_id, conn=c)
        timeline = list_timeline_events(repo, review_id, conn=c)
        records = list_track_records(repo, review_id, conn=c)
        signals = list_management_signals(repo, review_id, conn=c)
        return {
            "people": people,
            "timeline": timeline,
            "track_records": records,
            "signals": signals,
            "summary": _management_summary_from_rows(people, timeline, records, signals),
        }

    if conn is not None:
        return build(conn)
    with repo._conn() as c:
        return build(c)


def management_research_summary(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    return management_research_bundle(repo, review_id, conn=conn)["summary"]


def snapshot_management_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    bundle = management_research_bundle(repo, review_id, conn=conn)
    return {
        "schema": "management-human-intelligence-v1",
        "question_scope": list(MANAGEMENT_QUESTION_IDS),
        "summary": bundle["summary"],
        "people": bundle["people"],
        "timeline": bundle["timeline"],
        "track_records": bundle["track_records"],
        "question_signals": bundle["signals"],
    }


__all__ = [
    "APPOINTMENT_TYPES", "CORROBORATION_STATUSES", "DEFAULT_TRACK_QUESTIONS",
    "HORIZONS", "HUMAN_SOURCE_CATEGORIES", "MANAGEMENT_DIMENSIONS",
    "MANAGEMENT_QUESTION_IDS", "SIGNAL_STATUSES", "TIMELINE_EVENT_TYPES",
    "TRACK_RECORD_TYPES", "TRACK_RESULT_STATUSES", "VERIFICATION_STATUSES",
    "add_timeline_event", "list_management_signals", "list_people", "list_timeline_events",
    "list_track_records", "management_research_bundle", "management_research_summary", "normalize_person_key",
    "save_management_signal", "save_person_version", "save_track_record",
    "snapshot_management_for_review",
]
