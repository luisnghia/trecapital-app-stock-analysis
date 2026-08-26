from pathlib import Path


def test_table11_and_table12_are_inside_analytical_hub_not_top_level_sections():
    source = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    assert '"🧮 Analytical Tools"' in source
    assert '"⭐ Watchlist"' in source
    sections_block = source.split("SECTIONS = [", 1)[1].split("]", 1)[0]
    assert '"📋 Table 1.1"' not in sections_block
    assert '"📊 Table 1.2"' not in sections_block
    hub = Path("modules/investment_checklist/ui/portfolio_extensions.py").read_text(encoding="utf-8")
    assert "1.1 · Quality Criteria Matrix" in hub
    assert "1.2 · Opportunity Inventory" in hub


def test_analyst_override_cells_use_apricot_yellow_and_versioned_reason():
    source = Path("modules/investment_checklist/ui/portfolio_extensions.py").read_text(encoding="utf-8")
    service = Path("modules/investment_checklist/services/portfolio_extensions.py").read_text(encoding="utf-8")
    assert 'APRICOT_YELLOW = "#F6C344"' in source
    assert "Điều chỉnh nhà phân tích — hỗ trợ TTM và các năm lịch sử" in source
    assert "Lý do điều chỉnh *" in source
    assert "version_no" in service
    assert "append_table_override" in service


def test_formula_tables_use_wrapped_html_not_clipped_dataframe_cells():
    source = Path("modules/investment_checklist/ui/portfolio_extensions.py").read_text(encoding="utf-8")
    integrated = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    assert "table-layout:fixed" in source
    assert "white-space:normal!important" in source
    assert "overflow-wrap:anywhere" in source
    assert "render_wrapped_table" in integrated


def test_watchlist_navigation_updates_shared_ticker_and_returns_to_research_home():
    source = Path("modules/investment_checklist/ui/portfolio_extensions.py").read_text(encoding="utf-8")
    assert '"shared_ticker"' in source
    assert '"module1_ticker"' in source
    assert '"module2_ticker"' in source
    assert 'st.session_state["checklist_section_global"] = "🏠 Research Home"' in source
    assert 'on_select="rerun"' in source
