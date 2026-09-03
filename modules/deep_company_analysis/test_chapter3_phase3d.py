from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter3_auto import (
    build_chapter3_assistant_draft,
    evidence_quality_coverage,
    extract_concentration_candidates,
    research_gap_suggestions,
)


def row(group: str, snippet: str, *, score: int = 60, url: str = "https://example.com") -> dict:
    return {
        "Nhóm thông tin": group,
        "Tiêu đề": "Evidence",
        "Nguồn/URL": url,
        "Trích yếu": snippet,
        "Điểm phù hợp": score,
    }


def test_export_share_must_not_become_customer_concentration():
    df = pd.DataFrame([row(
        "Nguồn doanh nghiệp/IR | Q8",
        "Với 80% doanh thu đến từ xuất khẩu, công ty phục vụ thị trường trong và ngoài nước.",
    )])
    assert extract_concentration_candidates(df) == []
    quality = evidence_quality_coverage(df)
    assert quality["eligible_fields"]["Q8 Concentration evidence"] is False


def test_named_customers_without_revenue_share_are_evidence_but_not_concentration_metric():
    df = pd.DataFrame([row(
        "BCTC/PDF chính thức | Q8",
        "Các khoản phải thu khách hàng bao gồm Mitsubishi Corporation và ICL Specialty Products Inc.",
    )])
    assert extract_concentration_candidates(df) == []
    assert evidence_quality_coverage(df)["eligible_fields"]["Q8 Concentration evidence"] is False


def test_customer_support_evidence_counts_for_q11_without_auto_judgement():
    df = pd.DataFrame([row(
        "Nguồn doanh nghiệp/IR | Q11",
        "Mọi thắc mắc khách hàng liên hệ tổng đài tư vấn; công ty tiếp nhận và giải đáp thông tin cho khách hàng.",
        url="https://dgcmall.vn/lien-he",
    )])
    quality = evidence_quality_coverage(df)
    assert quality["eligible_fields"]["Q11 Customer-orientation evidence"] is True
    draft = build_chapter3_assistant_draft(df)
    assert draft["q11"]["customer_orientation_summary"]


def test_placeholder_links_do_not_inflate_quality_coverage():
    df = pd.DataFrame([row(
        "Nguồn công bố chính thức | Q14",
        "Nguồn ưu tiên để kiểm tra DGC: mở link để đối chiếu với dữ liệu trong app.",
    )])
    quality = evidence_quality_coverage(df)
    assert quality["eligible_fields"]["Q14 Replacement/disappearance evidence"] is False


def test_missing_metrics_generate_explicit_research_gaps():
    quality = evidence_quality_coverage(pd.DataFrame())
    gaps = research_gap_suggestions(quality)
    assert any(text.startswith("Q8") for text in gaps)
    assert any(text.startswith("Q10") for text in gaps)
    assert any("Profit Relevance" in text for text in gaps)
