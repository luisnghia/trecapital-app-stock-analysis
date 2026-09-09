from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import inspect
from zipfile import ZipFile

import pandas as pd

from modules.investment_checklist.services import financial_evidence as financial_service
from modules.investment_checklist.services import reporting as report_service
from modules.investment_checklist.services.financial_evidence import (
    MISSING_STANDARDIZED_DATA,
    extract_question_financial_evidence,
)
from modules.investment_checklist.services.reporting import (
    build_investment_checklist_docx,
    build_investment_checklist_report_payload,
)


class Provider:
    def __init__(self, annual_df):
        self.annual_df = annual_df


class FakeRepo:
    def __init__(self):
        self.company = {
            "id": 1,
            "host_company_key": "TICKER:DGC",
            "ticker": "DGC",
            "company_name": "Hóa chất Đức Giang",
            "exchange": "HOSE",
            "industry_name": "Hóa chất",
        }
        self.review = {
            "id": 9,
            "company_ref_id": 1,
            "as_of_date": "2026-09-09",
            "review_type": "full",
            "status": "in_progress",
            "review_reason": "V99 regression",
        }
        self.questions = [
            {"question_id": "Q25", "question_no": 25, "group_name": "Operating & Financial Health", "question_vi": "Bảng cân đối mạnh hay yếu?", "research_mode": "hybrid", "supporting_tool": "Balance Sheet"},
            {"question_id": "Q32", "question_no": 32, "group_name": "Earnings & Cash Flow", "question_vi": "Doanh nghiệp có yêu cầu capex cao hay thấp?", "research_mode": "hybrid", "supporting_tool": "Capex"},
        ]
        self.assessment = {
            "id": 101,
            "review_id": 9,
            "question_id": "Q25",
            "version_no": 3,
            "analyst_answer": "Thanh khoản tốt nhưng cần theo dõi nợ vay.",
            "assessment": -1,
            "confidence": 4,
            "materiality": 5,
            "status": "answered",
            "change_reason": "Cập nhật sau BCTC mới",
        }

    def get_company_ref(self, company_ref_id):
        return deepcopy(self.company) if int(company_ref_id) == 1 else None

    def get_review(self, review_id):
        return deepcopy(self.review) if int(review_id) == 9 else None

    def list_questions(self):
        return deepcopy(self.questions)

    def latest_assessments_for_review(self, review_id):
        return [deepcopy(self.assessment)] if int(review_id) == 9 else []

    def review_metrics(self, review_id):
        return {"answered": 1, "research_gaps": 0, "critical_unknowns": 0, "needs_review": 0, "research_completion": 1 / 59}

    def quality_tally(self, review_id):
        return 7


def _provider():
    return Provider(pd.DataFrame([
        {
            "ticker": "DGC", "period": "2025", "period_type": "Y",
            "cash_and_short_investments_bil": 9500.0,
            "total_assets_bil": 18000.0,
            "total_equity_bil": 14500.0,
            "interest_bearing_debt_bil": 1200.0,
            "source_module": "module1_normalized_cache",
            "data_origin": "fireant_normalized",
        },
        {
            "ticker": "DGC", "period": "2026 TTM", "period_type": "TTM",
            "cash_and_short_investments_bil": 10200.0,
            "total_assets_bil": 19500.0,
            "total_equity_bil": 15500.0,
            "interest_bearing_debt_bil": 900.0,
            "source_module": "module1_normalized_cache",
            "data_origin": "fireant_normalized",
        },
    ]))


def test_v99_financial_evidence_has_full_source_traceability():
    rows = extract_question_financial_evidence(_provider(), "Q25")
    assert rows
    debt = next(row for row in rows if row["metric_code"] == "debt" and row["source_period"] == "2026 TTM")
    assert debt["value"] == 900.0
    assert debt["source_field"] == "interest_bearing_debt_bil"
    assert debt["source_module"] == "module1_normalized_cache"
    assert debt["source_period"] == "2026 TTM"
    assert debt["data_origin"] == "fireant_normalized"


def test_v99_missing_canonical_evidence_is_explicit_and_never_zero_filled():
    provider = Provider(pd.DataFrame([{"ticker": "DGC", "period": "2026 TTM", "period_type": "TTM"}]))
    rows = extract_question_financial_evidence(provider, "Q32")
    assert len(rows) == 1
    assert rows[0]["evidence_status"] == "missing"
    assert rows[0]["value"] is None
    assert rows[0]["value_display"] == MISSING_STANDARDIZED_DATA


def test_v99_report_payload_preserves_analyst_judgment_exactly():
    repo = FakeRepo()
    before = deepcopy(repo.assessment)
    payload = build_investment_checklist_report_payload(repo, 1, 9, data_provider=_provider())
    q25 = next(q for group in payload["groups"] for q in group["questions"] if q["question_id"] == "Q25")
    assert q25["assessment"] == before
    assert q25["assessment"]["assessment"] == -1
    assert q25["assessment"]["confidence"] == 4
    assert q25["assessment"]["analyst_answer"] == "Thanh khoản tốt nhưng cần theo dõi nợ vay."
    assert repo.assessment == before
    assert payload["governance"]["analyst_judgment_preserved"] is True


def test_v99_report_layer_has_no_parallel_financial_fetch_or_formula_engine():
    source = inspect.getsource(financial_service) + "\n" + inspect.getsource(report_service)
    forbidden = (
        "requests.get(", "httpx.get(", "urllib.request", "_fetch_source(",
        "module1_engine", "module2_engine", "build_module2_valuation_table", "append_ttm_row",
    )
    assert not any(token in source for token in forbidden)
    assert "annual_df" in inspect.getsource(financial_service)
    assert "Trecapital Data Layer" in source


def test_v99_docx_contains_analyst_assessment_source_trace_and_missing_marker():
    repo = FakeRepo()
    payload = build_investment_checklist_report_payload(repo, 1, 9, data_provider=_provider())
    blob = build_investment_checklist_docx(payload)
    assert blob[:2] == b"PK"
    with ZipFile(BytesIO(blob)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Thanh khoản tốt nhưng cần theo dõi nợ vay." in xml
    assert "interest_bearing_debt_bil" in xml
    assert "2026 TTM" in xml
    # Q32 has no direct CFO/Capex/FCF field in the fixture; missing stays explicit.
    assert MISSING_STANDARDIZED_DATA in xml
