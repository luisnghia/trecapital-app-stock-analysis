from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

from adapters.module2_web_research import EvidenceResult
import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter8_gap_directed_research as gdr
from modules.deep_company_analysis.chapter8_gap_engine import build_dimension_coverage, validate_source_locks
import modules.deep_company_analysis.chapter8_research_v53 as v53


def _candidate(question: str, text: str, *, subtopic: str = "", grade: str = "A — Company/Official disclosure") -> dict:
    return {
        "Select": False,
        "Candidate ID": f"{question}-{abs(hash(text))}",
        "Question": question,
        "Manager ID": "",
        "Manager": "",
        "Subtopic": subtopic,
        "Direction": "Neutral / context — analyst assess",
        "Source Grade": grade,
        "Explicitness": "fixture",
        "Source Title": "Official disclosure",
        "Source URL / File": "https://ducgiangchem.vn/disclosure",
        "Source Date": "",
        "As-of Date": "2026",
        "Evidence Text / Reference": text,
        "Source Method": "fixture",
        "Data Origin": "fixture",
        "Status": "Candidate — analyst verify",
    }


def _manager_reference() -> pd.DataFrame:
    return pd.DataFrame([
        {"Manager ID": "MGR-001", "Manager": "Nguyen Van A", "Role": "CEO", "Source": "Chapter 7"},
        {"Manager ID": "MGR-002", "Manager": "Tran Thi B", "Role": "CFO", "Source": "Chapter 7"},
    ])


def test_gap_target_plan_uses_only_open_source_locked_dimensions():
    candidates = pd.DataFrame([
        _candidate("Q43", "The company expanded employee training and đào tạo programs."),
        _candidate("Q46", "The AGM approved a cash dividend / cổ tức for 2026."),
    ])
    targets = gdr.build_gap_targets(candidates, _manager_reference(), max_targets=20)
    assert not targets.empty
    assert "training_resources" not in set(targets["Dimension Key"])
    assert "shearn_action_3" not in set(targets["Dimension Key"])
    assert "discipline_hurdle_context" not in set(targets["Dimension Key"])
    assert targets["Boundary"].str.contains("not a management score", case=False).all()


def test_gap_target_plan_round_robins_across_questions_instead_of_first_question_only():
    targets = gdr.build_gap_targets(pd.DataFrame(), pd.DataFrame(), max_targets=9)
    assert len(targets) == 9
    assert list(targets["Question"]) == list(ch8.QUESTION_KEYS)


def test_manager_scoped_query_uses_only_confirmed_chapter7_names():
    target = {
        "Question": "Q46",
        "Dimension Key": "shearn_action_1",
    }
    with_manager = gdr.build_target_queries("DGC", "CTCP Tập đoàn Hóa chất Đức Giang", target, _manager_reference())
    without_manager = gdr.build_target_queries("DGC", "CTCP Tập đoàn Hóa chất Đức Giang", target, pd.DataFrame())
    assert any("Nguyen Van A" in q or "Tran Thi B" in q for q in with_manager)
    assert all("Nguyen Van A" not in q and "Tran Thi B" not in q for q in without_manager)
    assert all("CEO" not in q and "CFO" not in q for q in without_manager)


def test_target_row_converter_requires_dimension_match_and_keeps_analyst_verify_status():
    raw = pd.DataFrame([
        {
            "Tiêu đề": "DGC customer policy",
            "Nguồn/URL": "https://ducgiangchem.vn/customer-policy",
            "Trích yếu": "The company described customer service and khách hàng commitments.",
            "Trạng thái": "Tìm thấy",
        },
        {
            "Tiêu đề": "DGC unrelated item",
            "Nguồn/URL": "https://ducgiangchem.vn/unrelated",
            "Trích yếu": "This disclosure only discusses a factory address.",
            "Trạng thái": "Tìm thấy",
        },
    ])
    target = {"Question": "Q39", "Dimension Key": "customers"}
    candidates = gdr.target_rows_to_candidates(raw, "DGC", target, pd.DataFrame())
    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["Subtopic"] == "Customers"
    assert row["Status"] == "Candidate — analyst verify"
    assert row["Select"] is False or bool(row["Select"]) is False
    assert "gap-directed" in row["Source Method"].lower()


def test_q47_share_count_decline_is_not_convertible_to_explicit_buyback_target():
    raw = pd.DataFrame([
        {
            "Tiêu đề": "DGC share count update",
            "Nguồn/URL": "https://ducgiangchem.vn/share-count",
            "Trích yếu": "Shares outstanding declined from 400 million to 380 million shares.",
            "Trạng thái": "Tìm thấy",
        },
    ])
    target = {"Question": "Q47", "Dimension Key": "authorization_program"}
    candidates = gdr.target_rows_to_candidates(raw, "DGC", target, pd.DataFrame())
    assert candidates.empty
    assert validate_source_locks()["q47_share_count_is_proof"] is False


def test_gap_directed_agent_can_close_only_the_targeted_dimension_without_auto_promotion(monkeypatch):
    def fake_search(self, ticker: str, company_name: str = "", max_results_per_query: int = 5):  # noqa: ARG001
        table = pd.DataFrame([
            {
                "Tiêu đề": "DGC customer commitment",
                "Nguồn/URL": "https://ducgiangchem.vn/customer-commitment",
                "Tên miền": "ducgiangchem.vn",
                "Trích yếu": "DGC described customer service and khách hàng commitments in its 2026 disclosure.",
                "Trạng thái": "Tìm thấy",
                "Truy vấn": "fixture",
            },
        ])
        return EvidenceResult(table=table, raw_path=None, note="fixture")

    monkeypatch.setattr(gdr._GapTargetAgent, "search", fake_search)
    agent = gdr.GapDirectedResearchAgent("/tmp/ch8_gap_directed_test")
    result = agent.search(
        "DGC",
        "CTCP Tập đoàn Hóa chất Đức Giang",
        existing_candidates=pd.DataFrame(),
        manager_reference=pd.DataFrame(),
        max_targets=1,
        max_results_per_query=1,
    )
    before = build_dimension_coverage(pd.DataFrame())
    before_open = int((before["Source Locked"].eq("Yes") & ~before["Coverage Status"].eq("Candidate coverage — analyst verify")).sum())
    after_open = int((result.after_coverage["Source Locked"].eq("Yes") & ~result.after_coverage["Coverage Status"].eq("Candidate coverage — analyst verify")).sum())
    assert len(result.new_candidates) == 1
    assert before_open - after_open == 1
    assert result.new_candidates["Status"].eq("Candidate — analyst verify").all()
    assert result.new_candidates["Select"].eq(False).all()


def test_v53_wrapper_does_not_write_workspace_or_create_investment_output():
    source = inspect.getsource(v53).casefold() + inspect.getsource(gdr.GapDirectedResearchAgent).casefold()
    assert "promote_selected_candidates" not in source
    assert "save_record" not in source
    assert "analyst_assessment" not in source
    assert "investment signal" in source  # only the explicit non-output boundary text
    assert "no management score" in source


def test_existing_chapter8_ui_is_routed_to_v53_without_parallel_state_store():
    root = Path(__file__).resolve().parents[2]
    page_support = (root / "modules/deep_company_analysis/chapter8_page_support.py").read_text(encoding="utf-8")
    compatibility = (root / "modules/deep_company_analysis/chapter8_research_v52.py").read_text(encoding="utf-8")
    assert "chapter8_research_v52 import CANDIDATE_COLUMNS, Chapter8ResearchAgent" in page_support
    assert "chapter8_research_v53 import *" in compatibility
    assert "chapter8_store" not in inspect.getsource(gdr).casefold()


def test_source_locks_remain_q43_fourteen_q46_five_and_no_sixth_action():
    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert "discipline" in " ".join(locks["q46_context_dimensions"]).lower()
