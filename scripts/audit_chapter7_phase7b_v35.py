from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "modules" / "deep_company_analysis" / "chapter7.py"
BRIDGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_data_bridge.py"
UI = ROOT / "modules" / "deep_company_analysis" / "chapter7_data_bridge_ui.py"
PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"


def main() -> None:
    core = CORE.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")
    ui = UI.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")

    assert "SCHEMA_VERSION = 2" in core
    for token in (
        '"Compensation Scope"',
        '"Data Quality Flags"',
        '"Registered Shares"',
        '"Executed Shares"',
        '"Publication Date"',
        '"Effective Date"',
        '"As-of Date"',
    ):
        assert token in core, token

    for table in (
        "chapter7_source_documents",
        "chapter7_raw_management_records",
        "chapter7_candidate_records",
        "chapter7_role_history",
        "chapter7_data_conflicts",
        "chapter7_data_refresh_runs",
        "chapter7_review_queue",
    ):
        assert table in bridge, table

    assert "Raw -> Candidate -> Analyst-confirmed apply" in bridge
    assert "do not auto-merge" in bridge
    assert "PDF is unstructured" in bridge
    assert "Registered Shares" in bridge and "Executed Shares" in bridge
    assert "Actual Shares" in bridge and "RSU / Restricted" in bridge and "Unvested Awards" in bridge
    assert "protected_before" in bridge
    assert '"q33"' in bridge and '"q38"' in bridge
    assert "final_management_classification" in bridge
    assert "analyst_summary" in bridge

    # Event/as-of data only; no fake TTM implementation token in executable bridge/UI.
    executable = "\n".join(line for line in (bridge + "\n" + ui).splitlines() if not line.lstrip().startswith("#"))
    assert '"TTM"' not in executable
    assert "append_ttm" not in executable.lower()

    assert "render_structured_management_bridge" in page
    assert "Phase 7A + 7B structured data bridge" in page
    assert "Completion Gate" in page and "Phase 7D" in page
    assert "BUY/SELL signal" in ui
    assert "Candidate Data → Analyst Review → Apply" in ui

    print("PASS Chapter 7 Phase 7B static source/boundary audit")


if __name__ == "__main__":
    main()
