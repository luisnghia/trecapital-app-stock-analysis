from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from modules.investment_checklist.contracts import CompanyContext, HostContext
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
    assert "if core_ready:" in source
    assert "self._portfolio_extension_schema_ready = True" in source
