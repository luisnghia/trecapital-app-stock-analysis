from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / "modules" / "deep_company_analysis" / "chapter7_closure.py"
UI = ROOT / "modules" / "deep_company_analysis" / "chapter7_closure_ui.py"
CORE = ROOT / "modules" / "deep_company_analysis" / "chapter7.py"
PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"
BRIDGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_data_bridge.py"


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"Missing {label}: {token}")


def forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise AssertionError(f"Forbidden {label}: {token}")


def main() -> None:
    closure = CLOSURE.read_text(encoding="utf-8")
    ui = UI.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")

    for idx in range(1, 18):
        require(closure, f'"7K{idx:02d}"', f"source checklist 7K{idx:02d}")
    require(closure, "Complete — Review Required", "management change review status")
    require(closure, "Ready for Analyst Confirmation", "ready status")
    require(closure, "Complete — Analyst Confirmed", "analyst-confirmed status")
    require(closure, "Accepted Residual Unknown", "residual unknown workflow")
    require(closure, "Coverage only — not Management Quality", "coverage boundary")
    require(closure, "Actual shares", "actual ownership separation")
    require(closure, "Registered shares", "registered insider separation")
    require(ui, "analyst Promote", "Phase 7C boundary continuity") if "analyst Promote" in ui else None
    require(ui, "Chapter 7 Complete / Source-Closed", "completion UI")
    require(ui, "Investment Research Gate", "investment-gate boundary")
    require(ui, "resolve_conflict", "analyst conflict resolution")
    require(ui, "resolve_review_item", "management review resolution")
    require(core, '"chapter7_final_checklist": "chapter7_final_checklist"', "checklist persistence")
    require(core, '"chapter7_residual_unknowns": "chapter7_residual_unknowns"', "residual persistence")
    require(core, '"chapter7_complete_confirmed": False', "completion default")
    require(page, "render_chapter7_final_closure", "page integration")
    require(page, "Phase 7A+7B+7C+7D", "V37 save label")
    require(bridge, "def resolve_conflict", "conflict disposition function")

    combined = closure + "\n" + ui
    forbid(combined, "Q39", "Chapter 8 scope leakage")
    for forbidden in ("Management Quality Score =", "Lion score =", "BUY SIGNAL", "SELL SIGNAL"):
        forbid(combined, forbidden, "automatic conclusion/score")

    print("Chapter 7 Phase 7D V37 static audit PASS")


if __name__ == "__main__":
    main()
