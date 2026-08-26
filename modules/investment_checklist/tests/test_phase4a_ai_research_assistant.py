from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import uuid

import pytest
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.ai_research_assistant import (
    decide_ai_suggestion,
    list_ai_runs,
    list_ai_suggestions,
    record_ai_run,
)
from modules.investment_checklist.services.evidence_workspace import create_source, list_review_evidence
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase4a.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix: str = "AI"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE4A:{suffix}", ticker="VCB", company_name="Vietcombank",
        exchange="HOSE", company_type="bank", actor="test",
    )
    review_id = repo.create_review(
        company_ref_id, date(2026, 8, 22), analyst_user_id="analyst",
        review_reason="Phase 4A governed AI QA",
    )
    source_id = create_source(
        repo, company_ref_id=company_ref_id, source_type="annual_report",
        title=f"VCB Annual Report 2025 {suffix}", publisher="VCB",
        document_date=date(2025, 12, 31), reliability=5, actor="analyst",
    )
    return company_ref_id, review_id, source_id


def _suggestions(source_id: int):
    return [
        {
            "suggestion_type": "evidence_candidate",
            "source_id": source_id,
            "question_id": "Q22",
            "evidence_type": "metric",
            "relationship": "supporting",
            "direction": "supports",
            "locator_text": "Trang 94, mục Chất lượng tài sản",
            "excerpt": "Tỷ lệ nợ xấu hợp nhất cuối năm là 0,97%.",
            "rationale": "NPL là operating driver trọng yếu của ngân hàng.",
            "confidence": 4,
            "materiality": 5,
        },
        {
            "suggestion_type": "research_gap",
            "question_id": "Q33",
            "rationale": "Chưa có hồ sơ đầy đủ về nhiệm kỳ lãnh đạo.",
            "confidence": 3,
            "materiality": 4,
        },
    ]


def _record(repo, company_ref_id: int, review_id: int, source_id: int):
    return record_ai_run(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        run_type="evidence_extraction",
        provider="test-provider",
        model_name="research-model",
        model_version="2026-08-22",
        prompt_version="phase4a-v1",
        prompt_text="Extract cited evidence and research gaps. Do not assess the company.",
        source_ids=[source_id],
        suggestions=_suggestions(source_id),
        actor="analyst",
    )


def test_ai_run_is_hashed_and_accept_requires_analyst_without_assessment_write(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id = _seed(repo)
    run_id = _record(repo, company_ref_id, review_id, source_id)

    run = list_ai_runs(repo, review_id)[0]
    assert run["id"] == run_id
    assert run["suggestion_count"] == 2 and run["pending_count"] == 2
    assert len(run["prompt_hash"]) == 64 and len(run["output_hash"]) == 64
    assert "Extract cited evidence" not in str(run)

    suggestions = list_ai_suggestions(repo, review_id, pending_only=True)
    evidence_item = next(item for item in suggestions if item["suggestion_type"] == "evidence_candidate")
    result = decide_ai_suggestion(
        repo, evidence_item["id"], decision="accepted",
        reason="Đã mở đúng trang 94 và đối chiếu số liệu.", actor="analyst",
    )
    assert result["created_evidence_id"] and result["created_link_id"]
    link = list_review_evidence(repo, review_id, question_id="Q22")[0]
    assert link["verification_status"] == "unverified"
    assert link["locator_text"] == "Trang 94, mục Chất lượng tài sản"

    with repo._conn() as c:
        assessment_count = c.execute(
            "SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)
        ).fetchone()["n"]
    assert assessment_count == 0
    with pytest.raises(ValidationError, match="đã được analyst quyết định"):
        decide_ai_suggestion(
            repo, evidence_item["id"], decision="rejected", reason="Không được ghi đè", actor="analyst"
        )


def test_research_gap_decision_and_immutable_review_snapshot(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id = _seed(repo, "SNAP")
    _record(repo, company_ref_id, review_id, source_id)
    gap = next(
        item for item in list_ai_suggestions(repo, review_id) if item["suggestion_type"] == "research_gap"
    )
    result = decide_ai_suggestion(
        repo, gap["id"], decision="accepted", reason="Xác nhận cần nghiên cứu thêm", actor="analyst"
    )
    assert result["created_evidence_id"] is None and result["created_link_id"] is None

    snapshot_id = repo.finalize_review(review_id, actor="analyst", finalize_reason="Phase 4A snapshot QA")
    payload = repo.get_snapshot(snapshot_id)["payload"]
    assert payload["snapshot_schema"] == "phase1b-review-v9-evidence-peer-ai-management-monitoring-decision-topdown-latest-data"
    assert payload["ai_research"]["schema"] == "ai-research-assistant-v2-provider-execution"
    assert len(payload["ai_research"]["runs"]) == 1
    assert len(payload["ai_research"]["suggestions"]) == 2
    assert len(payload["ai_research"]["decisions"]) == 1

    with pytest.raises(ValidationError, match="read-only"):
        record_ai_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="research_gap", provider="test", model_name="test",
            prompt_version="v2", prompt_text="Find gaps", source_ids=[],
            suggestions=[_suggestions(source_id)[1]], actor="analyst",
        )


def test_exact_citation_source_manifest_and_drift_guardrails(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id = _seed(repo, "CITE")
    bad = _suggestions(source_id)[0].copy()
    bad["locator_text"] = ""
    with pytest.raises(ValidationError, match="Vị trí trích dẫn"):
        record_ai_run(
            repo, company_ref_id=company_ref_id, review_id=review_id,
            run_type="evidence_extraction", provider="test", model_name="test",
            prompt_version="v1", prompt_text="Extract", source_ids=[source_id],
            suggestions=[bad], actor="analyst",
        )

    _record(repo, company_ref_id, review_id, source_id)
    item = next(
        row for row in list_ai_suggestions(repo, review_id) if row["suggestion_type"] == "evidence_candidate"
    )
    with repo._conn() as c:
        c.execute("UPDATE research_sources SET source_hash=? WHERE id=?", ("changed-source-hash", source_id))
    with pytest.raises(ValidationError, match="citation drift"):
        decide_ai_suggestion(
            repo, item["id"], decision="accepted", reason="Thử nguồn đã đổi", actor="analyst"
        )


def test_review_delete_removes_ai_workflow_but_keeps_promoted_evidence(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id = _seed(repo, "DELETE")
    _record(repo, company_ref_id, review_id, source_id)
    item = next(
        row for row in list_ai_suggestions(repo, review_id) if row["suggestion_type"] == "evidence_candidate"
    )
    result = decide_ai_suggestion(
        repo, item["id"], decision="accepted", reason="QA promotion", actor="analyst"
    )
    preview = review_delete_preview(repo, review_id)
    assert preview["counts"]["ai_runs"] == 1
    assert preview["counts"]["ai_suggestions"] == 2
    delete_review_manually(
        repo, review_id, actor="admin", reason="Xóa QA",
        confirmation_text=f"XÓA REVIEW #{review_id}",
    )
    with repo._conn() as c:
        assert c.execute("SELECT id FROM research_evidence WHERE id=?", (result["created_evidence_id"],)).fetchone()
        assert c.execute("SELECT COUNT(*) n FROM ai_research_runs WHERE review_id=?", (review_id,)).fetchone()["n"] == 0


def test_phase4a_ui_smoke_and_no_network_or_assessment_write_contract(tmp_path, monkeypatch):
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL", "TEST_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    repo = _repo(tmp_path)
    company_ref_id, review_id, source_id = _seed(repo, "UI")
    _record(repo, company_ref_id, review_id, source_id)

    app = f'''
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.ai_research_assistant import render_ai_research_assistant
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
render_ai_research_assistant(repo, {company_ref_id}, repo.get_review({review_id}), "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0 and len(at.error) == 0
    assert any("AI Research Assistant" in str(item.value) for item in at.markdown)

    service = Path("modules/investment_checklist/services/ai_research_assistant.py").read_text(encoding="utf-8")
    ui = Path("modules/investment_checklist/ui/ai_research_assistant.py").read_text(encoding="utf-8")
    combined = service + ui
    assert "save_assessment(" not in combined
    for forbidden in ("import requests", "import openai", "urlopen(", "httpx."):
        assert forbidden not in combined
    shell = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    page = Path("pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    assert '"🤖 AI Research Assistant"' in shell
    assert "AI có kiểm soát" in page


def test_postgres_phase4a_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    suffix = uuid.uuid4().hex[:10].upper()
    company_ref_id, review_id, source_id = _seed(repo, suffix)
    _record(repo, company_ref_id, review_id, source_id)
    item = next(
        row for row in list_ai_suggestions(repo, review_id) if row["suggestion_type"] == "evidence_candidate"
    )
    result = decide_ai_suggestion(
        repo, item["id"], decision="accepted", reason="PostgreSQL CI", actor="ci"
    )
    assert result["created_evidence_id"] and result["created_link_id"]
    repo.close()
