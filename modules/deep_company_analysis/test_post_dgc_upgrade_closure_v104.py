from __future__ import annotations

from pathlib import Path

from modules.deep_company_analysis.appendix_c import QUESTION_IDS
from modules.deep_company_analysis.event_question_mapping_v103 import AI_ROLE, CONCLUSION_OWNER, EVENT_RULES, validate_mapping_contract
from modules.deep_company_analysis.investment_checklist_report import build_checklist_rows

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_closure_marker_declares_v99_v103_and_boundaries() -> None:
    text = _text("docs/POST_DGC_UPGRADE_COMPLETE.md")
    for token in ("V99", "V100", "V101", "V102", "V103", "Trecapital Data Layer", "Research Assistant", "Module 2"):
        assert token in text
    for forbidden in ("automatic BUY/HOLD/SELL", "automatic intrinsic-value or MOS change", "automatic Investment Research Gate change"):
        assert forbidden in text


def test_required_post_dgc_modules_and_tests_exist() -> None:
    required = (
        "modules/deep_company_analysis/cyclical_normalization.py",
        "modules/deep_company_analysis/test_cyclical_normalization_v100.py",
        "modules/deep_company_analysis/investment_checklist_report.py",
        "modules/deep_company_analysis/investment_checklist_report_v102.py",
        "modules/deep_company_analysis/investment_checklist_report_v103.py",
        "modules/deep_company_analysis/event_question_mapping_v103.py",
        "modules/deep_company_analysis/test_event_question_mapping_v103.py",
        "docs/BOOK_IMPLEMENTATION_COMPLETE.md",
    )
    assert all((ROOT / path).is_file() for path in required)


def test_source_lock_and_unknown_guard_are_preserved() -> None:
    assert len(QUESTION_IDS) == 59
    assert QUESTION_IDS[0] == "Q01" and QUESTION_IDS[-1] == "Q59"
    answers = {f"Q{i:02d}": {"status": "Pass", "evidence": ""} for i in range(33, 53)}
    rows = {row["question_id"]: row for row in build_checklist_rows(answers)}
    assert all(rows[f"Q{i:02d}"]["status"] == "Unknown" for i in range(33, 53))


def test_event_mapping_closure_contract() -> None:
    assert validate_mapping_contract() == ()
    assert tuple(EVENT_RULES) == ("raw_material_cost", "audit_governance", "project_delay")
    assert AI_ROLE == "Research Assistant"
    assert CONCLUSION_OWNER == "Analyst"


def test_report_contract_contains_review_and_provenance_surfaces() -> None:
    report_text = _text("modules/deep_company_analysis/investment_checklist_report.py")
    combined = report_text + _text("modules/deep_company_analysis/investment_checklist_report_v102.py") + _text("modules/deep_company_analysis/investment_checklist_report_v103.py")
    for token in ("What changed since last review", "Critical unknowns", "source_field", "source_module", "source_period", "data_origin"):
        assert token in combined


def test_book_marker_forbids_new_book_phase_without_concrete_gap() -> None:
    text = _text("docs/BOOK_IMPLEMENTATION_COMPLETE.md")
    assert "59/59" in text
    assert "no new book-implementation phase" in text
