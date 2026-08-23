from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import uuid

import pytest
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.evidence_workspace import create_evidence_version, create_source
from modules.investment_checklist.services.management_intelligence import (
    MANAGEMENT_QUESTION_IDS,
    add_timeline_event,
    list_management_signals,
    list_people,
    list_timeline_events,
    list_track_records,
    management_research_summary,
    save_management_signal,
    save_person_version,
    save_track_record,
)
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase5.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix: str = "MGMT"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE5:{suffix}", ticker="FPT", company_name="FPT Corporation",
        exchange="HOSE", company_type="normal", actor="test",
    )
    review_id = repo.create_review(
        company_ref_id, date(2026, 8, 22), analyst_user_id="analyst",
        review_reason="Phase 5 Management & Human Intelligence QA",
    )
    source_id = create_source(
        repo, company_ref_id=company_ref_id, source_type="annual_report",
        title=f"Annual report 2025 {suffix}", publisher="FPT",
        document_date=date(2025, 12, 31), reliability=5, actor="analyst",
    )
    evidence_id = create_evidence_version(
        repo, company_ref_id=company_ref_id, source_id=source_id, evidence_type="fact",
        excerpt="Ban điều hành công bố lịch sử nhiệm kỳ và mục tiêu vận hành năm 2026.",
        locator_text="Trang 42, mục Ban điều hành", evidence_date=date(2025, 12, 31),
        verification_status="verified", direction="context", confidence=5, actor="analyst",
    )
    return company_ref_id, review_id, evidence_id


def test_phase5_people_timeline_are_append_only_and_evidence_scoped(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, evidence_id = _seed(repo)
    first_id = save_person_version(
        repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-fpt",
        full_name="CEO FPT", current_title="Tổng giám đốc", appointment_type="internal",
        start_date="2020-01-01", ownership_pct=0.25, source_evidence_id=evidence_id,
        verification_status="verified", actor="analyst",
    )
    with pytest.raises(ValidationError, match="Lý do tạo version"):
        save_person_version(
            repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-fpt",
            full_name="CEO FPT", current_title="Tổng giám đốc", appointment_type="internal",
            source_evidence_id=evidence_id, actor="analyst",
        )
    second_id = save_person_version(
        repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-fpt",
        full_name="CEO FPT", current_title="Tổng giám đốc kiêm Thành viên HĐQT",
        appointment_type="internal", source_evidence_id=evidence_id,
        change_reason="Cập nhật chức danh theo báo cáo thường niên", actor="analyst",
    )
    assert second_id > first_id
    people = list_people(repo, review_id)
    assert len(people) == 1 and people[0]["version_no"] == 2

    event_id = add_timeline_event(
        repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-fpt",
        event_date="2020-01-01", event_type="appointed", organization="FPT",
        role_title="Tổng giám đốc", event_summary="Được bổ nhiệm sau quá trình thăng tiến nội bộ.",
        source_evidence_id=evidence_id, confidence=5, actor="analyst",
    )
    assert event_id and len(list_timeline_events(repo, review_id)) == 1


def test_phase5_signal_guardrails_coverage_and_no_final_assessment_write(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, evidence_id = _seed(repo, "SIGNAL")
    with pytest.raises(ValidationError, match="Unknown khác Neutral"):
        save_management_signal(
            repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q35",
            subject_key="management-team", signal_status="research_gap", signal_score=1,
            rationale="Chưa đủ bằng chứng", actor="analyst",
        )
    save_management_signal(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q35",
        subject_key="management-team", signal_status="mixed", signal_score=0,
        rationale="Hành động xây đội ngũ tích cực nhưng succession evidence còn hạn chế.",
        source_evidence_id=evidence_id, confidence=4, materiality=5, actor="analyst",
    )
    with repo._conn() as c:
        assert c.execute("SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)).fetchone()["n"] == 0
    summary = management_research_summary(repo, review_id)
    assert summary["question_total"] == 22 == len(MANAGEMENT_QUESTION_IDS)
    assert summary["covered_questions"] == ["Q35"]
    assert summary["evidence_backed_questions"] == ["Q35"]
    assert summary["evidence_coverage_pct"] == pytest.approx(1 / 22)


def test_phase5_track_records_snapshot_lock_and_question_mapping(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, evidence_id = _seed(repo, "TRACK")
    save_track_record(
        repo, company_ref_id=company_ref_id, review_id=review_id, record_type="guidance",
        title="Guidance doanh thu 2026", statement_text="CEO đưa mục tiêu tăng trưởng doanh thu 20%.",
        question_ids=["Q41", "Q50"], subject_key="ceo-fpt", event_date="2026-01-20",
        expected_outcome="Doanh thu tăng 20%", result_status="pending", horizon="1y",
        source_category="company", credibility=5, corroboration_status="not_applicable",
        source_evidence_id=evidence_id, actor="analyst",
    )
    save_track_record(
        repo, company_ref_id=company_ref_id, review_id=review_id, record_type="human_intelligence",
        title="Kiểm chứng văn hóa tuyển dụng", statement_text="Nguồn ngành nhận xét chất lượng hiring ổn định.",
        question_ids=["Q43", "Q44"], subject_key="management-team", event_date="2026-08-01",
        result_status="verified", source_category="industry_insider", credibility=4,
        corroboration_status="single_source", confidential=True, actor="analyst",
    )
    with pytest.raises(ValidationError, match="chỉ được liên kết"):
        save_track_record(
            repo, company_ref_id=company_ref_id, review_id=review_id, record_type="guidance",
            title="Sai mapping", statement_text="Không được gắn Q58", question_ids=["Q58"],
            actor="analyst",
        )
    assert len(list_track_records(repo, review_id)) == 2
    snapshot_id = repo.finalize_review(review_id, actor="analyst", finalize_reason="Đóng Phase 5 QA")
    payload = repo.get_snapshot(snapshot_id)["payload"]
    assert payload["snapshot_schema"] == "phase1b-review-v7-evidence-peer-ai-management-monitoring-decision"
    assert payload["management_intelligence"]["schema"] == "management-human-intelligence-v1"
    assert len(payload["management_intelligence"]["track_records"]) == 2
    with pytest.raises(ValidationError, match="read-only"):
        save_track_record(
            repo, company_ref_id=company_ref_id, review_id=review_id, record_type="ma_decision",
            title="Locked", statement_text="Không được ghi", question_ids=["Q58"], actor="analyst",
        )


def test_phase5_review_delete_counts_and_removes_owned_records(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, evidence_id = _seed(repo, "DELETE")
    save_person_version(
        repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-fpt",
        full_name="CEO FPT", current_title="CEO", source_evidence_id=evidence_id, actor="analyst",
    )
    add_timeline_event(
        repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-fpt",
        event_date="2020-01-01", event_type="appointed", organization="FPT", role_title="CEO",
        event_summary="Bổ nhiệm", source_evidence_id=evidence_id, actor="analyst",
    )
    save_management_signal(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q33",
        subject_key="ceo-fpt", signal_status="supported", signal_score=1,
        rationale="Có hồ sơ", source_evidence_id=evidence_id, actor="analyst",
    )
    save_track_record(
        repo, company_ref_id=company_ref_id, review_id=review_id, record_type="ma_decision",
        title="M&A", statement_text="Quy trình", question_ids=["Q58"], actor="analyst",
    )
    preview = review_delete_preview(repo, review_id)
    assert preview["counts"]["management_people"] == 1
    assert preview["counts"]["management_timeline"] == 1
    assert preview["counts"]["management_track_records"] == 1
    assert preview["counts"]["management_signals"] == 1
    delete_review_manually(
        repo, review_id, actor="admin", reason="Xóa QA Phase 5",
        confirmation_text=f"XÓA REVIEW #{review_id}",
    )
    with repo._conn() as c:
        for table in (
            "management_people_versions", "management_timeline_events",
            "management_track_records", "management_question_signals",
        ):
            assert c.execute(f"SELECT COUNT(*) n FROM {table} WHERE review_id=?", (review_id,)).fetchone()["n"] == 0
        assert c.execute("SELECT id FROM research_evidence WHERE id=?", (evidence_id,)).fetchone()


def test_phase5_streamlit_ui_and_source_contract(tmp_path, monkeypatch):
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL", "TEST_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    repo = _repo(tmp_path)
    company_ref_id, review_id, _ = _seed(repo, "UI")
    app = f'''
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.management_intelligence import render_management_intelligence
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
render_management_intelligence(repo, {company_ref_id}, repo.get_review({review_id}), "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0 and len(at.error) == 0
    assert any("Management & Human Intelligence" in str(item.value) for item in at.markdown)
    service = Path("modules/investment_checklist/services/management_intelligence.py").read_text(encoding="utf-8").lower()
    ui = Path("modules/investment_checklist/ui/management_intelligence.py").read_text(encoding="utf-8").lower()
    for forbidden in ("save_assessment(", "import openai", "import requests", "import httpx", "urlopen("):
        assert forbidden not in service
        assert forbidden not in ui
    shell = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    active_shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    page = Path("pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    assert '"👥 Management & Human Intel"' in shell
    assert "from .management_intelligence import render_management_intelligence" in active_shell
    assert 'elif section == "👥 Management & Human Intel":' in active_shell
    assert "render_management_intelligence(repo, company_ref_id, review, actor)" in active_shell
    assert "integration_preview_v3 import render_investment_checklist" in page


def test_postgres_phase5_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    suffix = uuid.uuid4().hex[:10].upper()
    company_ref_id, review_id, evidence_id = _seed(repo, suffix)
    save_person_version(
        repo, company_ref_id=company_ref_id, review_id=review_id, person_key="ceo-ci",
        full_name="CEO CI", current_title="CEO", source_evidence_id=evidence_id, actor="ci",
    )
    save_management_signal(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q35",
        subject_key="ceo-ci", signal_status="supported", signal_score=1,
        rationale="PostgreSQL Phase 5", source_evidence_id=evidence_id, actor="ci",
    )
    assert list_people(repo, review_id)[0]["person_key"] == "ceo-ci"
    assert list_management_signals(repo, review_id)[0]["question_id"] == "Q35"
    repo.close()
