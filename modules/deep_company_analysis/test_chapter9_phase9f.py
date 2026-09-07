from __future__ import annotations

from pathlib import Path
import inspect

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_page_support as ui
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


def test_phase9f_ui_keeps_exact_source_lock_and_26_dimensions():
    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    assert len(contract.all_dimensions()) == 26
    src = inspect.getsource(ui)
    assert "26 source dimensions" in src
    assert "Michael Shearn" in src
    assert "Q48–Q52" in src


def test_phase9f_exposes_research_candidate_review_and_explicit_promotion():
    src = inspect.getsource(ui)
    assert "Tự nghiên cứu Q48–Q52" in src
    assert "Evidence Candidates" in src
    assert "Promote evidence đã chọn" in src
    assert "validate_candidate_for_promotion" in src
    assert "promote_selected_candidates" in src
    assert "LinkColumn" in src


def test_phase9f_uses_chapter7_manager_ssot_and_does_not_create_manager_master():
    src = inspect.getsource(ui)
    assert "load_chapter7_record" in src
    assert "Chapter 7 manager master" in src
    assert "manager_master =" not in src
    assert "create_manager" not in src


def test_phase9f_q48_q52_ceo_boundary_is_visible_to_analyst():
    src = inspect.getsource(ui)
    assert "Q48 và Q52 là **CEO-specific**" in src
    assert "candidate chỉ được promote khi khớp đúng CEO/Tổng Giám đốc" in src
    assert "Candidate bị bỏ qua" in src


def test_phase9f_financing_exception_is_preserved_in_ui():
    src = inspect.getsource(ui)
    assert "Q52_FINANCING_CONTEXT_EXCEPTION" in src
    assert "Context / exception" not in src or "Direction cue" in src


def test_phase9f_persists_workspace_and_snapshot_but_preview_is_read_only():
    src = inspect.getsource(ui)
    assert "Lưu Chapter 9 workspace" in src
    assert "Lưu snapshot Chapter 9" in src
    assert "load_snapshot" in src
    assert "Preview snapshot (read-only)" in src
    assert "snapshot không tự restore/ghi đè current workspace" in src


def test_phase9f_does_not_add_automatic_management_or_investment_decision():
    src = inspect.getsource(ui).casefold()
    assert "không tạo management quality score" in src
    assert "không phải kết luận positive/negative trait" in src
    assert "buy/hold/sell" in src
    forbidden_assignments = (
        "management_score =",
        "character_classification =",
        "research_gate =",
        "buy_signal =",
        "sell_signal =",
    )
    assert all(token not in src for token in forbidden_assignments)


def test_phase9f_is_wired_into_unified_deep_company_page_after_chapter8():
    root = Path(__file__).resolve().parents[2]
    page = root / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
    standalone = root / "pages" / "10_Phan_tich_chuyen_sau_Chuong_9.py"
    text = page.read_text(encoding="utf-8")
    assert "from modules.deep_company_analysis.chapter9_page_support import render_chapter9_tab" in text
    assert "🧠 Chương 9 — Phẩm chất quản lý" in text
    assert "dca_ch9_ticker" in text
    assert "render_chapter9_tab(chapter9_ticker)" in text
    assert text.index("🧭 Chương 8 — Năng lực vận hành") < text.index("🧠 Chương 9 — Phẩm chất quản lý")
    assert not standalone.exists()
