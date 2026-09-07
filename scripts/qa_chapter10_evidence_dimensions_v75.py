from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10


def main() -> None:
    counts = ch10.dimension_count_by_question()
    catalog = ch10.dimension_catalog()
    assert ch10.CHAPTER_NUMBER == 10
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.QUESTION_SOURCE_PAGE_RANGES == {
        "Q53": (281, 282), "Q54": (282, 283), "Q55": (283, 284), "Q56": (284, 296), "Q57": (296, 303)
    }
    assert counts == {"Q53": 4, "Q54": 4, "Q55": 4, "Q56": 15, "Q57": 7}
    assert len(catalog) == 34
    assert len(set(ch10.dimension_ids())) == 34
    payload = ch10.empty_payload("TEST")
    assert set(payload["dimension_status"].values()) == {"Unknown"}

    source = Path(ch10.__file__).read_text(encoding="utf-8").casefold()
    assert "import streamlit" not in source
    assert "import httpx" not in source
    assert "import requests" not in source
    assert "import sqlite3" not in source
    assert "import psycopg" not in source
    assert "fireant" not in source
    assert "simplize" not in source
    assert "duplicate financial ssot" in source

    report = {
        "phase": "Chapter 10 Phase 10B Evidence Dimensions V75",
        "acceptance": "PASS",
        "chapter": 10,
        "chapter_title": ch10.CHAPTER_TITLE,
        "source_lock": ch10.SOURCE_LOCK,
        "exact_question_range": ch10.SOURCE_QUESTION_RANGE,
        "source_printed_page_range": "281-303",
        "question_page_ranges": {k: list(v) for k, v in ch10.QUESTION_SOURCE_PAGE_RANGES.items()},
        "dimension_count": len(catalog),
        "dimension_count_by_question": counts,
        "unknown_first": True,
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
        "ccc_calculated_in_phase10b": False,
        "next_phase": "Phase 10C — canonical data bridge and deterministic evidence extraction for source-supported quantitative dimensions.",
    }
    out = Path("reports/CH10_PHASE10B_EVIDENCE_DIMENSIONS_V75.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
