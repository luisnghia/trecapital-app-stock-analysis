import json
from dataclasses import dataclass

import pandas as pd

from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.trecapital_bridge import CurrentRepoDataProvider
from modules.investment_checklist.trecapital_debt_enricher import augment_debt_from_latest_fireant_raw


@dataclass
class Company:
    ticker: str
    market_cap_bil: float
    current_price: float
    shares_outstanding_mil: float | None = None


def test_synthetic_zero_debt_is_unknown_not_debt_free():
    d = pd.DataFrame([{
        "ticker": "AAA", "period": "2026 TTM", "period_type": "Y", "year": 2026,
        "interest_bearing_debt_bil": 0.0, "operating_profit_bil": 100.0,
        "pretax_profit_bil": 90.0, "free_cash_flow_bil": 50.0,
    }])
    x = CurrentRepoDataProvider(Company("AAA", 5000.0, 20000.0), d).get_inventory_source_data(None)
    assert x.total_debt is None
    assert x.tev is None
    assert any("Chưa có cấu phần nợ vay" in note for note in x.source_notes)


def test_debt_components_are_used_and_zero_fill_is_ignored():
    d = pd.DataFrame([{
        "ticker": "AAA", "period": "2026 TTM", "period_type": "Y", "year": 2026,
        "interest_bearing_debt_bil": 0.0,
        "short_term_debt_bil": 1200.0, "long_term_debt_bil": 800.0,
        "cash_equivalents_bil": 500.0, "short_term_investments_bil": 300.0,
        "operating_profit_bil": 1000.0, "ebitda_bil": 1200.0, "pretax_profit_bil": 900.0,
        "free_cash_flow_bil": 400.0,
    }])
    x = CurrentRepoDataProvider(Company("AAA", 5000.0, 20000.0), d).get_inventory_source_data(None)
    assert x.total_debt == 2000.0
    assert x.tev == 6200.0  # 5,000 market cap + (2,000 debt - 800 cash/ST investments)


def test_ccc_uses_shearn_average_balance_proxy_and_history_contains_ttm():
    d = pd.DataFrame([
        {"ticker":"AAA","period":"2025","period_type":"Y","year":2025,"revenue_bil":10000.0,"gross_profit_bil":3000.0,
         "inventory_bil":1000.0,"accounts_receivable_bil":800.0,"accounts_payable_bil":600.0,"shares_outstanding_mil":500.0,
         "year_end_price":18000.0,"short_term_debt_bil":500.0,"long_term_debt_bil":500.0,"cash_equivalents_bil":300.0,
         "operating_profit_bil":1200.0,"ebitda_bil":1400.0,"pretax_profit_bil":1100.0,"free_cash_flow_bil":700.0,"interest_paid_bil":-80.0},
        {"ticker":"AAA","period":"2026 TTM","period_type":"Y","year":2026,"revenue_bil":12000.0,"gross_profit_bil":3600.0,
         "inventory_bil":1200.0,"accounts_receivable_bil":900.0,"accounts_payable_bil":700.0,"shares_outstanding_mil":500.0,
         "short_term_debt_bil":550.0,"long_term_debt_bil":450.0,"cash_equivalents_bil":400.0,
         "operating_profit_bil":1300.0,"ebitda_bil":1500.0,"pretax_profit_bil":1200.0,"free_cash_flow_bil":750.0,"interest_paid_bil":-85.0},
    ])
    provider = CurrentRepoDataProvider(Company("AAA", 10000.0, 20000.0, 500.0), d)
    x = provider.get_inventory_source_data(None)
    # DIO=(1100/8400)*365, DSO=(850/12000)*365, DPO=(650/8400)*365
    expected = (1100.0 / 8400.0 + 850.0 / 12000.0 - 650.0 / 8400.0) * 365.0
    assert abs(x.ccc_days - expected) < 0.01
    hist = provider.get_inventory_proxy_history(10)
    assert any(r["source_type"] == "TTM" and r["ccc_days"] is not None for r in hist)
    assert any(r["period"] == "2025" for r in hist)


def test_fireant_raw_debt_enricher_reads_borrowing_lines_without_network(tmp_path):
    raw = {
        "responses": [{
            "url": "https://www.fireant.vn/api/Data/Finance/LastestFinancialReports?symbol=AAA&type=1&year=2026&quarter=0&count=12",
            "body": json.dumps([
                {"ID": 99901, "Name": "Vay và nợ thuê tài chính ngắn hạn", "Values": [{"Year": 2025, "Quarter": 0, "Value": 1_200_000_000_000}]},
                {"ID": 99902, "Name": "Vay và nợ thuê tài chính dài hạn", "Values": [{"Year": 2025, "Quarter": 0, "Value": 800_000_000_000}]},
            ], ensure_ascii=False),
        }]
    }
    (tmp_path / "fireant_excel_vba_AAA_999.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    annual = pd.DataFrame([{"ticker":"AAA","period_type":"Y","period":"2025","year":2025}])
    quarterly = pd.DataFrame()
    a, q, note = augment_debt_from_latest_fireant_raw(annual, quarterly, "AAA", tmp_path)
    assert float(a.iloc[0]["short_term_debt_bil"]) == 1200.0
    assert float(a.iloc[0]["long_term_debt_bil"]) == 800.0
    assert float(a.iloc[0]["interest_bearing_debt_bil"]) == 2000.0
    assert "Debt được bổ sung" in note


def test_ccc_persists_and_table11_has_review_history(tmp_path):
    catalog = "modules/investment_checklist/catalog/question_catalog_prd.csv"
    repo = SQLiteChecklistRepository(tmp_path / "checklist.db", catalog)
    repo.initialize()
    cid = repo.upsert_company_ref(host_company_key="T:AAA", ticker="AAA", company_name="AAA Corp")
    r1 = repo.create_review(cid, "2025-12-31")
    repo.save_screening(review_id=r1, criterion_code="Q1", analyst_value="yes", confidence=4)
    repo.save_inventory_snapshot(company_ref_id=cid, as_of_date="2025-12-31", review_id=r1, ccc_days=42.0, tev=1000.0, ebit=100.0)
    hist = repo.inventory_history(cid)
    assert hist[0]["ccc_days"] == 42.0
    matrix = repo.screening_history_matrix(cid)
    assert len(matrix) == 1 and matrix[0]["Total ✓"] == 1
