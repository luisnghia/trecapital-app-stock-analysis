from pathlib import Path


def test_phase6b_is_wired_to_unified_chapter6_page():
    root = Path(__file__).resolve().parent
    text = (root / "chapter6_page_support.py").read_text(encoding="utf-8")
    assert "build_chapter6_quant_context" in text
    assert "_render_phase6b_quantitative_bridge(ticker)" in text
    assert "Cập nhật canonical data Chương 6" in text
    assert "render_static_table(" in text
    assert "st.dataframe(" not in text


def test_phase6b_methodology_locks_critical_boundaries():
    root = Path(__file__).resolve().parents[2]
    formulas = (root / "docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md").read_text(encoding="utf-8")
    implementation = (root / "docs/CHAPTER6_PHASE6B_IMPLEMENTATION.md").read_text(encoding="utf-8")
    combined = formulas + implementation
    assert "tax_paid_bil" in combined
    assert "Cash impact from ΔOWC = -ΔOWC" in combined
    assert "does not import Module-1 `maintenance_capex_bil`" in combined
    assert "Invalid" in combined
    assert "BUY/HOLD/SELL" in combined
