from __future__ import annotations

from datetime import date
import os
import uuid

import pytest
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.evidence_workspace import (
    create_evidence_version,
    create_source,
    evidence_summary,
    link_evidence_to_question,
    list_latest_evidence,
    list_review_evidence,
    snapshot_evidence_for_review,
    unlink_evidence_from_question,
)
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _sqlite_repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "evidence.db", CATALOG)
    repo.initialize()
    return repo


def _company(repo, suffix: str = "FPT"):
    return repo.upsert_company_ref(
        host_company_key=f"EVIDENCE:{suffix}", ticker=suffix[:3],
        company_name=f"Evidence {suffix}", exchange="HOSE", actor="test",
    )


def _seed_evidence(repo, company_ref_id: int, review_id: int):
    source_id = create_source(
        repo, company_ref_id=company_ref_id, source_type="annual_report",
        title="Báo cáo thường niên 2025", publisher="Doanh nghiệp",
        url="https://example.com/annual-report-2025", document_date=date(2025, 12, 31),
        accessed_at=date(2026, 8, 22), reliability=5, actor="analyst",
    )
    evidence_id = create_evidence_version(
        repo, company_ref_id=company_ref_id, source_id=source_id, evidence_type="metric",
        excerpt="Tỷ lệ khách hàng tái ký hợp đồng đạt 92%.", locator_text="Trang 83, mục Khách hàng",
        evidence_date=date(2025, 12, 31), verification_status="verified", direction="supports",
        confidence=5, actor="analyst",
    )
    link_id = link_evidence_to_question(
        repo, review_id=review_id, question_id="Q10", evidence_id=evidence_id,
        relationship="primary", materiality=5, link_note="Retention trực tiếp", actor="analyst",
    )
    return source_id, evidence_id, link_id


def test_evidence_versioning_coverage_and_immutable_snapshot(tmp_path):
    repo = _sqlite_repo(tmp_path)
    company_ref_id = _company(repo)
    review_id = repo.create_review(
        company_ref_id, date(2026, 6, 30), analyst_user_id="analyst", review_reason="Review bán niên"
    )
    source_id, evidence_v1, _ = _seed_evidence(repo, company_ref_id, review_id)

    with pytest.raises(ValidationError, match="Nguồn đã tồn tại"):
        create_source(
            repo, company_ref_id=company_ref_id, source_type="annual_report",
            title="Báo cáo thường niên 2025", publisher="Doanh nghiệp",
            url="https://example.com/annual-report-2025", document_date=date(2025, 12, 31),
            accessed_at=date(2026, 8, 22), reliability=5,
        )

    first = list_latest_evidence(repo, company_ref_id)[0]
    assert first["id"] == evidence_v1 and first["version_no"] == 1
    with pytest.raises(ValidationError, match="Lý do"):
        create_evidence_version(
            repo, company_ref_id=company_ref_id, source_id=source_id,
            evidence_key=first["evidence_key"], evidence_type="metric",
            excerpt="Retention 90% sau đối chiếu.", verification_status="verified",
            direction="supports", confidence=5,
        )
    evidence_v2 = create_evidence_version(
        repo, company_ref_id=company_ref_id, source_id=source_id,
        evidence_key=first["evidence_key"], evidence_type="metric",
        excerpt="Tỷ lệ khách hàng tái ký sau đối chiếu là 90%.", locator_text="Trang 84",
        evidence_date=date(2025, 12, 31), verification_status="verified",
        direction="supports", confidence=5, change_reason="Đối chiếu lại phụ lục", actor="analyst",
    )
    latest = list_latest_evidence(repo, company_ref_id)
    assert len(latest) == 1 and latest[0]["id"] == evidence_v2 and latest[0]["version_no"] == 2

    link_evidence_to_question(
        repo, review_id=review_id, question_id="Q10", evidence_id=evidence_v2,
        relationship="supporting", materiality=4, actor="analyst",
    )
    summary = evidence_summary(repo, review_id)
    assert summary["covered_questions"] == 1
    assert summary["active_links"] == 2
    assert summary["verified_questions"] == 1

    snapshot_before = snapshot_evidence_for_review(repo, review_id)
    assert {row["version_no"] for row in snapshot_before["links"]} == {1, 2}
    snapshot_id = repo.finalize_review(review_id, actor="analyst", finalize_reason="Đủ bằng chứng")
    immutable = repo.get_snapshot(snapshot_id)["payload"]
    assert immutable["snapshot_schema"] == "phase1b-review-v2-evidence"
    assert immutable["research_evidence"] == snapshot_before

    with pytest.raises(ValidationError, match="read-only"):
        link_evidence_to_question(
            repo, review_id=review_id, question_id="Q11", evidence_id=evidence_v2,
            relationship="supporting", materiality=3,
        )
    with pytest.raises(ValidationError, match="read-only"):
        unlink_evidence_from_question(repo, list_review_evidence(repo, review_id)[0]["link_id"], reason="Không dùng")
    assert repo.get_snapshot(snapshot_id)["payload"] == immutable


def test_review_delete_removes_links_but_keeps_reusable_source_and_evidence(tmp_path):
    repo = _sqlite_repo(tmp_path)
    company_ref_id = _company(repo, "DEL")
    review_id = repo.create_review(company_ref_id, date(2026, 6, 30), review_reason="Test delete")
    source_id, evidence_id, _ = _seed_evidence(repo, company_ref_id, review_id)

    preview = review_delete_preview(repo, review_id)
    assert preview["counts"]["evidence_links"] == 1
    delete_review_manually(
        repo, review_id, actor="admin", reason="Dữ liệu thử nghiệm",
        confirmation_text=f"XÓA REVIEW #{review_id}",
    )
    assert repo.get_review(review_id) is None
    assert list_review_evidence(repo, review_id) == []
    assert list_latest_evidence(repo, company_ref_id)[0]["id"] == evidence_id
    with repo._conn() as conn:
        assert conn.execute("SELECT id FROM research_sources WHERE id=?", (source_id,)).fetchone()


def test_evidence_workspace_streamlit_smoke_all_sections(tmp_path, monkeypatch):
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL", "TEST_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    repo = _sqlite_repo(tmp_path)
    company_ref_id = _company(repo, "SMK")
    review_id = repo.create_review(company_ref_id, date(2026, 6, 30), review_reason="UI smoke")
    _seed_evidence(repo, company_ref_id, review_id)

    app = f'''
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.evidence_workspace import render_evidence_workspace
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
review = repo.get_review({review_id})
render_evidence_workspace(repo, {company_ref_id}, review, "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0 and len(at.error) == 0

    selector = next(item for item in at.radio if item.label == "Evidence workspace")
    for section in ("Nguồn", "Bằng chứng", "Liên kết Q01–Q59", "Coverage"):
        selector.set_value(section).run()
        assert len(at.exception) == 0
        selector = next(item for item in at.radio if item.label == "Evidence workspace")


def test_postgres_evidence_workspace_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    suffix = uuid.uuid4().hex[:10].upper()
    company_ref_id = _company(repo, suffix)
    review_id = repo.create_review(company_ref_id, date(2026, 8, 22), review_reason="PostgreSQL evidence CI")
    _, evidence_id, _ = _seed_evidence(repo, company_ref_id, review_id)
    rows = list_review_evidence(repo, review_id, question_id="Q10")
    assert len(rows) == 1 and rows[0]["evidence_id"] == evidence_id
    snapshot_id = repo.finalize_review(review_id, actor="ci", finalize_reason="Evidence CI pass")
    payload = repo.get_snapshot(snapshot_id)["payload"]
    assert payload["research_evidence"]["summary"]["covered_questions"] == 1
    repo.close()
