from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modules.deep_company_analysis.appendix_b import MANAGEMENT_INTERVIEW_TOPICS, SOURCE_PRINT_PAGES
from modules.deep_company_analysis.appendix_b_history import compare_versions, history_summary, source_baseline_fingerprint
from modules.deep_company_analysis.appendix_b_store import create_snapshot, list_snapshots, record_re_review
from modules.deep_company_analysis.appendix_b_workspace import new_research_gap, new_session


def main() -> None:
    session = new_session("QA", "CEO", "2026-09-08", "QA Company")
    session["topic_entries"][0]["management_response_observation"] = "Prior operating decision described by management."
    session["topic_entries"][0]["past_behavior_evidence"] = "Analyst-recorded past behavior evidence."
    session["topic_entries"][0]["dca_question_refs"] = ["Q43", "Q49"]
    gap = new_research_gap("QA", "Clarify succession evidence", ["Q43"], session["session_id"])
    before = {"ticker": "QA", "company_name": "QA Company", "sessions": [session], "research_gaps": [gap]}
    after = json.loads(json.dumps(before))
    after["sessions"][0]["analyst_session_note"] = "Analyst re-reviewed the interview record."
    delta = compare_versions(before, after)
    summary = history_summary(before, after)

    assert SOURCE_PRINT_PAGES == (331, 334)
    assert len(MANAGEMENT_INTERVIEW_TOPICS) == 8
    assert set(delta["Delta"]).issubset({"Unchanged", "Added", "Removed", "Changed"})
    assert source_baseline_fingerprint(before) != source_baseline_fingerprint(after)
    assert summary["automatic_management_score"] is False
    assert summary["automatic_ceo_quality_classifier"] is False
    assert summary["automatic_credibility_or_personality_score"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["automatic_mos_change"] is False
    assert summary["automatic_research_gate_change"] is False

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "qa.sqlite"
        snap = create_snapshot(db, "QA", before["sessions"], before["research_gaps"], "QA Company")
        assert snap["snapshot_id"] == 1
        assert len(list_snapshots(db, "QA")) == 1
        rr = record_re_review(db, "QA", "Appendix B", "Explicit analyst re-review")
        assert rr["scope"] == "Appendix B"

    report = {
        "phase": "Appendix B Phase C / V95",
        "acceptance": "PASS",
        "source_print_pages": list(SOURCE_PRINT_PAGES),
        "source_locked_topics": len(MANAGEMENT_INTERVIEW_TOPICS),
        "neutral_delta_vocabulary": ["Unchanged", "Added", "Removed", "Changed"],
        "immutable_snapshot": True,
        "explicit_analyst_re_review": True,
        "automatic_management_score": False,
        "automatic_ceo_quality_classifier": False,
        "automatic_credibility_or_personality_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_ssot_added": False,
        "appendix_b_closure": "COMPLETE",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_B_PHASEC_HISTORY_CLOSURE_V95.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
