from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter4_evidence_c3 as c3
from modules.deep_company_analysis.chapter4_evidence_c2 import Phase4C2Result


def _q19_row(subtopic: str, snippet: str, url: str = "https://example.com/a", quality: str = "B — Independent financial source"):
    return {
        "Question": "Q19",
        "Subtopic": subtopic,
        "Direction": "Neutral — Candidate",
        "Evidence Quality": quality,
        "Explicitness": "Competitor-intelligence candidate — analyst verify relevance/root cause",
        "Period Candidate": "2025",
        "Title": "Industry evidence",
        "URL": url,
        "Snippet": snippet,
        "Source Group": "Dữ liệu/tin tài chính",
        "Source Method": "test",
    }


def _pricing_row(url: str, quality: str, explicit: bool = True, commodity: bool = False):
    return {
        "Question": "Q16",
        "Subtopic": "Actual Pricing / Customer Response",
        "Direction": "Neutral — Candidate",
        "Evidence Quality": quality,
        "Explicitness": "Explicit price + customer/volume candidate" if explicit else "Price mention only — insufficient for Pricing Power",
        "Event Type Candidate": "Price + reaction with commodity/cost context — analyst separate pass-through from Pricing Power" if commodity else "Price + customer/volume response candidate — analyst verify",
        "Period Candidate": "2025",
        "Title": "Pricing evidence",
        "URL": url,
        "Snippet": "Giá bán tăng trong khi sản lượng và nhu cầu khách hàng vẫn tăng.",
        "Source Group": "",
        "Source Method": "test",
    }


def test_multilabel_classification_keeps_all_supported_shearn_buckets():
    labels = c3.q19_multilabel_subtopics(
        "Cạnh tranh giá gay gắt do dư cung công suất và đối thủ Trung Quốc mở rộng nhà máy; một nhà sản xuất rút lui."
    )
    assert "Limited / Direct Competition" in labels
    assert "How Competitors Compete" in labels
    assert "Fierceness / Price Competition" in labels
    assert "Low-cost Country Competition" in labels
    assert "Industry Change / Capacity Competition" in labels
    assert "Why Competitors Failed" in labels


def test_expand_q19_multilabel_removes_first_match_limitation():
    frame = pd.DataFrame([
        _q19_row(
            "Low-cost Country Competition",
            "Đối thủ Trung Quốc mở rộng công suất và cạnh tranh giá khiến một nhà máy phải đóng cửa.",
        )
    ])
    expanded = c3.expand_q19_multilabel(frame)
    assert set(expanded["Subtopic"]) >= {
        "Limited / Direct Competition",
        "How Competitors Compete",
        "Fierceness / Price Competition",
        "Low-cost Country Competition",
        "Industry Change / Capacity Competition",
        "Why Competitors Failed",
    }


def test_q19_coverage_matrix_never_hides_gaps():
    q19 = pd.DataFrame([
        _q19_row("Substitute Products", "Sản phẩm thay thế có giá thấp hơn."),
        _q19_row("Low-cost Country Competition", "Nhập khẩu từ Trung Quốc.", "https://other.com/b"),
    ])
    coverage = c3.q19_coverage_matrix(q19)
    assert len(coverage) == len(c3.SHEARN_Q19_SUBTOPICS)
    assert int(coverage["Candidates"].sum()) == 2
    assert (coverage["Coverage"] == "Gap").any()


def test_q16_corroboration_requires_two_domains_and_independent_source():
    pricing = pd.DataFrame([
        _pricing_row("https://company.vn/a", "A — Company/Official disclosure", commodity=True),
        _pricing_row("https://research.vn/b", "B — Independent financial source"),
    ])
    matrix = c3.q16_corroboration_matrix(pricing)
    assert len(matrix) == 1
    row = matrix.iloc[0]
    assert int(row["Distinct domains"]) == 2
    assert int(row["Independent candidates"]) == 1
    assert str(row["Corroboration status"]).startswith("Period-level corroboration")
    assert int(row["Commodity/pass-through candidates"]) == 1


def test_q16_price_only_never_becomes_corroboration():
    pricing = pd.DataFrame([
        _pricing_row("https://company.vn/a", "A — Company/Official disclosure", explicit=False),
        _pricing_row("https://research.vn/b", "B — Independent financial source", explicit=False),
    ])
    matrix = c3.q16_corroboration_matrix(pricing)
    assert matrix.empty


def test_merge_preserves_analyst_fields_and_marks_candidate():
    record = {
        "ticker": "DGC",
        "q19_assessment": "Analyst-owned conclusion",
        "research_gate": "Watch",
        "evidence_matrix": [],
    }
    candidate = pd.DataFrame([_q19_row("Why Competitors Failed", "Một đối thủ đóng cửa do sai lầm vận hành.")])
    out = c3.merge_c3_candidates_into_evidence_matrix(record, candidate)
    assert out["q19_assessment"] == "Analyst-owned conclusion"
    assert out["research_gate"] == "Watch"
    assert out["evidence_matrix"][0]["Status"] == "Candidate — Analyst verify"
    assert "Phase 4C.3" in out["evidence_matrix"][0]["Data Origin"]


def test_engine_closes_only_supported_gaps_and_keeps_unknowns(monkeypatch, tmp_path):
    base_q19 = pd.DataFrame([
        _q19_row("Substitute Products", "Substitute sản phẩm thay thế có thể gây mất thị phần."),
        _q19_row("Low-cost Country Competition", "Cạnh tranh nhập khẩu từ Trung Quốc."),
    ])
    base_pricing = pd.DataFrame([
        _pricing_row("https://company.vn/a", "A — Company/Official disclosure"),
    ])
    base = Phase4C2Result(
        pricing_candidates=base_pricing,
        competitor_universe=pd.DataFrame(),
        competitor_evidence=base_q19,
        combined_candidates=pd.DataFrame(),
        note="baseline",
        audit={},
    )

    monkeypatch.setattr(c3, "_targeted_q16_reaction_search", lambda *a, **k: (
        pd.DataFrame([_pricing_row("https://research.vn/b", "B — Independent financial source")]), []
    ))
    monkeypatch.setattr(c3, "_registered_gap_rows", lambda *a, **k: (pd.DataFrame(), []))
    monkeypatch.setattr(c3, "_targeted_q19_search", lambda *a, **k: (
        pd.DataFrame([
            _q19_row("Fierceness / Price Competition", "Cạnh tranh giá gay gắt và dư cung.", "https://industry.vn/c"),
        ]), []
    ))

    result = c3.Phase4C3Engine(tmp_path).search("DGC", "Duc Giang", "Hóa chất", pd.DataFrame(), baseline=base)
    assert not result.pricing_corroboration.empty
    assert result.pricing_corroboration.iloc[0]["Corroboration status"].startswith("Period-level corroboration")
    assert "Fierceness / Price Competition" in set(result.q19_evidence["Subtopic"])
    assert any("Q19" in gap for gap in result.gaps)


def test_guardrails_are_all_false():
    assert c3.guardrails()
    assert all(value is False for value in c3.guardrails().values())
