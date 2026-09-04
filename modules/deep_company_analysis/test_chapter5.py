from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import modules.deep_company_analysis.chapter5 as ch5


def _contains_confidence(value) -> bool:
    if isinstance(value, dict):
        return any("confidence" in str(k).casefold() or _contains_confidence(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_confidence(x) for x in value)
    return False


def test_chapter5_has_q21_to_q26_and_no_confidence_fields():
    record = ch5.empty_payload("DGC", "Duc Giang")
    assert set(record["question_status"]) == set(ch5.QUESTION_KEYS)
    assert set(record["question_trend"]) == set(ch5.QUESTION_KEYS)
    assert not _contains_confidence(record)


def test_q23_contains_all_shearn_default_operational_risks():
    record = ch5.empty_payload("DGC")
    rows = record["q23_risks"]
    assert len(rows) == len(ch5.SHEARN_Q23_RISKS) == 17
    expected = [name for name, _ in ch5.SHEARN_Q23_RISKS]
    assert [row["Risk"] for row in rows] == expected
    assert all(row["Origin"] == "Shearn" for row in rows)
    assert all(row["Frequency"] == "Unknown" for row in rows)
    assert all(row["Severity"] == "Unknown" for row in rows)


def test_q23_analyst_can_add_risk_without_losing_shearn_defaults():
    rows = ch5._default_risk_rows()
    rows.append({"Risk": "Geopolitical route disruption", "Risk (VI)": "Đứt gãy tuyến logistics địa chính trị", "Origin": "", "Severity": "High"})
    normalized = ch5.ensure_shearn_risks(rows)
    assert len(normalized) == 18
    custom = [row for row in normalized if row["Risk"] == "Geopolitical route disruption"][0]
    assert custom["Origin"] == "Analyst-defined"
    assert custom["Severity"] == "High"
    assert sum(row["Origin"] == "Shearn" for row in normalized) == 17


def test_shearn_default_origin_cannot_be_silently_overwritten():
    rows = ch5._default_risk_rows()
    rows[0]["Origin"] = "Analyst-defined"
    normalized = ch5.ensure_shearn_risks(rows)
    assert normalized[0]["Risk"] == "Overcapacity"
    assert normalized[0]["Origin"] == "Shearn"


def test_strip_confidence_fields_is_recursive():
    record = ch5.empty_payload("DGC")
    record["confidence"] = "High"
    record["q21"]["Analyst Confidence"] = 5
    record["q23_risks"][0]["Confidence"] = "Medium"
    clean = ch5._strip_confidence_fields(record)
    assert not _contains_confidence(clean)


def test_guardrails_are_all_false():
    flags = ch5.guardrails()
    assert flags
    assert all(value is False for value in flags.values())
    assert flags["auto_risk_rating"] is False
    assert flags["missing_risk_data_is_low_risk"] is False
    assert flags["auto_roic_quality_conclusion"] is False


def test_cross_check_marks_catastrophic_unknown_frequency_as_research_gap():
    record = ch5.empty_payload("DGC")
    record["q23_risks"][0]["Severity"] = "Catastrophic"
    record["q23_risks"][0]["Frequency"] = "Unknown"
    checks = ch5.cross_question_checks(record)
    assert any("Critical Research Gap" in text for text in checks)


def test_cross_check_does_not_auto_judge_high_roic_as_compounder():
    record = ch5.empty_payload("DGC")
    record["q26"]["current_roic_quality"] = "High"
    record["q26"]["reinvestment_runway"] = "None"
    checks = ch5.cross_question_checks(record)
    assert any("compounder" in text for text in checks)


def test_save_load_snapshot_persistence_and_no_confidence(tmp_path, monkeypatch):
    db = tmp_path / "chapter5_test.db"
    monkeypatch.setattr(ch5, "DB_PATH", db)
    record = ch5.empty_payload("DGC", "Duc Giang")
    record["question_status"]["Q23"] = "Partial"
    record["q23_risks"][0]["Frequency"] = "High"
    record["q23_risks"][0]["Severity"] = "High"
    record["q23_risks"].append({"Risk": "Analyst custom risk", "Risk (VI)": "Rủi ro riêng", "Origin": "", "Frequency": "Low", "Severity": "High", "Confidence": "should disappear"})
    saved = ch5.save_record(record, create_snapshot=True)
    loaded = ch5.load_record("DGC")
    history = ch5.load_snapshots("DGC")
    assert saved["question_status"]["Q23"] == "Partial"
    assert loaded["q23_risks"][0]["Frequency"] == "High"
    assert any(row["Risk"] == "Analyst custom risk" and row["Origin"] == "Analyst-defined" for row in loaded["q23_risks"])
    assert not _contains_confidence(loaded)
    assert len(history) == 1


def test_roic_registry_keeps_canonical_separate_from_shearn_variants():
    rows = ch5.empty_payload("DGC")["q26_roic_variants"]
    canonical = [row for row in rows if row["Origin"] == "Trecapital canonical"]
    analytical = [row for row in rows if row["Origin"] == "Shearn analytical"]
    assert len(canonical) == 1
    assert canonical[0]["ROIC Variant"] == "Trecapital Canonical ROIC"
    assert len(analytical) >= 6
