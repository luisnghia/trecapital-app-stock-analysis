from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_research as research

REPORT = Path("reports/CH11_PHASE11D_RESEARCH_V85.json")


def main() -> None:
    plan = research.research_plan("TEST", "Test Company", "example.com")
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.QUESTION_SOURCE_PAGES == {"Q58": 305, "Q59": 310}
    assert ch11.dimension_count_by_question() == {"Q58": 8, "Q59": 7}
    assert len(ch11.dimension_ids()) == 15
    assert len(plan) == 15
    assert set(plan["Dimension ID"]) == set(ch11.dimension_ids())

    records = [
        {
            "dimension_id": "q58_decision_process_and_rationale",
            "title": "Annual report",
            "url": "https://example.com/annual-report",
            "text": "Management discussed acquisition rationale, expected benefits, costs and risks.",
        },
        {
            "dimension_id": "q59_price_discipline_and_walkaway",
            "title": "Archived conference call",
            "url": "https://example.com/call",
            "text": "Management walked away from an acquisition after the price exceeded its limit.",
        },
    ]
    candidates = research.build_candidates(records, official_domain="example.com")
    assert len(candidates) == 2
    assert set(candidates["Source Grade"]) == {"A — Official"}
    gaps = research.research_gaps(candidates)
    assert len(gaps) == 13

    workspace = ch11.empty_payload("TEST", "Test Company")
    before = json.loads(json.dumps(workspace))
    selected = [str(candidates.iloc[0]["Candidate ID"])]
    promoted = research.promote_selected_candidates(workspace, candidates, selected)
    assert len(promoted["evidence"]) == 1
    assert promoted["question_status"] == before["question_status"]
    assert promoted["confidence"] == before["confidence"]
    assert promoted["analyst_assessment"] == before["analyst_assessment"]
    assert promoted["dimension_status"] == before["dimension_status"]

    summary = research.phase_summary()
    assert summary["automatic_ma_score"] is False
    assert summary["automatic_acquisition_success_conclusion"] is False
    assert summary["automatic_synergy_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_research_gate_changed"] is False
    assert summary["duplicate_financial_ssot_added"] is False

    report = {
        **summary,
        "source_lock": ch11.SOURCE_LOCK,
        "question_pages": ch11.QUESTION_SOURCE_PAGES,
        "dimension_count_by_question": ch11.dimension_count_by_question(),
        "candidate_columns": list(candidates.columns),
        "sample_candidate_count": len(candidates),
        "sample_open_gap_count": len(gaps),
        "explicit_promotion_preserves_analyst_fields": True,
        "acceptance": "PASS",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: Chapter 11 V85 Research Assistant covers Q58-Q59 / 15 source-locked dimensions and preserves analyst, SSOT and investment boundaries.")


if __name__ == "__main__":
    main()
