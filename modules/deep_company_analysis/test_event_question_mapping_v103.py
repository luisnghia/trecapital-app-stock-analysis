from __future__ import annotations

from io import BytesIO

import pandas as pd
from docx import Document

from modules.deep_company_analysis.appendix_c import QUESTION_IDS, QUESTION_TITLES
from modules.deep_company_analysis.event_question_mapping_v103 import (
    AI_ROLE,
    CONCLUSION_OWNER,
    EVENT_RULES,
    map_event_to_questions,
    map_events_to_questions,
    render_event_mapping_rows,
    validate_mapping_contract,
)
from modules.deep_company_analysis.investment_checklist_report import build_checklist_rows
from modules.deep_company_analysis.investment_checklist_report_v103 import build_investment_checklist_report_v103_docx


def _event(event_type: str, event_id: str = "E1", summary: str = "Material event") -> dict[str, str]:
    return {
        "event_type": event_type,
        "event_id": event_id,
        "event_date": "2026-08-31",
        "event_summary": summary,
        "source_field": "disclosure_event",
        "source_module": "company_disclosures",
        "source_period": "2026-08",
        "data_origin": "issuer filing",
    }


def _canonical_df() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in range(2015, 2025):
        n = year - 2014
        rows.append({
            "year": year, "period": str(year), "period_type": "Y",
            "revenue_bil": 1000.0 + n * 100, "gross_profit_bil": 300.0 + n * 30,
            "ebit_bil": 180.0 + n * 18, "ebitda_bil": 220.0 + n * 20,
            "net_profit_bil": 120.0 + n * 12, "npat_mi_bil": 110.0 + n * 11,
            "cfo_bil": 150.0 + n * 13, "capex_bil": -(40.0 + n),
            "cash_bil": 250.0 + n * 10, "total_debt_bil": 100.0 + n * 5,
            "equity_bil": 600.0 + n * 40, "roic_pct": 12.0 + n / 10,
            "roce_pct": 14.0 + n / 10, "accounts_receivable_bil": 120.0 + n,
            "inventory_bil": 100.0 + n * 2, "accounts_payable_bil": 80.0 + n,
            "ccc_days": 45.0 + n / 2, "source_module": "Trecapital Data Layer",
            "data_origin": "fixture/canonical",
        })
    rows.append({
        "year": 2025, "period": "TTM 2025", "period_type": "TTM",
        "revenue_bil": 2200.0, "gross_profit_bil": 660.0, "ebit_bil": 396.0,
        "ebitda_bil": 450.0, "net_profit_bil": 260.0, "npat_mi_bil": 245.0,
        "cfo_bil": 300.0, "capex_bil": -60.0, "cash_bil": 390.0,
        "total_debt_bil": 150.0, "equity_bil": 1050.0, "roic_pct": 14.0,
        "roce_pct": 16.0, "accounts_receivable_bil": 150.0, "inventory_bil": 140.0,
        "accounts_payable_bil": 105.0, "ccc_days": 49.0,
        "source_module": "Trecapital Data Layer", "data_origin": "fixture/canonical",
    })
    return pd.DataFrame(rows)


def test_contract_and_exact_three_event_families() -> None:
    assert validate_mapping_contract() == ()
    assert tuple(EVENT_RULES) == ("raw_material_cost", "audit_governance", "project_delay")
    assert AI_ROLE == "Research Assistant"
    assert CONCLUSION_OWNER == "Analyst"


def test_mapped_question_ids_are_canonical_references() -> None:
    for event_type in EVENT_RULES:
        rows = map_event_to_questions(_event(event_type))
        assert rows
        assert all(row["question_id"] in QUESTION_IDS for row in rows)
        assert all("question" not in row for row in rows)
        assert all("status" not in row for row in rows)


def test_required_event_families_route_deterministically() -> None:
    assert [x["question_id"] for x in map_event_to_questions(_event("raw-material/cost"))] == ["Q20", "Q23", "Q24", "Q45"]
    assert [x["question_id"] for x in map_event_to_questions(_event("audit/governance"))] == ["Q27", "Q40", "Q49", "Q50"]
    assert [x["question_id"] for x in map_event_to_questions(_event("project-delay"))] == ["Q23", "Q42", "Q55", "Q56"]


def test_provenance_is_complete_and_dedupe_stable() -> None:
    events = [_event("project_delay"), _event("project_delay"), _event("audit", "E2", "Audit change")]
    first = map_events_to_questions(events)
    second = map_events_to_questions(reversed(events))
    assert first == second
    assert len(first) == 8
    for row in first:
        for column in ("source_field", "source_module", "source_period", "data_origin"):
            assert row[column]


def test_wording_resolves_only_from_appendix_c() -> None:
    rows = render_event_mapping_rows([_event("raw_material_cost")])
    for row in rows:
        assert row["question"] == QUESTION_TITLES[row["question_id"]]


def test_q33_q52_unknown_guard_is_unchanged_without_evidence() -> None:
    answers = {f"Q{i:02d}": {"status": "Pass", "evidence": ""} for i in range(33, 53)}
    rows = {row["question_id"]: row for row in build_checklist_rows(answers)}
    assert all(rows[f"Q{i:02d}"]["status"] == "Unknown" for i in range(33, 53))


def test_v103_docx_composes_v102_and_event_mapping_without_owner_mutation() -> None:
    canonical = _canonical_df()
    before = canonical.copy(deep=True)
    payload = build_investment_checklist_report_v103_docx(
        company_name="DGC", as_of="TTM 2025", canonical_financial_df=canonical,
        answers={}, events=[_event("raw_material_cost")],
    )
    pd.testing.assert_frame_equal(canonical, before)
    document = Document(BytesIO(payload))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Event → Investment Checklist evidence routing" in text
    assert "Research-assistant routing only" in text
    tables_text = "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    assert QUESTION_TITLES["Q24"] in tables_text
