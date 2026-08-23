from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.repositories.sqlite_repository import (
    SQLiteChecklistRepository,
    ValidationError,
)
from modules.investment_checklist.services.peer_snapshots import (
    get_peer_snapshot,
    list_peer_snapshots,
    normalize_peer_result,
    save_peer_snapshot,
)
from modules.investment_checklist.services.review_admin import (
    delete_review_manually,
    review_delete_preview,
    review_delete_token,
)


CATALOG = Path("modules/investment_checklist/catalog/question_catalog_prd.csv")


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "phase3b.db", CATALOG)
    repo.initialize()
    cid = repo.upsert_company_ref(
        host_company_key="HOSE:DCM",
        ticker="DCM",
        company_name="Phân bón Cà Mau",
        exchange="HOSE",
        industry_name="Phân bón",
        company_type="cyclical",
    )
    rid = repo.create_review(cid, "2026-06-30", "full", "analyst", review_reason="Đánh giá Q2/2026")
    return repo, cid, rid


def _result():
    return pd.DataFrame([
        {"Mã": "DGC", "Mã đang phân tích": False, "Điểm tổng hợp": 78.0, "MOS hiện tại %": 15.0, "Moat score": 80.0, "ROE %": 29.0},
        {"Mã": "DCM", "Mã đang phân tích": True, "Điểm tổng hợp": 75.0, "MOS hiện tại %": 22.0, "Moat score": 70.0, "ROE %": 20.0},
        {"Mã": "DPM", "Mã đang phân tích": False, "Điểm tổng hợp": 75.0, "MOS hiện tại %": 30.0, "Moat score": 65.0, "ROE %": 18.0},
    ])


def test_phase3b_normalizes_ranking_and_appends_audited_versions(tmp_path):
    repo, cid, rid = _repo(tmp_path)
    normalized = normalize_peer_result(_result(), base_ticker="DCM")
    assert normalized["Mã"].tolist() == ["DGC", "DPM", "DCM"]
    assert normalized["Xếp hạng"].tolist() == [1, 2, 3]
    assert bool(normalized.loc[normalized["Mã"].eq("DCM"), "Mã đang phân tích"].iloc[0])

    v1 = save_peer_snapshot(
        repo,
        company_ref_id=cid,
        review_id=rid,
        result=_result(),
        base_ticker="DCM",
        target_mos_pct=50,
        save_reason="Peer cùng phân ngành sau BCTC Q2/2026",
        actor="analyst",
    )
    v2 = save_peer_snapshot(
        repo,
        company_ref_id=cid,
        review_id=rid,
        result=_result().assign(**{"Điểm tổng hợp": [79.0, 76.0, 74.0]}),
        base_ticker="DCM",
        target_mos_pct=50,
        save_reason="Cập nhật lại điểm sau rà soát nguồn",
        actor="analyst",
    )
    assert (v1, v2) == (1, 2)
    history = list_peer_snapshots(repo, rid)
    assert [row["version_no"] for row in history] == [2, 1]
    latest = get_peer_snapshot(repo, rid)
    assert latest["payload"]["question_links"] == ["Q19", "Q22", "Q24", "Q26", "Q32"]
    assert latest["peer_count"] == 3
    assert len(latest["payload_hash"]) == 64
    assert any(log["entity_type"] == "peer_comparison_snapshot" for log in repo.list_audit_logs(cid))


def test_phase3b_is_embedded_in_immutable_review_and_locked_after_finalize(tmp_path):
    repo, cid, rid = _repo(tmp_path)
    save_peer_snapshot(
        repo,
        company_ref_id=cid,
        review_id=rid,
        result=_result(),
        base_ticker="DCM",
        target_mos_pct=30,
        save_reason="Chốt peer cho review",
        actor="analyst",
    )
    snapshot_id = repo.finalize_review(rid, actor="analyst", finalize_reason="Hoàn tất review Q2/2026")
    immutable = repo.get_snapshot(snapshot_id)
    assert immutable["payload"]["snapshot_schema"] == "phase1b-review-v7-evidence-peer-ai-management-monitoring-decision"
    peer = immutable["payload"]["peer_comparison"]
    assert peer["version_no"] == 1
    assert peer["payload"]["base_ticker"] == "DCM"
    with pytest.raises(ValidationError, match="finalize"):
        save_peer_snapshot(
            repo,
            company_ref_id=cid,
            review_id=rid,
            result=_result(),
            base_ticker="DCM",
            target_mos_pct=30,
            save_reason="Không được ghi đè",
            actor="analyst",
        )


def test_phase3b_review_delete_counts_and_removes_owned_snapshots(tmp_path):
    repo, cid, rid = _repo(tmp_path)
    save_peer_snapshot(
        repo,
        company_ref_id=cid,
        review_id=rid,
        result=_result(),
        base_ticker="DCM",
        target_mos_pct=50,
        save_reason="Dữ liệu test cần xóa cùng review",
        actor="analyst",
    )
    preview = review_delete_preview(repo, rid)
    assert preview["counts"]["peer_snapshots"] == 1
    delete_review_manually(
        repo,
        rid,
        actor="analyst",
        reason="Xóa review test Phase 3B",
        confirmation_text=review_delete_token(rid),
    )
    with repo._conn() as c:
        assert c.execute("SELECT COUNT(*) n FROM peer_comparison_snapshots WHERE review_id=?", (rid,)).fetchone()["n"] == 0


def test_phase3b_rejects_wrong_or_oversized_peer_sets(tmp_path):
    repo, cid, rid = _repo(tmp_path)
    with pytest.raises(ValidationError, match="không chứa"):
        save_peer_snapshot(
            repo,
            company_ref_id=cid,
            review_id=rid,
            result=_result()[_result()["Mã"].ne("DCM")],
            base_ticker="DCM",
            target_mos_pct=50,
            save_reason="Sai mã gốc",
            actor="analyst",
        )
    too_many = pd.DataFrame([
        {
            "Mã": "DCM" if i == 0 else f"A{i}",
            "Mã đang phân tích": i == 0,
            "Điểm tổng hợp": 80 - i,
        }
        for i in range(11)
    ])
    with pytest.raises(ValidationError, match="tối đa"):
        normalize_peer_result(too_many, base_ticker="DCM")

    fpt_result_with_dcm_peer = _result().copy()
    fpt_result_with_dcm_peer["Mã đang phân tích"] = fpt_result_with_dcm_peer["Mã"].eq("DGC")
    with pytest.raises(ValidationError, match="được tạo cho mã gốc DGC"):
        normalize_peer_result(fpt_result_with_dcm_peer, base_ticker="DCM")


def test_phase3b_streamlit_ui_renders_without_network_or_assessment_write(tmp_path):
    db_path = (tmp_path / "ui_phase3b.db").as_posix()
    app = f'''
import pandas as pd
import streamlit as st
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.ui.peer_snapshot import render_peer_snapshot

repo = SQLiteChecklistRepository(r"{db_path}", r"modules/investment_checklist/catalog/question_catalog_prd.csv")
repo.initialize()
cid = repo.upsert_company_ref(host_company_key="HOSE:DCM", ticker="DCM", company_name="DCM")
reviews = repo.list_reviews(cid)
rid = reviews[0]["id"] if reviews else repo.create_review(cid, "2026-06-30", "full", "analyst", review_reason="UI smoke")
review = repo.get_review(rid)
st.session_state["peer_compare_result"] = pd.DataFrame([
    {{"Mã":"DCM","Mã đang phân tích":True,"Điểm tổng hợp":75,"MOS hiện tại %":20,"Moat score":70}},
    {{"Mã":"DPM","Mã đang phân tích":False,"Điểm tổng hợp":72,"MOS hiện tại %":30,"Moat score":65}},
])
st.session_state["module3_base_ticker"] = "DCM"
render_peer_snapshot(repo, company_ref_id=cid, review=review, base_ticker="DCM", actor="analyst")
'''
    at = AppTest.from_string(app, default_timeout=15).run()
    assert len(at.exception) == 0
    assert any("Peer Snapshot & Ranking" in str(item.value) for item in at.markdown)
    assert len(at.dataframe) >= 1


def test_phase3b_source_contract_has_no_network_ai_or_automatic_assessment_write():
    service = Path("modules/investment_checklist/services/peer_snapshots.py").read_text(encoding="utf-8").lower()
    ui = Path("modules/investment_checklist/ui/peer_snapshot.py").read_text(encoding="utf-8").lower()
    industry_ui = Path("modules/investment_checklist/ui/industry_overlay.py").read_text(encoding="utf-8")
    shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import httpx", "urllib.request", "openai", "anthropic"):
        assert forbidden not in service
        assert forbidden not in ui
    assert "save_assessment(" not in service
    assert "save_assessment(" not in ui
    assert "render_peer_snapshot" in industry_ui
    assert "company_ref_id=company_ref_id" in shell and "review=review" in shell
