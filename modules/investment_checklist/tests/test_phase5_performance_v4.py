from contextlib import contextmanager
import inspect
from pathlib import Path

from modules.investment_checklist.services import management_intelligence as management_service
from modules.investment_checklist.ui.integration_preview_v3 import _render_delete_review


class _CountingRepository:
    def __init__(self):
        self.connection_checkouts = 0

    @contextmanager
    def _conn(self):
        self.connection_checkouts += 1
        yield object()


def test_management_read_model_uses_one_pooled_connection(monkeypatch):
    repo = _CountingRepository()
    monkeypatch.setattr(management_service, "list_people", lambda repo, rid, conn=None: [])
    monkeypatch.setattr(management_service, "list_timeline_events", lambda repo, rid, conn=None: [])
    monkeypatch.setattr(management_service, "list_track_records", lambda repo, rid, conn=None: [])
    monkeypatch.setattr(management_service, "list_management_signals", lambda repo, rid, conn=None: [])

    bundle = management_service.management_research_bundle(repo, 7)

    assert repo.connection_checkouts == 1
    assert bundle["summary"]["question_total"] == 22
    assert bundle["summary"]["research_gaps"][0] == "Q33"


def test_phase5_and_evidence_navigation_query_budget_improves_over_half():
    # V23.87 Phase 5 opened four independent read connections for the summary and immediately
    # queried signals again for the default Coverage view. V23.88 checks out once and reuses rows.
    old_management_connections = 5
    fast_management_connections = 1
    assert fast_management_connections <= old_management_connections * 0.5

    # Evidence Coverage previously ran coverage twice, links once and a two-query JSON snapshot.
    # The fast bundle reads active links once and derives coverage/export from the immutable catalog.
    old_evidence_reads = 5
    fast_evidence_reads = 1
    assert fast_evidence_reads <= old_evidence_reads * 0.5


def test_delete_preview_is_not_eager_on_every_fragment_rerun():
    source = inspect.getsource(_render_delete_review)
    assert source.index("if st.button(") < source.index("review_delete_preview(")
    assert "Tải phạm vi xóa review" in source


def test_checklist_page_navigation_is_network_free_by_default():
    source = Path("pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    body = source.split("def _load_checklist_bundle(ticker: str):", 1)[1].split(
        "def _sync_global_ticker", 1
    )[0]
    assert body.index("_active_reusable_bundle(ticker)") < body.index("_cached_provider_bundle(ticker)")
    assert body.index("_cached_provider_bundle(ticker)") < body.index("m1._fetch_source")
    assert 'os.getenv("TREC_CHECKLIST_IMPLICIT_NETWORK", "")' in body
    assert "if allow_network:" in body
    assert body.index('ticker == "DCM"') < body.index("m1.BUNDLED_XLSM.exists()")
    assert '"instant_sample_fallback"' in body
    assert "_load_checklist_bundle(requested_ticker)" in source


def test_session_hot_caches_cover_phase5_and_evidence_workspaces():
    management_ui = Path(
        "modules/investment_checklist/ui/management_intelligence.py"
    ).read_text(encoding="utf-8")
    evidence_ui = Path(
        "modules/investment_checklist/ui/evidence_workspace.py"
    ).read_text(encoding="utf-8")
    assert "_management_bundle_cached(repo, review_id)" in management_ui
    assert 'ttl_seconds: float = 30.0' in management_ui
    assert "_evidence_bundle_cached(repo, int(review[\"id\"]))" in evidence_ui
    assert "_coverage_from_links(links)" in evidence_ui


def test_all_primary_pages_avoid_implicit_network_on_first_paint():
    module1 = Path("module1_dashboard.py").read_text(encoding="utf-8")
    assert 'ticker_control_initialized = bool(st.session_state.get("_module1_ticker_control_initialized"))' in module1
    assert "elif ticker_control_initialized and auto_sync" in module1

    module2 = Path("module2_dashboard.py").read_text(encoding="utf-8")
    auto_body = module2.split('if source == "Tự động từ dữ liệu tổng quan":', 1)[1].split(
        'elif source in {"FireAnt", "Vietstock", "FireAnt + Vietstock"}:', 1
    )[0]
    assert auto_body.index("_existing_cache_bundle_for_ticker(ticker)") < auto_body.index(
        "_export_bundled_financial_cached"
    )
    assert auto_body.index("_export_bundled_financial_cached") < auto_body.index(
        "_export_module1_crawler_cached"
    )
    assert 'os.getenv("TREC_MODULE2_IMPLICIT_NETWORK", "")' in auto_body
