from __future__ import annotations

import inspect

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_research as research
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


def _chapter7_payload() -> dict:
    return {
        "ticker": "DGC",
        "management_profiles": [
            {
                "Manager ID": "M001",
                "Manager": "Nguyễn Văn A",
                "Current Role": "Tổng Giám đốc / CEO",
                "Analyst Classification": "Unknown",
                "Confidence": "High",
            },
            {
                "Manager ID": "M002",
                "Manager": "Trần Văn B",
                "Current Role": "CFO",
                "Analyst Classification": "Unknown",
                "Confidence": "Medium",
            },
        ],
    }


def _scope() -> pd.DataFrame:
    return bridge.build_context(_chapter7_payload()).dimension_scope


def test_phase9d_preserves_26_source_dimensions_and_analyst_boundary():
    assert research.QUESTION_ORDER == ch9.QUESTION_KEYS
    assert len(contract.all_dimensions()) == 26
    assert set(research.DIMENSION_TERMS) == {dim.key for dim in contract.all_dimensions()}
    assert "analyst verification/promotion required" in research.RESEARCH_BOUNDARY
    src = inspect.getsource(research).casefold()
    assert "no automatic management" in src
    assert "no score/rank" in src
    assert "no mos/research gate" in src
    assert "no buy/hold/sell" in src
    assert "analyst_assessment" not in src
    assert "import streamlit" not in src


def test_dimension_matcher_maps_source_locked_topics_without_creating_new_dimensions():
    q48 = research.matched_dimensions(
        "Q48",
        "The CEO discussed his career history, lifelong learning and continuous improvement program.",
    )
    assert "q48_career_vs_job" in q48
    assert "q48_lifelong_learning" in q48
    assert set(q48) <= {dim.key for dim in contract.QUESTION_DIMENSIONS["Q48"]}

    q52 = research.matched_dimensions(
        "Q52",
        "The CEO joined an investor conference roadshow after an equity issuance to finance expansion.",
    )
    assert "q52_wall_street_event_frequency" in q52
    assert "q52_financing_context" in q52
    assert set(q52) <= {dim.key for dim in contract.QUESTION_DIMENSIONS["Q52"]}


def test_search_classifier_rejects_generic_direct_source_link_and_keeps_candidate_status():
    raw = pd.DataFrame([
        {
            "Trạng thái": "Link nguồn ưu tiên",
            "Tiêu đề": "DGC - trang IR",
            "Trích yếu": "Nguồn ưu tiên để kiểm tra báo cáo thường niên.",
            "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/",
        },
        {
            "Trạng thái": "Tìm thấy",
            "Tiêu đề": "CEO DGC trao đổi tại hội nghị nhà đầu tư",
            "Trích yếu": "Nguyễn Văn A tham dự hội nghị nhà đầu tư và roadshow sau kế hoạch huy động vốn.",
            "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/roadshow",
        },
    ])
    out = research.classify_search_rows(raw, "DGC", "Q52", _scope())
    assert not out.empty
    assert set(out["Status"]) == {"Candidate — analyst verify"}
    assert set(out["Question"]) == {"Q52"}
    assert set(out["Manager ID"]) == {"M001"}
    assert all(out["Source Grade"].str.startswith("A —"))
    assert not out["Source Title"].str.contains("trang IR", case=False).any()


def test_ceo_specific_search_never_attaches_evidence_to_non_ceo_manager():
    raw = pd.DataFrame([
        {
            "Trạng thái": "Tìm thấy",
            "Tiêu đề": "Trần Văn B trả lời báo chí",
            "Trích yếu": "Trần Văn B xuất hiện trên truyền hình và nói về giá cổ phiếu.",
            "Nguồn/URL": "https://example.com/interview",
        }
    ])
    out = research.classify_search_rows(raw, "DGC", "Q52", _scope())
    assert not out.empty
    assert set(out["Manager ID"]) == {""}
    assert set(out["Manager"]) == {""}


def test_original_official_document_extraction_links_only_exact_chapter7_manager_name():
    documents = [{
        "url": "https://ducgiangchem.vn/quan-he-co-dong/thu-co-dong-2025",
        "title": "Thư cổ đông 2025",
        "method": "HTML text extraction",
        "text": (
            "Trong thư gửi cổ đông năm 2025, Nguyễn Văn A giải thích mô hình kinh doanh bằng ngôn ngữ rõ ràng. "
            "Ông cũng mô tả các vấn đề gặp phải và biện pháp khắc phục dài hạn."
        ),
    }]
    out = research.official_documents_to_candidates(documents, "DGC", _scope())
    assert not out.empty
    assert any(out["Dimension Key"].eq("q50_shareholder_letters"))
    assert any(out["Manager ID"].eq("M001"))
    assert all(out["Status"].eq("Candidate — analyst verify"))
    assert all(out["Explicitness"].str.startswith("Extracted original source text"))


def test_q52_financing_context_is_context_exception_cue_not_positive_or_negative_label():
    text = "The CEO attended a roadshow because the company planned an equity issuance and acquisition financing."
    cue = research.direction_cue("q52_financing_context", text)
    assert cue == "Context / exception cue — analyst assess"
    assert "supporting" not in cue.casefold()
    assert "counter" not in cue.casefold()


def test_direction_cues_remain_non_conclusive_sorting_aids():
    assert research.direction_cue("q49_integrity_moment", "Management accepted responsibility and acted transparently.") == "Supporting cue — analyst assess"
    assert research.direction_cue("q49_adversity_response_pattern", "Management blamed outsiders and used a quick fix after the crisis.") == "Counter-evidence cue — analyst assess"
    assert research.direction_cue("q50_shareholder_letters", "The annual report discusses market conditions.") == "Neutral / context — analyst assess"


def test_source_family_preserves_source_contract_families():
    assert research.source_family("Q48", "CEO interview profile", "https://example.com/profile") == "Published manager interview/profile"
    assert research.source_family("Q50", "shareholder letter 2025", "https://example.com/letter") == "Sequential shareholder letter"
    assert research.source_family("Q52", "investor conference roadshow", "https://example.com/event") == "Investor-relations conference calendar/event"


def test_quality_summary_is_26_dimension_coverage_table_not_management_score():
    candidates = pd.DataFrame([
        {
            **{c: "" for c in research.CANDIDATE_COLUMNS},
            "Question": "Q49",
            "Dimension Key": "q49_integrity_moment",
            "Dimension": "Integrity",
            "Manager ID": "M001",
            "Source Grade": "A — Company/Official disclosure",
            "Explicitness": "Extracted original source text — analyst verify context",
            "Direction": "Supporting cue — analyst assess",
        },
        {
            **{c: "" for c in research.CANDIDATE_COLUMNS},
            "Question": "Q49",
            "Dimension Key": "q49_integrity_moment",
            "Dimension": "Integrity",
            "Source Grade": "C — Secondary/context source",
            "Explicitness": "Search title/snippet candidate — analyst verify original source",
            "Direction": "Counter-evidence cue — analyst assess",
        },
    ])
    summary = research.evidence_quality_summary(candidates)
    assert len(summary) == 26
    row = summary[summary["Dimension Key"].eq("q49_integrity_moment")].iloc[0]
    assert row["Candidates"] == 2
    assert row["A — Official"] == 1
    assert row["Direct-source text"] == 1
    assert row["Manager-linked"] == 1
    assert row["Boundary"] == "Coverage only — not a management score"


def test_research_gaps_keep_missing_evidence_unknown_and_preserve_scope_gaps():
    empty = pd.DataFrame(columns=research.CANDIDATE_COLUMNS)
    context = bridge.build_context({})
    gaps = research.research_gaps(empty, context.dimension_scope, context.gaps)
    assert set(research.RESEARCH_GAP_COLUMNS) == set(gaps.columns)
    assert {dim.key for dim in contract.all_dimensions()} <= set(gaps["Dimension Key"])
    assert set(ch9.QUESTION_KEYS) <= set(gaps["Question"])
    assert any(gaps["Status"].eq("Open — manager identity gap"))
    text = " ".join(gaps["Research Gap"].astype(str).tolist() + gaps["Next Action"].astype(str).tolist()).casefold()
    assert "good management" not in text
    assert "bad management" not in text
    assert "replacement manager ids" in text


def test_ceo_candidate_without_exact_name_creates_manager_link_verification_gap():
    scope = _scope()
    candidate = {
        **{c: "" for c in research.CANDIDATE_COLUMNS},
        "Question": "Q52",
        "Dimension Key": "q52_media_touting",
        "Dimension": next(dim.label for dim in contract.all_dimensions() if dim.key == "q52_media_touting"),
        "Manager ID": "",
        "Manager": "",
        "Source Grade": "B — Independent financial source/research",
        "Explicitness": "Search title/snippet candidate — analyst verify original source",
        "Direction": "Neutral / context — analyst assess",
        "Status": "Candidate — analyst verify",
    }
    candidates = pd.DataFrame([candidate], columns=research.CANDIDATE_COLUMNS)
    gaps = research.research_gaps(candidates, scope, pd.DataFrame(columns=bridge.SCOPE_GAP_COLUMNS))
    q52 = gaps[gaps["Dimension Key"].eq("q52_media_touting")]
    assert any(q52["Status"].eq("Open — manager-link verification gap"))
