from __future__ import annotations

from datetime import date
from pathlib import Path
import os
import subprocess
import sys

import psycopg
import pytest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository

CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL not configured")
    return value


def _truncate_target(url: str):
    # Ensure schema exists even when this file is collected before other PostgreSQL tests.
    PostgresChecklistRepository(url, CATALOG).initialize()
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE checklist_company_refs RESTART IDENTITY CASCADE")


def test_sqlite_to_postgres_migration_preserves_history_and_refuses_nonempty_target(tmp_path):
    url = _url()
    _truncate_target(url)

    source = Path(tmp_path) / "phase1b.db"
    sqlite_repo = SQLiteChecklistRepository(source, CATALOG)
    sqlite_repo.initialize()
    cid = sqlite_repo.upsert_company_ref(
        host_company_key="MIGRATE:FPT", ticker="FPT", company_name="FPT Migration Test", actor="migration-test"
    )
    rid = sqlite_repo.create_review(cid, date(2026, 6, 30), analyst_user_id="migration-test")
    sqlite_repo.save_assessment(
        review_id=rid, question_id="Q26", analyst_answer="ROIC retained",
        status="answered", assessment=2, confidence=4, materiality=5, actor="migration-test"
    )
    sqlite_repo.save_screening(
        review_id=rid, criterion_code="high_roic", analyst_value="yes", confidence=4,
        note="migration", actor="migration-test"
    )
    sqlite_repo.save_inventory_snapshot(
        company_ref_id=cid, as_of_date=date(2026, 6, 30), review_id=rid,
        tev=1200, ebit=100, ebitda=150, normalized_earnings=80,
        market_cap=1000, market_price=50000, target_price=70000,
        mos=0.2857, actor="migration-test"
    )
    sid = sqlite_repo.finalize_review(rid, actor="migration-test")
    original = sqlite_repo.get_snapshot(sid)["payload"]

    cmd = [
        sys.executable, "scripts/migrate_checklist_sqlite_to_postgres.py",
        "--sqlite", str(source), "--database-url", url,
    ]
    first = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)
    assert first.returncode == 0, first.stderr

    pg = PostgresChecklistRepository(url, CATALOG)
    pg.initialize()
    company = pg.get_company_ref_by_host_key("MIGRATE:FPT")
    assert company and company["ticker"] == "FPT"
    snapshots = pg.list_snapshots(company["id"])
    assert len(snapshots) == 1
    migrated = pg.get_snapshot(snapshots[0]["id"])["payload"]
    assert migrated["review"]["status"] == original["review"]["status"] == "completed"
    assert migrated["assessments"][0]["version_no"] == original["assessments"][0]["version_no"] == 1
    assert migrated["quality_tally"] == original["quality_tally"] == 1

    before_count = len(pg.list_audit_logs(company["id"], limit=1000))
    second = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)
    assert second.returncode != 0
    after_count = len(pg.list_audit_logs(company["id"], limit=1000))
    assert after_count == before_count
