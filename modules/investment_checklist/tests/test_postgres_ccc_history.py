from __future__ import annotations

from datetime import date
import os
import uuid

import pytest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository

CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def test_postgres_persists_ccc_and_table11_review_history():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    suffix = uuid.uuid4().hex[:10].upper()
    cid = repo.upsert_company_ref(host_company_key=f"CCC:{suffix}", ticker=f"H{suffix[:5]}", company_name="CCC History", actor="ci")
    rid = repo.create_review(cid, date(2026, 8, 21), analyst_user_id="ci")
    repo.save_screening(review_id=rid, criterion_code="high_roic", analyst_value="yes", confidence=4, actor="ci")
    repo.save_inventory_snapshot(company_ref_id=cid, as_of_date=date(2026, 8, 21), review_id=rid, tev=1000.0, ebit=100.0, ccc_days=37.0, actor="ci")
    inv = repo.inventory_history(cid)
    assert inv[0]["ccc_days"] == 37.0
    history = repo.screening_history_matrix(cid)
    assert len(history) == 1
    assert history[0]["ROIC cao"] == "yes"
    assert history[0]["Total ✓"] == 1
