from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "modules" / "deep_company_analysis" / "chapter7.py"
PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"
BRIDGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_data_bridge.py"
TEST = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_phase7b.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase7B integration marker not found: {label}")
    return text.replace(old, new, 1)


def patch_bridge() -> None:
    text = BRIDGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "BRIDGE_SCHEMA_VERSION = 1\n",
        "BRIDGE_SCHEMA_VERSION = 1\n"
        "BRIDGE_BOUNDARY = (\"No automatic OO/LT/HH, Lion/Hyena or Management Quality conclusion; \"
        "\"no MOS/Research Gate/BUY/SELL; insider activity is not a buy/sell signal.\")\n",
        "bridge boundary constant",
    )
    text = replace_once(
        text,
        '    text = " ".join(str(value or "").strip().split())\n    folded = unicodedata.normalize("NFKD", text)\n',
        '    text = " ".join(str(value or "").strip().split())\n'
        '    text = text.replace("Đ", "D").replace("đ", "d")\n'
        '    folded = unicodedata.normalize("NFKD", text)\n',
        "Vietnamese D normalization",
    )
    old = '''    patterns = (\n        (("chu tich hoi dong quan tri", "chu tich hdqt", "chairman"), "Chairman"),\n        (("pho chu tich", "vice chairman"), "Vice Chairman"),\n        (("tong giam doc", "ceo", "chief executive"), "CEO"),\n        (("pho tong giam doc", "deputy ceo", "deputy general director"), "Deputy CEO"),\n        (("giam doc tai chinh", "cfo", "chief financial"), "CFO"),\n        (("giam doc van hanh", "coo", "chief operating"), "COO"),\n        (("ke toan truong", "chief accountant"), "Chief Accountant"),\n        (("thanh vien hdqt doc lap", "independent director"), "Independent Director"),\n        (("thanh vien hoi dong quan tri", "thanh vien hdqt", "board director", "director"), "Board Director"),\n    )'''
    new = '''    # Specific titles must be tested before broader substrings (e.g. Phó TGĐ contains TGĐ).\n    patterns = (\n        (("pho chu tich", "vice chairman"), "Vice Chairman"),\n        (("pho tong giam doc", "deputy ceo", "deputy general director"), "Deputy CEO"),\n        (("thanh vien hdqt doc lap", "independent director"), "Independent Director"),\n        (("giam doc tai chinh", "cfo", "chief financial"), "CFO"),\n        (("giam doc van hanh", "coo", "chief operating"), "COO"),\n        (("ke toan truong", "chief accountant"), "Chief Accountant"),\n        (("chu tich hoi dong quan tri", "chu tich hdqt", "chairman"), "Chairman"),\n        (("tong giam doc", "ceo", "chief executive"), "CEO"),\n        (("thanh vien hoi dong quan tri", "thanh vien hdqt", "board director", "director"), "Board Director"),\n    )'''
    text = replace_once(text, old, new, "role specificity")
    text = replace_once(
        text,
        "                fp = _json_fingerprint(payload)\n",
        "                fp_payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))\n"
        "                if isinstance(fp_payload.get('_provenance'), dict):\n"
        "                    fp_payload['_provenance'].pop('retrieved_at', None)\n"
        "                fp = _json_fingerprint(fp_payload)\n",
        "stable normalized fingerprint",
    )
    BRIDGE.write_text(text, encoding="utf-8")


def patch_core() -> None:
    text = CORE.read_text(encoding="utf-8")
    text = replace_once(text, "SCHEMA_VERSION = 1", "SCHEMA_VERSION = 2", "schema version")
    text = replace_once(
        text,
        '    "From",\n    "To",\n    "Company",',
        '    "From",\n    "To",\n    "Date Precision",\n    "Company",',
        "career date precision",
    )
    text = replace_once(
        text,
        '    "Role",\n    "Salary (tỷ)",',
        '    "Role",\n    "Compensation Scope",\n    "Salary (tỷ)",',
        "comp scope",
    )
    text = replace_once(
        text,
        '    "Compensation Consultant",\n    "Source",\n    "Analyst Note",',
        '    "Compensation Consultant",\n    "Source",\n    "Data Quality Flags",\n    "Analyst Note",',
        "comp flags",
    )
    text = replace_once(
        text,
        'INSIDER_TRANSACTION_COLUMNS = [\n    "Transaction Date",\n    "Disclosure Date",',
        'INSIDER_TRANSACTION_COLUMNS = [\n    "Transaction Date",\n    "Transaction Date From",\n    "Transaction Date To",\n    "Disclosure Date",',
        "insider date range",
    )
    text = replace_once(
        text,
        '    "Transaction Type",\n    "Shares",\n    "Price",',
        '    "Transaction Type",\n    "Registered Shares",\n    "Executed Shares",\n    "Shares",\n    "Price",',
        "registered executed",
    )
    text = replace_once(
        text,
        'EVENT_COLUMNS = [\n    "Event Date",\n    "Manager ID",',
        'EVENT_COLUMNS = [\n    "Event Date",\n    "Publication Date",\n    "Effective Date",\n    "As-of Date",\n    "Manager ID",',
        "event three dates",
    )
    text = replace_once(
        text,
        '        "phase7a_source_lock_note": "Event/as-of management data; no fabricated TTM. AI/Data is evidence support only; analyst owns classifications and conclusions.",',
        '        "phase7a_source_lock_note": "Event/as-of management data; no fabricated TTM. AI/Data is evidence support only; analyst owns classifications and conclusions.",\n'
        '        "phase7b_bridge_note": "Structured official disclosure bridge uses Raw → Candidate → Analyst Apply; registered != executed; actual shares != options/RSU/ESOP; no auto management conclusion.",',
        "payload bridge note",
    )
    CORE.write_text(text, encoding="utf-8")


def patch_page() -> None:
    text = PAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor\n",
        "from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor\n"
        "from modules.deep_company_analysis.chapter7_data_bridge_ui import render_structured_management_bridge\n",
        "bridge ui import",
    )
    text = text.replace(
        "- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7A chưa có research assistant tự động.",
        "- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7B chỉ tự động hóa structured disclosure bridge; research assistant web/PDF sâu vẫn để Phase 7C.",
    )
    text = text.replace(
        "Phase 7C mới tự động phát hiện/research management events. Phase 7A chỉ cung cấp cấu trúc lưu và review.",
        "Phase 7B phát hiện event từ structured disclosures và đưa vào Review Queue; Phase 7C mới research/extract sâu từ nguồn unstructured/web.",
    )
    text = text.replace(
        "Phase 7A chưa có Chapter 7 Completion Gate chính thức; gate source-closure sẽ được khóa ở Phase 7D sau khi 7B/7C hoàn tất.",
        "Phase 7B chưa có Chapter 7 Completion Gate chính thức; gate source-closure sẽ được khóa ở Phase 7D sau khi 7C hoàn tất.",
    )
    text = text.replace(
        "Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A source-locked workspace",
        "Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A + 7B structured data bridge",
    )
    text = replace_once(
        text,
        "    _render_source_lock()\n    _render_status_panel(ticker, payload)\n\n    with st.container(border=True):\n        _render_q33(ticker, payload)",
        "    _render_source_lock()\n    _render_status_panel(ticker, payload)\n\n"
        "    with st.container(border=True):\n"
        "        payload = render_structured_management_bridge(ticker, payload)\n\n"
        "    with st.container(border=True):\n        _render_q33(ticker, payload)",
        "render bridge before Q33",
    )
    text = text.replace("💾 Lưu Chapter 7 — Phase 7A", "💾 Lưu Chapter 7 — Phase 7A+7B")
    text = text.replace(
        "Đã lưu Phase 7A. Không có classification/conclusion nào bị AI/Data ghi đè.",
        "Đã lưu Phase 7A+7B. Structured bridge không ghi đè classification/conclusion của analyst.",
    )
    PAGE.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST.read_text(encoding="utf-8")
    old = '''def test_no_management_quality_or_buy_sell_signal_in_bridge_contract():\n    contract = " ".join([\n        b.__doc__ or "",\n        json.dumps(b.EVENT_REVIEW_MAP),\n        " ".join(b.RECORD_TYPES),\n    ]).lower()\n    assert "no automatic" in contract\n    assert "buy/sell signal" in contract\n    assert "management quality" in contract'''
    new = '''def test_no_management_quality_or_buy_sell_signal_in_bridge_contract():\n    contract = " ".join([\n        b.BRIDGE_BOUNDARY,\n        json.dumps(b.EVENT_REVIEW_MAP),\n        " ".join(b.RECORD_TYPES),\n    ]).lower()\n    assert "no automatic" in contract\n    assert "buy/sell signal" in contract\n    assert "management quality" in contract'''
    text = replace_once(text, old, new, "bridge contract test")
    TEST.write_text(text, encoding="utf-8")


def main() -> None:
    patch_bridge()
    patch_core()
    patch_page()
    patch_tests()
    print("Chapter 7 Phase 7B V35 integration applied")


if __name__ == "__main__":
    main()
