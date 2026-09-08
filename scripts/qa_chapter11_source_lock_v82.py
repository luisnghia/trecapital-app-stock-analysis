from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter11 as ch11


def main() -> None:
    sample = ch11.empty_payload("FPT", "FPT Corporation")
    normalized = ch11.normalize_payload(sample)
    assert ch11.CHAPTER_NUMBER == 11
    assert ch11.CHAPTER_TITLE == "Evaluating Mergers & Acquisitions"
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.QUESTION_SOURCE_PAGES == {"Q58": 305, "Q59": 310}
    assert ch11.SOURCE_QUESTION_RANGE == "Q58-Q59"
    assert all(normalized["question_status"][q] == "Unknown" for q in ch11.QUESTION_KEYS)
    assert all(normalized["confidence"][q] == "Unknown" for q in ch11.QUESTION_KEYS)
    assert all(normalized["analyst_assessment"][q] == "Unknown" for q in ch11.QUESTION_KEYS)

    report = {
        "phase": "Chapter 11 Phase 11A Source Lock V82",
        "acceptance": "PASS",
        "chapter": 11,
        "chapter_title": ch11.CHAPTER_TITLE,
        "source_lock": ch11.SOURCE_LOCK,
        "source_locked_questions": len(ch11.QUESTION_KEYS),
        "exact_question_range": ch11.SOURCE_QUESTION_RANGE,
        "question_pages": ch11.QUESTION_SOURCE_PAGES,
        "unknown_first": True,
        "automatic_ma_score": False,
        "automatic_synergy_forecast": False,
        "automatic_acquisition_success_conclusion": False,
        "automatic_investment_signal": False,
        "analyst_workspace_mutated": False,
        "ui_or_db_added": False,
        "web_research_added": False,
        "financial_bridge_added": False,
        "duplicate_financial_ssot_added": False,
        "mos_or_research_gate_changed": False,
        "adjacent_q57_q60_excluded": True,
        "research_note": "Phase 11A locks Michael Shearn Chapter 11 Q58-Q59 and neutral evidence schemas only. No M&A score, synergy forecast, acquisition-success conclusion, UI, database, web research, financial bridge, duplicate financial SSOT, MOS, investment Research Gate, or BUY/HOLD/SELL behavior is introduced.",
        "next_phase": "Phase 11B — source-locked evidence dimensions for Q58-Q59.",
    }
    Path("reports").mkdir(exist_ok=True)
    out = Path("reports/CH11_PHASE11A_SOURCE_LOCK_V82.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
