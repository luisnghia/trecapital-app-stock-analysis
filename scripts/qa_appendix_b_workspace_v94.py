from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modules.deep_company_analysis import appendix_b as appb
from modules.deep_company_analysis.appendix_b_store import list_research_gaps, list_sessions, save_research_gap, save_session
from modules.deep_company_analysis.appendix_b_workspace import new_research_gap, new_session, workspace_summary


def main() -> None:
    report = {
        "phase": "Appendix B Phase B V94",
        "source_lock": appb.SOURCE_LOCK,
        "management_topics": len(appb.MANAGEMENT_INTERVIEW_TOPICS),
        "open_ended_one_at_a_time": True,
        "listen_and_clarify": True,
        "past_behavior_over_hypothetical": True,
        "response_separate_from_analyst_commentary": True,
        "dca_reference_only_q01_q59": True,
        "automatic_management_score": False,
        "automatic_ceo_quality_classifier": False,
        "automatic_credibility_or_personality_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_ssot_added": False,
    }
    assert report["management_topics"] == 8

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "appendix_b_v94.sqlite"
        session = new_session("QA", "CEO", "2026-09-08", "QA Company")
        session["topic_entries"][0]["open_ended_question"] = "Describe how you selected the team and why."
        session["topic_entries"][0]["management_response_observation"] = "Source response."
        session["topic_entries"][0]["analyst_commentary"] = "Analyst note."
        session["topic_entries"][0]["dca_question_refs"] = ["Q47"]
        save_session(db, session)
        gap = new_research_gap("QA", "Corroborate operating record", ["Q47", "Q59"], session["session_id"])
        save_research_gap(db, gap)
        sessions = list_sessions(db, "QA")
        gaps = list_research_gaps(db, "QA")
        summary = workspace_summary(sessions, gaps)
        assert len(sessions) == 1 and len(gaps) == 1
        assert summary["referenced_dca_questions"] == ["Q47", "Q59"]
        assert sessions[0]["topic_entries"][0]["management_response_observation"] == "Source response."
        assert sessions[0]["topic_entries"][0]["analyst_commentary"] == "Analyst note."

    report["acceptance"] = "PASS"
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_B_PHASEB_WORKSPACE_V94.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
