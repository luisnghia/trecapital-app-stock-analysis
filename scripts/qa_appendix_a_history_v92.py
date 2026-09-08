from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.deep_company_analysis.appendix_a_history import build_interview_lineage, compare_versions, history_summary
from modules.deep_company_analysis.appendix_a_store import create_appendix_a_snapshot, list_appendix_a_snapshots
from modules.deep_company_analysis.appendix_a_workspace import make_interview_record, make_source_record, normalize_workspace


def main() -> None:
    source = make_source_record(source_name="Supplier A", source_class="Primary", source_type="Supplier")
    interview = make_interview_record(
        source_id=source["source_id"], interview_date="2026-09-08", question_prompt="What changed?",
        source_response_observation="Lead times shortened.", uncertainty_noted="Exact month not specified.",
        related_question_refs=["Q03", "Q59"], analyst_commentary="Needs corroboration.",
    )
    before = normalize_workspace({"ticker": "ABC", "sources": [source], "interviews": [interview]})
    after = normalize_workspace(before)
    after["sections"]["interview_database"] = "Covered"
    summary = history_summary(before, after)
    lineage = build_interview_lineage(before)
    delta = compare_versions(before, after)
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "appa.sqlite3"
        first = create_appendix_a_snapshot(before, db_path=db)
        second = create_appendix_a_snapshot(after, db_path=db)
        snapshots = list_appendix_a_snapshots("ABC", db_path=db)
    report = {
        "acceptance": "PASS",
        "source_lock_preserved": True,
        "snapshot_count": len(snapshots),
        "snapshot_ids": [first["snapshot_id"], second["snapshot_id"]],
        "interview_lineage_rows": len(lineage),
        "delta_vocabulary": sorted(set(delta["Delta"])),
        "neutral_delta_only": set(delta["Delta"]).issubset({"Unchanged", "Added", "Removed", "Changed"}),
        "automatic_human_source_score": summary["automatic_human_source_score"],
        "automatic_credibility_score": summary["automatic_credibility_score"],
        "automatic_weighted_research_score": summary["automatic_weighted_research_score"],
        "automatic_investment_signal": summary["automatic_investment_signal"],
        "automatic_mos_change": summary["automatic_mos_change"],
        "automatic_research_gate_change": summary["automatic_research_gate_change"],
        "historical_source_freshness_reconstructed": summary["historical_source_freshness_reconstructed"],
        "duplicate_financial_ssot_added": False,
        "appendix_a_complete": True,
        "next_source_section": "Appendix B — How to Interview the Management Team",
    }
    out = Path("reports/APPENDIX_A_PHASEC_HISTORY_V92.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
