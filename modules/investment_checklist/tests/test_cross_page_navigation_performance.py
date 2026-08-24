from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from modules.investment_checklist.contracts import CompanyContext, HostContext
from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.services.extension_schema_cache import ensure_extension_schema
from modules.investment_checklist.services.integration_service import ChecklistIntegrationService


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def test_navigation_bootstrap_uses_one_checkout_and_skips_unchanged_sync_audit(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "navigation.db", CATALOG)
    repo.initialize()
    ensure_extension_schema(repo)
    company_ref_id = repo.upsert_company_ref(
        host_company_key="TICKER:FAST",
        ticker="FAST",
        company_name="Fast Navigation",
    )
    review_id = repo.create_review(company_ref_id, "2026-08-23", review_reason="Performance test")
    host = HostContext(
        company=CompanyContext(
            company_key="TICKER:FAST",
            ticker="FAST",
            company_name="Fast Navigation",
        )
    )
    integration = ChecklistIntegrationService(repo, host)

    original_conn = repo._conn
    with original_conn() as conn:
        audit_before = conn.execute(
            "SELECT COUNT(*) n FROM audit_logs WHERE company_ref_id=?", (company_ref_id,)
        ).fetchone()["n"]

    checkouts = 0

    @contextmanager
    def counted_conn():
        nonlocal checkouts
        checkouts += 1
        with original_conn() as conn:
            yield conn

    repo._conn = counted_conn
    bundle = integration.navigation_bootstrap(preferred_review_id=review_id)

    assert checkouts == 1
    assert bundle["company_ref_id"] == company_ref_id
    assert bundle["home_bundle"]["review_id"] == review_id
    assert bundle["watchlisted"] is False

    with original_conn() as conn:
        audit_after = conn.execute(
            "SELECT COUNT(*) n FROM audit_logs WHERE company_ref_id=?", (company_ref_id,)
        ).fetchone()["n"]
    assert audit_after == audit_before


def test_default_checklist_path_keeps_heavy_workspaces_and_financial_engines_lazy():
    shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    shell_preamble = shell.split("def _host_signature", 1)[0]
    assert "from .integration_preview import SECTIONS" not in shell
    assert "ai_research_assistant" not in shell_preamble
    assert "industry_overlay" not in shell_preamble
    assert "management_intelligence" not in shell_preamble
    assert "monitoring_delta_review" not in shell_preamble
    assert "investment_decision_journal" not in shell_preamble

    page = Path("pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    page_preamble = page.split("def _valuation_range", 1)[0]
    assert "from module2_engine import" not in page_preamble
    assert "trecapital_debt_enricher" not in page_preamble


def test_postgres_runtime_uses_migration_checkpoint_instead_of_replaying_schema():
    source = Path("modules/investment_checklist/repositories/postgres_repository.py").read_text(encoding="utf-8")
    assert "def _runtime_schema_ready" in source
    assert "information_schema.tables" in source
    assert "question_count" in source
    assert "screening_count" in source
    assert "if core_ready:" in source
    assert "self._portfolio_extension_schema_ready = True" in source


def test_postgres_runtime_checkpoint_rejects_empty_seed_catalogs():
    class FakeCursor:
        def __init__(self, *, question_count: int, screening_count: int):
            self.question_count = question_count
            self.screening_count = screening_count
            self.query_no = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, _params=()):
            self.query_no += 1

        def fetchall(self):
            return [
                {"table_name": name}
                for name in (
                    "checklist_company_refs", "checklist_questions", "screening_criteria",
                    "research_reviews", "research_source_contents", "monitoring_rules",
                    "investment_decisions", "decision_outcome_reviews", "topdown_sector_snapshots", "checklist_watchlist",
                    "analyst_table_overrides",
                )
            ]

        def fetchone(self):
            return {
                "question_count": self.question_count,
                "screening_count": self.screening_count,
            }

    class FakeConnection:
        def __init__(self, cursor):
            self._cursor = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return self._cursor

    class FakePool:
        def __init__(self, cursor):
            self._cursor = cursor

        def connection(self):
            return FakeConnection(self._cursor)

    repo = object.__new__(PostgresChecklistRepository)
    repo.question_catalog_path = Path(CATALOG)

    repo._pool = FakePool(FakeCursor(question_count=0, screening_count=0))
    assert repo._runtime_schema_ready() == (False, True)

    repo._pool = FakePool(FakeCursor(question_count=59, screening_count=10))
    assert repo._runtime_schema_ready() == (True, True)
