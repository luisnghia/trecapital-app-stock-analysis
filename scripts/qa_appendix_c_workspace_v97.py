from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import appendix_c as appc
from modules.deep_company_analysis import appendix_c_workspace as ws


def main() -> None:
    rows = ws.build_live_rows("QA", owner_payloads={})
    errors = list(appc.validate_source_lock()) + list(ws.validate_read_only_rows(rows))
    summary = ws.section_summary(rows)
    acceptance = "PASS" if not errors else "FAIL"
    report = {
        "phase": "Appendix C Phase B V97",
        "acceptance": acceptance,
        "question_coverage": len(rows),
        "section_coverage": len(summary),
        "source_lock": appc.SOURCE_LOCK,
        "live_owner_ssot_bridge": True,
        "appendix_answer_store_added": False,
        "duplicate_financial_or_question_ssot_added": False,
        "automatic_weighted_score": False,
        "automatic_management_or_growth_score": False,
        "automatic_investment_signal": False,
        "automatic_intrinsic_value_or_mos_change": False,
        "automatic_research_gate_change": False,
        "ai_role": "Research Assistant",
        "conclusion_owner": "Analyst",
        "errors": errors,
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/APPENDIX_C_PHASEB_WORKSPACE_V97.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
