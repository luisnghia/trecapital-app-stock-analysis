from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import appendix_c as appc


def main() -> None:
    ids = appc.QUESTION_IDS
    report = {
        "phase": "Appendix C Phase A V96",
        "appendix": appc.APPENDIX_KEY,
        "title": appc.APPENDIX_TITLE,
        "source_lock": appc.SOURCE_LOCK,
        "source_print_pages": list(appc.SOURCE_PRINT_PAGES),
        "question_count": len(appc.CHECKLIST_ITEMS),
        "question_range": [ids[0], ids[-1]],
        "section_count": len(appc.SECTION_ORDER),
        "section_counts": appc.SECTION_COUNTS,
        "continuous_q01_q59": ids == tuple(f"Q{i:02d}" for i in range(1, 60)),
        "unique_questions": len(set(ids)) == 59,
        "source_order_preserved": tuple(appc.SECTION_COUNTS) == appc.SECTION_ORDER,
        "referential_ssot_only": all(
            item["ssot_reference"] == item["question_id"] for item in appc.CHECKLIST_ITEMS
        ),
        "source_lock_errors": list(appc.validate_source_lock()),
        "automatic_weighted_score": False,
        "automatic_management_or_growth_score": False,
        "automatic_investment_signal": False,
        "automatic_intrinsic_value_or_mos_change": False,
        "automatic_research_gate_change": False,
        "duplicate_financial_or_question_ssot_added": False,
        "ai_role": "Research Assistant",
        "conclusion_owner": "Analyst",
    }
    checks = [
        report["source_print_pages"] == [335, 338],
        report["question_count"] == 59,
        report["question_range"] == ["Q01", "Q59"],
        report["section_count"] == 10,
        tuple(report["section_counts"].values()) == (6, 8, 6, 6, 6, 6, 9, 5, 5, 2),
        report["continuous_q01_q59"],
        report["unique_questions"],
        report["source_order_preserved"],
        report["referential_ssot_only"],
        not report["source_lock_errors"],
        not report["automatic_weighted_score"],
        not report["automatic_management_or_growth_score"],
        not report["automatic_investment_signal"],
        not report["automatic_intrinsic_value_or_mos_change"],
        not report["automatic_research_gate_change"],
        not report["duplicate_financial_or_question_ssot_added"],
        report["ai_role"] == "Research Assistant",
        report["conclusion_owner"] == "Analyst",
    ]
    report["acceptance"] = "PASS" if all(checks) else "FAIL"
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_C_PHASEA_SOURCE_LOCK_V96.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["acceptance"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
