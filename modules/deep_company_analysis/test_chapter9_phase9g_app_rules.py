from __future__ import annotations

from pathlib import Path

import modules.deep_company_analysis.chapter9_completion as completion


def test_phase9g_read_only_closure_tables_use_st_html_wrapped_renderer() -> None:
    ui_path = Path(__file__).with_name("chapter9_page_support.py")
    source = ui_path.read_text(encoding="utf-8")
    assert "static_table_html" in source
    assert "questions_html = static_table_html(questions, height=360)" in source
    assert "dimensions_html = static_table_html(dimensions, height=620)" in source
    assert "st.html(questions_html)" in source
    assert "st.html(dimensions_html)" in source


def test_phase9g_has_runtime_log_and_terminology_help() -> None:
    ui_path = Path(__file__).with_name("chapter9_page_support.py")
    source = ui_path.read_text(encoding="utf-8")
    assert "Giải thích thuật ngữ Phase 9G" in source
    assert "Research Completion Gate" in source
    assert "Source Lineage" in source
    assert "Known Unknown" in source
    assert "deep_company_analysis_chapter9.log" in source
    assert str(completion.LOG_PATH).endswith("data_cache/logs/deep_company_analysis_chapter9.log")


def test_phase9g_formula_logic_explanation_file_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    doc = root / "docs" / "FORMULA_EXPLANATION_CHAPTER9_PHASE9G_V68.md"
    text = doc.read_text(encoding="utf-8")
    assert "no financial valuation formula" in text.casefold()
    assert "no weighted score" in text.casefold()
    assert "source lineage rule" in text.casefold()
