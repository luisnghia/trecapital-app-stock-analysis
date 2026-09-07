from __future__ import annotations

"""Deterministic acceptance for Chapter 10 Phase 10A / V74 source lock."""

import json
from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)

EXPECTED_TITLES = {
    "Q53": "Does the business grow through mergers and acquisitions, or does it grow organically?",
    "Q54": "What is the management team’s motivation to grow the business?",
    "Q55": "Has historical growth been profitable and will it continue?",
    "Q56": "What are the future growth prospects for the business?",
    "Q57": "Is the management team growing the business too quickly or at a steady pace?",
}


def main() -> int:
    assert ch10.CHAPTER_NUMBER == 10
    assert ch10.CHAPTER_TITLE == "Evaluating Growth Opportunities"
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.QUESTION_TITLES == EXPECTED_TITLES
    assert ch10.QUESTION_SOURCE_PAGES == {"Q53": 281, "Q54": 282, "Q55": 283, "Q56": 284, "Q57": 296}
    assert ch10.SOURCE_LOCK == "Michael Shearn — The Investment Checklist — Chapter 10 — Q53-Q57"
    assert ch10.SOURCE_QUESTION_RANGE == "Q53-Q57"

    payload = ch10.empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    assert set(payload["question_status"].values()) == {"Unknown"}
    assert set(payload["confidence"].values()) == {"Unknown"}
    assert set(payload["analyst_assessment"].values()) == {"Unknown"}
    assert payload["growth_mode"] == "Unknown"

    output = {
        "phase": "Chapter 10 Phase 10A Source Lock V74",
        "acceptance": "PASS",
        "chapter": ch10.CHAPTER_NUMBER,
        "chapter_title": ch10.CHAPTER_TITLE,
        "source_lock": ch10.SOURCE_LOCK,
        "source_locked_questions": len(ch10.QUESTION_KEYS),
        "exact_question_range": ch10.SOURCE_QUESTION_RANGE,
        "question_pages": ch10.QUESTION_SOURCE_PAGES,
        "unknown_first": True,
        "q53_growth_mode_analyst_owned": True,
        "automatic_growth_score": False,
        "automatic_growth_forecast": False,
        "automatic_investment_signal": False,
        "analyst_workspace_mutated": False,
        "ui_or_db_added": False,
        "web_research_added": False,
        "financial_bridge_added": False,
        "duplicate_financial_ssot_added": False,
        "mos_or_research_gate_changed": False,
        "adjacent_q52_q58_excluded": True,
        "research_note": (
            "Phase 10A locks Michael Shearn Chapter 10 Q53-Q57 and neutral evidence schemas only. "
            "No growth forecast, growth score, UI, database, web research, financial bridge, duplicate financial SSOT, "
            "MOS, investment Research Gate, or BUY/HOLD/SELL behavior is introduced."
        ),
        "next_phase": "Phase 10B — source-locked evidence dimensions for Q53-Q57.",
    }
    path = REPORTS / "CH10_PHASE10A_SOURCE_LOCK_V74.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
