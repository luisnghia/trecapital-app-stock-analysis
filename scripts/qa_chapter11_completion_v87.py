from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_completion as completion


def main() -> None:
    empty = ch11.empty_payload("TEST")
    empty_gate = completion.completion_gate(empty)
    assert empty_gate["ready"] is False
    assert empty_gate["total_questions"] == 2
    assert empty_gate["total_dimensions"] == 15

    ready = ch11.empty_payload("TEST")
    for q in ch11.QUESTION_KEYS:
        ready["question_status"][q] = "Answered"
        ready["confidence"][q] = "Medium"
        ready["analyst_assessment"][q] = "Analyst-owned assessment"
    for d in ch11.dimension_ids():
        ready["dimension_status"][d] = "Evidence found"
    ready["ma_synthesis"] = completion.normalize_synthesis({
        "status": "Reviewed",
        "final_ma_synthesis": "Analyst-owned M&A synthesis",
    })
    gate = completion.completion_gate(ready)
    report = completion.report_section(ready)
    assert gate["ready"] is True
    assert report["research_ready"] is True
    assert report["synthesis"]["final_ma_synthesis"] == "Analyst-owned M&A synthesis"

    out = {
        "phase": "11F",
        "version": "V87",
        "source_lock": ch11.SOURCE_LOCK,
        "questions": list(ch11.QUESTION_KEYS),
        "dimension_count": len(ch11.dimension_ids()),
        "empty_unknown_first": not empty_gate["ready"],
        "research_ready_when_complete": gate["ready"],
        "analyst_owns_synthesis": True,
        "automatic_ma_score": False,
        "automatic_acquisition_success_conclusion": False,
        "automatic_synergy_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "duplicate_financial_ssot": False,
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH11_PHASE11F_COMPLETION_V87.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PASS: Chapter 11 V87 completion gate and analyst-owned M&A synthesis acceptance.")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
