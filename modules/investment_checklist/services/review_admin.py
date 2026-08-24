from __future__ import annotations

"""Administrative review deletion with explicit confirmation and audit preservation.

Normal checklist history is append-only. This service is the deliberate manual exception requested
for cleaning wrong/test reviews. It removes only records owned by the selected review, rewires later
review lineage to the deleted review's prior review, and keeps audit logs as tombstones.
"""

from typing import Any

from ..repositories.sqlite_repository import ValidationError
from .peer_snapshots import ensure_peer_snapshot_schema


def review_delete_token(review_id: int) -> str:
    return f"XÓA REVIEW #{int(review_id)}"


def review_delete_preview(repo, review_id: int) -> dict[str, Any]:
    ensure_peer_snapshot_schema(repo)
    review = repo.get_review(review_id)
    if not review:
        raise ValidationError("Review không tồn tại.")
    with repo._conn() as c:
        counts = {
            "analyst_assessments": int(c.execute("SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "screening_assessments": int(c.execute("SELECT COUNT(*) n FROM screening_assessments WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "evidence_links": int(c.execute("SELECT COUNT(*) n FROM evidence_question_links WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "inventory_snapshots": int(c.execute("SELECT COUNT(*) n FROM opportunity_inventory_snapshots WHERE last_review_id=?", (review_id,)).fetchone()["n"]),
            "immutable_snapshots": int(c.execute("SELECT COUNT(*) n FROM data_snapshots WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "peer_snapshots": int(c.execute("SELECT COUNT(*) n FROM peer_comparison_snapshots WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "ai_runs": int(c.execute("SELECT COUNT(*) n FROM ai_research_runs WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "ai_suggestions": int(c.execute("SELECT COUNT(*) n FROM ai_research_suggestions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_people": int(c.execute("SELECT COUNT(*) n FROM management_people_versions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_timeline": int(c.execute("SELECT COUNT(*) n FROM management_timeline_events WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_track_records": int(c.execute("SELECT COUNT(*) n FROM management_track_records WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_signals": int(c.execute("SELECT COUNT(*) n FROM management_question_signals WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "monitoring_rules": int(c.execute("SELECT COUNT(*) n FROM monitoring_rules WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "monitoring_observations": int(c.execute("SELECT COUNT(*) n FROM monitoring_observations WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "delta_items": int(c.execute("SELECT COUNT(*) n FROM delta_review_items WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "delta_decisions": int(c.execute("SELECT COUNT(*) n FROM delta_review_decisions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "investment_memos": int(c.execute("SELECT COUNT(*) n FROM investment_memo_versions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "thesis_pillars": int(c.execute("SELECT COUNT(*) n FROM investment_thesis_pillars WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "investment_risks": int(c.execute("SELECT COUNT(*) n FROM investment_risk_register WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "investment_decisions": int(c.execute("SELECT COUNT(*) n FROM investment_decisions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "decision_outcomes": int(c.execute(
                "SELECT COUNT(*) n FROM decision_outcome_reviews WHERE review_id=? OR decision_id IN "
                "(SELECT id FROM investment_decisions WHERE review_id=?)", (review_id, review_id)
            ).fetchone()["n"]),
            "topdown_sector_snapshots": int(c.execute(
                "SELECT COUNT(*) n FROM topdown_sector_snapshots WHERE review_id=?", (review_id,)
            ).fetchone()["n"]),
            "later_reviews_linked": int(c.execute("SELECT COUNT(*) n FROM research_reviews WHERE prior_review_id=?", (review_id,)).fetchone()["n"]),
        }
    return {"review": review, "counts": counts, "confirmation_token": review_delete_token(review_id)}


def delete_review_manually(
    repo,
    review_id: int,
    *,
    actor: str,
    reason: str,
    confirmation_text: str,
) -> dict[str, Any]:
    ensure_peer_snapshot_schema(repo)
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError("Lý do xóa review là bắt buộc.")
    expected = review_delete_token(review_id)
    if str(confirmation_text or "").strip() != expected:
        raise ValidationError(f"Nhập đúng chuỗi xác nhận: {expected}")

    with repo._conn() as c:
        review = repo.get_review(review_id, conn=c)
        if not review:
            raise ValidationError("Review không tồn tại hoặc đã bị xóa.")
        company_ref_id = int(review["company_ref_id"])
        prior_review_id = review.get("prior_review_id")

        assessment_ids = [int(r["id"]) for r in c.execute("SELECT id FROM analyst_assessments WHERE review_id=?", (review_id,))]
        screening_ids = [int(r["id"]) for r in c.execute("SELECT id FROM screening_assessments WHERE review_id=?", (review_id,))]

        counts = {
            "analyst_assessments": len(assessment_ids),
            "screening_assessments": len(screening_ids),
            "evidence_links": int(c.execute("SELECT COUNT(*) n FROM evidence_question_links WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "inventory_snapshots": int(c.execute("SELECT COUNT(*) n FROM opportunity_inventory_snapshots WHERE last_review_id=?", (review_id,)).fetchone()["n"]),
            "immutable_snapshots": int(c.execute("SELECT COUNT(*) n FROM data_snapshots WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "peer_snapshots": int(c.execute("SELECT COUNT(*) n FROM peer_comparison_snapshots WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "ai_runs": int(c.execute("SELECT COUNT(*) n FROM ai_research_runs WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "ai_suggestions": int(c.execute("SELECT COUNT(*) n FROM ai_research_suggestions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_people": int(c.execute("SELECT COUNT(*) n FROM management_people_versions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_timeline": int(c.execute("SELECT COUNT(*) n FROM management_timeline_events WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_track_records": int(c.execute("SELECT COUNT(*) n FROM management_track_records WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "management_signals": int(c.execute("SELECT COUNT(*) n FROM management_question_signals WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "monitoring_rules": int(c.execute("SELECT COUNT(*) n FROM monitoring_rules WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "monitoring_observations": int(c.execute("SELECT COUNT(*) n FROM monitoring_observations WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "delta_items": int(c.execute("SELECT COUNT(*) n FROM delta_review_items WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "delta_decisions": int(c.execute("SELECT COUNT(*) n FROM delta_review_decisions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "investment_memos": int(c.execute("SELECT COUNT(*) n FROM investment_memo_versions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "thesis_pillars": int(c.execute("SELECT COUNT(*) n FROM investment_thesis_pillars WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "investment_risks": int(c.execute("SELECT COUNT(*) n FROM investment_risk_register WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "investment_decisions": int(c.execute("SELECT COUNT(*) n FROM investment_decisions WHERE review_id=?", (review_id,)).fetchone()["n"]),
            "decision_outcomes": int(c.execute(
                "SELECT COUNT(*) n FROM decision_outcome_reviews WHERE review_id=? OR decision_id IN "
                "(SELECT id FROM investment_decisions WHERE review_id=?)", (review_id, review_id)
            ).fetchone()["n"]),
            "topdown_sector_snapshots": int(c.execute(
                "SELECT COUNT(*) n FROM topdown_sector_snapshots WHERE review_id=?", (review_id,)
            ).fetchone()["n"]),
            "later_reviews_linked": int(c.execute("SELECT COUNT(*) n FROM research_reviews WHERE prior_review_id=?", (review_id,)).fetchone()["n"]),
        }

        # Preserve later review chains. If B pointed to deleted A, B now points to A's prior review.
        c.execute("UPDATE research_reviews SET prior_review_id=? WHERE prior_review_id=?", (prior_review_id, review_id))
        # Delta items also carry an explicit immutable baseline FK. Rewire it when another prior
        # review exists; otherwise remove the now-unverifiable later-review queue items.
        if prior_review_id is not None:
            c.execute("UPDATE delta_review_items SET prior_review_id=? WHERE prior_review_id=?", (prior_review_id, review_id))
        else:
            c.execute(
                "DELETE FROM delta_review_decisions WHERE delta_item_id IN "
                "(SELECT id FROM delta_review_items WHERE prior_review_id=?)",
                (review_id,),
            )
            c.execute("DELETE FROM delta_review_items WHERE prior_review_id=?", (review_id,))

        # Explicit carry-forward references must not block deletion of the source assessment rows.
        if assessment_ids:
            marks = ",".join("?" for _ in assessment_ids)
            c.execute(f"UPDATE analyst_assessments SET copied_from_assessment_id=NULL WHERE copied_from_assessment_id IN ({marks})", tuple(assessment_ids))
        if screening_ids:
            marks = ",".join("?" for _ in screening_ids)
            c.execute(f"UPDATE screening_assessments SET copied_from_screening_id=NULL WHERE copied_from_screening_id IN ({marks})", tuple(screening_ids))

        # Existing audit entries are kept but detached from the soon-to-be-deleted FK row.
        c.execute("UPDATE audit_logs SET review_id=NULL WHERE review_id=?", (review_id,))

        # Review-owned snapshots/versions are deleted together with the review to avoid orphan history.
        c.execute("DELETE FROM data_snapshots WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM topdown_sector_snapshots WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM peer_comparison_snapshots WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM ai_suggestion_decisions WHERE suggestion_id IN (SELECT id FROM ai_research_suggestions WHERE review_id=?)", (review_id,))
        c.execute("DELETE FROM ai_research_suggestions WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM ai_research_runs WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM management_question_signals WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM management_track_records WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM management_timeline_events WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM management_people_versions WHERE review_id=?", (review_id,))
        c.execute(
            "DELETE FROM decision_outcome_reviews WHERE review_id=? OR decision_id IN "
            "(SELECT id FROM investment_decisions WHERE review_id=?)", (review_id, review_id)
        )
        c.execute("DELETE FROM investment_decisions WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM investment_risk_register WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM investment_thesis_pillars WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM investment_memo_versions WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM delta_review_decisions WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM delta_review_items WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM monitoring_observations WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM monitoring_rules WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM opportunity_inventory_snapshots WHERE last_review_id=?", (review_id,))
        c.execute("DELETE FROM evidence_question_links WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM analyst_assessments WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM screening_assessments WHERE review_id=?", (review_id,))
        c.execute("DELETE FROM research_reviews WHERE id=?", (review_id,))

        tombstone = {
            "deleted_review": review,
            "deleted_counts": counts,
            "delete_reason": reason,
            "lineage_rewired_to": prior_review_id,
        }
        repo._audit(
            c,
            company_ref_id=company_ref_id,
            review_id=None,
            actor=actor,
            action="manual_delete",
            entity_type="review_tombstone",
            entity_id=review_id,
            before=tombstone,
            after=None,
        )

    return {
        "review_id": int(review_id),
        "company_ref_id": company_ref_id,
        "counts": counts,
        "reason": reason,
        "lineage_rewired_to": prior_review_id,
    }
