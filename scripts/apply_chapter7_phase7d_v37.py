from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "modules" / "deep_company_analysis" / "chapter7.py"
PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"
BRIDGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_data_bridge.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase7D integration marker not found: {label}")
    return text.replace(old, new, 1)


def patch_core() -> None:
    text = CORE.read_text(encoding="utf-8")
    text = replace_once(text, "SCHEMA_VERSION = 2", "SCHEMA_VERSION = 3", "schema version")
    text = replace_once(
        text,
        '    "management_events": "chapter7_events",\n}',
        '    "management_events": "chapter7_events",\n'
        '    "chapter7_final_checklist": "chapter7_final_checklist",\n'
        '    "chapter7_residual_unknowns": "chapter7_residual_unknowns",\n'
        '}',
        "closure child tables",
    )
    old_note = '        "phase7c_research_note": "Web/PDF/HTML Research Assistant produces candidate evidence and research gaps only; analyst must explicitly Promote; no auto classification, Management Quality conclusion or insider trading signal.",\n'
    new_note = old_note + (
        '        "phase7d_closure_note": "Final source closure verifies Q33-Q38 research completeness only; no Management Quality score, MOS, investment Research Gate or BUY/HOLD/SELL.",\n'
        '        "chapter7_final_checklist": [],\n'
        '        "chapter7_residual_unknowns": [],\n'
        '        "chapter7_complete_confirmed": False,\n'
        '        "chapter7_completion_note": "",\n'
        '        "chapter7_completion_as_of": "",\n'
        '        "chapter7_completion_version": 0,\n'
        '        "chapter7_last_management_review_at": "",\n'
        '        "chapter7_last_management_review_result": "",\n'
        '        "chapter7_closure_source_snapshot": [],\n'
        '        "chapter7_closure_conflict_snapshot": [],\n'
        '        "chapter7_closure_review_snapshot": [],\n'
    )
    text = replace_once(text, old_note, new_note, "closure payload defaults")
    CORE.write_text(text, encoding="utf-8")


def patch_bridge() -> None:
    text = BRIDGE.read_text(encoding="utf-8")
    marker = '''def list_review_queue(ticker: str, status: str | None = "Open") -> list[dict[str, Any]]:\n'''
    addition = '''def resolve_conflict(conflict_id: int, status: str = "Resolved") -> None:\n    """Analyst-owned conflict disposition. No candidate or Chapter-7 conclusion is modified here."""\n    init_bridge_db()\n    allowed = {"Resolved", "Accepted residual uncertainty", "Needs analyst review"}\n    final_status = status if status in allowed else "Resolved"\n    with _connect() as conn:\n        conn.execute(\n            "UPDATE chapter7_data_conflicts SET status=?,updated_at=? WHERE id=?",\n            (final_status, _now(), int(conflict_id)),\n        )\n\n\n''' + marker
    text = replace_once(text, marker, addition, "resolve conflict function")
    text = replace_once(
        text,
        '    "refresh_registered_sources", "scan_local_sources", "list_candidates", "candidate_review_frame", "apply_candidate_ids",\n    "list_conflicts", "list_review_queue", "resolve_review_item", "latest_refresh_runs", "bridge_status_frame",\n',
        '    "refresh_registered_sources", "scan_local_sources", "list_candidates", "candidate_review_frame", "apply_candidate_ids",\n    "list_conflicts", "resolve_conflict", "list_review_queue", "resolve_review_item", "latest_refresh_runs", "bridge_status_frame",\n',
        "bridge export",
    )
    BRIDGE.write_text(text, encoding="utf-8")


def patch_page() -> None:
    text = PAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from modules.deep_company_analysis.chapter7_research_ui import render_chapter7_research_assistant\n",
        "from modules.deep_company_analysis.chapter7_research_ui import render_chapter7_research_assistant\n"
        "from modules.deep_company_analysis.chapter7_closure_ui import render_chapter7_final_closure\n",
        "closure UI import",
    )
    text = text.replace(
        "- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7B xử lý structured disclosure; Phase 7C research web/PDF/HTML chỉ tạo candidate evidence + research gaps và yêu cầu analyst Promote.",
        "- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7B xử lý structured disclosure; Phase 7C tạo candidate evidence; Phase 7D chỉ kiểm tra source/research completeness và yêu cầu analyst confirmation.",
    )
    text = text.replace(
        "Phase 7A chưa có Chapter 7 Completion Gate chính thức; Phase 7B/7C cũng không tự khóa chương. Final source-closure vẫn thuộc Phase 7D.",
        "Final source-closure vẫn thuộc Phase 7D; Phase 7D hiện triển khai Completion Gate chỉ cho research/source completeness, không phải Investment Research Gate.",
    )
    text = text.replace(
        "Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A + 7B structured bridge + 7C Evidence Research Assistant",
        "Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A + 7B + 7C + 7D Final Source Closure",
    )
    marker = "    with st.container(border=True):\n        _render_final_conclusion(ticker, payload)\n\n"
    insert = marker + "    with st.container(border=True):\n        payload = render_chapter7_final_closure(ticker, payload)\n\n"
    text = replace_once(text, marker, insert, "render Phase 7D after analyst dossier")
    text = text.replace("💾 Lưu Chapter 7 — Phase 7A+7B+7C", "💾 Lưu Chapter 7 — Phase 7A+7B+7C+7D")
    text = text.replace(
        "Đã lưu Phase 7A+7B+7C. Structured bridge/Research Assistant không ghi đè classification/conclusion của analyst.",
        "Đã lưu Phase 7A+7B+7C+7D. Data/Research/Closure layers không ghi đè classification/conclusion của analyst.",
    )
    PAGE.write_text(text, encoding="utf-8")


def main() -> None:
    patch_core()
    patch_bridge()
    patch_page()
    print("Chapter 7 Phase 7D V37 integration applied")


if __name__ == "__main__":
    main()
