from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_history as hist
import modules.deep_company_analysis.chapter11_store as store


def sample() -> dict:
    p = ch11.empty_payload("FPT", "FPT")
    p["question_status"]["Q58"] = "Answered"
    p["confidence"]["Q58"] = "High"
    p["analyst_assessment"]["Q58"] = "Analyst-owned conclusion"
    d = ch11.dimension_ids("Q58")[0]
    p["dimension_status"][d] = "Evidence found"
    p["evidence"] = [{"Question":"Q58","Dimension ID":d,"Observation / Claim":"evidence","Candidate ID":"qa-c1"}]
    p["ma_synthesis"] = {"status":"Draft","final_ma_synthesis":"Analyst synthesis"}
    return p


def main() -> None:
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert len(ch11.dimension_ids()) == 15
    p = sample()
    changed = deepcopy(p)
    changed["ma_synthesis"]["final_ma_synthesis"] = "Revised analyst synthesis"
    summary = hist.history_summary(p, changed)
    assert summary["changed_fields"] >= 1
    assert summary["historical_source_freshness_reconstructed"] is False
    assert summary["automatic_question_status_change"] is False
    assert summary["automatic_confidence_change"] is False
    assert summary["automatic_analyst_text_change"] is False
    assert summary["automatic_ma_score"] is False
    assert summary["automatic_acquisition_success_classification"] is False
    assert summary["automatic_synergy_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_investment_research_gate_changed"] is False

    with tempfile.TemporaryDirectory() as td:
        original = store.DB_PATH
        store.DB_PATH = Path(td) / "chapter11.db"
        try:
            store.save_record("FPT", p, "FPT")
            snap = store.create_snapshot("FPT", reason="V88 QA baseline")
            store.save_record("FPT", changed, "FPT")
            old = store.load_snapshot("FPT", snap["snapshot_id"])
            assert old is not None
            assert old["payload"]["ma_synthesis"]["final_ma_synthesis"] == "Analyst synthesis"
            reviewed = store.mark_explicit_re_review("FPT", ["Q58", "M&A Synthesis"], "QA review")
            assert reviewed["ma_synthesis"]["last_re_review_note"] == "QA review"
            assert reviewed["question_status"]["Q58"] == "Answered"
            assert reviewed["confidence"]["Q58"] == "High"
        finally:
            store.DB_PATH = original

    print("PASS: Chapter 11 V88 immutable snapshots, neutral delta, lineage and explicit analyst re-review preserve source/SSOT/investment boundaries.")


if __name__ == "__main__":
    main()
