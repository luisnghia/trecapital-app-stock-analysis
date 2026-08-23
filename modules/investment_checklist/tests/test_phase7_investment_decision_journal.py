from __future__ import annotations

from datetime import date
import hashlib
import os
from pathlib import Path
import uuid

import pytest
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.evidence_workspace import create_evidence_version, create_source
from modules.investment_checklist.services.investment_decision_journal import (
    add_decision_outcome_review,
    decision_journal_bundle,
    list_decision_outcomes,
    list_investment_memos,
    list_risk_register,
    list_thesis_pillars,
    record_investment_decision,
    save_investment_memo,
    save_risk_register_item,
    save_thesis_pillar,
)
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase7.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix: str = "MEMO"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE7:{suffix}", ticker="FPT", company_name="FPT Corporation",
        exchange="HOSE", actor="test",
    )
    review_id = repo.create_review(
        company_ref_id, date(2026, 8, 22), analyst_user_id="analyst",
        review_reason="Phase 7 Investment Memo & Decision Journal QA",
    )
    source_id = create_source(
        repo, company_ref_id=company_ref_id, source_type="annual_report",
        title=f"Annual report 2025 {suffix}", publisher="FPT",
        document_date=date(2025, 12, 31), reliability=5, actor="analyst",
    )
    support_id = create_evidence_version(
        repo, company_ref_id=company_ref_id, source_id=source_id,
        evidence_type="metric", excerpt="Doanh thu ký mới và doanh thu định kỳ tăng trưởng hai chữ số.",
        locator_text="Trang 32, kết quả kinh doanh", evidence_date=date(2025, 12, 31),
        verification_status="verified", direction="supports", confidence=5, actor="analyst",
    )
    contradict_id = create_evidence_version(
        repo, company_ref_id=company_ref_id, source_id=source_id,
        evidence_type="risk", excerpt="Biên lợi nhuận mảng công nghệ chịu áp lực từ chi phí nhân sự.",
        locator_text="Trang 47, quản trị rủi ro", evidence_date=date(2025, 12, 31),
        verification_status="verified", direction="contradicts", confidence=5, actor="analyst",
    )
    return company_ref_id, review_id, support_id, contradict_id


def _memo(repo, company_ref_id, review_id, evidence_id):
    return save_investment_memo(
        repo, company_ref_id=company_ref_id, review_id=review_id, memo_key="primary",
        title="FPT investment memo", thesis_summary="Tăng trưởng dài hạn dựa trên chuyển đổi số.",
        variant_perception="Thị trường đánh giá thấp độ bền doanh thu định kỳ.",
        business_quality="ROIC cao, bảng cân đối lành mạnh và năng lực tuyển dụng.",
        valuation_summary="Ba kịch bản định giá được tách khỏi thesis chất lượng.",
        catalysts="Hợp đồng quốc tế và tăng năng suất AI.",
        invalidation_conditions="Doanh thu ký mới giảm và biên lợi nhuận suy yếu kéo dài.",
        time_horizon_months=36, source_evidence_id=evidence_id, actor="analyst",
    )


def _pillar(repo, company_ref_id, review_id, support_id, contradict_id=None, status="supported"):
    return save_thesis_pillar(
        repo, company_ref_id=company_ref_id, review_id=review_id, pillar_key="recurring-growth",
        pillar_type="business", statement_text="Doanh thu định kỳ hỗ trợ tăng trưởng bền vững.",
        status=status, falsification_test="Doanh thu ký mới giảm hai kỳ liên tiếp.",
        supporting_evidence_id=support_id,
        contradicting_evidence_id=contradict_id if status == "mixed" else None,
        confidence=4, materiality=5, actor="analyst",
    )


def _risk(repo, company_ref_id, review_id, evidence_id):
    return save_risk_register_item(
        repo, company_ref_id=company_ref_id, review_id=review_id, risk_key="talent-cost",
        risk_category="execution", statement_text="Chi phí nhân sự có thể làm giảm biên lợi nhuận.",
        probability=3, impact=4, resilience=4, mitigation="Theo dõi năng suất và giá bán theo quý.",
        early_warning="Biên lợi nhuận giảm trên 150 bps hai quý liên tiếp.", status="monitoring",
        source_evidence_id=evidence_id, actor="analyst",
    )


def test_phase7_versions_falsification_and_evidence_guardrails(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, support_id, contradict_id = _seed(repo)
    first = _memo(repo, company_ref_id, review_id, support_id)
    with pytest.raises(ValidationError, match="Lý do tạo version memo"):
        _memo(repo, company_ref_id, review_id, support_id)
    second = save_investment_memo(
        repo, company_ref_id=company_ref_id, review_id=review_id, memo_key="primary",
        title="FPT investment memo v2", thesis_summary="Thesis được cập nhật sau BCTC.",
        variant_perception="Thị trường vẫn đánh giá thấp doanh thu định kỳ.",
        business_quality="Chất lượng vận hành giữ ổn định.", valuation_summary="Kịch bản định giá cập nhật.",
        catalysts="Hợp đồng quốc tế.", invalidation_conditions="Biên giảm kéo dài.",
        time_horizon_months=36, source_evidence_id=support_id,
        change_reason="Cập nhật BCTC năm", actor="analyst",
    )
    assert second > first
    assert list_investment_memos(repo, review_id)[0]["version_no"] == 2
    with pytest.raises(ValidationError, match="supporting evidence"):
        save_thesis_pillar(
            repo, company_ref_id=company_ref_id, review_id=review_id, pillar_key="missing-evidence",
            pillar_type="moat", statement_text="Lợi thế chưa có nguồn.", status="supported",
            falsification_test="Mất thị phần.", confidence=3, materiality=4, actor="analyst",
        )
    _pillar(repo, company_ref_id, review_id, support_id, contradict_id, status="mixed")
    _risk(repo, company_ref_id, review_id, contradict_id)
    assert len(list_thesis_pillars(repo, review_id)) == 1
    assert list_risk_register(repo, review_id)[0]["risk_score"] == 12


def test_phase7_analyst_signature_snapshot_hash_mos_and_seal(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id, support_id, contradict_id = _seed(repo, "SIGN")
    _memo(repo, company_ref_id, review_id, support_id)
    _pillar(repo, company_ref_id, review_id, support_id)
    _risk(repo, company_ref_id, review_id, contradict_id)
    with pytest.raises(ValidationError, match="xác nhận"):
        record_investment_decision(
            repo, company_ref_id=company_ref_id, review_id=review_id, decision="buy",
            decision_reason="Chất lượng và định giá phù hợp.", time_horizon_months=36,
            primary_invalidation="Thesis tăng trưởng bị phá vỡ.", market_price=100,
            intrinsic_low=110, intrinsic_base=140, intrinsic_high=170,
            acknowledged_gaps=False, analyst_confirmed=True, actor="analyst",
        )
    decision_id = record_investment_decision(
        repo, company_ref_id=company_ref_id, review_id=review_id, decision="buy",
        decision_reason="Chất lượng và định giá phù hợp.", time_horizon_months=36,
        primary_invalidation="Thesis tăng trưởng bị phá vỡ.", market_price=100,
        intrinsic_low=110, intrinsic_base=140, intrinsic_high=170,
        target_position_pct=4, max_position_pct=6,
        acknowledged_gaps=True, analyst_confirmed=True, actor="analyst",
    )
    with repo._conn() as c:
        decision = dict(c.execute("SELECT * FROM investment_decisions WHERE id=?", (decision_id,)).fetchone())
        assert decision["mos_base"] == pytest.approx((140 - 100) / 140)
        assert hashlib.sha256(decision["memo_snapshot_json"].encode("utf-8")).hexdigest() == decision["memo_snapshot_hash"]
        assert c.execute("SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)).fetchone()["n"] == 0
    with pytest.raises(ValidationError, match="niêm phong"):
        _risk(repo, company_ref_id, review_id, contradict_id)
    with pytest.raises(ValidationError, match="bất biến"):
        record_investment_decision(
            repo, company_ref_id=company_ref_id, review_id=review_id, decision="hold",
            decision_reason="Không được ghi lần hai.", time_horizon_months=12,
            primary_invalidation="Không áp dụng.", market_price=100, intrinsic_low=90,
            intrinsic_base=120, intrinsic_high=150, acknowledged_gaps=True,
            analyst_confirmed=True, actor="analyst",
        )


def test_phase7_post_decision_review_snapshot_lock_and_manual_delete(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, decision_review_id, support_id, contradict_id = _seed(repo, "OUTCOME")
    _memo(repo, company_ref_id, decision_review_id, support_id)
    _pillar(repo, company_ref_id, decision_review_id, support_id)
    _risk(repo, company_ref_id, decision_review_id, contradict_id)
    decision_id = record_investment_decision(
        repo, company_ref_id=company_ref_id, review_id=decision_review_id, decision="watch",
        decision_reason="Chờ margin of safety rộng hơn.", time_horizon_months=24,
        primary_invalidation="Tăng trưởng ký mới suy giảm.", acknowledged_gaps=True,
        analyst_confirmed=True, actor="analyst",
    )
    snapshot_id = repo.finalize_review(decision_review_id, actor="analyst", finalize_reason="Ký và đóng memo")
    payload = repo.get_snapshot(snapshot_id)["payload"]
    assert payload["snapshot_schema"] == "phase1b-review-v7-evidence-peer-ai-management-monitoring-decision"
    assert payload["investment_memo_decision_journal"]["schema"] == "investment-memo-decision-journal-v1"
    assert payload["investment_memo_decision_journal"]["decision"]["id"] == decision_id
    outcome_review_id = repo.create_review(
        company_ref_id, date(2026, 12, 31), review_type="delta", analyst_user_id="analyst",
        review_reason="Đánh giá outcome sau quyết định",
    )
    with pytest.raises(ValidationError, match="exact evidence"):
        add_decision_outcome_review(
            repo, decision_id=decision_id, company_ref_id=company_ref_id, review_id=outcome_review_id,
            as_of_date=date(2026, 12, 31), thesis_status="intact", outcome_label="positive",
            process_grade=4, outcome_summary="Thesis diễn biến đúng.", lessons_learned="Giữ kỷ luật.", actor="analyst",
        )
    add_decision_outcome_review(
        repo, decision_id=decision_id, company_ref_id=company_ref_id, review_id=outcome_review_id,
        as_of_date=date(2026, 12, 31), thesis_status="intact", outcome_label="positive",
        process_grade=4, outcome_summary="Thesis diễn biến đúng.", lessons_learned="Giữ kỷ luật.",
        source_evidence_id=support_id, actor="analyst",
    )
    assert len(list_decision_outcomes(repo, company_ref_id)) == 1
    preview = review_delete_preview(repo, decision_review_id)
    assert preview["counts"]["investment_decisions"] == 1
    assert preview["counts"]["decision_outcomes"] == 1
    delete_review_manually(
        repo, decision_review_id, actor="admin", reason="Xóa Phase 7 QA",
        confirmation_text=f"XÓA REVIEW #{decision_review_id}",
    )
    assert repo.get_review(outcome_review_id)
    with repo._conn() as c:
        for table in ("investment_memo_versions", "investment_thesis_pillars", "investment_risk_register", "investment_decisions"):
            assert c.execute(f"SELECT COUNT(*) n FROM {table} WHERE review_id=?", (decision_review_id,)).fetchone()["n"] == 0
        assert c.execute("SELECT COUNT(*) n FROM decision_outcome_reviews WHERE decision_id=?", (decision_id,)).fetchone()["n"] == 0
        assert c.execute("SELECT id FROM research_evidence WHERE id=?", (support_id,)).fetchone()


def test_phase7_streamlit_route_and_no_ai_no_assessment_contract(tmp_path, monkeypatch):
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL", "TEST_DATABASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    repo = _repo(tmp_path)
    company_ref_id, review_id, _, _ = _seed(repo, "UI")
    app = f'''
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.investment_decision_journal import render_investment_decision_journal
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
render_investment_decision_journal(repo, {company_ref_id}, repo.get_review({review_id}), "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0 and len(at.error) == 0
    assert any("Investment Memo & Decision Journal" in str(item.value) for item in at.markdown)
    for view in ("Investment Memo", "Thesis Pillars", "Risk Register", "Decision Journal"):
        at.radio[0].set_value(view).run()
        assert len(at.exception) == 0 and len(at.error) == 0
    service = Path("modules/investment_checklist/services/investment_decision_journal.py").read_text(encoding="utf-8").lower()
    ui = Path("modules/investment_checklist/ui/investment_decision_journal.py").read_text(encoding="utf-8").lower()
    for forbidden in ("save_assessment(", "import openai", "import requests", "import httpx", "urlopen("):
        assert forbidden not in service and forbidden not in ui
    shell = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    active_shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    assert '"📝 Investment Memo & Decision"' in shell
    assert 'elif section == "📝 Investment Memo & Decision":' in active_shell
    assert "render_investment_decision_journal(repo, company_ref_id, review, actor)" in active_shell


def test_postgres_phase7_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    suffix = uuid.uuid4().hex[:10].upper()
    company_ref_id, review_id, support_id, contradict_id = _seed(repo, suffix)
    _memo(repo, company_ref_id, review_id, support_id)
    _pillar(repo, company_ref_id, review_id, support_id)
    _risk(repo, company_ref_id, review_id, contradict_id)
    bundle = decision_journal_bundle(repo, review_id)
    assert bundle["summary"]["pillars"] == 1 and bundle["summary"]["open_risks"] == 1
    repo.close()
