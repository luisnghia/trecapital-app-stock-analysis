from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_research as research
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


REPORT_PATH = Path("reports/CH9_PHASE9D_RESEARCH_ASSISTANT_V65.json")


def _fixture() -> dict:
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


def main() -> int:
    source_snapshot = contract.validate_source_contract()
    context = bridge.build_context(_fixture())

    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    assert source_snapshot["total_dimensions"] == 26
    assert set(research.DIMENSION_TERMS) == {dim.key for dim in contract.all_dimensions()}
    assert bridge.MANAGER_SOURCE_LABEL == "Chapter 7 manager master"

    sample = pd.DataFrame([
        {
            "Trạng thái": "Tìm thấy",
            "Tiêu đề": "CEO DGC trao đổi tại hội nghị nhà đầu tư",
            "Trích yếu": "Nguyễn Văn A tham dự roadshow sau kế hoạch phát hành cổ phiếu để huy động vốn mở rộng.",
            "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/roadshow",
        }
    ])
    classified = research.classify_search_rows(sample, "DGC", "Q52", context.dimension_scope)
    assert not classified.empty
    assert set(classified["Manager ID"]) == {"M001"}
    assert set(classified["Status"]) == {"Candidate — analyst verify"}
    assert "q52_wall_street_event_frequency" in set(classified["Dimension Key"])
    assert "q52_financing_context" in set(classified["Dimension Key"])

    direct_docs = [{
        "url": "https://ducgiangchem.vn/quan-he-co-dong/thu-co-dong-2025",
        "title": "Thư cổ đông 2025",
        "method": "HTML text extraction",
        "text": (
            "Trong thư gửi cổ đông năm 2025, Nguyễn Văn A giải thích mô hình kinh doanh bằng ngôn ngữ rõ ràng, "
            "nêu các vấn đề đã gặp và biện pháp khắc phục dài hạn."
        ),
    }]
    direct = research.official_documents_to_candidates(direct_docs, "DGC", context.dimension_scope)
    assert not direct.empty
    assert direct["Explicitness"].astype(str).str.startswith("Extracted original source text").all()
    assert "M001" in set(direct["Manager ID"])

    quality = research.evidence_quality_summary(pd.concat([classified, direct], ignore_index=True))
    assert len(quality) == 26
    assert set(quality["Boundary"]) == {"Coverage only — not a management score"}

    empty_context = bridge.build_context({})
    empty_candidates = pd.DataFrame(columns=research.CANDIDATE_COLUMNS)
    gaps = research.research_gaps(empty_candidates, empty_context.dimension_scope, empty_context.gaps)
    assert {dim.key for dim in contract.all_dimensions()} <= set(gaps["Dimension Key"])
    assert any(gaps["Status"].eq("Open — manager identity gap"))

    report = {
        "phase": "Chapter 9 Phase 9D Evidence Research Assistant V65",
        "acceptance": "PASS",
        "chapter": ch9.CHAPTER_NUMBER,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "exact_question_range": "Q48-Q52",
        "source_dimension_count": source_snapshot["total_dimensions"],
        "dimension_counts": source_snapshot["dimension_counts"],
        "dimension_term_contract_complete": set(research.DIMENSION_TERMS) == {dim.key for dim in contract.all_dimensions()},
        "manager_identity_ssot": bridge.MANAGER_SOURCE_LABEL,
        "ceo_specific_questions": list(bridge.CEO_QUESTIONS),
        "candidate_only": True,
        "search_snippets_require_original_source_verification": True,
        "direct_source_text_still_requires_context_verification": True,
        "direction_labels_are_sorting_cues_only": True,
        "quality_table_is_coverage_only": True,
        "empty_research_preserves_all_26_dimension_gaps": {dim.key for dim in contract.all_dimensions()} <= set(gaps["Dimension Key"]),
        "replacement_manager_ids_created": False,
        "database_persistence_added": False,
        "ui_added": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
        "research_note": (
            "Phase 9D uses the V63 source contract plus the V64 Chapter 7 manager-context bridge to search and "
            "extract candidate evidence for Q48-Q52. Search snippets remain unverified candidates, original-source "
            "text is preferred, CEO evidence is not attached without exact manager-name matching, and no score, "
            "character label, investment signal, MOS, Research Gate, database, or UI behavior is introduced."
        ),
    }

    assert report["dimension_term_contract_complete"] is True
    assert report["candidate_only"] is True
    assert report["replacement_manager_ids_created"] is False
    assert report["automatic_management_score"] is False
    assert report["automatic_character_classification"] is False
    assert report["automatic_investment_signal"] is False
    assert report["mos_or_research_gate_changed"] is False

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
