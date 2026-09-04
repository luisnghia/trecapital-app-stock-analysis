from __future__ import annotations

from copy import deepcopy

import pandas as pd

from modules.deep_company_analysis.chapter5 import empty_payload
from modules.deep_company_analysis.chapter5_evidence import (
    candidate_rows,
    evidence_quality_summary,
    guardrails,
    merge_candidates_into_record,
    research_gaps,
)


def _raw(rows):
    return pd.DataFrame(rows)


def _row(focus: str, snippet: str, *, status: str = "Tìm thấy", title: str = "DGC evidence", url: str = "https://example.com/a", group: str = "Nguồn doanh nghiệp/IR"):
    return {
        "_Focus": focus,
        "_SourceMethod": "Test source",
        "Nhóm thông tin": group,
        "Tiêu đề": title,
        "Nguồn/URL": url,
        "Trích yếu": snippet,
        "Trạng thái": status,
        "Truy vấn": "test query",
    }


def test_q21_q22_candidates_do_not_encode_materiality_or_criticality():
    df = candidate_rows(_raw([
        _row("Q21_Q22", "Sản lượng tăng 12% chủ yếu do công suất nhà máy mới; ASP giảm nhẹ.")
    ]))
    assert set(df["Question"]) == {"Q21", "Q22"}
    q21 = df[df["Question"].eq("Q21")].iloc[0]
    q22 = df[df["Question"].eq("Q22")].iloc[0]
    assert "analyst decides materiality" in q21["Explicitness"]
    assert "verify explicit causality" in q22["Explicitness"]
    assert "critical" not in q22["Subtopic"].lower()


def test_navigation_links_are_never_promoted_to_evidence():
    df = candidate_rows(_raw([
        _row("Q25", "Nguồn để kiểm tra nợ vay covenant", status="Link nguồn ưu tiên")
    ]))
    assert df.empty


def test_q23_candidate_never_sets_frequency_or_severity():
    record = empty_payload("DGC", "Duc Giang")
    record["q23_risks"][0]["Frequency"] = "Rare"
    record["q23_risks"][0]["Severity"] = "High"
    before = deepcopy(record["q23_risks"])
    candidates = candidate_rows(_raw([
        _row("Q23", "Rủi ro dư thừa công suất và cạnh tranh gia tăng gây áp lực giá.")
    ]))
    merged = merge_candidates_into_record(record, candidates)
    assert merged["q23_risks"] == before
    assert merged["evidence_matrix"][0]["Status"] == "Candidate — Analyst verify"


def test_q24_input_cost_evidence_does_not_set_inflation_resilience():
    record = empty_payload("DGC")
    record["q24"]["inflation_resilience"] = "Unknown"
    candidates = candidate_rows(_raw([
        _row("Q24", "Giá nguyên liệu và điện tăng làm tăng chi phí đầu vào.")
    ]))
    merged = merge_candidates_into_record(record, candidates)
    assert merged["q24"]["inflation_resilience"] == "Unknown"


def test_q25_candidate_does_not_fabricate_covenant_or_off_bs_rows():
    record = empty_payload("DGC")
    candidates = candidate_rows(_raw([
        _row("Q25", "Doanh nghiệp duy trì thanh khoản và có khoản nợ vay ngắn hạn.")
    ]))
    merged = merge_candidates_into_record(record, candidates)
    assert merged["q25_covenants"] == []
    assert merged["q25_off_balance_obligations"] == []
    assert merged["q25"]["balance_sheet_assessment"] == "Unknown"


def test_q26_reinvestment_candidate_does_not_invent_incremental_roic_or_compounder():
    record = empty_payload("DGC")
    record["q26"]["current_roic_quality"] = "Unknown"
    candidates = candidate_rows(_raw([
        _row("Q26", "Công ty triển khai dự án mở rộng công suất với tổng mức đầu tư 2.000 tỷ đồng.")
    ]))
    merged = merge_candidates_into_record(record, candidates)
    assert merged["q26_reinvestment"] == []
    assert merged["q26"]["current_roic_quality"] == "Unknown"
    assert merged["q26"]["incremental_roic_assessment"] == "Unknown"


def test_merge_preserves_all_analyst_conclusions_and_manual_rows():
    record = empty_payload("DGC")
    record["q21"]["overall_assessment"] = "Stable"
    record["q21"]["conclusion"] = "Analyst conclusion must survive."
    record["q21_fundamentals"] = [{"Fundamental Driver": "Phosphorus volume", "Analyst Conclusion": "Manual"}]
    record["q25"]["balance_sheet_assessment"] = "Strong"
    record["q26"]["current_roic_quality"] = "High"
    before = deepcopy(record)
    candidates = candidate_rows(_raw([
        _row("Q21_Q22", "Sản lượng giảm do nhu cầu yếu", url="https://example.com/q21"),
        _row("Q25", "Nợ vay đáo hạn trong năm tới", url="https://example.com/q25"),
        _row("Q26", "Dự án mở rộng công suất mới", url="https://example.com/q26"),
    ]))
    merged = merge_candidates_into_record(record, candidates)
    for key in ("q21", "q22", "q23", "q24", "q25", "q26", "q21_fundamentals", "q22_metrics", "q23_risks", "q24_inflation_exposures", "q25_debt_instruments", "q26_reinvestment"):
        assert merged[key] == before[key]


def test_conflicting_evidence_is_preserved_side_by_side():
    candidates = candidate_rows(_raw([
        _row("Q23", "Rủi ro gián đoạn nguồn cung giảm và tình hình ổn định.", url="https://example.com/support"),
        _row("Q23", "Rủi ro gián đoạn nguồn cung tăng mạnh gây áp lực sản xuất.", url="https://example.com/counter"),
    ]))
    assert len(candidates) == 2
    directions = set(candidates["Direction"])
    assert "Supporting — Candidate" in directions
    assert "Contradicting — Candidate" in directions


def test_research_gaps_are_tasks_not_negative_judgements():
    candidates = candidate_rows(_raw([
        _row("Q21_Q22", "Sản lượng sản xuất 100 nghìn tấn.")
    ]))
    gaps = research_gaps(candidates)
    assert gaps
    assert all(g["Status"] == "Open — Candidate" for g in gaps)
    assert all("buy" not in g["Research Gap"].lower() and "sell" not in g["Research Gap"].lower() for g in gaps)


def test_quality_summary_covers_all_six_questions():
    summary = evidence_quality_summary(pd.DataFrame())
    assert list(summary["Question"]) == ["Q21", "Q22", "Q23", "Q24", "Q25", "Q26"]
    assert set(summary["Coverage Status"]) == {"Gap"}


def test_phase5c_guardrails_all_false():
    flags = guardrails()
    assert len(flags) >= 15
    assert all(value is False for value in flags.values())
    for required in (
        "overwrite_analyst_assessment",
        "auto_risk_severity",
        "fabricate_covenant",
        "fabricate_off_bs_obligation",
        "assume_all_cash_is_excess",
        "auto_compounder_conclusion",
        "auto_research_gate_change",
        "auto_buy_hold_sell",
    ):
        assert required in flags
