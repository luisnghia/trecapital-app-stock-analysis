from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import uuid

import pytest
from streamlit.testing.v1 import AppTest

import module_topdown_engine as topdown
from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.evidence_workspace import create_evidence_version, create_source
from modules.investment_checklist.services.review_admin import delete_review_manually, review_delete_preview
from modules.investment_checklist.services.topdown_sector_context import (
    SNAPSHOT_SCHEMA,
    list_topdown_sector_snapshots,
    save_topdown_sector_snapshot,
)


CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase8.db", CATALOG)
    repo.initialize()
    return repo


def _seed(repo, suffix: str = "TOPDOWN"):
    company_ref_id = repo.upsert_company_ref(
        host_company_key=f"PHASE8:{suffix}",
        ticker="DCM",
        company_name="PetroVietnam Ca Mau Fertilizer",
        exchange="HOSE",
        industry_name="Hóa chất cơ bản/Phân bón",
        actor="test",
    )
    review_id = repo.create_review(
        company_ref_id,
        date(2026, 8, 24),
        analyst_user_id="analyst",
        review_reason="Phase 8 Fisher Top-down QA",
    )
    return company_ref_id, review_id


def _payload(*, benchmark_id: str = "vnindex_khoi_tao", requires_update: bool = True):
    inp = topdown.default_input()
    inp.benchmark_id = benchmark_id
    meta = next(item for item in topdown.benchmark_config()["benchmarks"] if item["id"] == benchmark_id)
    inp.benchmark_weights = dict(meta["ty_trong"])
    inp.trien_vong_driver = {
        driver["id"]: float((index % 5) - 2)
        for index, driver in enumerate(topdown.drivers_config()["drivers"])
    }
    ranking_df = topdown.cham_diem_tat_ca_nganh(inp)
    weights_df = topdown.bang_ty_trong_de_xuat(ranking_df, inp)
    ranking = [
        {
            "rank": int(row["Xếp hạng"]),
            "sector_code": str(row["Mã ngành"]),
            "sector_name": str(row["Ngành"]),
            "score": float(row["Điểm tổng hợp"]),
        }
        for _, row in ranking_df.iterrows()
    ]
    weights = [
        {
            "sector_code": str(row["Mã ngành"]),
            "sector_name": str(row["Ngành"]),
            "sector_score": float(row["Điểm tổng hợp"]),
            "benchmark_weight_pct": float(row["Tỷ trọng benchmark %"]),
            "proposed_weight_pct": float(row["Tỷ trọng đề xuất %"]),
            "tilt_pct": float(row["Độ lệch điểm %"]),
            "signal": str(row["Khuyến nghị"]),
        }
        for _, row in weights_df.iterrows()
    ]
    return {
        "schema": SNAPSHOT_SCHEMA,
        "methodology_version": topdown.APP_VERSION,
        "generated_at": "2026-08-24T08:00:00+00:00",
        "cycle_phase": inp.pha_chu_ky,
        "benchmark": {
            "id": benchmark_id,
            "name": meta["ten"],
            "reliability_note": meta["do_tin_cay"],
            "requires_update": requires_update,
            "weights": {key: float(value) for key, value in inp.benchmark_weights.items()},
        },
        "parameters": {
            "max_deviation_pct": inp.lech_toi_da,
            "scoring_weights": inp.trong_so,
            "driver_outlook": inp.trien_vong_driver,
        },
        "ranking": ranking,
        "weights": weights,
        "sync_checks": [],
        "source_mapping_sha256": hashlib.sha256(
            Path("docs/SOURCE_MAPPING_FISHER.md").read_bytes()
        ).hexdigest(),
    }


def test_phase8_actual_allocation_direction_matches_normalized_weight_delta():
    inp = topdown.default_input()
    inp.pha_chu_ky = "contraction"
    ranking_df = topdown.cham_diem_tat_ca_nganh(inp)
    weights_df = topdown.bang_ty_trong_de_xuat(ranking_df, inp)

    assert "Phân bổ thực tế" in weights_df.columns
    for _, row in weights_df.iterrows():
        delta = float(row["Độ lệch điểm %"])
        expected = "Tăng tỷ trọng" if delta > 0.05 else "Giảm tỷ trọng" if delta < -0.05 else "Bám benchmark"
        assert row["Phân bổ thực tế"] == expected

    # Reproduces the live acceptance case: a neutral pre-normalization signal can become
    # an actual overweight after underweighted sectors are normalized back to 100%.
    neutral_overweights = weights_df[
        (weights_df["Khuyến nghị"] == "Trung lập theo benchmark")
        & (weights_df["Phân bổ thực tế"] == "Tăng tỷ trọng")
    ]
    assert not neutral_overweights.empty


def test_phase8_unverified_snapshot_is_append_only_hashed_and_never_writes_assessment(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo)
    payload = _payload()
    snapshot_id = save_topdown_sector_snapshot(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        payload=payload,
        selected_sector_code="MAT",
        as_of_date=date(2026, 8, 24),
        horizon_months=12,
        benchmark_status="unverified",
        research_gaps=["Cập nhật tỷ trọng ngành từ HOSE."],
        analyst_confirmed=True,
        change_reason="Lưu baseline sector context",
        actor="analyst",
    )
    rows = list_topdown_sector_snapshots(repo, review_id)
    assert rows[0]["id"] == snapshot_id
    assert rows[0]["version_no"] == 1
    assert rows[0]["payload_hash_valid"] is True
    assert rows[0]["selected_sector_code"] == "MAT"
    assert any("chưa được kiểm chứng" in gap for gap in rows[0]["research_gaps"])
    with repo._conn() as c:
        assert c.execute(
            "SELECT COUNT(*) n FROM analyst_assessments WHERE review_id=?", (review_id,)
        ).fetchone()["n"] == 0
    with pytest.raises(ValidationError, match="đã được lưu"):
        save_topdown_sector_snapshot(
            repo,
            company_ref_id=company_ref_id,
            review_id=review_id,
            payload=payload,
            selected_sector_code="MAT",
            as_of_date=date(2026, 8, 24),
            benchmark_status="unverified",
            analyst_confirmed=True,
            change_reason="Duplicate",
        )


def test_phase8_verified_benchmark_requires_exact_verified_active_evidence(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo, "VERIFIED")
    payload = _payload()
    with pytest.raises(ValidationError, match="exact evidence"):
        save_topdown_sector_snapshot(
            repo,
            company_ref_id=company_ref_id,
            review_id=review_id,
            payload=payload,
            selected_sector_code="MAT",
            as_of_date=date(2026, 8, 24),
            benchmark_status="analyst_verified",
            analyst_confirmed=True,
            change_reason="Verify benchmark",
        )
    source_id = create_source(
        repo,
        company_ref_id=company_ref_id,
        source_type="regulator",
        title="HOSE sector weights 2026-08-24",
        publisher="HOSE",
        document_date=date(2026, 8, 24),
        reliability=5,
        actor="analyst",
    )
    evidence_id = create_evidence_version(
        repo,
        company_ref_id=company_ref_id,
        source_id=source_id,
        evidence_type="metric",
        excerpt="Tỷ trọng vốn hóa theo 11 nhóm ngành tại ngày 24/08/2026.",
        locator_text="Bảng sector weights",
        evidence_date=date(2026, 8, 24),
        verification_status="verified",
        direction="context",
        confidence=5,
        actor="analyst",
    )
    snapshot_id = save_topdown_sector_snapshot(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        payload=payload,
        selected_sector_code="MAT",
        as_of_date=date(2026, 8, 24),
        benchmark_status="analyst_verified",
        benchmark_source_evidence_id=evidence_id,
        analyst_confirmed=True,
        change_reason="Đối chiếu exact HOSE evidence",
        actor="analyst",
    )
    assert list_topdown_sector_snapshots(repo, review_id)[0]["id"] == snapshot_id


def test_phase8_version_snapshot_lock_and_manual_review_delete(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo, "LOCK")
    payload = _payload(benchmark_id="msci_world_2008", requires_update=False)
    first = save_topdown_sector_snapshot(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        payload=payload,
        selected_sector_code="MAT",
        as_of_date=date(2026, 8, 24),
        benchmark_status="historical_source",
        analyst_confirmed=True,
        change_reason="Historical Fisher benchmark context",
        actor="analyst",
    )
    second = save_topdown_sector_snapshot(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        payload=payload,
        selected_sector_code="IND",
        as_of_date=date(2026, 8, 24),
        benchmark_status="historical_source",
        analyst_confirmed=True,
        change_reason="Sửa mapping ngành doanh nghiệp",
        actor="analyst",
    )
    assert second > first
    immutable_id = repo.finalize_review(
        review_id, actor="analyst", finalize_reason="Khóa Phase 8 QA"
    )
    immutable = repo.get_snapshot(immutable_id)["payload"]
    assert immutable["fisher_topdown_sector_context"]["latest"]["id"] == second
    assert len(immutable["fisher_topdown_sector_context"]["version_history"]) == 2
    with pytest.raises(ValidationError, match="read-only"):
        save_topdown_sector_snapshot(
            repo,
            company_ref_id=company_ref_id,
            review_id=review_id,
            payload=payload,
            selected_sector_code="FIN",
            as_of_date=date(2026, 8, 24),
            benchmark_status="historical_source",
            analyst_confirmed=True,
            change_reason="Should be blocked",
        )
    preview = review_delete_preview(repo, review_id)
    assert preview["counts"]["topdown_sector_snapshots"] == 2
    delete_review_manually(
        repo,
        review_id,
        actor="admin",
        reason="Xóa Phase 8 QA",
        confirmation_text=f"XÓA REVIEW #{review_id}",
    )
    with repo._conn() as c:
        assert c.execute(
            "SELECT COUNT(*) n FROM topdown_sector_snapshots WHERE review_id=?", (review_id,)
        ).fetchone()["n"] == 0


def test_phase8_route_standalone_page_and_no_ai_no_assessment_contract():
    active_shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    service = Path("modules/investment_checklist/services/topdown_sector_context.py").read_text(encoding="utf-8").lower()
    ui = Path("modules/investment_checklist/ui/topdown_sector_context.py").read_text(encoding="utf-8").lower()
    dashboard = Path("module_topdown_dashboard.py").read_text(encoding="utf-8")
    nav = Path("tre_sidebar_nav.py").read_text(encoding="utf-8")
    assert '"🧭 Fisher Top-down & Sector"' not in active_shell
    assert 'elif section == "🧭 Fisher Top-down & Sector":' not in active_shell
    assert "pages/06_Phan_tich_TopDown_Nganh.py" in nav
    assert "render_bang_thuat_ngu(df)" in dashboard
    assert "table-layout:fixed" in dashboard
    assert "white-space:normal!important" in dashboard
    assert "overflow-wrap:anywhere" in dashboard
    assert "st.html(" in dashboard
    for forbidden in ("save_assessment(", "import openai", "import requests", "import httpx", "urlopen("):
        assert forbidden not in service and forbidden not in ui


def test_phase8_streamlit_workspace_smoke(tmp_path):
    repo = _repo(tmp_path)
    company_ref_id, review_id = _seed(repo, "UI")
    payload_path = tmp_path / "topdown_payload.json"
    payload_path.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
    app = f'''
import json
from pathlib import Path
import streamlit as st
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.topdown_sector_context import render_topdown_sector_context
repo = SQLiteChecklistRepository(r"{repo.db_path}", r"{CATALOG}")
repo.initialize()
st.session_state["topdown_governed_snapshot_payload"] = json.loads(Path(r"{payload_path}").read_text(encoding="utf-8"))
render_topdown_sector_context(repo, {company_ref_id}, repo.get_review({review_id}), "analyst")
'''
    at = AppTest.from_string(app, default_timeout=20).run()
    assert len(at.exception) == 0 and len(at.error) == 1
    assert "Benchmark đang là giá trị khởi tạo" in str(at.error[0].value)
    assert any("Fisher Top-down & Sector Context" in str(item.value) for item in at.markdown)


def test_postgres_phase8_end_to_end():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    company_ref_id, review_id = _seed(repo, uuid.uuid4().hex[:10].upper())
    snapshot_id = save_topdown_sector_snapshot(
        repo,
        company_ref_id=company_ref_id,
        review_id=review_id,
        payload=_payload(),
        selected_sector_code="MAT",
        as_of_date=date(2026, 8, 24),
        benchmark_status="unverified",
        analyst_confirmed=True,
        change_reason="Postgres Phase 8 QA",
        actor="test",
    )
    assert list_topdown_sector_snapshots(repo, review_id)[0]["id"] == snapshot_id
    repo.close()
