from __future__ import annotations

from copy import deepcopy
import json

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_history as hist
import modules.deep_company_analysis.chapter10_store as store

p = ch10.empty_payload("TEST", "Test Co")
p["question_status"]["Q53"] = "Answered"
p["confidence"]["Q53"] = "High"
p["analyst_assessment"]["Q53"] = "Mixed"
p["growth_mode"] = "Mixed"
p["growth_synthesis"] = {"final_growth_synthesis": "Analyst-owned synthesis"}
q = deepcopy(p)
q["growth_synthesis"]["final_growth_synthesis"] = "Changed analyst-owned synthesis"
summary = hist.history_summary(p, q)

assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
assert len(ch10.dimension_ids()) == 34
assert store.SCHEMA_VERSION == 2
assert summary["changed_fields"] >= 1
assert summary["historical_source_freshness_reconstructed"] is False
assert summary["automatic_growth_mode_change"] is False
assert summary["automatic_question_status_change"] is False
assert summary["automatic_confidence_change"] is False
assert summary["automatic_analyst_text_change"] is False
assert summary["automatic_growth_score"] is False
assert summary["automatic_growth_forecast"] is False
assert summary["automatic_investment_signal"] is False
assert summary["mos_or_investment_research_gate_changed"] is False

report = {
    "phase": "Chapter 10 Phase 10G Snapshot History V80",
    "acceptance": "PASS",
    "chapter": 10,
    "source_lock": ch10.SOURCE_LOCK,
    "question_range": ch10.SOURCE_QUESTION_RANGE,
    "evidence_dimensions": len(ch10.dimension_ids()),
    "schema_version": store.SCHEMA_VERSION,
    "immutable_snapshot_api": True,
    "neutral_delta_states": ["Unchanged", "Added", "Removed", "Changed"],
    **summary,
    "next_phase": "Phase 10H — integrate version lineage/history and explicit re-review controls into the Chapter 10 Streamlit report workflow, then close Chapter 10 if acceptance remains green.",
}
print(json.dumps(report, ensure_ascii=False, indent=2))
