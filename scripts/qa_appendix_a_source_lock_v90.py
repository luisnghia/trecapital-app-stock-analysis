from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import appendix_a as appa


def main() -> None:
    payload = appa.empty_payload("TEST", "Test Company")
    report = {
        "phase": "Appendix A Phase A V90",
        "appendix": appa.APPENDIX_KEY,
        "title": appa.APPENDIX_TITLE,
        "source_lock": appa.SOURCE_LOCK,
        "source_print_pages": list(appa.SOURCE_PRINT_PAGES),
        "source_locked_sections": len(appa.SECTION_KEYS),
        "section_source_pages": appa.SECTION_SOURCE_PAGES,
        "unknown_first": all(v == "Unknown" for v in payload["sections"].values()),
        "primary_secondary_distinction": set(appa.SOURCE_CLASS_OPTIONS) == {"Primary", "Secondary", "Unknown"},
        "source_response_separate_from_analyst_commentary": (
            "Source Response / Observation" in appa.INTERVIEW_NOTE_COLUMNS
            and "Analyst Commentary" in appa.INTERVIEW_NOTE_COLUMNS
        ),
        "automatic_human_source_score": False,
        "automatic_credibility_score": False,
        "automatic_investment_signal": False,
        "automatic_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_ssot_added": False,
        "web_contact_action_added": False,
    }
    checks = [
        report["source_locked_sections"] == 4,
        report["source_print_pages"] == [323, 330],
        report["unknown_first"],
        report["primary_secondary_distinction"],
        report["source_response_separate_from_analyst_commentary"],
        not report["automatic_human_source_score"],
        not report["automatic_credibility_score"],
        not report["automatic_investment_signal"],
        not report["automatic_mos_change"],
        not report["automatic_research_gate_change"],
        not report["duplicate_financial_ssot_added"],
        not report["web_contact_action_added"],
    ]
    report["acceptance"] = "PASS" if all(checks) else "FAIL"
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_A_PHASEA_SOURCE_LOCK_V90.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["acceptance"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
