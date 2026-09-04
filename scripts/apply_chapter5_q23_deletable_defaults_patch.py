from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CH5 = ROOT / "modules" / "deep_company_analysis" / "chapter5.py"
TEST = ROOT / "modules" / "deep_company_analysis" / "test_chapter5_q23_deletable_defaults.py"

text = CH5.read_text(encoding="utf-8")

new_function = '''def ensure_shearn_risks(rows: Any) -> list[dict[str, Any]]:
    """Normalize only the Q23 risk rows that currently exist.

    Shearn's 17 risks are seeded only when a brand-new Chapter-5 record is created via
    ``empty_payload``.  After that, the analyst owns the register: deleting one or all
    default rows is persistent and this function must never silently re-create them.

    Rows whose risk name still matches a Shearn default retain the canonical bilingual
    label and ``Origin = Shearn``.  Any other row is treated as ``Analyst-defined``.
    """
    incoming = [dict(x) for x in rows] if isinstance(rows, list) else []
    defaults = {_risk_key(row): row for row in _default_risk_rows()}
    result: list[dict[str, Any]] = []

    for row in incoming:
        key = _risk_key(row)
        if not key:
            continue
        normalized = {col: row.get(col, "") for col in RISK_COLUMNS}
        default = defaults.get(key)
        if default is not None:
            normalized["Risk"] = default["Risk"]
            normalized["Risk (VI)"] = default["Risk (VI)"]
            normalized["Origin"] = "Shearn"
        else:
            normalized["Origin"] = "Analyst-defined"
        result.append(normalized)
    return result
'''

pattern = re.compile(r"def ensure_shearn_risks\(rows: Any\) -> list\[dict\[str, Any\]\]:\n.*?\n\ndef _strip_confidence_fields", re.S)
if not pattern.search(text):
    raise SystemExit("Could not locate ensure_shearn_risks block")
text = pattern.sub(new_function + "\n\ndef _strip_confidence_fields", text, count=1)

old_load = '''    record = _merge_dict(base, payload)\n    record["ticker"] = ticker\n    record["company_name"] = company_name or record.get("company_name", "")\n    record["q23_risks"] = ensure_shearn_risks(record.get("q23_risks"))\n    return _strip_confidence_fields(record)'''
new_load = '''    record = _merge_dict(base, payload)\n    record["ticker"] = ticker\n    record["company_name"] = company_name or record.get("company_name", "")\n    # Defaults belong only to a new record.  For an existing record, a missing/empty Q23\n    # list means the analyst has no saved default rows and must not be silently repopulated.\n    if "q23_risks" not in payload:\n        record["q23_risks"] = []\n    record["q23_risks"] = ensure_shearn_risks(record.get("q23_risks"))\n    return _strip_confidence_fields(record)'''
if old_load not in text:
    raise SystemExit("Could not locate load_record Q23 block")
text = text.replace(old_load, new_load, 1)

old_ui = '''        st.markdown("**17 rủi ro mặc định dưới đây là các operational-risk examples Shearn nêu trực tiếp trong Chương 5. Người phân tích có thể thêm dòng mới; dòng mới sẽ được lưu là `Analyst-defined`.**")\n        risk_df = _editor("Risk Underwriter Register — Shearn defaults + Analyst-defined risks", record.get("q23_risks", []), RISK_COLUMNS, f"{prefix}_q23_risks", 520)'''
new_ui = '''        st.markdown("**Khi tạo mới bản ghi Chương 5, app nạp sẵn 17 operational-risk examples Shearn nêu trong sách. Sau đó người phân tích toàn quyền xóa các dòng không phù hợp hoặc thêm rủi ro mới. Rủi ro đã xóa sẽ không tự xuất hiện lại khi lưu/mở lại; dòng mới được lưu là `Analyst-defined`.**")\n        risk_df = _editor("Risk Underwriter Register — Shearn defaults chỉ seed khi tạo mới + Analyst-defined risks", record.get("q23_risks", []), RISK_COLUMNS, f"{prefix}_q23_risks", 520)'''
if old_ui not in text:
    raise SystemExit("Could not locate Q23 UI help block")
text = text.replace(old_ui, new_ui, 1)

CH5.write_text(text, encoding="utf-8")

TEST.write_text('''from __future__ import annotations\n\nimport modules.deep_company_analysis.chapter5 as ch5\n\n\ndef test_new_record_seeds_all_shearn_q23_risks():\n    record = ch5.empty_payload("DGC")\n    assert len(record["q23_risks"]) == len(ch5.SHEARN_Q23_RISKS) == 17\n    assert all(row["Origin"] == "Shearn" for row in record["q23_risks"])\n\n\ndef test_deleted_shearn_risk_is_not_recreated_by_normalizer():\n    rows = ch5._default_risk_rows()[1:]\n    normalized = ch5.ensure_shearn_risks(rows)\n    assert len(normalized) == 16\n    assert not any(row["Risk"] == "Overcapacity" for row in normalized)\n\n\ndef test_all_default_risks_can_be_deleted():\n    assert ch5.ensure_shearn_risks([]) == []\n\n\ndef test_deleted_default_risk_stays_deleted_after_save_reload(tmp_path, monkeypatch):\n    monkeypatch.setattr(ch5, "DB_PATH", tmp_path / "chapter5_q23_delete.db")\n    record = ch5.empty_payload("DGC", "Duc Giang")\n    record["q23_risks"] = [row for row in record["q23_risks"] if row["Risk"] != "Overcapacity"]\n    ch5.save_record(record)\n    loaded = ch5.load_record("DGC")\n    assert len(loaded["q23_risks"]) == 16\n    assert not any(row["Risk"] == "Overcapacity" for row in loaded["q23_risks"])\n\n\ndef test_empty_risk_register_stays_empty_after_save_reload(tmp_path, monkeypatch):\n    monkeypatch.setattr(ch5, "DB_PATH", tmp_path / "chapter5_q23_empty.db")\n    record = ch5.empty_payload("DGC", "Duc Giang")\n    record["q23_risks"] = []\n    ch5.save_record(record)\n    loaded = ch5.load_record("DGC")\n    assert loaded["q23_risks"] == []\n\n\ndef test_analyst_added_risk_is_normalized_to_analyst_defined():\n    rows = [{"Risk": "Geopolitical route disruption", "Risk (VI)": "Đứt gãy tuyến logistics", "Origin": ""}]\n    normalized = ch5.ensure_shearn_risks(rows)\n    assert len(normalized) == 1\n    assert normalized[0]["Origin"] == "Analyst-defined"\n''', encoding="utf-8")

print("Applied Chapter 5 Q23 deletable-default-risks patch")
