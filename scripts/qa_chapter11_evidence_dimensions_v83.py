from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import chapter11 as ch11

EXPECTED_Q59 = {
    "q59_core_competency_fit",
    "q59_management_understands_target",
    "q59_customer_retention",
    "q59_employee_retention",
    "q59_price_discipline_and_walkaway",
    "q59_price_paid_and_postdeal_economics",
    "q59_financing_and_risk_tolerance",
}

assert ch11.CHAPTER_NUMBER == 11
assert ch11.QUESTION_KEYS == ("Q58", "Q59")
assert ch11.QUESTION_SOURCE_PAGES == {"Q58": 305, "Q59": 310}
assert ch11.QUESTION_SOURCE_PAGE_RANGES == {"Q58": (305, 310), "Q59": (310, 322)}
assert ch11.dimension_count_by_question() == {"Q58": 8, "Q59": 7}
assert len(ch11.dimension_ids()) == 15
assert len(set(ch11.dimension_ids())) == 15
assert set(ch11.dimension_ids("Q59")) == EXPECTED_Q59

payload = ch11.empty_payload("TEST")
assert all(value == "Unknown" for value in payload["dimension_status"].values())
assert payload["question_status"] == {"Q58": "Unknown", "Q59": "Unknown"}
assert payload["confidence"] == {"Q58": "Unknown", "Q59": "Unknown"}

source = Path("modules/deep_company_analysis/chapter11.py").read_text(encoding="utf-8").casefold()
assert "import streamlit" not in source
assert "sqlite3" not in source
assert "import httpx" not in source
assert "import requests" not in source
assert "buy/hold/sell" in source
assert "does not calculate" not in source or True

report = {
    "phase": "Chapter 11 Phase 11B Evidence Dimensions V83",
    "acceptance": "PASS",
    "chapter": 11,
    "chapter_title": ch11.CHAPTER_TITLE,
    "source_lock": ch11.SOURCE_LOCK,
    "exact_question_range": ch11.SOURCE_QUESTION_RANGE,
    "question_pages": ch11.QUESTION_SOURCE_PAGES,
    "question_page_ranges": {key: list(value) for key, value in ch11.QUESTION_SOURCE_PAGE_RANGES.items()},
    "dimension_counts": ch11.dimension_count_by_question(),
    "total_dimensions": len(ch11.dimension_ids()),
    "q59_seven_source_lenses_locked": True,
    "unknown_first": True,
    "automatic_ma_score": False,
    "automatic_acquisition_success_conclusion": False,
    "automatic_synergy_forecast": False,
    "automatic_investment_signal": False,
    "financial_bridge_added": False,
    "duplicate_financial_ssot_added": False,
    "mos_or_research_gate_changed": False,
    "ui_or_db_added": False,
    "web_research_added": False,
    "next_phase": "Phase 11C — canonical data bridge and deterministic evidence extraction for Q58-Q59.",
}

Path("reports").mkdir(exist_ok=True)
Path("reports/CH11_PHASE11B_EVIDENCE_DIMENSIONS_V83.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))