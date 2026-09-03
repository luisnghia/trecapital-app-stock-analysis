from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter4_evidence import (
    _candidate_rows,
    _official_topic_rows,
    candidate_coverage,
    evidence_quality_summary,
    guardrails,
    merge_candidates_into_evidence_matrix,
    research_gaps,
)


def _raw(focus: str, title: str, snippet: str, group: str = "Nguồn doanh nghiệp/IR", status: str = "Tìm thấy") -> pd.DataFrame:
    return pd.DataFrame([{
        "_Focus": focus,
        "Tiêu đề": title,
        "Nguồn/URL": "https://example.com/a",
        "Trích yếu": snippet,
        "Nhóm thông tin": group,
        "Truy vấn": "query",
        "Trạng thái": status,
    }])


def test_q15_brand_candidate_is_not_a_moat_conclusion():
    candidates = _candidate_rows(_raw("Q15_Q16", "Thương hiệu", "Doanh nghiệp nói thương hiệu dẫn đầu và khách hàng trung thành."))
    q15 = candidates[candidates["Question"].eq("Q15")]
    assert not q15.empty
    assert q15.iloc[0]["Subtopic"] == "Brand Loyalty"
    assert "analyst verify" in q15.iloc[0]["Explicitness"].lower()
    assert guardrails()["auto_moat_conclusion"] is False


def test_q16_requires_price_plus_customer_or_volume_for_explicit_candidate():
    only_price = _candidate_rows(_raw("Q15_Q16", "Tăng giá", "Công ty tăng giá bán 8%."))
    q16 = only_price[only_price["Question"].eq("Q16")]
    assert not q16.empty
    assert "insufficient" in q16.iloc[0]["Explicitness"].lower()

    explicit = _candidate_rows(_raw("Q15_Q16", "Tăng giá", "Công ty tăng giá bán 8% trong khi sản lượng và retention khách hàng ổn định."))
    q16b = explicit[explicit["Question"].eq("Q16")]
    assert "explicit price + customer/volume" in q16b.iloc[0]["Explicitness"].lower()


def test_q20_supplier_risk_is_counter_candidate_not_supplier_rating():
    candidates = _candidate_rows(_raw("Q20", "Nguồn cung", "Doanh nghiệp phụ thuộc nhà cung cấp chính và có rủi ro gián đoạn nguồn cung."))
    assert candidates.iloc[0]["Question"] == "Q20"
    assert str(candidates.iloc[0]["Direction"]).startswith("Contradicting")
    assert guardrails()["auto_supplier_quality_conclusion"] is False


def test_merge_only_appends_candidate_evidence_and_preserves_analyst_judgement():
    record = {
        "q15": {"sustainable_advantage": "Yes", "conclusion": "Analyst conclusion"},
        "q16": {"pricing_power": "Moderate"},
        "evidence_matrix": [],
    }
    candidates = pd.DataFrame([{
        "Question": "Q15",
        "Subtopic": "Cost Advantages — Scale / Location / Unique Asset",
        "Direction": "Supporting — Candidate",
        "Evidence Quality": "A — Company/Official disclosure",
        "Explicitness": "Candidate — analyst verify mechanism/copyability",
        "Title": "Nguồn nguyên liệu",
        "URL": "https://example.com/source",
        "Snippet": "Nguồn nguyên liệu tích hợp.",
        "Source Group": "Nguồn doanh nghiệp/IR",
        "Query": "q",
        "Focus": "Q15_Q16",
        "Source Method": "Official annual-report PDF direct extraction",
    }])
    merged = merge_candidates_into_evidence_matrix(record, candidates)
    assert merged["q15"]["sustainable_advantage"] == "Yes"
    assert merged["q15"]["conclusion"] == "Analyst conclusion"
    assert merged["q16"]["pricing_power"] == "Moderate"
    assert len(merged["evidence_matrix"]) == 1
    assert merged["evidence_matrix"][0]["Status"] == "Candidate — Analyst verify"
    assert "Phase 4C.1" in merged["evidence_matrix"][0]["Data Origin"]
    assert "Official annual-report PDF" in merged["evidence_matrix"][0]["Analyst Note"]


def test_candidate_coverage_counts_each_question():
    df = pd.DataFrame({"Question": ["Q15", "Q15", "Q19", "Q20"]})
    counts = candidate_coverage(df)
    assert counts["Q15"] == 2
    assert counts["Q16"] == 0
    assert counts["Q19"] == 1
    assert counts["Q20"] == 1


def test_phase4c_guardrails_locked():
    flags = guardrails()
    assert all(value is False for value in flags.values())


def test_direct_source_navigation_link_is_not_promoted_to_evidence():
    df = _raw("Q15_Q16", "DGC - trang IR", "Nguồn ưu tiên để kiểm tra lợi thế cạnh tranh.", status="Link nguồn ưu tiên")
    assert _candidate_rows(df).empty


def test_official_source_extraction_surfaces_q15_q20_and_keeps_them_candidate():
    text = """
    Công ty có lợi thế cạnh tranh nhờ tự chủ nguồn nguyên liệu apatit và quy mô sản xuất lớn.
    Nguồn cung lưu huỳnh nhập khẩu có thể biến động, gây rủi ro giá nguyên liệu và chuỗi cung ứng.
    """
    rows = _official_topic_rows(
        ticker="DGC",
        page_title="Báo cáo thường niên",
        url="https://example.com/annual.pdf",
        text=text,
        source_method="Official annual-report PDF direct extraction",
    )
    candidates = _candidate_rows(pd.DataFrame(rows))
    assert not candidates[candidates["Question"].eq("Q15")].empty
    assert not candidates[candidates["Question"].eq("Q20")].empty
    assert set(candidates["Evidence Quality"]) == {"A — Company/Official disclosure"}
    assert all("Candidate" in value for value in candidates["Direction"].astype(str))


def test_official_q16_still_requires_price_plus_reaction_in_same_context():
    text = """
    Năm 2025 công ty tăng giá bán bình quân 7% trong khi sản lượng tiêu thụ và nhu cầu khách hàng vẫn ổn định.
    """
    rows = _official_topic_rows(
        ticker="DGC",
        page_title="BCTN 2025",
        url="https://example.com/annual.pdf",
        text=text,
        source_method="Official annual-report PDF direct extraction",
    )
    candidates = _candidate_rows(pd.DataFrame(rows))
    q16 = candidates[candidates["Question"].eq("Q16")]
    assert not q16.empty
    assert q16.iloc[0]["Explicitness"] == "Explicit price + customer/volume candidate"


def test_evidence_quality_summary_marks_q16_thin_without_explicit_reaction():
    candidates = _candidate_rows(_raw("Q15_Q16", "Giá bán", "Doanh nghiệp tăng giá bán 5%."))
    summary = evidence_quality_summary(candidates)
    q16 = summary[summary["Question"].eq("Q16")].iloc[0]
    assert "Mỏng" in q16["Coverage Status"]
    assert q16["Q16 Explicit"] == 0
    gaps = research_gaps(candidates)
    assert any(item.startswith("Q16:") for item in gaps)


def test_evidence_quality_summary_recognizes_two_official_candidates_as_stronger_coverage():
    candidates = pd.DataFrame([
        {
            "Question": "Q20", "Evidence Quality": "A — Company/Official disclosure",
            "Direction": "Neutral — Candidate", "Explicitness": "Supplier/commodity candidate",
        },
        {
            "Question": "Q20", "Evidence Quality": "A — Company/Official disclosure",
            "Direction": "Contradicting — Candidate", "Explicitness": "Supplier/commodity candidate",
        },
    ])
    summary = evidence_quality_summary(candidates)
    q20 = summary[summary["Question"].eq("Q20")].iloc[0]
    assert q20["Nguồn A"] == 2
    assert str(q20["Coverage Status"]).startswith("Khá")
