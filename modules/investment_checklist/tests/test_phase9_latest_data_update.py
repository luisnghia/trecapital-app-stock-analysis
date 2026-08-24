from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview
from modules.investment_checklist.services.topdown_data_update import (
    decide_driver_suggestion,
    get_update_run_bundle,
    latest_accepted_driver_outlook,
    list_pending_driver_suggestions,
    load_source_registry,
    run_latest_data_update,
    source_coverage_rows,
    source_registry_hash,
)


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"
NOW = datetime(2026, 8, 24, 2, 30, tzinfo=timezone.utc)


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase9.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix: str = "LATEST"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE9:{suffix}",
        ticker="DCM",
        company_name="PetroVietnam Ca Mau Fertilizer",
        exchange="HOSE",
        industry_name="Hóa chất cơ bản/Phân bón",
        actor="test",
    )
    review_id = repo.create_review(
        company_ref_id,
        "2026-08-24",
        analyst_user_id="analyst",
        review_reason="Phase 9 latest-on-click QA",
    )
    return company_ref_id, review_id


def _client(call_log: list[str] | None = None) -> httpx.Client:
    call_log = call_log if call_log is not None else []

    def handler(request: httpx.Request):
        call_log.append(str(request.url))
        path = request.url.path
        if "NGDP_RPCH" in path:
            return httpx.Response(
                200,
                json={
                    "values": {
                        "NGDP_RPCH": {
                            "VNM": {
                                "2024": 6.1,
                                "2025": 7.1,
                                "2026": 6.4,
                                "2027": 6.2,
                                "2031": 5.8,
                            }
                        }
                    }
                },
                request=request,
            )
        if "NE.GDI.FTOT.KD.ZG" in path:
            return httpx.Response(
                200,
                json=[
                    {"page": 1, "pages": 1, "total": 3},
                    [
                        {"date": "2025", "value": 8.0, "obs_status": ""},
                        {"date": "2024", "value": 4.0, "obs_status": ""},
                        {"date": "2023", "value": None, "obs_status": ""},
                    ],
                ],
                request=request,
            )
        if "series/observations" in path:
            return httpx.Response(
                200,
                json={
                    "observations": [
                        {"date": "2026-08-22", "value": "18.0"},
                        {"date": "2026-08-21", "value": "11.0"},
                    ]
                },
                request=request,
            )
        return httpx.Response(404, json={"error": "fixture not found"}, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_phase9_registry_covers_exactly_26_drivers_and_records_hash():
    registry = load_source_registry()
    rows = source_coverage_rows(registry)
    assert len(rows) == 26
    assert len({row["Driver ID"] for row in rows}) == 26
    assert len(source_registry_hash(registry)) == 64
    assert any(row["Cơ chế"] == "Tự động khi bấm Cập nhật" for row in rows)
    assert any(row["Cơ chế"] == "Research gap — cần nguồn/analyst" for row in rows)


def test_phase9_manual_click_fetches_latest_only_creates_suggestions_and_never_assessment(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo)
    calls: list[str] = []
    client = _client(calls)
    run_id = run_latest_data_update(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        driver_ids=["gdp_growth", "capex_cycle"],
        actor="analyst",
        http_client=client,
        api_keys={},
        now=NOW,
    )
    client.close()

    assert len(calls) == 2
    bundle = get_update_run_bundle(repo, run_id)
    assert bundle["run"]["trigger_type"] == "manual_click"
    assert bundle["run"]["status"] == "completed"
    assert bundle["run"]["success_count"] == 2
    assert len(bundle["observations"]) == 2
    assert len(bundle["suggestions"]) == 2
    gdp = next(row for row in bundle["observations"] if row["driver_id"] == "gdp_growth")
    capex = next(row for row in bundle["observations"] if row["driver_id"] == "capex_cycle")
    assert gdp["period_label"] == "2026" and gdp["value_numeric"] == 6.4
    assert gdp["previous_value_numeric"] == 7.1
    assert capex["period_label"] == "2025" and capex["value_numeric"] == 8.0
    assert all("?" not in row["source_url"] for row in bundle["observations"])
    assert all(len(row["payload_hash"]) == 64 for row in bundle["observations"])
    with repo._conn() as c:
        assert c.execute(
            "SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)
        ).fetchone()["n"] == 0


def test_phase9_optional_key_is_never_called_without_key_and_key_is_never_persisted(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo, "KEY")
    calls: list[str] = []
    client = _client(calls)
    missing_key_run = run_latest_data_update(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        driver_ids=["risk_aversion"],
        http_client=client,
        api_keys={},
        now=NOW,
    )
    assert calls == []
    assert get_update_run_bundle(repo, missing_key_run)["run"]["status"] == "failed"

    key = "a" * 32
    keyed_run = run_latest_data_update(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        driver_ids=["risk_aversion"],
        http_client=client,
        api_keys={"FRED_API_KEY": key},
        now=NOW,
    )
    client.close()
    assert len(calls) == 1 and key in calls[0]
    raw = json.dumps(get_update_run_bundle(repo, keyed_run), ensure_ascii=False)
    assert key not in raw
    assert "?" not in get_update_run_bundle(repo, keyed_run)["observations"][0]["source_url"]


def test_phase9_accept_reject_lock_snapshot_and_review_delete(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo, "GOVERNED")
    client = _client()
    run_id = run_latest_data_update(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        driver_ids=["gdp_growth", "capex_cycle"],
        http_client=client,
        api_keys={},
        now=NOW,
    )
    client.close()
    pending = list_pending_driver_suggestions(repo, review_id)
    assert len(pending) == 2
    accepted = next(row for row in pending if row["driver_id"] == "gdp_growth")
    rejected = next(row for row in pending if row["driver_id"] == "capex_cycle")
    with pytest.raises(ValidationError, match="xác nhận"):
        decide_driver_suggestion(
            repo,
            suggestion_id=accepted["id"],
            decision="accept",
            decision_reason="Đồng ý dữ liệu IMF",
            applied_score=-1,
        )
    decide_driver_suggestion(
        repo,
        suggestion_id=accepted["id"],
        decision="accept",
        decision_reason="Đã đối chiếu WEO và chấp nhận điều chỉnh giảm",
        applied_score=-1,
        analyst_confirmed=True,
    )
    decide_driver_suggestion(
        repo,
        suggestion_id=rejected["id"],
        decision="reject",
        decision_reason="Dữ liệu năm chưa đủ mới cho quyết định hiện tại",
    )
    assert latest_accepted_driver_outlook(repo, review_id) == {"gdp_growth": -1}
    with pytest.raises(ValidationError, match="đã được quyết định"):
        decide_driver_suggestion(
            repo,
            suggestion_id=accepted["id"],
            decision="accept",
            decision_reason="Duplicate",
            applied_score=0,
            analyst_confirmed=True,
        )

    snapshot_id = repo.finalize_review(
        review_id, actor="analyst", finalize_reason="Khóa Phase 9 governed QA"
    )
    snapshot = repo.get_snapshot(snapshot_id)["payload"]
    assert snapshot["topdown_latest_data"]["latest_accepted_driver_outlook"] == {"gdp_growth": -1}
    calls: list[str] = []
    blocked_client = _client(calls)
    with pytest.raises(ValidationError, match="finalize"):
        run_latest_data_update(
            repo,
            company_ref_id=company_ref_id,
            review_id=review_id,
            driver_ids=["gdp_growth"],
            http_client=blocked_client,
            now=NOW,
        )
    blocked_client.close()
    assert calls == []

    preview = review_delete_preview(repo, review_id)
    assert preview["counts"]["topdown_data_runs"] == 1
    assert preview["counts"]["topdown_data_observations"] == 2
    assert preview["counts"]["topdown_driver_suggestions"] == 2
    assert preview["counts"]["topdown_driver_decisions"] == 2
    delete_review_manually(
        repo,
        review_id,
        actor="admin",
        reason="Xóa Phase 9 QA",
        confirmation_text=f"XÓA REVIEW #{review_id}",
    )
    with repo._conn() as c:
        for table in (
            "topdown_data_update_runs",
            "topdown_data_observations",
            "topdown_driver_suggestions",
            "topdown_driver_decisions",
        ):
            assert c.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"] == 0


def test_phase9_route_ui_no_background_network_and_schema_security_contract(tmp_path):
    shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    service = Path("modules/investment_checklist/services/topdown_data_update.py").read_text(encoding="utf-8")
    ui = Path("modules/investment_checklist/ui/topdown_data_update.py").read_text(encoding="utf-8")
    migration = Path("sql/schema_checklist_phase9_latest_data.sql").read_text(encoding="utf-8").lower()
    assert '"🔄 Latest Data Update"' in shell
    assert 'elif section == "🔄 Latest Data Update":' in shell
    assert "st_autorefresh" not in service + ui
    assert "schedule" not in service.lower()
    assert "save_assessment(" not in service + ui
    assert "trigger_type='manual_click'" in migration
    for table in (
        "topdown_data_update_runs",
        "topdown_data_observations",
        "topdown_driver_suggestions",
        "topdown_driver_decisions",
    ):
        assert f"alter table public.{table} enable row level security" in migration
        assert f"revoke all on table public.{table} from anon, authenticated" in migration

    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo, "UI")
    app = f'''
import httpx
httpx.Client.get = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("background network call"))
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.topdown_data_update import render_topdown_data_update
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
render_topdown_data_update(repo, {company_ref_id}, repo.get_review({review_id}), "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0
    assert any("Latest Data Update" in str(item.value) for item in at.markdown)
    assert any("Cập nhật dữ liệu mới nhất" in str(item.label) for item in at.button)
    with repo._conn() as c:
        assert c.execute("SELECT COUNT(*) n FROM topdown_data_update_runs").fetchone()["n"] == 0


def test_postgres_phase9_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    company_ref_id, review_id = _seed(repo, uuid.uuid4().hex[:10].upper())
    client = _client()
    run_id = run_latest_data_update(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        driver_ids=["gdp_growth"],
        http_client=client,
        now=NOW,
    )
    client.close()
    assert get_update_run_bundle(repo, run_id)["run"]["status"] == "completed"
    repo.close()
