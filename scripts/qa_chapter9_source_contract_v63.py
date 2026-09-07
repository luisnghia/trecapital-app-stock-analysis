from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as v63


REPORT_PATH = Path("reports/CH9_PHASE9B_SOURCE_CONTRACT_V63.json")


def main() -> int:
    snapshot = v63.validate_source_contract()
    report = {
        "phase": "Chapter 9 Phase 9B Source Contract V63",
        "acceptance": "PASS",
        **snapshot,
        "exact_question_range": "Q48-Q52",
        "q48_prompt_labels_match_phase9a": tuple(
            dim.label for dim in v63.QUESTION_DIMENSIONS["Q48"]
        )
        == ch9.Q48_PASSION_RESEARCH_PROMPTS,
        "q49_adversity_pattern_count": len(v63.Q49_ADVERSITY_RESPONSE_PATTERNS),
        "q50_shareholder_letter_element_count": len(v63.Q50_SHAREHOLDER_LETTER_ELEMENTS),
        "q50_communication_check_count": len(v63.Q50_COMMUNICATION_CHECKS),
        "q52_self_promoter_trait_count": len(v63.Q52_SELF_PROMOTER_TRAITS),
        "q52_wall_street_frequency_kept_as_text_context": "more than two to four times per month"
        in v63.Q52_WALL_STREET_EVENT_RED_FLAG_TEXT,
        "q52_financing_exception_preserved": "finance" in v63.Q52_FINANCING_CONTEXT_EXCEPTION.casefold(),
        "all_dimension_rows_unknown_first": all(
            row["Evidence Status"] == "Open — analyst research required"
            and not row["Supporting Evidence"]
            and not row["Counter-Evidence"]
            for row in v63.default_dimension_rows()
        ),
        "ui_or_db_added": False,
        "web_research_added": False,
        "financial_bridge_added": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "analyst_workspace_mutated": False,
        "mos_or_research_gate_changed": False,
        "research_note": (
            "Phase 9B source-locks 26 analyst-review dimensions across Q48-Q52. "
            "Exact prompts, named subsections, explicit trait lists, and source-paragraph dimensions are "
            "distinguished by origin. Red flags remain research cues rather than deterministic judgments; "
            "Chapter 7 remains manager-identity SSOT and no UI, database, web research, financial bridge, "
            "score, MOS, Research Gate, or investment signal is added."
        ),
    }
    assert report["q48_prompt_labels_match_phase9a"] is True
    assert report["q49_adversity_pattern_count"] == 5
    assert report["q50_shareholder_letter_element_count"] == 5
    assert report["q50_communication_check_count"] == 4
    assert report["q52_self_promoter_trait_count"] == 6
    assert report["q52_wall_street_frequency_kept_as_text_context"] is True
    assert report["q52_financing_exception_preserved"] is True
    assert report["all_dimension_rows_unknown_first"] is True
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
