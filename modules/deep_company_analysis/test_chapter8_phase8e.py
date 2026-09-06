from __future__ import annotations

from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_integration import (
    build_chapter8_report_frames,
    build_chapter8_status_table,
    build_chapter8_summary,
)
from scripts.apply_chapter8_phase8e_v46 import patch_dca_page, patch_report_page


ROOT = Path(__file__).resolve().parents[2]


def test_empty_summary_is_descriptive_and_has_no_score_signal():
    payload = ch8.empty_payload("DGC", "DGC")
    summary = build_chapter8_summary(payload)
    assert summary["total_questions"] == 9
    assert summary["answered"] == 0
    assert summary["unknown"] == 9
    assert summary["automatic_management_score"] is False
    assert summary["automatic_investment_signal"] is False


def test_summary_counts_analyst_owned_state_without_overwriting_it():
    payload = ch8.empty_payload("DGC", "DGC")
    payload["question_status"]["Q39"] = "Answered"
    payload["question_status"]["Q40"] = "Partial"
    payload["question_status"]["Q47"] = "N/A"
    payload["confidence"]["Q39"] = "High"
    payload["analyst_assessment"]["Q39"] = "Analyst conclusion must remain verbatim."
    payload["evidence"] = [{"Question": "Q39", "Claim": "Promoted evidence"}]
    payload["research_gaps"] = [
        {"Question": "Q40", "Research Gap": "Need disclosure", "Status": "Open"},
        {"Question": "Q47", "Research Gap": "Resolved gap", "Status": "Resolved"},
    ]
    summary = build_chapter8_summary(payload)
    assert summary["answered"] == 1
    assert summary["partial"] == 1
    assert summary["not_applicable"] == 1
    assert summary["promoted_evidence"] == 1
    assert summary["research_gaps_total"] == 2
    assert summary["research_gaps_open"] == 1
    assert summary["analyst_conclusions"] == 1
    assert summary["confidence_known"] == 1
    assert payload["analyst_assessment"]["Q39"] == "Analyst conclusion must remain verbatim."


def test_status_table_preserves_all_q39_q47_in_source_order():
    payload = ch8.empty_payload("DGC", "DGC")
    frame = build_chapter8_status_table(payload)
    assert list(frame["Question"]) == list(ch8.QUESTION_KEYS)
    assert frame.shape[0] == 9
    assert "Analyst Assessment" in frame.columns


def test_report_frames_use_source_locked_columns():
    payload = ch8.empty_payload("DGC", "DGC")
    payload["q46_capital_allocation"] = [{"Action": "Pay dividends", "Amount (tỷ)": 100.0}]
    payload["q47_buyback_history"] = [{"Authorization": "Official disclosure"}]
    frames = build_chapter8_report_frames(payload)
    assert set(frames) == {"status", "evidence", "research_gaps", "capital_allocation", "buybacks"}
    assert list(frames["capital_allocation"].columns) == ch8.CAPITAL_ALLOCATION_COLUMNS
    assert list(frames["buybacks"].columns) == ch8.BUYBACK_HISTORY_COLUMNS
    assert "Management Score" not in frames["status"].columns


def test_phase8e_patch_is_idempotent_on_current_pages():
    dca = (ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py").read_text(encoding="utf-8")
    report = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")
    patched_dca = patch_dca_page(dca)
    patched_report = patch_report_page(report)
    assert patch_dca_page(patched_dca) == patched_dca
    assert patch_report_page(patched_report) == patched_report
    assert "render_chapter8_tab" in patched_dca
    assert "🧭 Chương 8 — Năng lực vận hành" in patched_dca
    assert "Deep Company Analysis — Chương 8" in patched_report


def test_no_numeric_management_score_or_investment_signal_is_created():
    payload = ch8.empty_payload("DGC", "DGC")
    summary = build_chapter8_summary(payload)
    forbidden = {"score", "management_score", "buy_signal", "sell_signal", "research_gate", "mos"}
    assert forbidden.isdisjoint(summary.keys())
    assert isinstance(build_chapter8_report_frames(payload)["status"], pd.DataFrame)
