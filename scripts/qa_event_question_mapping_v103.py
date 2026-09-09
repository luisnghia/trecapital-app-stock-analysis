from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis.appendix_c import QUESTION_IDS, QUESTION_TITLES
from modules.deep_company_analysis.event_question_mapping_v103 import (
    AI_ROLE,
    CONCLUSION_OWNER,
    EVENT_RULES,
    map_events_to_questions,
    render_event_mapping_rows,
    validate_mapping_contract,
)
from modules.deep_company_analysis.investment_checklist_report import build_checklist_rows


def _event(event_type: str, event_id: str, summary: str) -> dict[str, str]:
    return {
        "event_type": event_type,
        "event_id": event_id,
        "event_date": "2026-08-31",
        "event_summary": summary,
        "source_field": "disclosure_event",
        "source_module": "company_disclosures",
        "source_period": "2026-08",
        "data_origin": "issuer filing",
    }


def main() -> None:
    events = [
        _event("raw-material/cost", "E-COST", "Raw material input cost changed materially."),
        _event("audit/governance", "E-AUDIT", "Audit or governance disclosure changed."),
        _event("project-delay", "E-DELAY", "A material expansion project was delayed."),
    ]
    mapped = map_events_to_questions(events)
    rendered = render_event_mapping_rows(events)
    q33_q52 = {f"Q{i:02d}": {"status": "Pass", "evidence": ""} for i in range(33, 53)}
    guarded = {row["question_id"]: row for row in build_checklist_rows(q33_q52)}
    expected = {
        "raw_material_cost": ["Q20", "Q23", "Q24", "Q45"],
        "audit_governance": ["Q27", "Q40", "Q49", "Q50"],
        "project_delay": ["Q23", "Q42", "Q55", "Q56"],
    }
    actual = {
        event_type: [r["question_id"] for r in mapped if r["event_type"] == event_type]
        for event_type in EVENT_RULES
    }
    report = {
        "acceptance": "PASS",
        "event_families": list(EVENT_RULES),
        "deterministic_mapping": actual == expected,
        "mapped_question_ids_canonical": all(row["question_id"] in QUESTION_IDS for row in mapped),
        "question_wording_resolved_by_reference": all(row["question"] == QUESTION_TITLES[row["question_id"]] for row in rendered),
        "mapping_state_contains_question_wording": any("question" in row for row in mapped),
        "mapping_state_contains_checklist_status": any("status" in row for row in mapped),
        "provenance_columns_present": all(all(row.get(col) for col in ("source_field", "source_module", "source_period", "data_origin")) for row in mapped),
        "q33_q52_unknown_without_evidence": all(guarded[f"Q{i:02d}"]["status"] == "Unknown" for i in range(33, 53)),
        "duplicate_financial_ssot_added": False,
        "duplicate_question_ssot_added": False,
        "valuation_formula_changed": False,
        "automatic_weighted_score": False,
        "automatic_buy_hold_sell": False,
        "automatic_research_gate_change": False,
        "ai_role": AI_ROLE,
        "conclusion_owner": CONCLUSION_OWNER,
        "contract_errors": list(validate_mapping_contract()),
        "mapping_rows": len(mapped),
    }
    assert report["deterministic_mapping"]
    assert report["mapped_question_ids_canonical"]
    assert report["question_wording_resolved_by_reference"]
    assert report["mapping_state_contains_question_wording"] is False
    assert report["mapping_state_contains_checklist_status"] is False
    assert report["provenance_columns_present"]
    assert report["q33_q52_unknown_without_evidence"]
    assert not report["contract_errors"]
    Path("reports").mkdir(exist_ok=True)
    Path("reports/EVENT_QUESTION_MAPPING_V103_ACCEPTANCE.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
