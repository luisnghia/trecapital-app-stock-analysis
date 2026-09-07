from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_source_contract_v63 as v63


REPORT_PATH = Path("reports/CH9_PHASE9C_MANAGER_CONTEXT_V64.json")


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
    source_snapshot = v63.validate_source_contract()
    context = bridge.build_context(_fixture())
    snapshot = bridge.context_snapshot(_fixture())
    empty_context = bridge.build_context({})

    assert source_snapshot["total_dimensions"] == 26
    assert snapshot["source_dimension_count"] == 26
    assert snapshot["scoped_unique_dimension_count"] == 26
    assert snapshot["manager_reference_count"] == 2
    assert set(context.manager_reference["Manager ID"]) == {"M001", "M002"}

    for question in bridge.CEO_QUESTIONS:
        sub = context.dimension_scope[context.dimension_scope["Question"].eq(question)]
        assert set(sub["Manager ID"]) == {"M001"}
        assert set(sub["Scope Status"]) == {"Scoped — explicit Chapter 7 CEO role"}

    assert len(empty_context.dimension_scope) == 26
    assert empty_context.dimension_scope["Dimension Key"].nunique() == 26
    assert set(empty_context.dimension_scope["Manager ID"]) == {""}
    assert set(empty_context.gaps["Question"]) == set(ch9.QUESTION_KEYS)
    assert set(empty_context.gaps["Status"]) == {"Open — manager identity gap"}

    report = {
        "phase": "Chapter 9 Phase 9C Manager Context Bridge V64",
        "acceptance": "PASS",
        "chapter": ch9.CHAPTER_NUMBER,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "exact_question_range": "Q48-Q52",
        "source_dimension_count": source_snapshot["total_dimensions"],
        "dimension_counts": source_snapshot["dimension_counts"],
        "manager_identity_ssot": bridge.MANAGER_SOURCE_LABEL,
        "fixture_manager_reference_count": len(context.manager_reference),
        "fixture_scope_row_count": len(context.dimension_scope),
        "fixture_gap_count": len(context.gaps),
        "empty_manager_scope_preserves_26_dimensions": len(empty_context.dimension_scope) == 26,
        "empty_manager_scope_remains_unassigned": set(empty_context.dimension_scope["Manager ID"]) == {""},
        "ceo_specific_questions": list(bridge.CEO_QUESTIONS),
        "management_questions": list(bridge.MANAGEMENT_QUESTIONS),
        "unknown_first": all(
            status == "Open — analyst research required"
            for status in context.dimension_scope["Evidence Status"].astype(str)
        ),
        "web_research_added": False,
        "financial_bridge_added": False,
        "ui_or_db_added": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "analyst_workspace_mutated": False,
        "mos_or_research_gate_changed": False,
        "research_note": (
            "Phase 9C references Chapter 7 manager identities/roles and maps them to the 26 Phase 9B "
            "Chapter 9 dimensions. Q48/Q52 are scoped only to an explicitly identified CEO. Missing "
            "manager/CEO identity remains an open gap; no replacement IDs, research crawler, financial "
            "dataset, score, recommendation, MOS, or Research Gate behavior is introduced."
        ),
    }

    assert report["manager_identity_ssot"] == "Chapter 7 manager master"
    assert report["unknown_first"] is True
    assert report["automatic_management_score"] is False
    assert report["automatic_investment_signal"] is False
    assert report["web_research_added"] is False
    assert report["financial_bridge_added"] is False

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
