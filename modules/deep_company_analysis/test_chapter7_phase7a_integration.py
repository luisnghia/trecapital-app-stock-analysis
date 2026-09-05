from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE_SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"
UNIFIED_PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"


def test_chapter7_page_support_uses_shared_sortable_table_contract():
    text = PAGE_SUPPORT.read_text(encoding="utf-8")
    assert "sortable_data_editor" in text
    assert "render_static_table" in text
    assert "st.dataframe(" not in text
    assert "st.table(" not in text
    assert "st.data_editor(" not in text
    assert "num_rows=\"dynamic\"" in text


def test_chapter7_page_support_preserves_analyst_boundary():
    text = PAGE_SUPPORT.read_text(encoding="utf-8")
    assert "Founder không tự động = OO1" in text
    assert "outsider không tự động" in text
    assert "Không có Lion score" in text
    assert "không phải Buy/Sell Signal" in text
    assert "Không tạo TTM giả" in text
    assert 'disabled=["Suggested Classification"]' in text


def test_unified_page_contains_chapter7_tab_after_patch():
    text = UNIFIED_PAGE.read_text(encoding="utf-8")
    assert "render_chapter7_tab" in text
    assert "chapter7_tab" in text
    assert "👥 Chương 7 — Ban điều hành" in text
    assert 'st.session_state.get("dca_ch7_ticker")' in text


def test_chapter7_does_not_introduce_completion_gate_before_phase7d():
    text = PAGE_SUPPORT.read_text(encoding="utf-8")
    assert "Phase 7A chưa có Chapter 7 Completion Gate chính thức" in text
    assert "chapter7_complete_confirmed" not in text
