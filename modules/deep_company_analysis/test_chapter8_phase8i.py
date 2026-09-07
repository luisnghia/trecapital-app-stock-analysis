from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
import modules.deep_company_analysis.chapter8_official_deep_retrieval as deep
import modules.deep_company_analysis.chapter8_research_v54 as v54


def _target(question: str, key: str, label: str) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Question": question,
            "Dimension Key": key,
            "Dimension": label,
            "Query Terms": "fixture",
            "Next Action": "fixture",
            "Source Locked": "Yes",
            "Boundary": "Coverage audit only — not a management score; analyst verification/promotion required.",
        }
    ])


def _manager_reference() -> pd.DataFrame:
    return pd.DataFrame([
        {"Manager ID": "MGR-001", "Manager": "Nguyen Van A", "Role": "CEO", "Source": "Chapter 7"},
        {"Manager ID": "MGR-002", "Manager": "Tran Thi B", "Role": "CFO", "Source": "Chapter 7"},
    ])


def test_official_deep_targets_include_only_open_source_locked_dimensions():
    targets = deep.build_official_deep_targets(pd.DataFrame(), max_targets=64)
    assert not targets.empty
    assert targets["Question"].isin(ch8.QUESTION_KEYS).all()
    assert targets["Source Locked"].eq("Yes").all()
    assert "discipline_hurdle_context" not in set(targets["Dimension Key"].astype(str))
    assert targets["Boundary"].astype(str).str.contains("not a management score", case=False).all()
    q43 = targets[targets["Question"].eq("Q43")]
    q46 = targets[targets["Question"].eq("Q46")]
    assert len(q43) == 14
    assert len(q46) == 5


def test_direct_official_text_closes_only_matching_target_and_remains_analyst_verify():
    documents = [{
        "url": "https://ducgiangchem.vn/annual-report-2026.pdf",
        "title": "Annual report 2026",
        "text": "The company expanded customer service and customer feedback programs for key customers.",
        "method": "fixture PDF",
        "depth": 2,
    }]
    targets = _target("Q39", "customers", "Customers")
    candidates = deep.documents_to_gap_candidates(documents, "DGC", targets, pd.DataFrame())
    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["Question"] == "Q39"
    assert row["Subtopic"] == "Customers"
    assert row["Status"] == "Candidate — analyst verify"
    assert bool(row["Select"]) is False
    assert "official deep retrieval" in str(row["Source Method"]).lower()
    assert str(row["Source Grade"]).startswith("A —")


def test_q47_share_count_decline_alone_is_not_deep_retrieval_buyback_evidence():
    documents = [{
        "url": "https://ducgiangchem.vn/share-count-2026",
        "title": "Share count update",
        "text": "Shares outstanding declined from 400 million to 380 million shares during 2026.",
        "method": "fixture HTML",
        "depth": 1,
    }]
    targets = _target("Q47", "execution_shares_cash", "Execution / shares / cash")
    candidates = deep.documents_to_gap_candidates(documents, "DGC", targets, pd.DataFrame())
    assert candidates.empty
    assert validate_source_locks()["q47_share_count_is_proof"] is False


def test_q47_explicit_repurchase_language_can_be_candidate_but_not_auto_promoted():
    documents = [{
        "url": "https://ducgiangchem.vn/buyback-resolution-2026.pdf",
        "title": "Buyback resolution 2026",
        "text": "The company approved a share repurchase program and disclosed the maximum cash amount for the buyback.",
        "method": "fixture PDF",
        "depth": 2,
    }]
    targets = _target("Q47", "authorization_program", "Authorization / program")
    candidates = deep.documents_to_gap_candidates(documents, "DGC", targets, pd.DataFrame())
    assert len(candidates) >= 1
    assert candidates["Status"].eq("Candidate — analyst verify").all()
    assert candidates["Select"].eq(False).all()


def test_manager_scope_can_only_match_confirmed_chapter7_manager_id():
    documents = [{
        "url": "https://ducgiangchem.vn/agm-2026.pdf",
        "title": "AGM 2026",
        "text": "Nguyen Van A presented the capital allocation plan and dividend proposal to shareholders.",
        "method": "fixture PDF",
        "depth": 2,
    }]
    targets = _target("Q46", "shearn_action_3", "Pay dividends")
    candidates = deep.documents_to_gap_candidates(documents, "DGC", targets, _manager_reference())
    assert not candidates.empty
    assert set(candidates["Manager ID"].astype(str)) == {"MGR-001"}
    assert set(candidates["Manager"].astype(str)) == {"Nguyen Van A"}


def test_deep_agent_merges_candidates_without_touching_workspace(monkeypatch, tmp_path):
    documents = [{
        "url": "https://ducgiangchem.vn/customer-report-2026.pdf",
        "title": "Customer report 2026",
        "text": "Customer service and khách hàng feedback were reviewed by the operating team.",
        "method": "fixture PDF",
        "depth": 2,
    }]

    def fake_discover(ticker, targets, **kwargs):  # noqa: ARG001
        attempts = pd.DataFrame([{
            "URL": documents[0]["url"],
            "Domain": "ducgiangchem.vn",
            "Status": "Fetched",
            "Method": "fixture",
            "Source Grade": "A — Company/Official disclosure",
        }])
        return documents, attempts, "fixture deep retrieval"

    def fake_targets(candidates, max_targets=48):  # noqa: ARG001
        return _target("Q39", "customers", "Customers")

    monkeypatch.setattr(deep, "discover_official_document_pool", fake_discover)
    monkeypatch.setattr(deep, "build_official_deep_targets", fake_targets)
    result = deep.OfficialDeepRetrievalAgent(tmp_path).search(
        "DGC",
        existing_candidates=pd.DataFrame(),
        manager_reference=pd.DataFrame(),
        max_targets=1,
    )
    assert len(result.new_candidates) == 1
    assert len(result.merged_candidates) == 1
    assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
    assert "no management score" in result.note.lower()


def test_v54_wrapper_and_production_compatibility_preserve_analyst_boundary():
    source = inspect.getsource(v54).casefold() + inspect.getsource(deep.OfficialDeepRetrievalAgent).casefold()
    assert "promote_selected_candidates" not in source
    assert "save_record" not in source
    assert "analyst_assessment" not in source
    assert "no management score" in source
    root = Path(__file__).resolve().parents[2]
    compatibility = (root / "modules/deep_company_analysis/chapter8_research_v52.py").read_text(encoding="utf-8")
    page_support = (root / "modules/deep_company_analysis/chapter8_page_support.py").read_text(encoding="utf-8")
    assert "chapter8_research_v54 import *" in compatibility
    assert "chapter8_research_v52 import CANDIDATE_COLUMNS, Chapter8ResearchAgent" in page_support


def test_source_lock_contract_remains_q43_fourteen_q46_five_and_q47_explicit():
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert locks["q47_share_count_is_proof"] is False
