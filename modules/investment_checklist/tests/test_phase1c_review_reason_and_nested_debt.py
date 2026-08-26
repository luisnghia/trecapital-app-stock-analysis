from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.trecapital_debt_enricher import augment_debt_from_latest_fireant_raw
import modules.investment_checklist.ui as checklist_ui  # noqa: F401 - applies package timeline policy
from modules.investment_checklist.ui import page

CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def test_nested_fireant_debt_wrapper_is_parsed(tmp_path):
    nested_body = {
        "data": {
            "items": [
                {"Name": "Vay và nợ thuê tài chính ngắn hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 3_565_000_000_000}]},
                {"Name": "Vay và nợ thuê tài chính dài hạn", "Values": [{"Year": 2026, "Quarter": 2, "Value": 24_000_000_000}]},
                # Detail must not be added on top of the core short/long debt rows.
                {"Name": "Trái phiếu phát hành", "Values": [{"Year": 2026, "Quarter": 2, "Value": 500_000_000_000}]},
            ]
        }
    }
    manifest = {
        "responses": [{
            "url": "https://www.fireant.vn/api/Data/Finance/LastestFinancialReports?symbol=DCM&type=1&year=2026&quarter=2&count=20",
            "body": json.dumps(nested_body, ensure_ascii=False),
        }]
    }
    (tmp_path / "fireant_excel_vba_DCM_1.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    quarterly = pd.DataFrame([{"ticker": "DCM", "period_type": "Q", "period": "Q2/2026", "year": 2026, "quarter": 2}])
    annual, q, note = augment_debt_from_latest_fireant_raw(pd.DataFrame(), quarterly, "DCM", tmp_path)
    assert annual.empty
    assert float(q.iloc[0]["short_term_debt_bil"]) == 3565.0
    assert float(q.iloc[0]["long_term_debt_bil"]) == 24.0
    assert float(q.iloc[0]["interest_bearing_debt_bil"]) == 3589.0
    assert "Trecapital FireAnt raw audit" in note


def test_proxy_and_review_dates_put_ttm_above_every_calendar_date():
    dates = [
        page._period_sort_date("2024", "TTM"),
        page._period_sort_date("TTM", "TTM"),
        page._period_sort_date("2026-06-30", "TTM"),
        page._period_sort_date("2025", "TTM"),
    ]
    ordered = sorted(dates, reverse=True)
    assert ordered[0] == pd.Timestamp.max.normalize()
    assert ordered[1:] == [
        pd.Timestamp("2026-06-30"),
        pd.Timestamp("2025-12-31"),
        pd.Timestamp("2024-12-31"),
    ]


def test_sqlite_persists_review_create_and_finalize_reasons(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "checklist.db", CATALOG)
    repo.initialize()
    cid = repo.upsert_company_ref(host_company_key="T:RSN", ticker="RSN", company_name="Reason Test")
    with pytest.raises(ValidationError):
        repo.create_review(cid, "2026-08-21", review_reason="   ")
    rid = repo.create_review(cid, "2026-08-21", review_reason="BCTC quý mới và cập nhật thesis")
    assert repo.get_review(rid)["review_reason"] == "BCTC quý mới và cập nhật thesis"
    with pytest.raises(ValidationError):
        repo.finalize_review(rid, finalize_reason="")
    repo.finalize_review(rid, finalize_reason="Đã hoàn tất kiểm tra và khóa nhận định")
    review = repo.get_review(rid)
    assert review["status"] == "completed"
    assert review["finalize_reason"] == "Đã hoàn tất kiểm tra và khóa nhận định"


def test_postgres_persists_review_reasons_when_ci_database_is_available():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    cid = repo.upsert_company_ref(host_company_key="REASON:CI", ticker="RSNCI", company_name="Reason CI")
    rid = repo.create_review(cid, "2026-08-21", review_reason="CI reason")
    assert repo.get_review(rid)["review_reason"] == "CI reason"
    repo.finalize_review(rid, finalize_reason="CI finalize reason")
    assert repo.get_review(rid)["finalize_reason"] == "CI finalize reason"
    repo.close()
