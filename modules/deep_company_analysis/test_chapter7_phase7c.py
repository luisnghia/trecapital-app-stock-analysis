from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis import chapter7 as ch7
from modules.deep_company_analysis import chapter7_research as r


def _candidate(cid: str = "c1") -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Select": True,
            "Candidate ID": cid,
            "Question": "Q37",
            "Manager": "Nguyen Van A",
            "Subtopic": "Actual ownership",
            "Direction": "Neutral / context — analyst assess",
            "Source Grade": "A — Company/Official disclosure",
            "Explicitness": "Explicit title/snippet candidate",
            "Source Title": "Annual report 2025",
            "Source URL / File": "https://example.com/ar.pdf",
            "Source Date": "2026-03-01",
            "As-of Date": "2025",
            "Evidence Text / Reference": "Nguyen Van A holds 1,000,000 shares.",
            "Source Method": "Phase 7C focused web research",
            "Data Origin": "External research candidate — analyst verification required",
            "Status": "Candidate — analyst verify",
        }
    ])


def test_phase7c_boundary_is_explicit_and_non_conclusive():
    contract = r.RESEARCH_BOUNDARY.lower()
    assert "no automatic" in contract
    assert "lion/hyena" in contract
    assert "management quality" in contract
    assert "buy/sell signal" in contract
    assert "research gate" in contract


def test_source_grading_prefers_official_and_financial_sources():
    official = {"Tên miền": "hsx.vn", "Nhóm thông tin": "Nguồn công bố chính thức"}
    finance = {"Tên miền": "vietstock.vn", "Nhóm thông tin": "Dữ liệu/tin tài chính"}
    context = {"Tên miền": "example.org", "Nhóm thông tin": "Tin tham khảo"}
    assert r.source_grade(official, "ABC").startswith("A —")
    assert r.source_grade(finance, "ABC").startswith("B —")
    assert r.source_grade(context, "ABC").startswith("C —")


def test_query_text_is_not_silently_promoted_as_evidence():
    raw = pd.DataFrame([
        {
            "Nhóm thông tin": "Tin tham khảo",
            "Tiêu đề": "Unrelated result",
            "Nguồn/URL": "https://example.org/x",
            "Tên miền": "example.org",
            "Trích yếu": "Unrelated market context only.",
            "Trạng thái": "Tìm thấy",
            "Truy vấn": "CEO chairman founder ownership appointment biography",
        }
    ])
    out = r.classify_search_rows(raw, "ABC", "Q33", ["Nguyen Van A"])
    assert out.empty


def test_official_direct_link_is_source_lead_not_extracted_fact():
    raw = pd.DataFrame([
        {
            "Nhóm thông tin": "Nguồn công bố chính thức",
            "Tiêu đề": "ABC - official disclosure search",
            "Nguồn/URL": "https://hsx.vn/official",
            "Tên miền": "hsx.vn",
            "Trích yếu": "Official source starting point.",
            "Trạng thái": "Link nguồn ưu tiên",
        }
    ])
    out = r.classify_search_rows(raw, "ABC", "Q38", [])
    assert len(out) == 1
    assert out.iloc[0]["Explicitness"] == "Source lead — open/verify"
    assert out.iloc[0]["Source Grade"].startswith("A —")


def test_research_gaps_cover_all_q33_q38_and_identity_gap():
    gaps = r.research_gaps(pd.DataFrame(columns=r.CANDIDATE_COLUMNS), managers=[])
    assert set(r.QUESTION_ORDER).issubset(set(gaps["Question"]))
    assert (gaps["Status"] == "Open — identity gap").any()


def test_promote_selected_evidence_preserves_analyst_owned_conclusions():
    payload = ch7.empty_payload("ABC", "ABC Co")
    payload["management_profiles"] = [{"Manager ID": "M1", "Manager": "Nguyen Van A"}]
    payload["q33"]["analyst_classification"] = "LT1"
    payload["q35"]["overall_classification"] = "Lion"
    payload["q38"]["insider_behavior"] = "Neutral"
    payload["final_management_classification"] = "LT1"
    payload["analyst_summary"] = "Analyst-owned conclusion"

    before = {
        "q33": payload["q33"].copy(),
        "q35": payload["q35"].copy(),
        "q38": payload["q38"].copy(),
        "final": payload["final_management_classification"],
        "summary": payload["analyst_summary"],
    }
    updated, stats = r.promote_candidates_into_record(payload, _candidate(), ["c1"])
    assert stats["promoted"] == 1
    assert updated["evidence_matrix"][0]["Manager ID"] == "M1"
    assert updated["q33"] == before["q33"]
    assert updated["q35"] == before["q35"]
    assert updated["q38"] == before["q38"]
    assert updated["final_management_classification"] == before["final"]
    assert updated["analyst_summary"] == before["summary"]


def test_promote_is_deduplicated():
    payload = ch7.empty_payload("ABC")
    once, stats1 = r.promote_candidates_into_record(payload, _candidate(), ["c1"])
    twice, stats2 = r.promote_candidates_into_record(once, _candidate(), ["c1"])
    assert stats1["promoted"] == 1
    assert stats2["promoted"] == 0
    assert stats2["duplicates"] == 1
    assert len(twice["evidence_matrix"]) == 1


def test_deep_extract_keeps_source_text_as_candidate(monkeypatch):
    candidates = _candidate()
    monkeypatch.setattr(
        r,
        "fetch_document_text",
        lambda url: (
            "Nguyen Van A was appointed chief executive in 2024. The annual report states long-term employee development and customer focus.",
            "PDF text extraction (no OCR)",
        ),
    )
    deep = r.deep_extract_candidates(candidates, ["c1"], managers=["Nguyen Van A"])
    assert not deep.empty
    assert deep.iloc[0]["Status"] == "Candidate — analyst verify"
    assert "deep extraction" in deep.iloc[0]["Source Method"].lower()
    assert deep.iloc[0]["Manager"] == "Nguyen Van A"


def test_page_support_integrates_phase7c_without_completion_gate():
    from pathlib import Path
    page = Path(__file__).with_name("chapter7_page_support.py").read_text(encoding="utf-8")
    assert "render_chapter7_research_assistant" in page
    assert "Phase 7A+7B+7C" in page
    assert "Final source-closure vẫn thuộc Phase 7D" in page
