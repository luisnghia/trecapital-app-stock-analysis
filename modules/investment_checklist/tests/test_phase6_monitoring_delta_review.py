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
from modules.investment_checklist.services.monitoring_delta_review import (
    add_monitoring_observation,
    create_delta_item,
    list_delta_items,
    list_monitoring_observations,
    list_monitoring_rules,
    monitoring_delta_bundle,
    record_delta_decision,
    save_monitoring_rule,
)
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase6.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix: str = "DELTA"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE6:{suffix}", ticker="FPT", company_name="FPT Corporation",
        exchange="HOSE", actor="test",
    )
    prior_id = repo.create_review(
        company_ref_id, date(2025, 12, 31), analyst_user_id="analyst",
        review_reason="Baseline completed review",
    )
    repo.save_assessment(
        review_id=prior_id, question_id="Q16", analyst_answer="Pricing power ổn định",
        status="answered", assessment=1, confidence=4, materiality=5,
        change_reason="Baseline", actor="analyst",
    )
    repo.finalize_review(prior_id, actor="analyst", finalize_reason="Baseline cho delta QA")
    review_id = repo.create_review(
        company_ref_id, date(2026, 8, 22), review_type="delta", analyst_user_id="analyst",
        review_reason="BCTC quý mới và thay đổi pricing power",
    )
    source_id = create_source(
        repo, company_ref_id=company_ref_id, source_type="quarterly_report",
        title=f"Quarterly report 2026 {suffix}", publisher="FPT",
        document_date=date(2026, 6, 30), reliability=5, actor="analyst",
    )
    evidence_id = create_evidence_version(
        repo, company_ref_id=company_ref_id, source_id=source_id, evidence_type="metric",
        excerpt="Biên lợi nhuận gộp giảm 350 điểm cơ bản so với cùng kỳ.",
        locator_text="Trang 12, thuyết minh doanh thu", evidence_date=date(2026, 6, 30),
        verification_status="verified", direction="contradicts", confidence=5, actor="analyst",
    )
    return company_ref_id, prior_id, review_id, evidence_id


def _rule(repo, company_ref_id, review_id, evidence_id):
    return save_monitoring_rule(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q16",
        rule_key="q16-gross-margin", title="Theo dõi biên lợi nhuận gộp",
        description="Kích hoạt khi biên gộp giảm trên 2 điểm phần trăm.",
        cadence="quarterly", trigger_type="metric_threshold", metric_key="gross_margin",
        comparison_operator="delta", threshold_value=-2.0, threshold_unit="ppt",
        materiality=5, source_evidence_id=evidence_id, actor="analyst",
    )


def test_phase6_rule_versions_threshold_guardrails_and_evidence_scope(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, _, review_id, evidence_id = _seed(repo)
    first = _rule(repo, company_ref_id, review_id, evidence_id)
    with pytest.raises(ValidationError, match="Lý do tạo version"):
        _rule(repo, company_ref_id, review_id, evidence_id)
    second = save_monitoring_rule(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q16",
        rule_key="q16-gross-margin", title="Theo dõi biên lợi nhuận gộp",
        description="Nâng độ nhạy trigger lên 1,5 điểm phần trăm.", cadence="quarterly",
        trigger_type="metric_threshold", metric_key="gross_margin", comparison_operator="delta",
        threshold_value=-1.5, threshold_unit="ppt", materiality=5,
        source_evidence_id=evidence_id, change_reason="Thesis nhạy hơn với pricing power", actor="analyst",
    )
    assert second > first
    rules = list_monitoring_rules(repo, review_id)
    assert len(rules) == 1 and rules[0]["version_no"] == 2
    with pytest.raises(ValidationError, match="Metric threshold"):
        save_monitoring_rule(
            repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q17",
            title="Rule sai", description="Thiếu ngưỡng", cadence="quarterly",
            trigger_type="metric_threshold", actor="analyst",
        )


def test_phase6_observation_delta_queue_and_no_auto_assessment_write(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, prior_id, review_id, evidence_id = _seed(repo, "QUEUE")
    rule_id = _rule(repo, company_ref_id, review_id, evidence_id)
    with pytest.raises(ValidationError, match="exact evidence"):
        add_monitoring_observation(
            repo, company_ref_id=company_ref_id, review_id=review_id, rule_id=rule_id,
            observed_at=date(2026, 8, 22), as_of_date=date(2026, 6, 30),
            observation_status="triggered", summary="Không có evidence", actor="analyst",
        )
    observation_id = add_monitoring_observation(
        repo, company_ref_id=company_ref_id, review_id=review_id, rule_id=rule_id,
        observed_at=date(2026, 8, 22), as_of_date=date(2026, 6, 30),
        observation_status="triggered", observed_value=-3.5, observed_unit="ppt",
        summary="Biên gộp giảm vượt ngưỡng theo dõi.", source_evidence_id=evidence_id,
        confidence=5, materiality=5, actor="analyst",
    )
    item_id = create_delta_item(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q16",
        change_type="metric_threshold", proposed_action="revise",
        rationale="Pricing power có dấu hiệu suy yếu so với baseline.", observation_id=observation_id,
        source_evidence_id=evidence_id, confidence=5, materiality=5, actor="analyst",
    )
    item = list_delta_items(repo, review_id)[0]
    assert item["id"] == item_id and item["prior_review_id"] == prior_id
    assert item["baseline_assessment_id"] is not None
    with repo._conn() as c:
        assert c.execute("SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)).fetchone()["n"] == 0
    with pytest.raises(ValidationError, match="Analyst Workspace"):
        record_delta_decision(
            repo, delta_item_id=item_id, decision="revise", decision_reason="Chưa có assessment", actor="analyst",
        )


def test_phase6_decision_requires_matching_analyst_assessment_and_is_immutable(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, _, review_id, evidence_id = _seed(repo, "DECISION")
    rule_id = _rule(repo, company_ref_id, review_id, evidence_id)
    observation_id = add_monitoring_observation(
        repo, company_ref_id=company_ref_id, review_id=review_id, rule_id=rule_id,
        observed_at=date(2026, 8, 22), as_of_date=date(2026, 6, 30), observation_status="triggered",
        summary="Trigger pricing power", source_evidence_id=evidence_id, actor="analyst",
    )
    item_id = create_delta_item(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q16",
        change_type="metric_threshold", proposed_action="revise", rationale="Cần revise",
        observation_id=observation_id, source_evidence_id=evidence_id, actor="analyst",
    )
    assessment_id = repo.save_assessment(
        review_id=review_id, question_id="Q16", analyst_answer="Pricing power suy yếu",
        status="needs_review", assessment=-1, confidence=4, materiality=5,
        change_reason="Biên gộp giảm vượt ngưỡng", actor="analyst",
    )
    decision_id = record_delta_decision(
        repo, delta_item_id=item_id, decision="revise",
        decision_reason="Đã cập nhật assessment theo evidence quý mới",
        resulting_assessment_id=assessment_id, actor="analyst",
    )
    assert decision_id and list_delta_items(repo, review_id)[0]["decision"] == "revise"
    with pytest.raises(ValidationError, match="bất biến"):
        record_delta_decision(
            repo, delta_item_id=item_id, decision="dismiss", decision_reason="Không được sửa", actor="analyst",
        )


def test_phase6_snapshot_review_lock_and_review_deletion(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, _, review_id, evidence_id = _seed(repo, "SNAPSHOT")
    rule_id = _rule(repo, company_ref_id, review_id, evidence_id)
    observation_id = add_monitoring_observation(
        repo, company_ref_id=company_ref_id, review_id=review_id, rule_id=rule_id,
        observed_at=date(2026, 8, 22), as_of_date=date(2026, 6, 30), observation_status="research_gap",
        summary="Cần kiểm chứng thêm từ khách hàng.", actor="analyst",
    )
    create_delta_item(
        repo, company_ref_id=company_ref_id, review_id=review_id, question_id="Q16",
        change_type="new_evidence", proposed_action="research_gap", rationale="Chưa đủ kiểm chứng chéo",
        observation_id=observation_id, confidence=3, materiality=5, actor="analyst",
    )
    snapshot_id = repo.finalize_review(review_id, actor="analyst", finalize_reason="Đóng Phase 6 QA")
    payload = repo.get_snapshot(snapshot_id)["payload"]
    assert payload["snapshot_schema"] == "phase1b-review-v8-evidence-peer-ai-management-monitoring-decision-topdown"
    assert payload["monitoring_delta_review"]["schema"] == "monitoring-delta-review-v1"
    assert payload["monitoring_delta_review"]["summary"]["open_delta_items"] == 1
    with pytest.raises(ValidationError, match="read-only"):
        add_monitoring_observation(
            repo, company_ref_id=company_ref_id, review_id=review_id, rule_id=rule_id,
            observed_at=date.today(), as_of_date=date.today(), observation_status="unknown",
            summary="Locked", actor="analyst",
        )
    preview = review_delete_preview(repo, review_id)
    assert preview["counts"]["monitoring_rules"] == 1
    assert preview["counts"]["monitoring_observations"] == 1
    assert preview["counts"]["delta_items"] == 1
    delete_review_manually(
        repo, review_id, actor="admin", reason="Xóa Phase 6 QA",
        confirmation_text=f"XÓA REVIEW #{review_id}",
    )
    with repo._conn() as c:
        for table in ("monitoring_rules", "monitoring_observations", "delta_review_items", "delta_review_decisions"):
            assert c.execute(f"SELECT COUNT(*) n FROM {table} WHERE review_id=?", (review_id,)).fetchone()["n"] == 0
        assert c.execute("SELECT id FROM research_evidence WHERE id=?", (evidence_id,)).fetchone()


def test_phase6_streamlit_route_and_no_network_no_auto_assessment_contract(tmp_path, monkeypatch):
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL", "TEST_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    repo = _repo(tmp_path)
    company_ref_id, _, review_id, _ = _seed(repo, "UI")
    app = f'''
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.monitoring_delta_review import render_monitoring_delta_review
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
render_monitoring_delta_review(repo, {company_ref_id}, repo.get_review({review_id}), "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0 and len(at.error) == 0
    assert any("Monitoring & Delta Review" in str(item.value) for item in at.markdown)
    for view in ("Monitoring Rules", "Observations", "Delta Queue"):
        at.radio[0].set_value(view).run()
        assert len(at.exception) == 0 and len(at.error) == 0
    service = Path("modules/investment_checklist/services/monitoring_delta_review.py").read_text(encoding="utf-8").lower()
    ui = Path("modules/investment_checklist/ui/monitoring_delta_review.py").read_text(encoding="utf-8").lower()
    for forbidden in ("save_assessment(", "import openai", "import requests", "import httpx", "urlopen("):
        assert forbidden not in service and forbidden not in ui
    shell = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    active_shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    assert '"📡 Monitoring & Delta Review"' in shell
    assert 'elif section == "📡 Monitoring & Delta Review":' in active_shell
    assert "render_monitoring_delta_review(repo, company_ref_id, review, actor)" in active_shell


def test_postgres_phase6_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    suffix = uuid.uuid4().hex[:10].upper()
    company_ref_id, _, review_id, evidence_id = _seed(repo, suffix)
    _rule(repo, company_ref_id, review_id, evidence_id)
    bundle = monitoring_delta_bundle(repo, review_id)
    assert bundle["summary"]["active_rules"] == 1
    repo.close()
