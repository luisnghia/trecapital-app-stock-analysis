from copy import deepcopy

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_completion as c10c


def _complete_payload():
    p = ch10.empty_payload("AAA")
    for q in ch10.QUESTION_KEYS:
        p["question_status"][q] = "Answered"
        p["confidence"][q] = "Medium"
        p["analyst_assessment"][q] = f"Analyst conclusion for {q}"
    for d in ch10.dimension_ids():
        p["dimension_status"][d] = "Evidence found"
    return p


def test_gate_unknown_first_blocks_completion():
    gate = c10c.completion_gate(ch10.empty_payload("AAA"))
    assert gate["ready"] is False
    assert gate["total_questions"] == 5
    assert gate["total_dimensions"] == 34
    assert len(gate["blockers"]) == 5


def test_gate_ready_only_when_all_research_requirements_resolved():
    gate = c10c.completion_gate(_complete_payload())
    assert gate["ready"] is True
    assert gate["resolved_dimensions"] == 34
    assert all(v["ready"] for v in gate["questions"].values())


def test_one_unknown_dimension_blocks_only_its_question():
    p = _complete_payload()
    dim = ch10.dimension_ids("Q56")[0]
    p["dimension_status"][dim] = "Unknown"
    gate = c10c.completion_gate(p)
    assert gate["ready"] is False
    assert gate["questions"]["Q56"]["ready"] is False
    assert dim in gate["questions"]["Q56"]["unresolved_dimensions"]


def test_completion_does_not_mutate_analyst_workspace():
    p = _complete_payload()
    before = deepcopy(p)
    c10c.completion_gate(p)
    assert p == before


def test_synthesis_is_analyst_owned_and_normalized():
    s = c10c.normalize_synthesis({"status": "Final", "final_growth_synthesis": "Analyst text"})
    assert s["status"] == "Final"
    assert s["final_growth_synthesis"] == "Analyst text"
    assert c10c.normalize_synthesis({"status": "BUY"})["status"] == "Unknown"


def test_attach_synthesis_does_not_change_question_conclusions():
    p = _complete_payload()
    before = deepcopy(p["analyst_assessment"])
    out = c10c.attach_synthesis(p, {"status": "Draft", "final_growth_synthesis": "Draft"})
    assert out["analyst_assessment"] == before
    assert out["growth_synthesis"]["status"] == "Draft"


def test_report_is_neutral_research_summary():
    p = _complete_payload()
    p = c10c.attach_synthesis(p, {"status": "Reviewed", "final_growth_synthesis": "Neutral analyst synthesis"})
    report = c10c.report_section(p)
    assert report["research_ready"] is True
    assert len(report["questions"]) == 5
    assert "Growth Score" in report["boundary_note"]
    assert "BUY/HOLD/SELL" in report["boundary_note"]


def test_source_lock_and_question_range_unchanged():
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.SOURCE_QUESTION_RANGE == "Q53-Q57"
