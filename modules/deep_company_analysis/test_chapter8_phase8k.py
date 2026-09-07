from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
import modules.deep_company_analysis.chapter8_official_source_adapters as direct
import modules.deep_company_analysis.chapter8_research_v56 as v56


def test_official_allow_list_accepts_exchange_staticfile_and_company_ir_but_rejects_secondary():
    assert direct.is_official_url("https://staticfile.hsx.vn/Uploads/UploadDocuments/x.pdf", "DGC")
    assert direct.is_official_url("https://ducgiangchem.vn/quan-he-co-dong/x.pdf", "DGC")
    assert direct.is_official_url("https://www.hnx.vn/x", "DGC")
    assert direct.is_official_url("https://ssc.gov.vn/x", "DGC")
    assert not direct.is_official_url("https://cafef.vn/x", "DGC")
    assert not direct.is_official_url("https://example.com/x", "DGC")


def test_normalize_manual_urls_dedupes_and_ignores_non_http():
    urls = direct.normalize_manual_urls("https://staticfile.hsx.vn/a.pdf\nhttps://staticfile.hsx.vn/a.pdf; file:///tmp/x.pdf")
    assert urls == ["https://staticfile.hsx.vn/a.pdf"]


def test_wrong_ticker_official_document_is_rejected(monkeypatch):
    monkeypatch.setattr(
        direct,
        "fetch_document_text",
        lambda *args, **kwargs: ("Mã chứng khoán: HPG. Công ty Cổ phần Tập đoàn Hòa Phát", "fixture PDF"),
    )
    docs, attempts = direct.fetch_official_url_documents(
        "DGC", ["https://staticfile.hsx.vn/Uploads/UploadDocuments/fake.pdf"]
    )
    assert docs == []
    assert attempts.iloc[0]["Official"] == "Yes"
    assert attempts.iloc[0]["Ticker Match"] == "No"
    assert "ticker mismatch" in str(attempts.iloc[0]["Status"]).lower()


def test_matching_official_document_is_retained(monkeypatch):
    monkeypatch.setattr(
        direct,
        "fetch_document_text",
        lambda *args, **kwargs: ("CÔNG TY HÓA CHẤT ĐỨC GIANG. Mã chứng khoán: DGC. khách hàng customer service.", "fixture PDF"),
    )
    docs, attempts = direct.fetch_official_url_documents(
        "DGC", ["https://staticfile.hsx.vn/Uploads/UploadDocuments/fake.pdf"]
    )
    assert len(docs) == 1
    assert attempts.iloc[0]["Ticker Match"] == "Yes"
    assert str(attempts.iloc[0]["Source Grade"]).startswith("A —")


def test_agent_keeps_candidates_analyst_verify_and_does_not_mutate_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(
        direct,
        "fetch_official_url_documents",
        lambda *args, **kwargs: ([{
            "url": "https://staticfile.hsx.vn/Uploads/UploadDocuments/fake.pdf",
            "title": "DGC disclosure",
            "text": "Mã chứng khoán: DGC. Customer service and customer feedback programs improved for customers.",
            "method": "fixture PDF",
            "depth": 0,
        }], pd.DataFrame([{
            "URL": "https://staticfile.hsx.vn/Uploads/UploadDocuments/fake.pdf",
            "Domain": "staticfile.hsx.vn",
            "Official": "Yes",
            "Ticker Match": "Yes",
            "Status": "Fetched",
            "Method": "fixture",
            "Source Grade": "A — Exchange/Regulator disclosure",
        }], columns=direct.MANUAL_URL_COLUMNS)),
    )
    result = direct.OfficialURLIngestionAgent(tmp_path).ingest(
        "DGC",
        ["https://staticfile.hsx.vn/Uploads/UploadDocuments/fake.pdf"],
        existing_candidates=pd.DataFrame(),
        manager_reference=pd.DataFrame(),
        max_targets=64,
    )
    assert not result.new_candidates.empty
    assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
    assert result.new_candidates["Select"].eq(False).all()
    assert "no auto-promotion" in result.note.lower()


def test_v56_wrapper_exposes_explicit_ingestion_without_parallel_store():
    source = inspect.getsource(v56).casefold() + inspect.getsource(direct.OfficialURLIngestionAgent).casefold()
    assert "promote_selected_candidates" not in source
    assert "save_record" not in source
    assert "analyst_assessment" not in source
    assert "no auto-promotion" in source or "no management score" in source


def test_source_lock_contract_survives_v56():
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert locks["q47_share_count_is_proof"] is False


def test_production_compatibility_can_route_to_v56_without_new_workspace_store():
    root = Path(__file__).resolve().parents[2]
    compatibility = (root / "modules/deep_company_analysis/chapter8_research_v52.py").read_text(encoding="utf-8")
    assert "chapter8_research_v56 import *" in compatibility
    assert "chapter8_store" not in inspect.getsource(direct).casefold()
