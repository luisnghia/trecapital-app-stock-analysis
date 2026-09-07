from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_completion as completion
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


def _chapter7_payload() -> dict:
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


def _verified_evidence(question: str, dimension_key: str, manager_id: str = "M001") -> dict:
    return {
        "Question": question,
        "Dimension Key": dimension_key,
        "Manager ID": manager_id,
        "Manager": "Nguyễn Văn A" if manager_id == "M001" else "",
        "Observation / Claim": "Verified observation",
        "Source URL / File": "https://example.com/source",
        "Evidence Text / Reference": "Original source reference",
        "Source Grade": "B — reputable source",
        "Status": "Promoted — analyst verified",
        "Direction": "Neutral",
    }


def test_phase9g_preserves_exact_26_dimension_source_contract_and_boundaries() -> None:
    assert len(contract.all_dimensions()) == 26
    source = Path(completion.__file__).read_text(encoding="utf-8").casefold()
    assert "research-completion gate only" in source
    assert "not a management-quality score" in source
    assert "buy/hold/sell" in source
    assert "automatic_management_score" in source
    assert "chapter 7" in source
    assert "26 phase 9b source dimensions" in source


def test_empty_workspace_with_known_managers_keeps_all_dimensions_open_not_fabricated() -> None:
    payload = ch9.empty_payload("DGC")
    table = completion.build_dimension_closure(payload, _chapter7_payload())
    assert len(table) == 26
    assert table["Dimension Key"].nunique() == 26
    assert set(table["Closure Status"]) == {"Open — no coverage"}
    snap = completion.completion_snapshot(payload, _chapter7_payload())
    assert snap["closed_dimensions"] == 0
    assert snap["open_dimensions"] == 26
    assert snap["research_completion_gate"] == "Blocked — research incomplete"


def test_missing_chapter7_manager_master_blocks_all_dimension_closure() -> None:
    table = completion.build_dimension_closure(ch9.empty_payload("DGC"), {})
    assert len(table) == 26
    assert set(table["Closure Status"]) == {"Blocked — manager scope"}
    assert all("Chapter 7" in text for text in table["Next Action"].astype(str))


def test_verified_evidence_closes_only_its_exact_source_dimension() -> None:
    payload = ch9.empty_payload("DGC")
    payload["evidence"] = [_verified_evidence("Q48", "q48_career_vs_job")]
    table = completion.build_dimension_closure(payload, _chapter7_payload())
    row = table[table["Dimension Key"].eq("q48_career_vs_job")].iloc[0]
    assert row["Closure Status"] == "Closed — verified evidence"
    assert row["Verified Evidence"] == 1
    assert row["Source-Lineage Rows"] == 1
    assert (table["Closure Status"] == "Closed — verified evidence").sum() == 1


def test_promoted_evidence_without_source_lineage_does_not_close_dimension() -> None:
    payload = ch9.empty_payload("DGC")
    row = _verified_evidence("Q49", "q49_integrity_moment", "M001")
    row["Source URL / File"] = ""
    payload["evidence"] = [row]
    table = completion.build_dimension_closure(payload, _chapter7_payload())
    item = table[table["Dimension Key"].eq("q49_integrity_moment")].iloc[0]
    assert item["Closure Status"] == "Review — source lineage incomplete"


def test_unverified_manual_evidence_requires_analyst_verification() -> None:
    payload = ch9.empty_payload("DGC")
    row = _verified_evidence("Q50", "q50_shareholder_letters", "M001")
    row["Status"] = "Manual — not reviewed"
    payload["evidence"] = [row]
    table = completion.build_dimension_closure(payload, _chapter7_payload())
    item = table[table["Dimension Key"].eq("q50_shareholder_letters")].iloc[0]
    assert item["Closure Status"] == "Review — evidence verification"


def test_open_gap_remains_open_and_closed_gap_is_known_unknown_not_fake_evidence() -> None:
    payload = ch9.empty_payload("DGC")
    payload["research_gaps"] = [
        {
            "Question": "Q51",
            "Dimension Key": "q51_long_term_focus",
            "Research Gap": "No reliable historical interview found.",
            "Status": "Open — evidence gap",
        },
        {
            "Question": "Q52",
            "Dimension Key": "q52_media_touting",
            "Research Gap": "Archive unavailable after documented search.",
            "Status": "Closed — analyst accepted known unknown",
        },
    ]
    table = completion.build_dimension_closure(payload, _chapter7_payload())
    q51 = table[table["Dimension Key"].eq("q51_long_term_focus")].iloc[0]
    q52 = table[table["Dimension Key"].eq("q52_media_touting")].iloc[0]
    assert q51["Closure Status"] == "Open — research gap"
    assert q52["Closure Status"] == "Closed — analyst accepted known unknown"
    assert q52["Evidence Rows"] == 0


def test_question_ready_requires_all_dimensions_closed_plus_analyst_owned_fields() -> None:
    payload = ch9.empty_payload("DGC")
    evidence = []
    for dim in contract.QUESTION_DIMENSIONS["Q48"]:
        evidence.append(_verified_evidence("Q48", dim.key, "M001"))
    payload["evidence"] = evidence

    table = completion.build_question_completion(payload, _chapter7_payload())
    q48 = table[table["Question"].eq("Q48")].iloc[0]
    assert q48["Closed Dimensions"] == 6
    assert q48["Completion Status"] == "Review — analyst research status not closed"

    payload["question_status"]["Q48"] = "Answered"
    payload["confidence"]["Q48"] = "Low"
    payload["analyst_assessment"]["Q48"] = "Analyst-written conclusion"
    table = completion.build_question_completion(payload, _chapter7_payload())
    q48 = table[table["Question"].eq("Q48")].iloc[0]
    assert q48["Completion Status"] == "Ready — research closure complete"


def test_completion_engine_never_mutates_analyst_payload_or_chapter7_payload() -> None:
    payload = ch9.empty_payload("DGC")
    payload["question_status"]["Q48"] = "Partial"
    payload["confidence"]["Q48"] = "Medium"
    payload["analyst_assessment"]["Q48"] = "My conclusion"
    chapter7 = _chapter7_payload()
    before_payload = deepcopy(payload)
    before_ch7 = deepcopy(chapter7)
    completion.completion_snapshot(payload, chapter7)
    assert payload == before_payload
    assert chapter7 == before_ch7


def test_completion_snapshot_is_readiness_metadata_never_quality_or_investment_score() -> None:
    snap = completion.completion_snapshot(ch9.empty_payload("DGC"), _chapter7_payload())
    assert snap["source_dimension_count"] == 26
    assert snap["automatic_question_status_change"] is False
    assert snap["automatic_confidence_change"] is False
    assert snap["automatic_analyst_assessment"] is False
    assert snap["automatic_management_score"] is False
    assert snap["automatic_character_classification"] is False
    assert snap["automatic_investment_signal"] is False
    assert snap["mos_or_investment_research_gate_changed"] is False


def test_completion_log_is_jsonl_and_never_breaks_workspace(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "chapter9.log"
    monkeypatch.setattr(completion, "LOG_PATH", log_path)
    completion.append_completion_log("dgc", "completion_view", {"closed": 3})
    text = log_path.read_text(encoding="utf-8")
    assert '"ticker": "DGC"' in text
    assert '"event": "completion_view"' in text


def test_question_completion_columns_are_counts_and_statuses_not_management_scores() -> None:
    joined = " ".join(completion.QUESTION_COMPLETION_COLUMNS).casefold()
    assert "management score" not in joined
    assert "weighted score" not in joined
    assert "buy signal" not in joined
    assert "sell signal" not in joined
    assert "margin of safety" not in joined
