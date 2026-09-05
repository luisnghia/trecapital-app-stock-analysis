from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "modules" / "deep_company_analysis" / "chapter7_research.py"
RESEARCH_UI = ROOT / "modules" / "deep_company_analysis" / "chapter7_research_ui.py"
PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"
DOC = ROOT / "docs" / "CHAPTER7_PHASE7C_EVIDENCE_RESEARCH_ASSISTANT.md"


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"Missing {label}: {token}")


def main() -> None:
    research = RESEARCH.read_text(encoding="utf-8")
    ui = RESEARCH_UI.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")

    for token in ("Q33", "Q34", "Q35", "Q36", "Q37", "Q38"):
        require(research, f'"{token}"', f"{token} research coverage")

    require(research, "RESEARCH_BOUNDARY", "research boundary")
    require(research, "No automatic OO/LT/HH", "no auto manager classification")
    require(research, "no automatic insider", "no auto insider signal")
    require(research, "Analyst promotion is required", "explicit analyst promotion")
    require(research, "A — Company/Official disclosure", "source grade A")
    require(research, "B — Independent financial source/research", "source grade B")
    require(research, "C — Secondary/context source", "source grade C")
    require(research, "PDF text extraction (no OCR)", "PDF no-OCR boundary")
    require(research, "Promoted candidate — analyst verify", "promoted candidate status")

    require(ui, "render_chapter7_research_assistant", "Phase 7C UI")
    require(ui, "Research Q33–Q38", "focused research action")
    require(ui, "Trích sâu PDF/HTML đã chọn", "deep extraction action")
    require(ui, "Promote evidence đã chọn + lưu Research Gaps", "explicit promote action")
    require(page, "render_chapter7_research_assistant(ticker, payload)", "page integration")
    require(page, "Phase 7A+7B+7C", "V36 phase caption/save label")
    require(page, "Phase 7A chưa có Chapter 7 Completion Gate chính thức", "Phase 7A regression lock")
    require(page, "Final source-closure vẫn thuộc Phase 7D", "completion gate boundary")
    require(doc, "No automatic Lion/Hyena", "documentation boundary")

    forbidden_research_writes = (
        'out["final_management_classification"] =',
        'out["q33"]["analyst_classification"] =',
        'out["q35"]["overall_classification"] =',
        'out["q38"]["insider_behavior"] =',
        'out["analyst_summary"] =',
    )
    for token in forbidden_research_writes:
        if token in research:
            raise AssertionError(f"Phase 7C must not write analyst-owned conclusion: {token}")

    print("PASS Chapter 7 Phase 7C V36 static source/boundary audit")


if __name__ == "__main__":
    main()
