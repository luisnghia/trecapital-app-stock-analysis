from __future__ import annotations

import modules.deep_company_analysis.chapter5 as ch5


def test_new_record_seeds_all_shearn_q23_risks():
    record = ch5.empty_payload("DGC")
    assert len(record["q23_risks"]) == len(ch5.SHEARN_Q23_RISKS) == 17
    assert all(row["Origin"] == "Shearn" for row in record["q23_risks"])


def test_deleted_shearn_risk_is_not_recreated_by_normalizer():
    rows = ch5._default_risk_rows()[1:]
    normalized = ch5.ensure_shearn_risks(rows)
    assert len(normalized) == 16
    assert not any(row["Risk"] == "Overcapacity" for row in normalized)


def test_all_default_risks_can_be_deleted():
    assert ch5.ensure_shearn_risks([]) == []


def test_deleted_default_risk_stays_deleted_after_save_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(ch5, "DB_PATH", tmp_path / "chapter5_q23_delete.db")
    record = ch5.empty_payload("DGC", "Duc Giang")
    record["q23_risks"] = [row for row in record["q23_risks"] if row["Risk"] != "Overcapacity"]
    ch5.save_record(record)
    loaded = ch5.load_record("DGC")
    assert len(loaded["q23_risks"]) == 16
    assert not any(row["Risk"] == "Overcapacity" for row in loaded["q23_risks"])


def test_empty_risk_register_stays_empty_after_save_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(ch5, "DB_PATH", tmp_path / "chapter5_q23_empty.db")
    record = ch5.empty_payload("DGC", "Duc Giang")
    record["q23_risks"] = []
    ch5.save_record(record)
    loaded = ch5.load_record("DGC")
    assert loaded["q23_risks"] == []


def test_analyst_added_risk_is_normalized_to_analyst_defined():
    rows = [{"Risk": "Geopolitical route disruption", "Risk (VI)": "Đứt gãy tuyến logistics", "Origin": ""}]
    normalized = ch5.ensure_shearn_risks(rows)
    assert len(normalized) == 1
    assert normalized[0]["Origin"] == "Analyst-defined"
