from __future__ import annotations

import inspect

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter8_research as r


def _manager_reference() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Manager ID": "M001",
            "Manager": "Đào Hữu Duy Anh",
            "Current Role": "CEO",
            "Analyst Classification": "Unknown",
            "Chapter 7 Confidence": "High",
            "Source": "Chapter 7 manager master",
        }
    ])


def test_phase8c_is_q39_q47_evidence_only_and_preserves_analyst_boundary():
    assert r.QUESTION_ORDER == ch8.QUESTION_KEYS
    assert "analyst verification/promotion required" in r.RESEARCH_BOUNDARY
    src = inspect.getsource(r).casefold()
    assert "no management score" in src
    assert "no automatic competence conclusion" in src
    assert "no buy/hold/sell" in src
    assert "analyst_assessment" not in src


def test_source_grading_prioritizes_registered_company_and_regulator_sources():
    assert r.source_grade_from_url("https://ducgiangchem.vn/quan-he-co-dong/", "DGC").startswith("A —")
    assert r.source_grade_from_url("https://www.hsx.vn/Modules/Listed/Web/Symbols", "DGC").startswith("A —")
    assert r.source_grade_from_url("https://finance.vietstock.vn/DGC", "DGC").startswith("B —")
    assert r.source_grade_from_url("https://example.com/article", "DGC").startswith("C —")


def test_search_classifier_does_not_treat_generic_direct_source_link_as_evidence():
    raw = pd.DataFrame([
        {
            "Trạng thái": "Link nguồn ưu tiên",
            "Tiêu đề": "DGC - trang IR/quan hệ cổ đông doanh nghiệp",
            "Trích yếu": "Nguồn ưu tiên để kiểm tra BCTN/CBTT.",
            "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/",
        },
        {
            "Trạng thái": "Tìm thấy",
            "Tiêu đề": "DGC công bố kế hoạch lợi nhuận năm 2026",
            "Trích yếu": "Doanh nghiệp công bố kế hoạch lợi nhuận và chỉ tiêu kinh doanh năm 2026.",
            "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/ke-hoach-2026",
        },
    ])
    out = r.classify_search_rows(raw, "DGC", "Q41", _manager_reference())
    assert len(out) == 1
    assert out.iloc[0]["Question"] == "Q41"
    assert out.iloc[0]["Source Grade"].startswith("A —")
    assert out.iloc[0]["Status"] == "Candidate — analyst verify"


def test_official_text_extraction_maps_manager_id_only_from_chapter7_reference():
    documents = [{
        "url": "https://ducgiangchem.vn/quan-he-co-dong/bo-nhiem",
        "title": "Thông tin bổ nhiệm",
        "method": "HTML text extraction",
        "text": (
            "Ông Đào Hữu Duy Anh được bổ nhiệm Tổng Giám đốc. "
            "Công ty tiếp tục chương trình đào tạo nhân viên và phát triển lãnh đạo nội bộ."
        ),
    }]
    out = r.official_documents_to_candidates(documents, "DGC", _manager_reference())
    assert not out.empty
    scoped = out[out["Manager"].eq("Đào Hữu Duy Anh")]
    assert not scoped.empty
    assert set(scoped["Manager ID"]) == {"M001"}
    assert all(scoped["Status"].eq("Candidate — analyst verify"))


def test_official_text_without_chapter7_manager_reference_never_invents_manager_id():
    documents = [{
        "url": "https://ducgiangchem.vn/quan-he-co-dong/bo-nhiem",
        "title": "Thông tin bổ nhiệm",
        "method": "HTML text extraction",
        "text": "Ông Đào Hữu Duy Anh được bổ nhiệm Tổng Giám đốc và phụ trách tuyển dụng nhân tài.",
    }]
    out = r.official_documents_to_candidates(documents, "DGC", pd.DataFrame())
    assert not out.empty
    assert set(out["Manager ID"]) == {""}
    assert set(out["Manager"]) == {""}


def test_q47_requires_explicit_buyback_language_not_share_count_decline():
    no_buyback = [{
        "url": "https://ducgiangchem.vn/report",
        "title": "Annual report",
        "method": "PDF text extraction (no OCR)",
        "text": "Shares outstanding declined from 100 million to 95 million during 2025.",
    }]
    assert r.official_documents_to_candidates(no_buyback, "DGC", _manager_reference()).query("Question == 'Q47'").empty

    explicit = [{
        "url": "https://ducgiangchem.vn/cbtt-buyback",
        "title": "Phương án mua lại cổ phiếu",
        "method": "HTML text extraction",
        "text": "HĐQT phê duyệt phương án mua lại cổ phiếu và công bố giá mua lại dự kiến.",
    }]
    q47 = r.official_documents_to_candidates(explicit, "DGC", _manager_reference())
    assert not q47[q47["Question"].eq("Q47")].empty


def test_q46_subtopics_preserve_exact_five_shearn_uses_and_do_not_add_debt_bucket():
    labels = [label for label, _ in r.SUBTOPICS["Q46"]]
    for action in ch8.CAPITAL_ALLOCATION_ACTIONS:
        assert action in labels
    assert not any("debt" in label.casefold() for label in labels)


def test_quality_summary_is_coverage_only_not_management_score():
    candidates = pd.DataFrame([
        {**{c: "" for c in r.CANDIDATE_COLUMNS}, "Question": "Q43", "Source Grade": "A — Company/Official disclosure", "Direction": "Supporting cue — analyst assess"},
        {**{c: "" for c in r.CANDIDATE_COLUMNS}, "Question": "Q43", "Source Grade": "B — Independent financial source/research", "Direction": "Counter-evidence cue — analyst assess"},
    ])
    summary = r.evidence_quality_summary(candidates)
    q43 = summary[summary["Question"].eq("Q43")].iloc[0]
    assert q43["Candidates"] == 2
    assert q43["A — Official"] == 1
    assert q43["B — Independent"] == 1
    assert q43["Boundary"] == "Coverage only — not a management score"


def test_research_gaps_keep_unknown_and_manager_identity_gap_without_fabrication():
    candidates = pd.DataFrame(columns=r.CANDIDATE_COLUMNS)
    gaps = r.research_gaps(candidates, pd.DataFrame())
    assert set(ch8.RESEARCH_GAP_COLUMNS) == set(gaps.columns)
    assert set(ch8.QUESTION_KEYS) <= set(gaps["Question"])
    assert any(gaps["Status"].eq("Open — manager identity gap"))
    text = " ".join(gaps["Research Gap"].astype(str)).casefold()
    assert "replacement manager ids" in text
    assert "good management" not in text
    assert "bad management" not in text
