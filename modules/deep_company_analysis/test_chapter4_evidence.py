from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter4_evidence import (
    _candidate_rows,
    candidate_coverage,
    guardrails,
    merge_candidates_into_evidence_matrix,
)


def _raw(focus: str, title: str, snippet: str, group: str = "Nguồn doanh nghiệp/IR") -> pd.DataFrame:
    return pd.DataFrame([{
        "_Focus": focus,
        "Tiêu đề": title,
        "Nguồn/URL": "https://example.com/a",
        "Trích yếu": snippet,
        "Nhóm thông tin": group,
        "Truy vấn": "query",
        "Trạng thái": "Tìm thấy",
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
    }])
    merged = merge_candidates_into_evidence_matrix(record, candidates)
    assert merged["q15"]["sustainable_advantage"] == "Yes"
    assert merged["q15"]["conclusion"] == "Analyst conclusion"
    assert merged["q16"]["pricing_power"] == "Moderate"
    assert len(merged["evidence_matrix"]) == 1
    assert merged["evidence_matrix"][0]["Status"] == "Candidate — Analyst verify"


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
    df = _raw("Q15_Q16", "DGC - trang IR", "Nguồn ưu tiên để kiểm tra lợi thế cạnh tranh.")
    df.loc[:, "Trạng thái"] = "Link nguồn ưu tiên"
    assert _candidate_rows(df).empty
