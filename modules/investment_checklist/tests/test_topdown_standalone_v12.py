from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import httpx
import pandas as pd
import pytest

from adapters.base import ProviderResult
import module_topdown_engine as engine
from module_topdown_macro_update import run_macro_update
from module_topdown_screening_data import screening_row_from_provider
from module_topdown_snapshot_store import TopDownMacroSnapshotStore, compare_snapshots


NOW = datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc)


def test_screening_derives_trecapital_metrics_without_manual_entry():
    overview = pd.DataFrame(
        [
            {
                "ticker": "DCM",
                "company_name": "Đạm Cà Mau",
                "industry": "Hóa chất cơ bản / Phân bón",
                "sub_industry": "Phân bón",
                "market_cap_bil": 1_000.0,
                "pe": 10.0,
                "pb": 2.0,
                "ps": 1.5,
            }
        ]
    )
    quarterly = pd.DataFrame(
        [
            {
                "year": 2025 + (index // 4),
                "quarter": index % 4 + 1,
                "cfo_bil": 10.0,
                "interest_bearing_debt_bil": 50.0,
                "equity_bil": 100.0,
            }
            for index in range(4)
        ]
    )
    result = ProviderResult(overview, pd.DataFrame(), quarterly, note="fixture")
    row = screening_row_from_provider("DCM", result, source="Trecapital fixture").row

    assert row["Mã ngành"] == "MAT"
    assert row["Vốn hóa (tỷ đồng)"] == 1_000.0
    assert row["P/CF (lần)"] == 25.0
    assert row["Nợ vay/Vốn chủ (lần)"] == 0.5
    assert row["GTGD bình quân 20 phiên (tỷ đồng)"] is None
    assert "GTGD bình quân 20 phiên" in row["Ghi chú dữ liệu"]


def test_screening_missing_metric_can_never_pass():
    row = engine.mau_bang_sang_loc(1).iloc[0].to_dict()
    row.update(
        {
            "Mã CK": "DCM",
            "Tên doanh nghiệp": "Đạm Cà Mau",
            "Mã ngành": "MAT",
            "Vốn hóa (tỷ đồng)": 10_000.0,
            "P/E (lần)": 8.0,
            "P/B (lần)": 1.5,
            "P/CF (lần)": 7.0,
            "P/S (lần)": 1.0,
            "Nợ vay/Vốn chủ (lần)": 0.2,
            # Liquidity intentionally missing.
        }
    )
    criteria = engine.scoring_config()["sang_loc_dinh_luong_mac_dinh"]["rong"]
    result = engine.chay_sang_loc(pd.DataFrame([row]), criteria).iloc[0]
    assert result["Kết quả"] == "Thiếu dữ liệu"
    assert "GTGD bình quân 20 phiên" in result["Lý do loại"]


def test_standalone_macro_update_uses_world_bank_fallback_and_never_writes_driver():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "NGDP_RPCH" in request.url.path:
            return httpx.Response(403, json={"error": "blocked"}, request=request)
        if "NY.GDP.MKTP.KD.ZG" in request.url.path:
            return httpx.Response(
                200,
                json=[
                    {"page": 1},
                    [
                        {"date": "2025", "value": 7.1, "obs_status": ""},
                        {"date": "2024", "value": 6.1, "obs_status": ""},
                    ],
                ],
                request=request,
            )
        return httpx.Response(404, json={"error": "fixture"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = run_macro_update(["gdp_growth"], http_client=client, api_keys={}, now=NOW)
    client.close()

    assert len(calls) == 2
    assert result["status"] == "completed"
    assert result["trigger_type"] == "manual_click"
    assert result["guardrail"].endswith("no company/checklist write")
    observation = result["observations"][0]
    assert observation["source_code"] == "world_bank_wdi"
    assert observation["series_code"] == "NY.GDP.MKTP.KD.ZG"
    assert observation["fallback_from"] == "imf_datamapper:NGDP_RPCH"
    assert result["suggestions"][0]["suggested_score"] == 2


def _snapshot_payload(score: float, rank: int) -> dict:
    return {
        "schema": "fisher-topdown-macro-snapshot-v1",
        "parameters": {"driver_outlook": {"gdp_growth": score}},
        "ranking": [
            {
                "sector_code": "MAT",
                "sector_name": "Nguyên vật liệu",
                "rank": rank,
                "score": 60.0 + score,
            }
        ],
    }


def test_macro_snapshot_store_is_append_only_and_comparable(tmp_path):
    store = TopDownMacroSnapshotStore(tmp_path / "macro.db")
    store.initialize()
    first = store.save(
        _snapshot_payload(0.0, 2),
        as_of_date="2026-08-01",
        snapshot_label="Baseline",
        save_reason="Start proxy",
        created_by="analyst",
        methodology_version="V1",
    )
    second = store.save(
        _snapshot_payload(1.0, 1),
        as_of_date="2026-08-24",
        snapshot_label="After update",
        save_reason="Macro changed",
        created_by="analyst",
        methodology_version="V1",
    )
    assert first["version_no"] == 1 and second["version_no"] == 2
    rows = store.list()
    assert [row["version_no"] for row in rows] == [2, 1]
    delta = compare_snapshots(rows[0], rows[1])
    assert delta["drivers"][0]["Thay đổi"] == 1.0
    assert delta["sectors"][0]["Hạng cũ"] == 2
    assert delta["sectors"][0]["Hạng mới"] == 1

    with sqlite3.connect(tmp_path / "macro.db") as conn, pytest.raises(
        sqlite3.IntegrityError, match="append-only"
    ):
        conn.execute("UPDATE topdown_macro_snapshots SET snapshot_label='mutated' WHERE id=1")


def test_fisher_page_and_checklist_routes_are_decoupled():
    dashboard = Path("module_topdown_dashboard.py").read_text(encoding="utf-8")
    legacy = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    fast = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")

    assert '"💾 Snapshot vĩ mô"' in dashboard
    assert '"🔄 Cập nhật dữ liệu vĩ mô mới nhất"' in dashboard
    assert '"🔄 Lấy dữ liệu & sàng lọc"' in dashboard
    assert '"🏢 Phân tích cổ phiếu 5 bước",' not in dashboard
    assert "_bridge_to_other_modules(" not in dashboard
    assert "topdown_phase9_applied" not in dashboard
    assert '"🔄 Latest Data Update"' not in legacy + fast
