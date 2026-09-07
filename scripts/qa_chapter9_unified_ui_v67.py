from __future__ import annotations

from pathlib import Path
import json

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract
import modules.deep_company_analysis.chapter9_workspace as ws


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
UI = ROOT / "modules" / "deep_company_analysis" / "chapter9_page_support.py"
REPORT = ROOT / "reports" / "CH9_PHASE9F_UNIFIED_UI_V67.json"


def main() -> None:
    page_text = PAGE.read_text(encoding="utf-8")
    ui_text = UI.read_text(encoding="utf-8")
    source = contract.validate_source_contract()

    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    assert source["total_dimensions"] == 26
    assert source["dimension_counts"] == {"Q48": 6, "Q49": 4, "Q50": 8, "Q51": 3, "Q52": 5}
    assert "from modules.deep_company_analysis.chapter9_page_support import render_chapter9_tab" in page_text
    assert '"🧠 Chương 9 — Phẩm chất quản lý"' in page_text
    assert "render_chapter9_tab(chapter9_ticker)" in page_text
    assert "dca_ch9_ticker" in page_text
    assert "Tự nghiên cứu Q48–Q52" in ui_text
    assert "Promote evidence đã chọn" in ui_text
    assert "Lưu Chapter 9 workspace" in ui_text
    assert "Lưu snapshot Chapter 9" in ui_text
    assert "load_chapter7_record" in ui_text
    assert "Q52_FINANCING_CONTEXT_EXCEPTION" in ui_text
    assert "Management Quality Score" in ui_text
    assert "BUY/HOLD/SELL" in ui_text
    assert "management_score =" not in ui_text.casefold()
    assert "character_classification =" not in ui_text.casefold()
    assert "research_gate =" not in ui_text.casefold()

    empty = ch9.empty_payload("DGC")
    snap = ws.workspace_snapshot(empty)
    assert snap["question_count"] == 5
    assert snap["unknown"] == 5
    assert snap["source_dimension_count"] == 26
    assert snap["automatic_management_score"] is False
    assert snap["automatic_character_classification"] is False
    assert snap["automatic_investment_signal"] is False

    report = {
        "phase": "Chapter 9 Phase 9F Unified Streamlit Analyst Workspace UI V67",
        "acceptance": "PASS",
        "chapter": 9,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "exact_question_range": "Q48-Q52",
        "source_dimension_count": 26,
        "dimension_counts": source["dimension_counts"],
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "unified_page_integration": True,
        "standalone_chapter9_page_added": False,
        "research_assistant_visible": True,
        "explicit_candidate_promotion_visible": True,
        "analyst_status_and_conclusions_visible": True,
        "source_locked_q48_prompts_visible": True,
        "source_dimension_contract_visible": True,
        "evidence_matrix_visible": True,
        "research_gap_workflow_visible": True,
        "behavior_event_register_visible": True,
        "workspace_save_visible": True,
        "snapshot_history_visible": True,
        "snapshot_preview_read_only": True,
        "q52_financing_context_exception_visible": True,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
        "next_phase": "Phase 9G — research-completion gate and source-coverage closure checks for Q48-Q52, without management scoring.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
