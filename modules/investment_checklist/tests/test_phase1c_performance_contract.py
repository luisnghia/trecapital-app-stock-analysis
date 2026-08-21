from pathlib import Path

from adapters.base import MODULE1_TIMESERIES_COLUMNS
from modules.investment_checklist.contracts import CompanyContext, HostContext
from modules.investment_checklist.services.integration_service import build_repository, clear_repository_cache


def test_repository_is_reused_across_streamlit_reruns(tmp_path):
    clear_repository_cache()
    host = HostContext(
        company=CompanyContext(company_key="TEST:CACHE", ticker="TST", company_name="Cache Test"),
        shared_db_path=tmp_path / "checklist.db",
    )
    first = build_repository(host)
    second = build_repository(host)
    assert first is second
    assert len(first.list_questions()) == 59
    assert len(first.list_screening_criteria()) == 10
    clear_repository_cache()


def test_ui_renders_only_selected_section_and_numeric_inventory_inputs():
    source = Path("modules/investment_checklist/ui/page.py").read_text(encoding="utf-8")
    assert "st.tabs(" not in source
    assert 'section = st.radio("Khu vực checklist"' in source
    assert 'format="%.0f"' in source
    assert 'format="%.1f"' in source
    assert "App không tự bịa số liệu" in source


def test_normalized_data_layer_preserves_ebitda_support_fields():
    required = {"depreciation_bil", "interest_paid_bil", "interest_expense_bil", "borrowing_cost_bil", "ebitda_bil"}
    assert required.issubset(set(MODULE1_TIMESERIES_COLUMNS))
