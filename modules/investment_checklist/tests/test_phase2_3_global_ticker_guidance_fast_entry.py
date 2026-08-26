from __future__ import annotations

from pathlib import Path

from modules.investment_checklist.source_table_guidance import (
    CHAPTER_9_NOTE,
    SOURCE_TABLE_GUIDANCE,
    SOURCE_TABLE_ORDER,
)


REQUIRED_SOURCE_TABLES = {
    "5.1", "5.2", "5.3", "5.4",
    "6.1", "6.2", "6.3", "6.4", "6.5", "6.6",
    "7.1",
    "8.1", "8.2", "8.3",
    "10.1",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_source_table_guidance_covers_all_chapter_5_to_10_numbered_tables_used_by_module():
    assert set(SOURCE_TABLE_ORDER) == REQUIRED_SOURCE_TABLES
    assert set(SOURCE_TABLE_GUIDANCE) == REQUIRED_SOURCE_TABLES
    for table_id in SOURCE_TABLE_ORDER:
        spec = SOURCE_TABLE_GUIDANCE[table_id]
        assert spec["title"].startswith(f"Table {table_id}")
        assert str(spec["objective"]).strip()
        assert len(tuple(spec["how_to_read"])) >= 2
        assert len(tuple(spec["checks"])) >= 2
        assert str(spec["caution"]).strip()
        assert str(spec["mapping"]).strip()


def test_chapter_9_is_not_fabricated_as_a_numbered_table():
    assert not any(table_id.startswith("9.") for table_id in SOURCE_TABLE_ORDER)
    note = CHAPTER_9_NOTE.lower()
    assert "q48" in note and "q52" in note
    assert "không" in note and "table 9" in note


def test_phase2_ui_wires_each_source_table_group_to_visible_guidance():
    source = (_repo_root() / "modules/investment_checklist/ui/quant_tools.py").read_text(encoding="utf-8")
    assert "render_full_chapter_5_to_10_guide" in source
    assert 'render_source_table_guidance(("5.1", "5.2"))' in source
    assert 'render_source_table_guidance(("5.3", "5.4"))' in source
    assert 'render_source_table_guidance(("6.1", "6.2"))' in source
    assert 'render_source_table_guidance(("6.3", "6.4", "6.5"))' in source
    assert 'render_source_table_guidance(("6.6",))' in source
    assert 'render_source_table_guidance(("8.2", "8.3"))' in source
    assert 'render_source_table_guidance(("10.1",))' in source


def test_checklist_page_uses_canonical_global_ticker_pipeline_and_shared_keys():
    source = (_repo_root() / "pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    assert '"Mã cổ phiếu"' in source
    assert '"Tự động cập nhật khi đổi mã"' in source
    assert 'm1._search_and_bind(safe, "FireAnt + Vietstock")' in source
    assert '"shared_ticker"' in source
    assert '"module1_ticker"' in source
    assert '"module2_ticker"' in source
    assert 'st.session_state["module1_input_ticker"] = safe' in source


def test_checklist_fast_entry_reuses_active_bundle_and_defers_full_financial_preparation():
    source = (_repo_root() / "pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    assert "_active_bundle_has_data_for_ticker" in source
    assert "class _LazyChecklistDataProvider" in source
    assert "_checklist_prepared_financials" in source

    render_tail = source.split("def render_page() -> None:", 1)[1]
    before_lazy_loader = render_tail.split("    def _load_annual_lazy()", 1)[0]
    # Common page-entry path must only read the overview row; annual/quarter/debt work is deferred.
    assert "m1._load_overview_cached" in before_lazy_loader
    assert "_prepare_financials_session(" not in before_lazy_loader

    load_bundle = source.split("def _load_checklist_bundle(ticker: str):", 1)[1].split("def _sync_global_ticker", 1)[0]
    # Reuse check must happen before any live provider call.
    assert load_bundle.index("_active_reusable_bundle(ticker)") < load_bundle.index("m1._fetch_source")
