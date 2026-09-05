from copy import deepcopy
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter6 as ch6
from modules.deep_company_analysis.chapter6_evidence import (
    classify_evidence_rows,
    evidence_quality_summary,
    manipulation_snapshot_candidates,
    manipulation_snapshot_table,
    merge_candidates_into_record,
    research_gaps,
)


def test_external_candidate_classification_uses_returned_text_and_quality_grades():
    raw = pd.DataFrame([
        {"_Focus": "Q28", "Tiêu đề": "DGC annual report recurring revenue contract renewal", "Trích yếu": "contracted revenue and renewal terms", "Nguồn/URL": "https://ducgiangchem.vn/quan-he-co-dong/report", "Tên miền": "ducgiangchem.vn", "Nhóm thông tin": "Tin tham khảo", "Trạng thái": "Tìm thấy"},
        {"_Focus": "Q31", "Tiêu đề": "DGC working capital", "Trích yếu": "inventory and receivable movements", "Nguồn/URL": "https://finance.vietstock.vn/DGC", "Tên miền": "finance.vietstock.vn", "Nhóm thông tin": "Dữ liệu/tin tài chính", "Trạng thái": "Tìm thấy"},
    ])
    out = classify_evidence_rows(raw, "DGC")
    assert len(out) == 2
    assert out.iloc[0]["Evidence Quality"].startswith("A —")
    assert out.iloc[1]["Evidence Quality"].startswith("B —")
    assert out["Status"].eq("Candidate — analyst verify").all()


def test_query_or_direct_link_without_evidence_text_does_not_become_candidate():
    raw = pd.DataFrame([
        {"_Focus": "Q32", "Tiêu đề": "DGC investor relations", "Trích yếu": "open this source to verify", "Nguồn/URL": "https://ducgiangchem.vn", "Tên miền": "ducgiangchem.vn", "Nhóm thông tin": "Nguồn doanh nghiệp/IR", "Trạng thái": "Link nguồn ưu tiên", "Truy vấn": "maintenance capex"},
    ])
    assert classify_evidence_rows(raw, "DGC").empty


def test_merge_only_changes_evidence_and_research_gaps_not_analyst_conclusions():
    record = ch6.empty_payload("DGC")
    record["q27"]["overall_assessment"] = "Balanced"
    record["q29"]["cycle_classification"] = "Mixed"
    record["earnings_distribution_width"] = "Medium"
    before = deepcopy(record)
    candidates = pd.DataFrame([{
        "Question": "Q27", "Subtopic": "Audit / accounting changes", "Direction": "Neutral / context",
        "Evidence Quality": "A — Company/Official disclosure", "Explicitness": "Explicit text candidate",
        "Period Candidate": "2025", "Title": "Annual report", "URL": "https://example.com/report",
        "Snippet": "accounting policy disclosure", "Source Group": "Official", "Source Method": "Phase 6C",
        "Data Origin": "External evidence candidate — analyst verification required", "Status": "Candidate — analyst verify",
    }])
    gaps = research_gaps(candidates)
    merged = merge_candidates_into_record(record, candidates, gaps)
    assert merged["q27"] == before["q27"]
    assert merged["q29"] == before["q29"]
    assert merged["earnings_distribution_width"] == "Medium"
    assert len(merged["evidence_matrix"]) == 1


def test_merge_deduplicates_same_candidate():
    record = ch6.empty_payload("DGC")
    candidate = pd.DataFrame([{
        "Question": "Q32", "Subtopic": "Maintenance vs growth capex", "Direction": "Neutral / context",
        "Evidence Quality": "B — Independent financial source/research", "Period Candidate": "2025",
        "Title": "Capex note", "URL": "https://example.com/capex", "Snippet": "maintenance capex disclosure",
        "Data Origin": "External evidence candidate — analyst verification required",
    }])
    once = merge_candidates_into_record(record, candidate)
    twice = merge_candidates_into_record(once, candidate)
    assert len(twice["evidence_matrix"]) == 1


def test_manipulation_bridge_is_read_only_and_ttm_guardrail_is_explicit():
    snapshot = {"ticker": "DGC", "layers": [
        {"layer": "1. Beneish M-Score", "latest_score": -1.85, "latest_risk": "Cảnh báo", "latest_period": "2025", "latest_note": "Review"},
        {"layer": "2. Accrual Quality / Sloan", "latest_score": 0.08, "latest_risk": "Trung bình", "latest_period": "2025", "latest_note": "Review"},
    ]}
    table = manipulation_snapshot_table(snapshot)
    assert table.iloc[-1]["Kỳ"] == "TTM"
    assert table.iloc[-1]["Mức cảnh báo"] == "N/A"
    candidates = manipulation_snapshot_candidates(snapshot)
    assert candidates["Question"].eq("Q27").all()
    assert candidates["Evidence Quality"].str.startswith("T —").all()


def test_phase6c_never_imports_module2_compute_engine():
    text = Path(__file__).with_name("chapter6_evidence.py").read_text(encoding="utf-8")
    assert "module2_engine" not in text
    assert "build_beneish" not in text
    assert "build_modified_jones" not in text
    assert "build_real_earnings" not in text


def test_quality_summary_is_coverage_not_score_and_gaps_are_tasks():
    candidates = pd.DataFrame(columns=["Question", "Evidence Quality", "Direction"])
    summary = evidence_quality_summary(candidates)
    assert len(summary) == 6
    assert summary["Boundary"].str.contains("not a quality score").all()
    gaps = research_gaps(candidates)
    assert len(gaps) == 6
    assert gaps["Status"].str.startswith("Open").all()
