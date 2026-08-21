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


def test_ui_renders_only_selected_section_and_blank_manual_overrides():
    source = Path("modules/investment_checklist/ui/page.py").read_text(encoding="utf-8")
    assert "st.tabs(" not in source
    assert 'section = st.radio("Khu vực checklist"' in source
    assert 'format="%.0f"' in source
    assert 'format="%.1f"' in source
    assert "App không tự bịa số liệu" in source
    assert "để trống = dùng số tự động" in source
    assert "def _effective(auto_value, manual_value)" in source
    assert "manual_value if manual_value is not None else auto_value" in source
    assert "value=None" in source
    assert "def base(k)" not in source
    assert "Snapshot cũ không được dùng" not in source  # wording may evolve; behavior is enforced by no base(latest)


def test_normalized_data_layer_preserves_ebitda_support_fields():
    required = {"depreciation_bil", "interest_paid_bil", "interest_expense_bil", "borrowing_cost_bil", "ebitda_bil"}
    assert required.issubset(set(MODULE1_TIMESERIES_COLUMNS))


def test_checklist_does_not_activate_stale_bundled_workbook_as_current_market_source():
    source = Path("pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    assert "def _load_checklist_bundle" in source
    assert "FireAnt + Vietstock" in source
    assert "Do NOT activate the workbook fallback" in source
    assert "def _sanitize_statement_only_fallback" in source
    assert '("current_price", "market_cap_bil", "shares_outstanding_mil", "pe", "pb", "ps")' in source
    assert '("current_price", "market_price_vnd", "year_end_price")' in source
    assert "_load_active_or_default(requested_ticker)" not in source
    assert "active_source_label" in source
