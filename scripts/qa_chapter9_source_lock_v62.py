from __future__ import annotations

"""Deterministic acceptance for Chapter 9 Phase 9A / V62 source lock."""

import json
from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)

EXPECTED_TITLES = {
    "Q48": "Does the CEO love the money or the business?",
    "Q49": "Can you identify a moment of integrity for the manager?",
    "Q50": "Are managers clear and consistent in their communications and actions with stakeholders?",
    "Q51": "Does management think independently and remain unswayed by what others in their industry are doing?",
    "Q52": "Is the CEO self-promoting?",
}


def main() -> int:
    assert ch9.CHAPTER_NUMBER == 9
    assert ch9.CHAPTER_TITLE == "Assessing the Quality of Management—Positive and Negative Traits"
    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    assert ch9.QUESTION_TITLES == EXPECTED_TITLES
    assert ch9.QUESTION_SOURCE_PAGES == {"Q48": 256, "Q49": 264, "Q50": 268, "Q51": 275, "Q52": 276}
    assert len(ch9.Q48_PASSION_RESEARCH_PROMPTS) == 6
    assert ch9.MANAGER_IDENTITY_SSOT == "Chapter 7 manager master"

    payload = ch9.empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    assert set(payload["question_status"].values()) == {"Unknown"}
    assert set(payload["confidence"].values()) == {"Unknown"}
    assert set(payload["analyst_assessment"].values()) == {"Unknown"}

    output = {
        "phase": "Chapter 9 Phase 9A Source Lock V62",
        "acceptance": "PASS",
        "chapter": ch9.CHAPTER_NUMBER,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "source_locked_questions": len(ch9.QUESTION_KEYS),
        "exact_question_range": "Q48-Q52",
        "question_pages": ch9.QUESTION_SOURCE_PAGES,
        "q48_source_locked_passion_prompts": len(ch9.Q48_PASSION_RESEARCH_PROMPTS),
        "manager_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "unknown_first": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "analyst_workspace_mutated": False,
        "ui_or_db_added": False,
        "web_research_added": False,
        "financial_bridge_added": False,
        "mos_or_research_gate_changed": False,
        "research_note": (
            "Phase 9A locks Michael Shearn Chapter 9 Q48-Q52 and neutral evidence schemas only. "
            "Chapter 7 remains manager-identity SSOT; no score, investment signal, UI, database, web research, "
            "financial bridge, MOS or Research Gate behavior is introduced."
        ),
    }
    path = REPORTS / "CH9_PHASE9A_SOURCE_LOCK_V62.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
