from __future__ import annotations

from datetime import date
import os
import uuid

import pytest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import ValidationError

CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _repo():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    r = PostgresChecklistRepository(url, CATALOG)
    r.initialize()
    return r


def test_postgres_phase1c_end_to_end_and_snapshot_lock():
    r = _repo()
    suffix = uuid.uuid4().hex[:10].upper()
    ticker = f"T{suffix[:5]}"
    cid = r.upsert_company_ref(
        host_company_key=f"TEST:{suffix}", ticker=ticker, company_name=f"Phase1C {suffix}",
        exchange="HOSE", industry_name="Technology", actor="ci"
    )
    assert len(r.list_questions()) == 59
    assert len(r.list_screening_criteria()) == 10

    rid = r.create_review(cid, date(2026, 8, 20), analyst_user_id="ci")
    r.save_assessment(
        review_id=rid, question_id="Q26", analyst_answer="ROIC quality checked",
        status="answered", assessment=1, confidence=4, materiality=5, actor="ci"
    )
    r.save_screening(
        review_id=rid, criterion_code="high_roic", analyst_value="yes",
        confidence=4, note="CI durable persistence", actor="ci"
    )
    r.save_inventory_snapshot(
        company_ref_id=cid, as_of_date=date(2026, 8, 20), review_id=rid,
        tev=1200, ebit=100, ebitda=150, normalized_earnings=80,
        total_debt=300, fcf_current=60, market_cap=1000,
        market_price=50000, target_price=70000, mos=0.2857,
        data_origin="host_data_layer", actor="ci"
    )
    sid = r.finalize_review(rid, actor="ci")
    snap = r.get_snapshot(sid)
    assert snap["payload"]["review"]["status"] == "completed"
    assert snap["payload"]["assessments"][0]["question_id"] == "Q26"
    assert snap["payload"]["quality_tally"] == 1

    with pytest.raises(ValidationError):
        r.save_assessment(
            review_id=rid, question_id="Q26", analyst_answer="must stay locked",
            status="answered", assessment=2, confidence=5, materiality=5,
            change_reason="should fail", actor="ci"
        )


def test_postgres_explicit_carry_forward():
    r = _repo()
    suffix = uuid.uuid4().hex[:10].upper()
    cid = r.upsert_company_ref(
        host_company_key=f"TEST-CARRY:{suffix}", ticker=f"C{suffix[:5]}",
        company_name=f"Carry {suffix}", actor="ci"
    )
    r1 = r.create_review(cid, date(2025, 12, 31), analyst_user_id="ci")
    r.save_assessment(
        review_id=r1, question_id="Q16", analyst_answer="Pricing power",
        status="answered", assessment=2, confidence=4, materiality=5, actor="ci"
    )
    r.finalize_review(r1, actor="ci")
    r2 = r.create_review(cid, date(2026, 6, 30), analyst_user_id="ci")
    assert r.latest_assessment(r2, "Q16") is None
    r.confirm_unchanged(r2, "Q16", actor="ci")
    current = r.latest_assessment(r2, "Q16")
    assert current["assessment"] == 2
    assert current["analyst_confirmed"] == 1
    assert current["copied_from_assessment_id"] is not None
