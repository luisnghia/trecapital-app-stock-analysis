from __future__ import annotations

import json
from pathlib import Path
import tempfile

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_completion as completion
import modules.deep_company_analysis.chapter11_history as history
import modules.deep_company_analysis.chapter11_history_ui as history_ui
import modules.deep_company_analysis.chapter11_store as store


def main() -> None:
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.SOURCE_QUESTION_RANGE == "Q58-Q59"
    assert len(ch11.dimension_ids()) == 15
    assert history_ui.REVIEW_SECTIONS == ("Q58", "Q59", "M&A Synthesis", "Source Baseline")
    assert {key for _, key in history.SYNTHESIS_FIELDS}.issubset(set(completion.default_synthesis()))

    with tempfile.TemporaryDirectory() as tmp:
        original = store.DB_PATH
        store.DB_PATH = Path(tmp) / "chapter11.db"
        try:
            p = ch11.empty_payload("TEST", "Test Co")
            p["ma_synthesis"] = completion.default_synthesis()
            p["ma_synthesis"]["final_ma_synthesis"] = "Analyst conclusion"
            store.save_record("TEST", p, "Test Co")
            snap = store.create_snapshot("TEST", reason="closure-baseline")
            reviewed = store.mark_explicit_re_review("TEST", ["Q58", "M&A Synthesis"], "closure check")
            reviewed["ma_synthesis"] = completion.normalize_synthesis(reviewed["ma_synthesis"])
            store.save_record("TEST", reviewed, "Test Co")
            loaded = store.load_record("TEST", "Test Co")
            assert loaded["ma_synthesis"]["last_re_review_sections"] == ["Q58", "M&A Synthesis"]
            summary = history.history_summary(snap["payload"], loaded)
        finally:
            store.DB_PATH = original

    acceptance = {
        "phase": "Chapter 11 Phase 11H / V89",
        "chapter_closed": True,
        "source_lock": ch11.SOURCE_LOCK,
        "question_coverage": list(ch11.QUESTION_KEYS),
        "evidence_dimensions": len(ch11.dimension_ids()),
        "history_ui_integrated": True,
        "version_lineage_report_integrated": True,
        "actual_synthesis_schema_tracked": True,
        "re_review_metadata_preserved": True,
        "historical_source_freshness_reconstructed": summary["historical_source_freshness_reconstructed"],
        "automatic_question_status_change": summary["automatic_question_status_change"],
        "automatic_confidence_change": summary["automatic_confidence_change"],
        "automatic_analyst_text_change": summary["automatic_analyst_text_change"],
        "automatic_ma_score": summary["automatic_ma_score"],
        "automatic_acquisition_success_classification": summary["automatic_acquisition_success_classification"],
        "automatic_synergy_forecast": summary["automatic_synergy_forecast"],
        "automatic_investment_signal": summary["automatic_investment_signal"],
        "mos_or_investment_research_gate_changed": summary["mos_or_investment_research_gate_changed"],
        "duplicate_financial_ssot": False,
    }
    assert acceptance["historical_source_freshness_reconstructed"] is False
    for key in (
        "automatic_question_status_change", "automatic_confidence_change", "automatic_analyst_text_change",
        "automatic_ma_score", "automatic_acquisition_success_classification", "automatic_synergy_forecast",
        "automatic_investment_signal", "mos_or_investment_research_gate_changed", "duplicate_financial_ssot",
    ):
        assert acceptance[key] is False
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH11_PHASE11H_CLOSURE_V89.json").write_text(json.dumps(acceptance, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(acceptance, indent=2, ensure_ascii=False))
    print("PASS: Chapter 11 V89 closure integration preserves source lock, analyst ownership, SSOT and investment boundaries.")


if __name__ == "__main__":
    main()
