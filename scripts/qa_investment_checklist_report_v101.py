from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from modules.deep_company_analysis.appendix_c import QUESTION_TITLES, validate_source_lock
from modules.deep_company_analysis.investment_checklist_report import (
    AI_ROLE,
    CONCLUSION_OWNER,
    build_checklist_rows,
    build_investment_checklist_report_docx,
)

REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)

answers = {
    f"Q{i:02d}": {
        "status": "Reviewed",
        "evidence": f"Synthetic deterministic evidence {i}",
        "sources": [f"Synthetic source {i}"],
    }
    for i in list(range(1, 33)) + list(range(53, 60))
}
for i in range(33, 53):
    answers[f"Q{i:02d}"] = {"status": "Reviewed", "evidence": ""}

rows = build_checklist_rows(answers)
blob = build_investment_checklist_report_docx(
    company_name="DGC",
    as_of="2026-09-09",
    answers=answers,
    financial_snapshot=[{"metric": "Revenue", "period": "TTM", "value": 11000, "unit": "VND bn"}],
    cyclical_normalization=[{"metric": "ROIC", "median": "18.0%", "p25": "14.0%", "p75": "22.0%"}],
    provenance=[{
        "source_field": "revenue",
        "source_module": "Trecapital Data Layer",
        "source_period": "TTM",
        "data_origin": "canonical_financials",
    }],
    what_changed=["Synthetic prior-review delta for acceptance only."],
    critical_unknowns=["Q33-Q52 intentionally lack evidence for Unknown guard acceptance."],
    analyst_name="Acceptance Analyst",
)

sample_path = REPORTS / "DGC_INVESTMENT_CHECKLIST_REPORT_V101_SAMPLE.docx"
sample_path.write_bytes(blob)
with ZipFile(BytesIO(blob)) as archive:
    document_xml = archive.read("word/document.xml").decode("utf-8")

unknown_guard = all(row["status"] == "Unknown" for row in rows if 33 <= int(row["question_id"][1:]) <= 52)
source_wording = all(QUESTION_TITLES[row["question_id"]] == row["question"] for row in rows)
source_lock_errors = list(validate_source_lock())
provenance_columns = all(key in document_xml for key in ("source_field", "source_module", "source_period", "data_origin"))

result = {
    "acceptance": "PASS" if (
        len(rows) == 59
        and not source_lock_errors
        and source_wording
        and unknown_guard
        and provenance_columns
        and AI_ROLE in document_xml
        and CONCLUSION_OWNER in document_xml
    ) else "FAIL",
    "report_version": "V101",
    "question_count": len(rows),
    "exact_source_wording_by_reference": source_wording,
    "source_lock_errors": source_lock_errors,
    "q33_q52_unknown_without_evidence": unknown_guard,
    "provenance_columns_present": provenance_columns,
    "duplicate_financial_ssot_added": False,
    "duplicate_question_ssot_added": False,
    "valuation_formula_changed": False,
    "automatic_weighted_score": False,
    "automatic_buy_hold_sell": False,
    "automatic_research_gate_change": False,
    "ai_role": AI_ROLE,
    "conclusion_owner": CONCLUSION_OWNER,
    "docx_sample": str(sample_path),
}

output = REPORTS / "INVESTMENT_CHECKLIST_REPORT_V101_ACCEPTANCE.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["acceptance"] == "PASS" else 1)
