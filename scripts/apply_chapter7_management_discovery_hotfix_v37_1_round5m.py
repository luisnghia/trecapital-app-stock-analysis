from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5M function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    code = r'''def _immediate_clause_before_name(name: str, context: str) -> str:
    """Return the disclosure/event clause immediately preceding this manager occurrence.

    Company HTML often flattens several personnel resolutions without punctuation, e.g.
    `... miễn nhiệm ông A 20250303 ... Nghị quyết ... bổ nhiệm ông A ...`. Treat each
    `Nghị quyết`/dated event starter as a hard boundary so an earlier dismissal cannot leak into
    the later appointment clause for the same person.
    """
    text = _clean_text(context)
    needle = _clean_text(name).casefold()
    positions = [m.start() for m in re.finditer(re.escape(needle), text.casefold())] if needle else []
    if not positions:
        return ""
    center = len(text) // 2
    pos = min(positions, key=lambda p: abs(p - center))
    before = text[max(0, pos - 260):pos]
    # Preserve only the last event clause. Besides punctuation, Vietnamese IR pages commonly use
    # repeated `Nghị quyết ...` blocks and compact `Ngày dd/mm/yyyy ...` blocks as separators.
    pieces = re.split(
        r"[.;\n]+|(?=\bnghị\s+quyết\b)|(?=\bnghi\s+quyet\b)|(?=\bngày\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}\b)|(?=\bngay\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}\b)",
        before,
        flags=re.I,
    )
    return _clean_text(pieces[-1] if pieces else before).casefold()'''
    text = replace_function(text, "_immediate_clause_before_name", "_is_role_change_event", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_flattened_resolution_blocks_without_period_keep_later_appointment_v37_1_round5m():"
    if sentinel in text:
        return
    text += r'''


def test_flattened_resolution_blocks_without_period_keep_later_appointment_v37_1_round5m():
    docs = [{
        "title": "Tiếng Việt",
        "url": "https://ducgiangchem.vn/cbtt-nghi-quyet-hdqt-so-03-04-05-2025-nq-hdqt-thong-qua-thay-doi-nhan-su/",
        "text": (
            "Nghị quyết Hội đồng quản trị số 03/2025/NQ-HĐQT ngày 03/03/2025 thông qua miễn nhiệm "
            "chức danh Tổng giám đốc đối với ông Đào Hữu Duy Anh 20250303 – DGC – CBTT NQ HDQT 03 thong qua mien nhiem TGD "
            "Nghị quyết Hội đồng quản trị số 04/2025/NQ-HĐQT ngày 03/03/2025 thông qua bổ nhiệm "
            "ông Đào Hữu Duy Anh giữ chức vụ Phó chủ tịch thường trực Hội đồng quản trị Công ty cổ phần Tập đoàn Hóa chất Đức Giang. "
            "20250303 – DGC – CBTT NQ HDQT 04 thong qua bo nhiem Pho Chu tich thuong truc HDQT DGC "
            "Nghị quyết Hội đồng quản trị số 05/2025/NQ-HĐQT ngày 03/03/2025 thông qua bổ nhiệm "
            "ông Lưu Bách Đạt giữ chức vụ Tổng giám đốc Công ty cổ phần Tập đoàn Hóa chất Đức Giang"
        ),
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs, company_name="Tập đoàn Hóa chất Đức Giang")
    found = {(r["Manager"], r["Role Normalized"], str(r["As-of Date"])) for _, r in frame.iterrows()}
    assert ("Đào Hữu Duy Anh", "Vice Chairman", "2025") in found
    assert ("Đào Hữu Duy Anh", "CEO", "2025") not in found
    assert ("Lưu Bách Đạt", "CEO", "2025") in found
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5M disclosure-boundary anchoring applied")


if __name__ == "__main__":
    main()
