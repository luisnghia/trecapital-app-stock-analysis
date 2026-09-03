from __future__ import annotations

from pathlib import Path
import sqlite3

import modules.deep_company_analysis.chapter4 as ch4


def _use_tmp_db(tmp_path: Path) -> None:
    ch4.DB_PATH = tmp_path / "chapter4_test.db"


def test_q15_sources_match_approved_six_plus_analyst_defined() -> None:
    names = [name for name, _ in ch4.Q15_SOURCES]
    origins = [origin for _, origin in ch4.Q15_SOURCES]
    assert names == [
        "Network Economics",
        "Brand Loyalty",
        "Patents",
        "Regulatory Licenses",
        "Switching Costs",
        "Cost Advantages — Scale / Location / Unique Asset",
        "Other Source — Analyst-defined",
    ]
    assert origins[:6] == ["Shearn"] * 6
    assert origins[6] == "Analyst-defined"


def test_empty_payload_has_no_auto_investment_or_moat_conclusion() -> None:
    payload = ch4.empty_payload("DGC", "Đức Giang")
    assert payload["q15"]["sustainable_advantage"] == "Unknown"
    assert payload["q16"]["pricing_power"] == "Unknown"
    assert payload["q17"]["industry_economics"] == "Unknown"
    assert payload["q19"]["competition_intensity"] == "Unknown"
    assert payload["q20"]["supplier_relationship"] == "Unknown"
    serialized = str(payload).lower()
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "chapter score" not in serialized
    assert "moat score" not in serialized


def test_phase4a_persistence_creates_normalized_child_tables_and_snapshot(tmp_path: Path) -> None:
    _use_tmp_db(tmp_path)
    payload = ch4.empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    payload["q15"]["sustainable_advantage"] = "Partial"
    payload["q15"]["overall_moat_trend"] = "Stable"
    payload["q15"]["conclusion"] = "Có candidate cost advantage nhưng cần chứng minh durability."
    payload["q15_advantages"] = [{
        "Specific Advantage": "Raw-material access",
        "Economic Mechanism": "Potential input-cost advantage",
        "Copyability": "Unknown",
        "Trend": "Unknown",
        "Conclusion": "Need evidence",
    }]
    payload["q20_suppliers"] = [{
        "Supplier / Group": "Nhóm quặng",
        "Input": "Apatit",
        "% Supply if Disclosed": "",
        "Relationship": "Unknown",
    }]

    status = ch4.save_record(payload)
    assert status == "partial"
    loaded = ch4.load_record("DGC")
    assert loaded["q15"]["sustainable_advantage"] == "Partial"
    assert loaded["q15_advantages"][0]["Specific Advantage"] == "Raw-material access"
    assert loaded["q20_suppliers"][0]["% Supply if Disclosed"] == ""

    with sqlite3.connect(ch4.DB_PATH) as conn:
        advantage_rows = conn.execute("SELECT COUNT(*) FROM chapter4_advantages WHERE ticker='DGC'").fetchone()[0]
        supplier_rows = conn.execute("SELECT COUNT(*) FROM chapter4_suppliers WHERE ticker='DGC'").fetchone()[0]
        snapshots = conn.execute("SELECT COUNT(*) FROM chapter4_snapshots WHERE ticker='DGC'").fetchone()[0]
    assert advantage_rows == 1
    assert supplier_rows == 1
    assert snapshots == 1


def test_question_status_requires_analyst_assessment_and_conclusion() -> None:
    payload = ch4.empty_payload("DGC")
    assert ch4.question_statuses(payload) == {q: "Unknown" for q in ch4.QUESTION_KEYS}

    payload["q15_advantages"] = [{"Specific Advantage": "Scale candidate"}]
    assert ch4.question_statuses(payload)["Q15"] == "Partial"

    payload["q15"]["sustainable_advantage"] = "Yes"
    assert ch4.question_statuses(payload)["Q15"] == "Partial"

    payload["q15"]["conclusion"] = "Analyst conclusion"
    assert ch4.question_statuses(payload)["Q15"] == "Answered"


def test_consistency_engine_only_warns_and_never_mutates_payload() -> None:
    payload = ch4.empty_payload("DGC")
    payload["q15"]["sustainable_advantage"] = "Yes"
    payload["q16"]["pricing_power"] = "None"
    payload["q20"]["commodity_dependence"] = "High"
    before = repr(payload)
    warnings = ch4.consistency_warnings(payload)
    after = repr(payload)
    assert len(warnings) >= 2
    assert before == after
    assert payload["q15"]["sustainable_advantage"] == "Yes"


def test_q20_missing_supplier_share_remains_unknown_not_diversified() -> None:
    payload = ch4.empty_payload("DGC")
    payload["q20_suppliers"] = [{
        "Supplier / Group": "Supplier candidate",
        "Input": "Raw material",
        "% Supply if Disclosed": "",
    }]
    assert payload["q20"]["supplier_concentration"] == "Unknown"


def test_q16_pricing_event_nature_defaults_to_unknown() -> None:
    payload = ch4.empty_payload("DGC")
    assert payload["q16"]["pricing_power"] == "Unknown"
    assert payload["q16"]["nature"] == "Unknown"
    # Phase 4A does not infer pricing power from margins or a pricing event row.
    payload["q16_pricing_events"] = [{"Period": "2026", "Gross Margin %": "35%"}]
    assert payload["q16"]["pricing_power"] == "Unknown"


def test_understanding_status_is_completeness_not_quality(tmp_path: Path) -> None:
    _use_tmp_db(tmp_path)
    payload = ch4.empty_payload("DGC")
    for key, field, assessment in (
        ("q15", "sustainable_advantage", "No"),
        ("q16", "pricing_power", "None"),
        ("q17", "industry_economics", "Bad"),
        ("q18", "trend", "Deteriorating"),
        ("q19", "competition_intensity", "Extreme"),
        ("q20", "supplier_relationship", "Adversarial"),
    ):
        payload[key][field] = assessment
        payload[key]["conclusion"] = "Đã hiểu và kết luận theo evidence."
    assert ch4.understanding_status(payload) == "understood"
