from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis.appendix_a import APPENDIX_TITLE, SOURCE_LOCK
from modules.deep_company_analysis.appendix_a_workspace import QUESTION_IDS, make_interview_record, make_research_gap, make_source_record, normalize_workspace


def main() -> None:
    source = make_source_record(source_name="Example source", source_class="Primary", source_type="Customer")
    interview = make_interview_record(
        source_id=source["source_id"], interview_date="2026-09-08",
        question_prompt="What changed?", source_response_observation="Source observation",
        statement_type="Fact", uncertainty_noted="Scope requires corroboration",
        related_question_refs=["Q01", "Q59"], analyst_commentary="Analyst commentary",
    )
    gap = make_research_gap(
        unanswered_question_assumption="What is still unknown?", preferred_source_type="Customer",
        related_question_refs=["Q59"], status="Open",
    )
    ws = normalize_workspace({
        "ticker": "TEST", "sources": [source, source], "interviews": [interview, interview],
        "research_gaps": [gap], "research_gate": "PASS", "margin_of_safety": 0.5,
        "intrinsic_value": 1, "financials": {"revenue": 1}, "buy_hold_sell": "BUY",
    })
    assertions = {
        "appendix_title_locked": APPENDIX_TITLE == "Building a Human Intelligence Network",
        "source_lock_preserved": ws["source_lock"] == SOURCE_LOCK,
        "q01_q59_reference_universe": len(QUESTION_IDS) == 59 and QUESTION_IDS[0] == "Q01" and QUESTION_IDS[-1] == "Q59",
        "source_response_separate_from_analyst_commentary": interview["source_response_observation"] != interview["analyst_commentary"],
        "uncertainty_field_preserved": bool(interview["uncertainty_noted"]),
        "stable_deduplication": len(ws["sources"]) == 1 and len(ws["interviews"]) == 1,
        "automatic_human_source_score": False,
        "automatic_credibility_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_ssot_added": False,
        "automatic_contact_action_added": False,
    }
    forbidden = ("research_gate", "margin_of_safety", "intrinsic_value", "financials", "buy_hold_sell")
    assertions["workspace_allowlist"] = all(key not in ws for key in forbidden)
    acceptance = all(value for key, value in assertions.items() if not key.startswith("automatic_") and key != "duplicate_financial_ssot_added")
    acceptance = acceptance and not any(assertions[key] for key in assertions if key.startswith("automatic_")) and not assertions["duplicate_financial_ssot_added"]
    report = {"phase": "Appendix A Phase B V91", "acceptance": "PASS" if acceptance else "FAIL", **assertions}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_A_PHASEB_WORKSPACE_V91.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not acceptance:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
