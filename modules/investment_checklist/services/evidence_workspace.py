from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from ..repositories.sqlite_repository import ValidationError


SOURCE_TYPES = (
    "annual_report", "quarterly_report", "filing", "investor_presentation",
    "earnings_call", "company_website", "regulator", "industry_report",
    "news", "interview", "customer_supplier_employee", "analyst_upload", "other",
)
EVIDENCE_TYPES = ("fact", "quote", "metric", "observation", "contradiction", "risk")
VERIFICATION_STATUSES = ("unverified", "verified", "disputed", "stale")
EVIDENCE_DIRECTIONS = ("supports", "contradicts", "context")
LINK_RELATIONSHIPS = ("primary", "supporting", "context", "contradicts")

SOURCE_TYPE_LABELS = {
    "annual_report": "Báo cáo thường niên",
    "quarterly_report": "Báo cáo quý",
    "filing": "Công bố thông tin / hồ sơ pháp lý",
    "investor_presentation": "Tài liệu nhà đầu tư",
    "earnings_call": "Earnings call / biên bản họp",
    "company_website": "Website doanh nghiệp",
    "regulator": "Cơ quan quản lý",
    "industry_report": "Báo cáo ngành",
    "news": "Báo chí",
    "interview": "Phỏng vấn",
    "customer_supplier_employee": "Khách hàng / nhà cung cấp / nhân viên",
    "analyst_upload": "Tài liệu analyst tải lên",
    "other": "Nguồn khác",
}


def _text(value: Any, *, required: bool = False, label: str = "Giá trị", max_length: int | None = None) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValidationError(f"{label} là bắt buộc.")
    if max_length is not None and len(result) > max_length:
        raise ValidationError(f"{label} không được vượt quá {max_length:,} ký tự.")
    return result


def _choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    result = _text(value, required=True, label=label)
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


def _date(repo, value: Any) -> str | None:
    if value in (None, ""):
        return None
    return repo._date(value)


def _source_hash(*, source_type: str, title: str, publisher: str, url: str, document_date: str | None) -> str:
    raw = "|".join((source_type, title.casefold(), publisher.casefold(), url.casefold(), document_date or ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _content_hash(*, evidence_type: str, locator_text: str, excerpt: str, evidence_date: str | None) -> str:
    raw = "|".join((evidence_type, locator_text.casefold(), excerpt.casefold(), evidence_date or ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_source(
    repo,
    *,
    company_ref_id: int,
    source_type: str,
    title: str,
    publisher: str = "",
    url: str = "",
    document_date=None,
    accessed_at=None,
    reliability: int = 3,
    notes: str = "",
    actor: str = "analyst",
) -> int:
    source_type = _choice(source_type, SOURCE_TYPES, "Loại nguồn")
    title = _text(title, required=True, label="Tiêu đề nguồn", max_length=500)
    publisher = _text(publisher, max_length=300)
    url = _text(url, max_length=2000)
    notes = _text(notes, max_length=5000)
    document_date = _date(repo, document_date)
    accessed_at = _date(repo, accessed_at)
    reliability = _score(reliability, "Độ tin cậy nguồn")
    fingerprint = _source_hash(
        source_type=source_type, title=title, publisher=publisher, url=url, document_date=document_date
    )

    with repo._conn() as c:
        company = repo.get_company_ref(company_ref_id, conn=c)
        if not company:
            raise ValidationError("Doanh nghiệp không tồn tại.")
        duplicate = c.execute(
            "SELECT id FROM research_sources WHERE company_ref_id=? AND source_hash=?",
            (company_ref_id, fingerprint),
        ).fetchone()
        if duplicate:
            raise ValidationError(f"Nguồn đã tồn tại (Source #{duplicate['id']}).")
        fields = {
            "company_ref_id": company_ref_id,
            "source_type": source_type,
            "title": title,
            "publisher": publisher or None,
            "url": url or None,
            "document_date": document_date,
            "accessed_at": accessed_at,
            "reliability": reliability,
            "notes": notes or None,
            "source_hash": fingerprint,
            "created_by": actor,
        }
        cur = c.execute(
            f"INSERT INTO research_sources({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        source_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM research_sources WHERE id=?", (source_id,)).fetchone())
        repo._audit(
            c, company_ref_id=company_ref_id, actor=actor, action="create",
            entity_type="research_source", entity_id=source_id, after=created,
        )
        return source_id


def archive_source(repo, source_id: int, *, reason: str, actor: str = "analyst") -> None:
    reason = _text(reason, required=True, label="Lý do lưu trữ nguồn", max_length=2000)
    with repo._conn() as c:
        before = repo._d(c.execute("SELECT * FROM research_sources WHERE id=?", (source_id,)).fetchone())
        if not before:
            raise ValidationError("Nguồn không tồn tại.")
        if before["status"] == "archived":
            return
        c.execute("UPDATE research_sources SET status='archived',notes=COALESCE(notes,'') || ? WHERE id=?", (f"\n[Archived] {reason}", source_id))
        after = repo._d(c.execute("SELECT * FROM research_sources WHERE id=?", (source_id,)).fetchone())
        repo._audit(
            c, company_ref_id=before["company_ref_id"], actor=actor, action="archive",
            entity_type="research_source", entity_id=source_id, before=before, after=after,
        )


def list_sources(repo, company_ref_id: int, *, include_archived: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM research_sources WHERE company_ref_id=?"
    params: tuple[Any, ...] = (company_ref_id,)
    if not include_archived:
        sql += " AND status='active'"
    sql += " ORDER BY document_date DESC,id DESC"
    with repo._conn() as c:
        return [dict(row) for row in c.execute(sql, params)]


def create_evidence_version(
    repo,
    *,
    company_ref_id: int,
    source_id: int,
    evidence_type: str,
    excerpt: str,
    locator_text: str = "",
    analyst_note: str = "",
    evidence_date=None,
    verification_status: str = "unverified",
    direction: str = "context",
    confidence: int = 3,
    evidence_key: str | None = None,
    change_reason: str = "",
    actor: str = "analyst",
) -> int:
    evidence_type = _choice(evidence_type, EVIDENCE_TYPES, "Loại bằng chứng")
    excerpt = _text(excerpt, required=True, label="Trích đoạn / sự kiện", max_length=5000)
    locator_text = _text(locator_text, max_length=500)
    analyst_note = _text(analyst_note, max_length=5000)
    verification_status = _choice(verification_status, VERIFICATION_STATUSES, "Trạng thái xác minh")
    direction = _choice(direction, EVIDENCE_DIRECTIONS, "Chiều bằng chứng")
    confidence = _score(confidence, "Độ tin cậy bằng chứng")
    evidence_date = _date(repo, evidence_date)
    change_reason = _text(change_reason, max_length=2000)

    with repo._conn() as c:
        source = repo._d(c.execute("SELECT * FROM research_sources WHERE id=?", (source_id,)).fetchone())
        if not source or int(source["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Nguồn không thuộc doanh nghiệp đang phân tích.")
        if source["status"] != "active":
            raise ValidationError("Nguồn đã lưu trữ; không thể thêm version bằng chứng mới.")

        previous = None
        if evidence_key:
            previous = repo._d(c.execute(
                "SELECT * FROM research_evidence WHERE source_id=? AND evidence_key=? ORDER BY version_no DESC,id DESC LIMIT 1",
                (source_id, evidence_key),
            ).fetchone())
            if not previous:
                raise ValidationError("Evidence key không tồn tại trong nguồn đã chọn.")
            if not change_reason:
                raise ValidationError("Lý do tạo version bằng chứng mới là bắt buộc.")
            version_no = int(previous["version_no"]) + 1
        else:
            evidence_key = str(uuid.uuid4())
            version_no = 1

        content_hash = _content_hash(
            evidence_type=evidence_type, locator_text=locator_text, excerpt=excerpt, evidence_date=evidence_date
        )
        fields = {
            "company_ref_id": company_ref_id,
            "source_id": source_id,
            "evidence_key": evidence_key,
            "version_no": version_no,
            "evidence_type": evidence_type,
            "locator_text": locator_text or None,
            "excerpt": excerpt,
            "analyst_note": analyst_note or None,
            "evidence_date": evidence_date,
            "verification_status": verification_status,
            "direction": direction,
            "confidence": confidence,
            "change_reason": change_reason or None,
            "supersedes_evidence_id": previous["id"] if previous else None,
            "content_hash": content_hash,
            "created_by": actor,
        }
        cur = c.execute(
            f"INSERT INTO research_evidence({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        evidence_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM research_evidence WHERE id=?", (evidence_id,)).fetchone())
        repo._audit(
            c, company_ref_id=company_ref_id, actor=actor,
            action="create" if previous is None else "append_version",
            entity_type="research_evidence", entity_id=evidence_id, before=previous, after=created,
        )
        return evidence_id


def list_latest_evidence(repo, company_ref_id: int, *, source_id: int | None = None) -> list[dict[str, Any]]:
    sql = """SELECT e.*,s.title source_title,s.source_type,s.publisher,s.document_date source_document_date,s.reliability source_reliability
    FROM research_evidence e JOIN research_sources s ON s.id=e.source_id
    WHERE e.company_ref_id=? AND NOT EXISTS(
        SELECT 1 FROM research_evidence newer
        WHERE newer.source_id=e.source_id AND newer.evidence_key=e.evidence_key AND newer.version_no>e.version_no
    )"""
    params: list[Any] = [company_ref_id]
    if source_id is not None:
        sql += " AND e.source_id=?"
        params.append(source_id)
    sql += " ORDER BY COALESCE(e.evidence_date,s.document_date) DESC,e.id DESC"
    with repo._conn() as c:
        return [dict(row) for row in c.execute(sql, tuple(params))]


def get_evidence(repo, evidence_id: int) -> dict[str, Any] | None:
    with repo._conn() as c:
        row = c.execute(
            """SELECT e.*,s.title source_title,s.source_type,s.publisher,s.url,s.document_date source_document_date,s.reliability source_reliability
            FROM research_evidence e JOIN research_sources s ON s.id=e.source_id WHERE e.id=?""",
            (evidence_id,),
        ).fetchone()
        return dict(row) if row else None


def _editable_review(repo, c, review_id: int) -> dict[str, Any]:
    review = repo.get_review(review_id, conn=c)
    if not review:
        raise ValidationError("Review không tồn tại.")
    if review["status"] == "completed":
        raise ValidationError("Review đã finalize; evidence links của review này là read-only.")
    return review


def link_evidence_to_question(
    repo,
    *,
    review_id: int,
    question_id: str,
    evidence_id: int,
    relationship: str = "supporting",
    materiality: int = 3,
    link_note: str = "",
    actor: str = "analyst",
) -> int:
    relationship = _choice(relationship, LINK_RELATIONSHIPS, "Vai trò bằng chứng")
    materiality = _score(materiality, "Mức độ trọng yếu")
    link_note = _text(link_note, max_length=3000)
    question_id = _text(question_id, required=True, label="Question ID").upper()

    with repo._conn() as c:
        review = _editable_review(repo, c, review_id)
        question = c.execute("SELECT question_id FROM checklist_questions WHERE question_id=? AND active=1", (question_id,)).fetchone()
        if not question:
            raise ValidationError("Question ID không hợp lệ.")
        evidence = repo._d(c.execute("SELECT * FROM research_evidence WHERE id=?", (evidence_id,)).fetchone())
        if not evidence or int(evidence["company_ref_id"]) != int(review["company_ref_id"]):
            raise ValidationError("Bằng chứng không thuộc doanh nghiệp của review.")
        existing = repo._d(c.execute(
            "SELECT * FROM evidence_question_links WHERE review_id=? AND question_id=? AND evidence_id=?",
            (review_id, question_id, evidence_id),
        ).fetchone())
        if existing and int(existing["is_active"]) == 1:
            raise ValidationError("Bằng chứng đã được liên kết với câu hỏi này.")
        if existing:
            c.execute(
                """UPDATE evidence_question_links SET relationship=?,materiality=?,link_note=?,is_active=1,
                deactivation_reason=NULL,deactivated_at=NULL,created_by=? WHERE id=?""",
                (relationship, materiality, link_note or None, actor, existing["id"]),
            )
            link_id = int(existing["id"])
            action = "reactivate"
        else:
            fields = {
                "company_ref_id": review["company_ref_id"],
                "review_id": review_id,
                "question_id": question_id,
                "evidence_id": evidence_id,
                "relationship": relationship,
                "materiality": materiality,
                "link_note": link_note or None,
                "created_by": actor,
            }
            cur = c.execute(
                f"INSERT INTO evidence_question_links({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                tuple(fields.values()),
            )
            link_id = int(cur.lastrowid)
            action = "create"
        after = repo._d(c.execute("SELECT * FROM evidence_question_links WHERE id=?", (link_id,)).fetchone())
        repo._audit(
            c, company_ref_id=review["company_ref_id"], review_id=review_id, actor=actor,
            action=action, entity_type="evidence_question_link", entity_id=link_id,
            before=existing, after=after,
        )
        return link_id


def unlink_evidence_from_question(repo, link_id: int, *, reason: str, actor: str = "analyst") -> None:
    reason = _text(reason, required=True, label="Lý do bỏ liên kết", max_length=2000)
    with repo._conn() as c:
        before = repo._d(c.execute("SELECT * FROM evidence_question_links WHERE id=?", (link_id,)).fetchone())
        if not before:
            raise ValidationError("Evidence link không tồn tại.")
        _editable_review(repo, c, int(before["review_id"]))
        if int(before["is_active"]) == 0:
            return
        c.execute(
            "UPDATE evidence_question_links SET is_active=0,deactivation_reason=?,deactivated_at=datetime('now') WHERE id=?",
            (reason, link_id),
        )
        after = repo._d(c.execute("SELECT * FROM evidence_question_links WHERE id=?", (link_id,)).fetchone())
        repo._audit(
            c, company_ref_id=before["company_ref_id"], review_id=before["review_id"], actor=actor,
            action="deactivate", entity_type="evidence_question_link", entity_id=link_id,
            before=before, after=after,
        )


def list_review_evidence(repo, review_id: int, *, question_id: str | None = None) -> list[dict[str, Any]]:
    sql = """SELECT l.id link_id,l.review_id,l.question_id,l.relationship,l.materiality,l.link_note,
    e.id evidence_id,e.evidence_key,e.version_no,e.evidence_type,e.locator_text,e.excerpt,e.analyst_note,
    e.evidence_date,e.verification_status,e.direction,e.confidence,e.content_hash,
    s.id source_id,s.source_type,s.title source_title,s.publisher,s.url,s.document_date source_document_date,
    s.accessed_at source_accessed_at,s.reliability source_reliability
    FROM evidence_question_links l
    JOIN research_evidence e ON e.id=l.evidence_id
    JOIN research_sources s ON s.id=e.source_id
    WHERE l.review_id=? AND l.is_active=1"""
    params: list[Any] = [review_id]
    if question_id:
        sql += " AND l.question_id=?"
        params.append(str(question_id).upper())
    sql += " ORDER BY CAST(SUBSTR(l.question_id,2) AS INTEGER),l.materiality DESC,l.id DESC"
    with repo._conn() as c:
        return [dict(row) for row in c.execute(sql, tuple(params))]


def evidence_coverage(repo, review_id: int) -> list[dict[str, Any]]:
    sql = """SELECT q.question_id,q.question_no,q.group_name,q.question_vi,
    COUNT(l.id) evidence_count,
    COALESCE(SUM(CASE WHEN e.verification_status='verified' THEN 1 ELSE 0 END),0) verified_count,
    COALESCE(SUM(CASE WHEN e.direction='contradicts' OR l.relationship='contradicts' THEN 1 ELSE 0 END),0) contradiction_count,
    COALESCE(MAX(l.materiality),0) max_materiality
    FROM checklist_questions q
    LEFT JOIN evidence_question_links l ON l.question_id=q.question_id AND l.review_id=? AND l.is_active=1
    LEFT JOIN research_evidence e ON e.id=l.evidence_id
    WHERE q.active=1
    GROUP BY q.question_id,q.question_no,q.group_name,q.question_vi
    ORDER BY q.question_no"""
    with repo._conn() as c:
        return [dict(row) for row in c.execute(sql, (review_id,))]


def evidence_summary(repo, review_id: int) -> dict[str, Any]:
    rows = evidence_coverage(repo, review_id)
    covered = sum(int(row["evidence_count"]) > 0 for row in rows)
    verified_questions = sum(int(row["verified_count"]) > 0 for row in rows)
    contradictions = sum(int(row["contradiction_count"]) for row in rows)
    return {
        "questions": len(rows),
        "covered_questions": covered,
        "verified_questions": verified_questions,
        "coverage_ratio": covered / len(rows) if rows else 0.0,
        "verified_ratio": verified_questions / len(rows) if rows else 0.0,
        "active_links": sum(int(row["evidence_count"]) for row in rows),
        "contradictions": contradictions,
    }


def snapshot_evidence_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    def build(c):
        links = [dict(row) for row in c.execute(
            """SELECT l.*,e.evidence_key,e.version_no,e.evidence_type,e.locator_text,e.excerpt,e.analyst_note,
            e.evidence_date,e.verification_status,e.direction,e.confidence,e.change_reason,e.content_hash,
            s.source_type,s.title source_title,s.publisher,s.url,s.document_date source_document_date,
            s.accessed_at source_accessed_at,s.reliability source_reliability,s.source_hash
            FROM evidence_question_links l
            JOIN research_evidence e ON e.id=l.evidence_id
            JOIN research_sources s ON s.id=e.source_id
            WHERE l.review_id=? AND l.is_active=1
            ORDER BY CAST(SUBSTR(l.question_id,2) AS INTEGER),l.materiality DESC,l.id""",
            (review_id,),
        )]
        coverage = evidence_coverage_from_links(c, review_id)
        return {
            "schema": "research-evidence-v1",
            "summary": coverage,
            "links": links,
        }

    if conn is not None:
        return build(conn)
    with repo._conn() as c:
        return build(c)


def evidence_coverage_from_links(c, review_id: int) -> dict[str, Any]:
    row = c.execute(
        """SELECT COUNT(*) active_links,COUNT(DISTINCT question_id) covered_questions,
        COALESCE(SUM(CASE WHEN e.verification_status='verified' THEN 1 ELSE 0 END),0) verified_links,
        COALESCE(SUM(CASE WHEN e.direction='contradicts' OR l.relationship='contradicts' THEN 1 ELSE 0 END),0) contradictions
        FROM evidence_question_links l JOIN research_evidence e ON e.id=l.evidence_id
        WHERE l.review_id=? AND l.is_active=1""",
        (review_id,),
    ).fetchone()
    result = dict(row) if row else {}
    return {
        "active_links": int(result.get("active_links") or 0),
        "covered_questions": int(result.get("covered_questions") or 0),
        "verified_links": int(result.get("verified_links") or 0),
        "contradictions": int(result.get("contradictions") or 0),
        "total_questions": 59,
    }


def export_evidence_json(repo, review_id: int) -> str:
    return json.dumps(snapshot_evidence_for_review(repo, review_id), ensure_ascii=False, indent=2, default=str)


__all__ = [
    "SOURCE_TYPES", "EVIDENCE_TYPES", "VERIFICATION_STATUSES", "EVIDENCE_DIRECTIONS",
    "LINK_RELATIONSHIPS", "SOURCE_TYPE_LABELS", "create_source", "archive_source", "list_sources",
    "create_evidence_version", "list_latest_evidence", "get_evidence", "link_evidence_to_question",
    "unlink_evidence_from_question", "list_review_evidence", "evidence_coverage", "evidence_summary",
    "snapshot_evidence_for_review", "export_evidence_json",
]
