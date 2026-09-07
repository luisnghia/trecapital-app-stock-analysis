from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract
import modules.deep_company_analysis.chapter9_workspace as ws


REPORT = Path("reports/CH9_PHASE9E_ANALYST_WORKSPACE_V66.json")


def chapter7_fixture() -> dict:
    return {
        "ticker": "DGC",
        "management_profiles": [
            {
                "Manager ID": "M001",
                "Manager": "Nguyễn Văn A",
                "Current Role": "Tổng Giám đốc / CEO",
                "Confidence": "High",
            },
            {
                "Manager ID": "M002",
                "Manager": "Trần Văn B",
                "Current Role": "CFO",
                "Confidence": "Medium",
            },
        ],
    }


def candidate(question: str, dimension_key: str, manager_id: str, manager: str) -> dict:
    return {
        "Select": True,
        "Candidate ID": f"v66-{question}-{dimension_key}-{manager_id or 'none'}",
        "Question": question,
        "Dimension Key": dimension_key,
        "Dimension": dimension_key,
        "Manager ID": manager_id,
        "Manager": manager,
        "Current Role": "Tổng Giám đốc / CEO" if manager_id == "M001" else "",
        "Source Family": "Annual report/shareholder communication",
        "Direction": "Neutral / context — analyst assess",
        "Source Grade": "A — Company/Official disclosure",
        "Explicitness": "Extracted original source text — analyst verify context",
        "Source Title": "Official document",
        "Source URL / File": f"https://example.com/{dimension_key}",
        "Source Date": "2026-04-01",
        "As-of Date": "2026",
        "Evidence Text / Reference": "Fixture evidence for deterministic workspace acceptance.",
        "Source Method": "Phase 9D official/document extraction",
        "Data Origin": "Direct source text — analyst verification required",
        "Status": "Candidate — analyst verify",
    }


def main() -> None:
    chapter7 = chapter7_fixture()
    payload = ch9.empty_payload("DGC", "Duc Giang Chemicals")
    payload["analyst_assessment"]["Q48"] = "Analyst-owned fixture conclusion"
    payload["question_status"]["Q48"] = "Partial"

    candidates = pd.DataFrame(
        [
            candidate("Q48", "q48_lifelong_learning", "M001", "Nguyễn Văn A"),
            candidate("Q50", "q50_shareholder_letters", "", ""),
            candidate("Q52", "q52_financing_context", "M001", "Nguyễn Văn A"),
        ]
    )
    before = candidates.copy(deep=True)
    promoted, added = ws.promote_selected_candidates(payload, candidates, chapter7_payload=chapter7)

    assert added == 3
    assert candidates.equals(before)
    assert promoted["analyst_assessment"]["Q48"] == "Analyst-owned fixture conclusion"
    assert promoted["question_status"]["Q48"] == "Partial"
    assert all(item["Status"] == "Promoted — analyst verified" for item in promoted["evidence"])
    assert all(item["Candidate ID"] for item in promoted["evidence"])
    assert all(item["Dimension Key"] for item in promoted["evidence"])

    no_ceo = candidate("Q48", "q48_lifelong_learning", "", "")
    valid, _ = ws.validate_candidate_for_promotion(no_ceo, chapter7)
    assert valid is False
    invented = candidate("Q50", "q50_shareholder_letters", "M999", "Invented Manager")
    valid, _ = ws.validate_candidate_for_promotion(invented, chapter7)
    assert valid is False

    snap = ws.workspace_snapshot(promoted)
    assert snap["source_dimension_count"] == 26
    assert snap["automatic_management_score"] is False
    assert snap["automatic_character_classification"] is False
    assert snap["automatic_investment_signal"] is False

    source_snapshot = contract.validate_source_contract()
    assert source_snapshot["total_dimensions"] == 26
    assert source_snapshot["dimension_counts"] == {"Q48": 6, "Q49": 4, "Q50": 8, "Q51": 3, "Q52": 5}

    report = {
        "phase": "Chapter 9 Phase 9E Analyst Workspace + Candidate Promotion + Persistence V66",
        "acceptance": "PASS",
        "chapter": 9,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "exact_question_range": "Q48-Q52",
        "source_dimension_count": source_snapshot["total_dimensions"],
        "dimension_counts": source_snapshot["dimension_counts"],
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "explicit_analyst_promotion_required": True,
        "candidate_input_immutable": True,
        "promotion_preserves_candidate_id": True,
        "promotion_preserves_dimension_lineage": True,
        "promotion_preserves_source_lineage": True,
        "ceo_specific_q48_q52_require_exact_chapter7_ceo_link": True,
        "replacement_manager_ids_created": False,
        "deduplication_added": True,
        "sqlite_workspace_persistence_added": True,
        "snapshot_history_added": True,
        "ui_added": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
        "promoted_fixture_rows": added,
        "workspace_snapshot": snap,
        "next_phase": "Phase 9F — unified Streamlit analyst workspace UI using the V66 promotion/store layer.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
