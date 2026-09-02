from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter3 import empty_payload
from modules.deep_company_analysis.chapter3_auto import (
    build_chapter3_assistant_draft,
    classify_evidence,
    extract_concentration_candidates,
    extract_retention_metrics,
    merge_assistant_draft,
)


def _evidence():
    return pd.DataFrame([
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q7",
            "Tiêu đề": "Khách hàng công nghiệp",
            "Nguồn/URL": "https://example.com/customers",
            "Trích yếu": "Sản phẩm được cung cấp cho khách hàng công nghiệp và nhà máy có yêu cầu kỹ thuật cao.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "BCTN/PDF chính thức của doanh nghiệp | Q8",
            "Tiêu đề": "Khách hàng lớn",
            "Nguồn/URL": "https://example.com/annual.pdf",
            "Trích yếu": "Khách hàng lớn nhất chiếm 18,5% doanh thu trong kỳ.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q9",
            "Tiêu đề": "Kênh bán hàng",
            "Nguồn/URL": "https://example.com/sales",
            "Trích yếu": "Doanh nghiệp bán hàng thông qua hợp đồng và hệ thống phân phối cho khách hàng công nghiệp.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "BCTN/PDF chính thức của doanh nghiệp | Q10",
            "Tiêu đề": "Customer retention",
            "Nguồn/URL": "https://example.com/retention.pdf",
            "Trích yếu": "Customer retention rate đạt 91,5% trong năm 2025.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q11",
            "Tiêu đề": "Phản hồi khách hàng",
            "Nguồn/URL": "https://example.com/service",
            "Trích yếu": "Công ty khảo sát mức độ hài lòng và xử lý phản hồi của khách hàng.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q12",
            "Tiêu đề": "Nhu cầu khách hàng",
            "Nguồn/URL": "https://example.com/usecase",
            "Trích yếu": "Giải pháp giúp khách hàng đáp ứng yêu cầu chất lượng nguyên liệu đầu vào cho sản xuất.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q13",
            "Tiêu đề": "Nguồn cung quan trọng",
            "Nguồn/URL": "https://example.com/dependency",
            "Trích yếu": "Khách hàng cần nguồn nguyên liệu đạt chuẩn và phải đánh giá nhà cung cấp thay thế.",
            "Điểm phù hợp": 60,
        },
        {
            "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q14",
            "Tiêu đề": "Nhà cung cấp thay thế",
            "Nguồn/URL": "https://example.com/switching",
            "Trích yếu": "Việc thay thế nguồn cung có thể cần thời gian đánh giá qualified supplier và gây gián đoạn.",
            "Điểm phù hợp": 60,
        },
    ])


def test_chapter3_evidence_is_classified_across_q7_q14():
    sections = classify_evidence(_evidence())
    assert set(sections) == {"Q7", "Q8", "Q9", "Q10", "Q11", "Q12", "Q13", "Q14"}
    assert all(not sections[q].empty for q in sections)


def test_retention_metric_requires_trusted_explicit_metric():
    metrics = extract_retention_metrics(_evidence())
    assert metrics["retention_rate"] == "91.5%"
    assert metrics["churn_rate"] == ""

    noisy = pd.DataFrame([{
        "Nhóm thông tin": "Tin tham khảo | Q10",
        "Tiêu đề": "Retention tips",
        "Nguồn/URL": "https://random.example.com",
        "Trích yếu": "Retention rate 99% là ví dụ chung, không liên quan doanh nghiệp.",
        "Điểm phù hợp": 5,
    }])
    assert extract_retention_metrics(noisy) == {}


def test_customer_concentration_needs_explicit_percent_and_trusted_source():
    rows = extract_concentration_candidates(_evidence())
    assert rows and rows[0]["Revenue share %"] == "18.5"

    vague = pd.DataFrame([{
        "Nhóm thông tin": "Nguồn doanh nghiệp/IR | Q8",
        "Tiêu đề": "Khách hàng đa dạng",
        "Nguồn/URL": "https://example.com",
        "Trích yếu": "Công ty phục vụ nhiều khách hàng ở nhiều ngành.",
        "Điểm phù hợp": 60,
    }])
    assert extract_concentration_candidates(vague) == []


def test_merge_fills_blank_evidence_fields_but_preserves_analyst_judgement():
    draft = build_chapter3_assistant_draft(_evidence())
    record = empty_payload("TST", "Test Co")
    record["q8"]["concentration_status"] = "Diversified"
    record["q9"]["sales_ease_status"] = "Hard"
    record["q13"]["dependency_class"] = "Nice to have, but not critical"
    record["q14"]["impact_level"] = "Low"
    record["q14"]["disappearance_conclusion"] = "Analyst conclusion"
    record["q11"]["customer_orientation_summary"] = "Analyst text must stay."

    merged = merge_assistant_draft(record, draft)
    assert merged["q7"]["core_customer_summary"]
    assert merged["q8"]["concentration_table"]
    assert merged["q10"]["retention_rate"] == "91.5%"
    assert merged["q10"]["retention_assessability"] == "Disclosed metric"
    assert merged["q11"]["customer_orientation_summary"] == "Analyst text must stay."
    assert merged["q8"]["concentration_status"] == "Diversified"
    assert merged["q9"]["sales_ease_status"] == "Hard"
    assert merged["q13"]["dependency_class"] == "Nice to have, but not critical"
    assert merged["q14"]["impact_level"] == "Low"
    assert merged["q14"]["disappearance_conclusion"] == "Analyst conclusion"


def test_draft_does_not_invent_retention_or_analyst_classifications_when_absent():
    evidence = _evidence().query("`Nhóm thông tin` != 'BCTN/PDF chính thức của doanh nghiệp | Q10'")
    draft = build_chapter3_assistant_draft(evidence)
    record = empty_payload("TST", "Test Co")
    merged = merge_assistant_draft(record, draft)
    assert merged["q10"]["retention_rate"] == ""
    assert merged["q10"]["retention_assessability"] == "Unknown"
    assert merged["q8"]["concentration_status"] == "Unknown"
    assert merged["q9"]["sales_ease_status"] == "Unknown"
    assert merged["q13"]["dependency_class"] == "Unknown"
    assert merged["q14"]["impact_level"] == "Unknown"
