from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from modules.deep_company_analysis.appendix_c import CHECKLIST_ITEMS, QUESTION_TITLES
from modules.deep_company_analysis.investment_checklist_report import (
    AI_ROLE,
    CONCLUSION_OWNER,
    ChecklistReportError,
    build_checklist_rows,
    build_investment_checklist_report_docx,
)


def _xml(blob: bytes) -> str:
    with ZipFile(BytesIO(blob)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_v101_preserves_exact_source_locked_wording_and_order() -> None:
    answers = {f"Q{i:02d}": {"status": "Reviewed", "evidence": f"Evidence {i}"} for i in range(1, 60)}
    rows = build_checklist_rows(answers)
    assert len(rows) == 59
    assert [row["question_id"] for row in rows] == [f"Q{i:02d}" for i in range(1, 60)]
    assert [row["question"] for row in rows] == [str(item["question"]) for item in CHECKLIST_ITEMS]
    for row in rows:
        assert row["question"] == QUESTION_TITLES[row["question_id"]]
        assert row["ssot_reference"] == row["question_id"]


def test_v101_q33_q52_guard_keeps_unknown_without_evidence() -> None:
    answers = {
        "Q32": {"status": "Reviewed"},
        "Q33": {"status": "Reviewed"},
        "Q40": {"status": "Complete", "evidence": []},
        "Q52": {"status": "Answered", "evidence": ""},
        "Q53": {"status": "Reviewed"},
    }
    by_id = {row["question_id"]: row for row in build_checklist_rows(answers)}
    assert by_id["Q32"]["status"] == "Reviewed"
    assert by_id["Q33"]["status"] == "Unknown"
    assert by_id["Q40"]["status"] == "Unknown"
    assert by_id["Q52"]["status"] == "Unknown"
    assert by_id["Q53"]["status"] == "Reviewed"
    assert by_id["Q33"]["evidence"] == ""


def test_v101_rejects_non_source_locked_question_ids() -> None:
    with pytest.raises(ChecklistReportError, match="Unknown question IDs"):
        build_checklist_rows({"Q60": {"status": "Reviewed", "evidence": "x"}})


def test_v101_generates_valid_evidence_rich_docx_with_provenance() -> None:
    answers = {
        "Q01": {
            "status": "Reviewed",
            "evidence": [{"summary": "Business model evidence"}],
            "sources": [{"title": "Annual report"}],
            "analyst_note": "Analyst note only",
        },
        "Q33": {"status": "Complete"},
    }
    blob = build_investment_checklist_report_docx(
        company_name="DGC",
        as_of="2026-09-09",
        answers=answers,
        financial_snapshot=[{"metric": "Revenue", "2025": 100, "TTM": 110}],
        cyclical_normalization=[{"metric": "ROIC", "median": "18.0%", "latest": "20.0%"}],
        provenance=[{
            "source_field": "revenue",
            "source_module": "Trecapital Data Layer",
            "source_period": "TTM",
            "data_origin": "canonical_financials",
        }],
        what_changed=["Revenue evidence refreshed."],
        critical_unknowns=["Supplier concentration evidence remains incomplete."],
        analyst_name="Test Analyst",
    )
    assert blob[:2] == b"PK"
    xml = _xml(blob)
    assert "DGC" in xml
    assert "Q01–Q59 Investment Checklist" in xml
    assert QUESTION_TITLES["Q01"] in xml
    assert QUESTION_TITLES["Q59"] in xml
    assert "Business model evidence" in xml
    assert "Annual report" in xml
    assert "Financial provenance / source table" in xml
    for column in ("source_field", "source_module", "source_period", "data_origin"):
        assert column in xml
    assert "Revenue evidence refreshed." in xml
    assert "Supplier concentration evidence remains incomplete." in xml
    assert AI_ROLE in xml
    assert CONCLUSION_OWNER in xml


def test_v101_empty_report_never_infers_missing_management_evidence() -> None:
    rows = build_checklist_rows(None)
    guarded = [row for row in rows if 33 <= int(row["question_id"][1:]) <= 52]
    assert len(guarded) == 20
    assert all(row["status"] == "Unknown" and row["evidence"] == "" for row in guarded)
