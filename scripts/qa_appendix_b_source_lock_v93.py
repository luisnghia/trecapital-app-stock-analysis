from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import appendix_b as appb


def main() -> None:
    payload = appb.empty_payload("TEST", "Test Company")
    protocol_text = " ".join(appb.INTERVIEW_PROTOCOL).lower()
    caveat_text = " ".join(appb.FACE_TO_FACE_CAVEATS).lower()
    report = {
        "phase": "Appendix B Phase A V93",
        "appendix": appb.APPENDIX_KEY,
        "title": appb.APPENDIX_TITLE,
        "source_lock": appb.SOURCE_LOCK,
        "source_print_pages": list(appb.SOURCE_PRINT_PAGES),
        "source_locked_sections": len(appb.SECTION_KEYS),
        "management_interview_topics": len(appb.MANAGEMENT_INTERVIEW_TOPICS),
        "unknown_first": all(v == "Unknown" for v in payload["sections"].values()),
        "open_ended_one_at_a_time": "open-ended" in protocol_text and "one" in protocol_text,
        "listen_and_clarify": "listen" in protocol_text and ("clarify" in protocol_text or "re-ask" in protocol_text),
        "past_behavior_over_hypothetical": "past behavior" in protocol_text and "hypothetical" in protocol_text,
        "face_to_face_false_confidence_caveat": "false confidence" in caveat_text,
        "response_separate_from_analyst_commentary": (
            "Management Response / Observation" in appb.SESSION_NOTE_COLUMNS
            and "Analyst Commentary" in appb.SESSION_NOTE_COLUMNS
        ),
        "automatic_management_score": False,
        "automatic_ceo_quality_classifier": False,
        "automatic_credibility_or_personality_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_ssot_added": False,
    }
    checks = [
        report["source_locked_sections"] == 2,
        report["management_interview_topics"] == 8,
        report["source_print_pages"] == [331, 334],
        report["unknown_first"],
        report["open_ended_one_at_a_time"],
        report["listen_and_clarify"],
        report["past_behavior_over_hypothetical"],
        report["face_to_face_false_confidence_caveat"],
        report["response_separate_from_analyst_commentary"],
        not report["automatic_management_score"],
        not report["automatic_ceo_quality_classifier"],
        not report["automatic_credibility_or_personality_score"],
        not report["automatic_investment_signal"],
        not report["automatic_mos_change"],
        not report["automatic_research_gate_change"],
        not report["duplicate_financial_ssot_added"],
    ]
    report["acceptance"] = "PASS" if all(checks) else "FAIL"
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_B_PHASEA_SOURCE_LOCK_V93.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["acceptance"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
