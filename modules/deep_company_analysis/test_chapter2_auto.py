from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter2 import empty_payload
from modules.deep_company_analysis.chapter2_auto import (
    build_chapter2_assistant_draft,
    build_financial_economics,
    extract_foreign_market_candidates,
    extract_timeline_candidates,
    merge_assistant_draft,
)


class DummyCompany:
    company_name = "CTCP Test"
    industry = "Hóa chất"


def _annual():
    return pd.DataFrame([
        {
            "period": "2025",
            "period_type": "Y",
            "year": 2025,
            "revenue_bil": 10000.0,
            "gross_profit_bil": 3000.0,
            "ebit_bil": 2000.0,
            "cfo_bil": 1800.0,
            "capex_bil": -600.0,
            "free_cash_flow_bil": 1200.0,
            "net_profit_bil": 1500.0,
        },
        {
            "period": "TTM",
            "period_type": "TTM",
            "year": 2026,
            "revenue_bil": 11000.0,
            "gross_profit_bil": 3080.0,
            "ebit_bil": 1980.0,
            "cfo_bil": 1900.0,
            "capex_bil": -660.0,
            "free_cash_flow_bil": 1240.0,
            "net_profit_bil": 1480.0,
        },
    ])


def _evidence():
    return pd.DataFrame([
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR",
            "Tiêu đề": "Công ty mở rộng nhà máy năm 2024",
            "Nguồn/URL": "https://example.com/history",
            "Trích yếu": "Năm 2024 doanh nghiệp mở rộng công suất nhà máy để phục vụ nhu cầu xuất khẩu.",
        },
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR",
            "Tiêu đề": "Thị trường xuất khẩu Thái Lan",
            "Nguồn/URL": "https://example.com/thailand",
            "Trích yếu": "Doanh thu tại Thái Lan chiếm 12,5% doanh thu và công ty bắt đầu từ năm 2019.",
        },
        {
            "Nhóm thông tin": "BCTN",
            "Tiêu đề": "Cơ cấu sản phẩm và phân phối",
            "Nguồn/URL": "https://example.com/products",
            "Trích yếu": "Doanh nghiệp sản xuất sản phẩm hóa chất và phân phối qua khách hàng công nghiệp.",
        },
        {
            "Nhóm thông tin": "BCTC",
            "Tiêu đề": "Ngoại tệ USD",
            "Nguồn/URL": "https://example.com/fx",
            "Trích yếu": "Doanh nghiệp có doanh thu xuất khẩu bằng USD và theo dõi rủi ro tỷ giá.",
        },
    ])


def test_financial_economics_prefers_ttm_and_calculates_margins():
    metrics = build_financial_economics(_annual())
    assert metrics["period"] == "TTM"
    assert metrics["revenue_bil"] == 11000.0
    assert round(metrics["gross_margin_pct"], 1) == 28.0
    assert round(metrics["ebit_margin_pct"], 1) == 18.0
    assert round(metrics["capex_revenue_pct"], 1) == 6.0
    assert metrics["fcf_bil"] == 1240.0


def test_timeline_and_foreign_market_candidates_are_evidence_grounded():
    evidence = _evidence()
    timeline = extract_timeline_candidates(evidence)
    assert any(row["Year"] == "2024" and row["Type"] == "New Capacity" for row in timeline)

    foreign = extract_foreign_market_candidates(evidence)
    thailand = next(row for row in foreign if row["Country / Region"] == "Thái Lan")
    assert thailand["Entry year"] == "2019"
    assert thailand["Revenue share %"] == "12.5"
    assert "example.com/thailand" in thailand["Evidence"]


def test_company_name_duc_giang_is_not_misclassified_as_germany():
    evidence = pd.DataFrame([
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q6",
            "Tiêu đề": "DGC — Giới thiệu doanh nghiệp",
            "Nguồn/URL": "https://ducgiangchem.vn/gioi-thieu/",
            "Trích yếu": "Tập đoàn Hóa chất Đức Giang đáp ứng yêu cầu khách hàng trong và ngoài nước.",
        }
    ])
    foreign = extract_foreign_market_candidates(evidence)
    assert not any(row["Country / Region"] == "Đức" for row in foreign)


def test_assistant_draft_and_merge_never_overwrite_analyst_or_fill_shearn_judgement_fields():
    draft = build_chapter2_assistant_draft(DummyCompany(), _annual(), _evidence(), source_label="test canonical")
    assert draft["q4"]["money_summary"]
    assert draft["q5"]["evolution"]
    assert draft["q6"]["foreign_markets"]

    record = empty_payload("TST", "CTCP Test")
    record["q3"]["own_words"] = "Đây là phần analyst tự viết."
    record["q4"]["money_summary"] = "Analyst money engine."
    record["q5"]["skill_vs_luck"] = "Analyst skill-vs-luck."
    merged = merge_assistant_draft(record, draft)

    assert merged["q3"]["own_words"] == "Đây là phần analyst tự viết."
    assert merged["q4"]["money_summary"] == "Analyst money engine."
    assert merged["q5"]["skill_vs_luck"] == "Analyst skill-vs-luck."
    assert merged["q5"]["evolution"]
    assert merged["q6"]["foreign_markets"]
    assert merged["assistant_provenance"]["source_label"] == "test canonical"


def test_blank_q4_gets_quantitative_draft_but_q1_q2_remain_analyst_only():
    draft = build_chapter2_assistant_draft(DummyCompany(), _annual(), _evidence())
    record = empty_payload("TST", "CTCP Test")
    merged = merge_assistant_draft(record, draft)
    assert "financial economics context" in merged["q4"]["money_summary"]
    assert merged["q1"] == record["q1"]
    assert merged["q2"] == record["q2"]
    assert merged["q3"]["own_words"] == ""
    assert merged["q5"]["skill_vs_luck"] == ""

def test_currency_evidence_rejects_eur_substring_noise_and_requires_fx_context():
    from modules.deep_company_analysis.chapter2_auto import extract_currency_candidates

    noisy = pd.DataFrame([{
        "Nhóm thông tin": "Tin tham khảo | Q6",
        "Tiêu đề": "Impossible de voir les messages Instagram",
        "Nguồn/URL": "https://forums.example.com/instagram",
        "Trích yếu": "Le forum reste accessible plusieurs heures pour les utilisateurs.",
        "Điểm phù hợp": 8,
    }])
    assert extract_currency_candidates(noisy) == []


def test_currency_evidence_accepts_explicit_currency_in_official_fx_context():
    from modules.deep_company_analysis.chapter2_auto import extract_currency_candidates

    official = pd.DataFrame([{
        "Nhóm thông tin": "BCTN/PDF chính thức của doanh nghiệp | Q6",
        "Tiêu đề": "Rủi ro ngoại tệ",
        "Nguồn/URL": "https://example.com/annual-report.pdf",
        "Trích yếu": "Doanh thu xuất khẩu được thanh toán bằng USD; doanh nghiệp theo dõi rủi ro tỷ giá.",
        "Điểm phù hợp": 0,
    }])
    rows = extract_currency_candidates(official)
    assert rows and rows[0]["Currency"] == "USD"
