from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

from adapters.module2_web_research import WebEvidenceAgent
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
import modules.deep_company_analysis.chapter8_official_archive_retrieval as archive
import modules.deep_company_analysis.chapter8_research_v55 as v55


def _target(question: str, key: str, label: str, terms: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Question": question,
                "Dimension Key": key,
                "Dimension": label,
                "Query Terms": terms,
                "Next Action": "fixture",
                "Source Locked": "Yes",
                "Boundary": "Coverage audit only — not a management score; analyst verification/promotion required.",
            }
        ]
    )


def _manager_reference() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Manager ID": "MGR-001", "Manager": "Nguyen Van A", "Role": "CEO", "Source": "Chapter 7"},
            {"Manager ID": "MGR-002", "Manager": "Tran Thi B", "Role": "CFO", "Source": "Chapter 7"},
        ]
    )


def test_official_archive_domains_are_only_trecapital_official_disclosure_domains():
    assert archive.OFFICIAL_ARCHIVE_DOMAINS
    assert {"hsx.vn", "hnx.vn", "ssc.gov.vn"}.intersection(set(archive.OFFICIAL_ARCHIVE_DOMAINS))
    allowed = archive.allowed_archive_domains("DGC")
    assert "ducgiangchem.vn" in allowed
    assert any(domain in allowed for domain in archive.OFFICIAL_ARCHIVE_DOMAINS)
    assert "cafef.vn" not in archive.OFFICIAL_ARCHIVE_DOMAINS
    assert "vietstock.vn" not in archive.OFFICIAL_ARCHIVE_DOMAINS


def test_archive_query_plan_is_site_restricted_and_question_scoped():
    targets = pd.concat(
        [
            _target("Q39", "customers", "Customers", "customer | khách hàng"),
            _target("Q47", "authorization_program", "Authorization / program", "buyback | cổ phiếu quỹ"),
        ],
        ignore_index=True,
    )
    plan = archive.build_archive_query_plan("DGC", "CTCP Tập đoàn Hóa chất Đức Giang", targets, max_queries=6)
    assert not plan.empty
    assert set(plan["Question"]) == {"Q39", "Q47"}
    assert plan["Query"].astype(str).str.startswith("site:").all()
    assert plan["Boundary"].astype(str).str.contains("analyst verification", case=False).all()
    q47 = " ".join(plan.loc[plan["Question"].eq("Q47"), "Query"].astype(str)).casefold()
    assert "buyback" in q47 or "repurchase" in q47 or "cổ phiếu quỹ" in q47


def test_archive_search_drops_nonofficial_results(monkeypatch, tmp_path):
    targets = _target("Q39", "customers", "Customers", "customer | khách hàng")
    plan = archive.build_archive_query_plan("DGC", "Đức Giang", targets, max_queries=1)

    def fake_ddg(self, client, q, max_results):  # noqa: ARG001
        return [
            {
                "Tiêu đề": "Official archive result",
                "Nguồn/URL": "https://ducgiangchem.vn/cbtt/annual-report-2024.pdf",
                "Trích yếu": "customer khách hàng annual report",
            },
            {
                "Tiêu đề": "Secondary article",
                "Nguồn/URL": "https://cafef.vn/dgc-example.chn",
                "Trích yếu": "customer khách hàng",
            },
        ], {}

    monkeypatch.setattr(WebEvidenceAgent, "_search_duckduckgo", fake_ddg)
    rows = archive.search_official_archives("DGC", plan, tmp_path, max_results_per_query=3)
    assert len(rows) == 1
    assert rows.iloc[0]["Domain"] == "ducgiangchem.vn"
    assert str(rows.iloc[0]["Source Grade"]).startswith("A —")


def test_historical_official_text_becomes_candidate_only_and_stays_unselected():
    documents = [
        {
            "url": "https://hsx.vn/Modules/CMS/Web/DownloadFile?id=dgc-2024",
            "title": "DGC annual disclosure 2024",
            "text": "The company expanded customer service and customer feedback programs for key customers.",
            "method": "fixture archive",
            "depth": "archive-search",
        }
    ]
    targets = _target("Q39", "customers", "Customers", "customer | khách hàng")
    candidates = archive.archive_documents_to_gap_candidates(documents, "DGC", targets, pd.DataFrame())
    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["Question"] == "Q39"
    assert row["Subtopic"] == "Customers"
    assert row["Status"] == "Candidate — analyst verify"
    assert bool(row["Select"]) is False
    assert "Phase 8J" in str(row["Source Method"])
    assert str(row["Source Grade"]).startswith("A —")


def test_q47_share_count_decline_alone_is_not_archive_buyback_evidence():
    documents = [
        {
            "url": "https://hsx.vn/disclosure/dgc-share-count-2024",
            "title": "DGC share count disclosure",
            "text": "Shares outstanding declined from 400 million to 380 million shares during 2024.",
            "method": "fixture archive",
            "depth": "archive-search",
        }
    ]
    targets = _target("Q47", "execution_shares_cash", "Execution / shares / cash", "share count | buyback")
    candidates = archive.archive_documents_to_gap_candidates(documents, "DGC", targets, pd.DataFrame())
    assert candidates.empty
    assert validate_source_locks()["q47_share_count_is_proof"] is False


def test_q47_explicit_historical_repurchase_can_be_candidate_but_not_promoted():
    documents = [
        {
            "url": "https://hsx.vn/disclosure/dgc-buyback-2023.pdf",
            "title": "DGC repurchase disclosure 2023",
            "text": "The issuer approved a share repurchase program and disclosed the maximum cash amount for the buyback.",
            "method": "fixture archive PDF",
            "depth": "archive-search",
        }
    ]
    targets = _target("Q47", "authorization_program", "Authorization / program", "buyback | repurchase program")
    candidates = archive.archive_documents_to_gap_candidates(documents, "DGC", targets, pd.DataFrame())
    assert len(candidates) >= 1
    assert candidates["Status"].eq("Candidate — analyst verify").all()
    assert candidates["Select"].eq(False).all()


def test_archive_manager_scope_can_only_reuse_chapter7_manager_identity():
    documents = [
        {
            "url": "https://hsx.vn/disclosure/dgc-dividend-2024.pdf",
            "title": "DGC dividend disclosure",
            "text": "Nguyen Van A presented the dividend proposal and capital allocation plan to shareholders.",
            "method": "fixture archive PDF",
            "depth": "archive-search",
        }
    ]
    targets = _target("Q46", "shearn_action_3", "Pay dividends", "dividend | cổ tức")
    candidates = archive.archive_documents_to_gap_candidates(documents, "DGC", targets, _manager_reference())
    assert not candidates.empty
    assert set(candidates["Manager ID"].astype(str)) == {"MGR-001"}
    assert set(candidates["Manager"].astype(str)) == {"Nguyen Van A"}


def test_archive_agent_merges_without_touching_analyst_workspace(monkeypatch, tmp_path):
    targets = _target("Q39", "customers", "Customers", "customer | khách hàng")
    plan = pd.DataFrame(
        [
            {
                "Question": "Q39",
                "Open Dimensions": 1,
                "Route": "Company historical IR",
                "Domain": "ducgiangchem.vn",
                "Query": 'site:ducgiangchem.vn "DGC" customer 2024',
                "Boundary": archive.BOUNDARY,
            }
        ]
    )
    search_rows = pd.DataFrame(
        [
            {
                "Question": "Q39",
                "Route": "Company historical IR",
                "Domain": "ducgiangchem.vn",
                "Title": "Customer archive",
                "URL": "https://ducgiangchem.vn/archive/customer-2024.pdf",
                "Snippet": "customer feedback",
                "Query": "fixture",
                "Source Grade": "A — Company/Official disclosure",
            }
        ]
    )
    documents = [
        {
            "url": "https://ducgiangchem.vn/archive/customer-2024.pdf",
            "title": "Customer archive",
            "text": "Customer service and customer feedback were reviewed by the operating team.",
            "method": "fixture archive PDF",
            "depth": "archive-search",
        }
    ]
    attempts = pd.DataFrame(
        [
            {
                "URL": documents[0]["url"],
                "Domain": "ducgiangchem.vn",
                "Status": "Fetched",
                "Method": "fixture",
                "Source Grade": "A — Company/Official disclosure",
            }
        ]
    )

    monkeypatch.setattr(archive, "build_official_deep_targets", lambda candidates, max_targets=48: targets)
    monkeypatch.setattr(archive, "build_archive_query_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(archive, "search_official_archives", lambda *args, **kwargs: search_rows)
    monkeypatch.setattr(archive, "fetch_archive_documents", lambda *args, **kwargs: (documents, attempts))

    result = archive.OfficialArchiveRetrievalAgent(tmp_path).search(
        "DGC",
        "Đức Giang",
        existing_candidates=pd.DataFrame(),
        manager_reference=pd.DataFrame(),
        max_targets=1,
        max_queries=1,
        max_documents=1,
    )
    assert len(result.new_candidates) == 1
    assert len(result.merged_candidates) == 1
    assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
    assert "no management score" in result.note.lower()


def test_v55_wrapper_compatibility_and_source_locks_preserve_analyst_control():
    source = inspect.getsource(v55).casefold() + inspect.getsource(archive.OfficialArchiveRetrievalAgent).casefold()
    assert "promote_selected_candidates" not in source
    assert "save_record" not in source
    assert "analyst_assessment" not in source
    assert "no management score" in source
    root = Path(__file__).resolve().parents[2]
    compatibility = (root / "modules/deep_company_analysis/chapter8_research_v52.py").read_text(encoding="utf-8")
    page_support = (root / "modules/deep_company_analysis/chapter8_page_support.py").read_text(encoding="utf-8")
    assert "chapter8_research_v53 import *" in compatibility
    assert "chapter8_research_v54 import *" in compatibility
    assert "chapter8_research_v55 import *" in compatibility
    assert "chapter8_research_v52 import CANDIDATE_COLUMNS, Chapter8ResearchAgent" in page_support

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert locks["q47_share_count_is_proof"] is False
