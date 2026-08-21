from __future__ import annotations

import os

import pandas as pd
import pytest

from modules.investment_checklist.contracts import CompanyContext, InventorySourceData
from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview
from modules.investment_checklist.source_policy import SourcePolicyDataProvider

CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


class _Provider:
    def __init__(self, annual_df: pd.DataFrame, data: InventorySourceData):
        self.annual_df = annual_df
        self.data = data

    def get_inventory_source_data(self, company):
        return self.data

    def get_inventory_proxy_history(self, years=10):
        return [
            {
                "period": "TTM",
                "source_type": "TTM",
                "tev": self.data.tev,
                "ebit": self.data.ebit,
                "ebitda": self.data.ebitda,
                "normalized_earnings": self.data.normalized_earnings,
                "total_debt": self.data.total_debt,
                "interest_expense": self.data.interest_expense,
                "fcf_current": self.data.fcf_current,
                "market_cap": self.data.market_cap,
                "dividend_per_share": self.data.dividend_per_share,
                "market_price": self.data.market_price,
                "target_price": self.data.target_price,
            }
        ]


def _sample_data():
    return InventorySourceData(
        as_of_date="TTM",
        tev=12_000,
        ebit=1_200,
        ebitda=1_500,
        normalized_earnings=1_000,
        total_debt=2_000,
        interest_expense=100,
        fcf_current=900,
        market_cap=11_000,
        dividend_per_share=1_000,
        market_price=20_000,
        fcf_estimate=1_700,
        target_price=25_000,
        mos=0.20,
        shares_outstanding_mil=550,
        ccc_days=45,
        source_notes=(),
    )


def _seed_review_chain(repo, host_key: str):
    repo.initialize()
    cid = repo.upsert_company_ref(host_company_key=host_key, ticker="DEL", company_name="Delete Test")
    code = repo.list_screening_criteria()[0]["criterion_code"]

    r1 = repo.create_review(cid, "2026-01-31", "full", "analyst", review_reason="Initial review")
    repo.save_assessment(
        review_id=r1,
        question_id="Q01",
        analyst_answer="Initial answer",
        status="answered",
        assessment=1,
        confidence=4,
        materiality=4,
        change_reason="Initial assessment",
        actor="analyst",
    )
    repo.save_screening(
        review_id=r1,
        criterion_code=code,
        analyst_value="yes",
        confidence=4,
        note="Initial screening",
        actor="analyst",
    )
    repo.save_inventory_snapshot(
        company_ref_id=cid,
        as_of_date="2026-01-31",
        review_id=r1,
        tev=12_000,
        ebit=1_200,
        ebitda=1_500,
        normalized_earnings=1_000,
        total_debt=2_000,
        interest_expense=100,
        fcf_current=900,
        market_cap=11_000,
        market_price=20_000,
        target_price=25_000,
        actor="analyst",
        note="Initial inventory",
    )
    repo.finalize_review(r1, actor="analyst", finalize_reason="Initial review complete")

    r2 = repo.create_review(cid, "2026-02-28", "delta", "analyst", review_reason="Follow-up review")
    a2 = repo.confirm_unchanged(r2, "Q01", actor="analyst")
    s2 = repo.confirm_screening_unchanged(r2, code, actor="analyst")
    assert repo.get_review(r2)["prior_review_id"] == r1
    return cid, r1, r2, a2, s2


def _assert_deleted_chain(repo, cid, r1, r2, a2, s2):
    assert repo.get_review(r1) is None
    assert repo.get_review(r2)["prior_review_id"] is None
    with repo._conn() as c:
        assert c.execute("SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (r1,)).fetchone()["n"] == 0
        assert c.execute("SELECT COUNT(*) n FROM screening_assessments WHERE review_id=?", (r1,)).fetchone()["n"] == 0
        assert c.execute("SELECT COUNT(*) n FROM opportunity_inventory_snapshots WHERE last_review_id=?", (r1,)).fetchone()["n"] == 0
        assert c.execute("SELECT COUNT(*) n FROM data_snapshots WHERE review_id=?", (r1,)).fetchone()["n"] == 0
        assert c.execute("SELECT copied_from_assessment_id FROM analyst_assessments WHERE id=?", (a2,)).fetchone()["copied_from_assessment_id"] is None
        assert c.execute("SELECT copied_from_screening_id FROM screening_assessments WHERE id=?", (s2,)).fetchone()["copied_from_screening_id"] is None
        tombstones = c.execute(
            "SELECT * FROM audit_logs WHERE company_ref_id=? AND action='manual_delete' AND entity_type='review_tombstone' AND entity_id=?",
            (cid, str(r1)),
        ).fetchall()
        assert len(tombstones) == 1
        assert tombstones[0]["review_id"] is None


def test_manual_review_delete_requires_reason_and_exact_confirmation_sqlite(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "delete.db", CATALOG)
    cid, r1, r2, a2, s2 = _seed_review_chain(repo, "DELETE:SQLITE")
    preview = review_delete_preview(repo, r1)
    assert preview["counts"]["analyst_assessments"] == 1
    assert preview["counts"]["screening_assessments"] == 1
    assert preview["counts"]["inventory_snapshots"] == 1
    assert preview["counts"]["immutable_snapshots"] == 1
    assert preview["counts"]["later_reviews_linked"] == 1

    with pytest.raises(ValidationError):
        delete_review_manually(repo, r1, actor="analyst", reason="", confirmation_text=preview["confirmation_token"])
    with pytest.raises(ValidationError):
        delete_review_manually(repo, r1, actor="analyst", reason="test cleanup", confirmation_text="XOA")

    delete_review_manually(
        repo,
        r1,
        actor="analyst",
        reason="Xóa review nhập thử sai",
        confirmation_text=preview["confirmation_token"],
    )
    _assert_deleted_chain(repo, cid, r1, r2, a2, s2)


def test_manual_review_delete_postgres_when_ci_database_is_available():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    try:
        unique = str(pd.Timestamp.utcnow().value)
        cid, r1, r2, a2, s2 = _seed_review_chain(repo, f"DELETE:PG:{unique}")
        token = review_delete_preview(repo, r1)["confirmation_token"]
        delete_review_manually(repo, r1, actor="analyst", reason="CI manual delete", confirmation_text=token)
        _assert_deleted_chain(repo, cid, r1, r2, a2, s2)
    finally:
        repo.close()


def test_cyclical_policy_does_not_mislabel_raw_ttm_as_normalized_earnings():
    inner = _Provider(pd.DataFrame([{"period": "TTM", "pretax_profit_bil": 1_000}]), _sample_data())
    wrapper = SourcePolicyDataProvider(inner, "cyclical")
    out = wrapper.get_inventory_source_data(CompanyContext("T:CY", "CY", "Cyclical", company_type="cyclical"))
    assert out.normalized_earnings is None
    assert any("chu kỳ" in x.lower() for x in out.source_notes)
    hist = wrapper.get_inventory_proxy_history(10)
    assert hist[0]["normalized_earnings"] is None
    assert hist[0]["tev_normalized_earnings"] is None
    # Shearn Pre-tax Earnings Yield is EBIT/TEV, so current watchlist yield remains visible.
    assert hist[0]["pretax_earnings_yield"] == 1_200 / 12_000


def test_financial_industry_policy_suppresses_industrial_table12_metrics():
    inner = _Provider(pd.DataFrame([{"period": "TTM", "pretax_profit_bil": 1_000}]), _sample_data())
    for company_type in ("bank", "insurance", "securities"):
        wrapper = SourcePolicyDataProvider(inner, company_type)
        out = wrapper.get_inventory_source_data(CompanyContext(f"T:{company_type}", company_type.upper(), company_type, company_type=company_type))
        assert out.tev is None
        assert out.ebitda is None
        assert out.fcf_current is None
        assert out.ccc_days is None
        assert any("ngành tài chính" in x.lower() for x in out.source_notes)
        hist = wrapper.get_inventory_proxy_history(10)
        assert hist[0]["tev"] is None
        assert hist[0]["debt_ebitda"] is None
        assert hist[0]["fcf_yield_ev"] is None


def test_normal_company_keeps_baseline_proxy_but_labels_it_explicitly():
    inner = _Provider(pd.DataFrame([{"period": "TTM", "pretax_profit_bil": 1_000}]), _sample_data())
    wrapper = SourcePolicyDataProvider(inner, "normal")
    out = wrapper.get_inventory_source_data(CompanyContext("T:N", "N", "Normal", company_type="normal"))
    assert out.normalized_earnings == 1_000
    assert any("baseline proxy" in x.lower() for x in out.source_notes)
