from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CH1 = ROOT / "modules" / "deep_company_analysis" / "chapter1.py"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Không tìm thấy đoạn cần patch:\n{old[:160]}")
    return text.replace(old, new, 1)


def main() -> None:
    text = CH1.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'STATUS_OPTIONS = ["— Chưa biết", "✓ Có", "X Không", "N/A"]\nGATES = {',
        'STATUS_OPTIONS = ["— Chưa biết", "✓ Có", "X Không", "N/A"]\n'
        'CONFIDENCE_LEVELS = {1: "Thấp", 2: "Trung bình", 3: "Cao"}\n'
        'DGC_TRIAL_PATH = APP_ROOT / "sample_data" / "deep_company_analysis" / "DGC_chapter1_trial.json"\n'
        'GATES = {',
    )

    marker = '\n\ndef _connect() -> sqlite3.Connection:\n'
    functions = '''\n\ndef _normalize_confidence(value: Any) -> int:\n    """Chuẩn hóa Confidence về 3 mức: 1 Thấp, 2 Trung bình, 3 Cao.\n\n    Bản cũ từng dùng thang 1–5; giá trị 4–5 được quy về mức Cao để không làm\n    hỏng dữ liệu SQLite đã lưu trước đó. Confidence không tham gia Quality Score.\n    """\n    try:\n        raw = int(value)\n    except Exception:\n        raw = 1\n    if raw <= 1:\n        return 1\n    if raw == 2:\n        return 2\n    return 3\n\n\ndef _confidence_label(value: Any) -> str:\n    return CONFIDENCE_LEVELS[_normalize_confidence(value)]\n\n\ndef load_dgc_trial_payload() -> dict[str, Any]:\n    """Nạp case DGC point-in-time dùng để kiểm thử workflow Chương 1 offline."""\n    if not DGC_TRIAL_PATH.exists():\n        raise FileNotFoundError(f"Không tìm thấy case DGC thử nghiệm: {DGC_TRIAL_PATH}")\n    payload = json.loads(DGC_TRIAL_PATH.read_text(encoding="utf-8"))\n    if _safe_ticker(payload.get("ticker", "")) != "DGC":\n        raise ValueError("Case thử nghiệm không phải DGC")\n    return payload\n'''
    if "def _normalize_confidence" not in text:
        if marker not in text:
            raise RuntimeError("Không tìm thấy marker _connect")
        text = text.replace(marker, functions + marker, 1)

    text = text.replace('"confidence": int(qrow["confidence"]),', '"confidence": _normalize_confidence(qrow["confidence"]),')
    text = text.replace('int(item.get("confidence", 1)),', '_normalize_confidence(item.get("confidence", 1)),')

    company_block = '''    with top2:\n        company_name = st.text_input("Tên doanh nghiệp", value=record.get("company_name", ""), key=f"dca_company_{ticker}")\n\n'''
    trial_block = company_block + '''    if ticker == "DGC":\n        st.caption("Có sẵn case DGC thử nghiệm point-in-time để kiểm tra workflow Chương 1; đây không phải dữ liệu live.")\n        if st.button("🧪 Nạp case thử nghiệm DGC (as-of 28/08/2026)", key="dca_load_dgc_trial"):\n            try:\n                save_record(load_dgc_trial_payload())\n                st.success("Đã nạp case DGC thử nghiệm vào SQLite local.")\n                st.rerun()\n            except Exception as exc:\n                st.error(f"Không nạp được case DGC: {exc}")\n\n'''
    if "dca_load_dgc_trial" not in text:
        text = replace_once(text, company_block, trial_block)

    text = text.replace(
        'st.caption("AI Suggested chưa bật ở bản offline này. Analyst Assessment là kết luận chính thức.")',
        'st.caption("AI Suggested chưa bật ở bản offline này. Analyst Assessment là kết luận chính thức. Confidence chỉ còn 3 mức: Thấp / Trung bình / Cao và không cộng vào Quality Score.")',
    )

    old_conf = '''            confidence = st.selectbox(\n                f"Confidence {book_label}",\n                [1, 2, 3, 4, 5],\n                index=max(0, min(4, int(item.get("confidence", 1)) - 1)),\n                label_visibility="collapsed",\n                key=f"dca_q_conf_{ticker}_{code}",\n            )'''
    new_conf = '''            current_confidence = _normalize_confidence(item.get("confidence", 1))\n            confidence = st.selectbox(\n                f"Confidence {book_label}",\n                list(CONFIDENCE_LEVELS),\n                index=list(CONFIDENCE_LEVELS).index(current_confidence),\n                format_func=lambda level: CONFIDENCE_LEVELS[level],\n                label_visibility="collapsed",\n                key=f"dca_q_conf_{ticker}_{code}",\n            )'''
    text = replace_once(text, old_conf, new_conf)

    CH1.write_text(text, encoding="utf-8")
    print("Chapter 1 V2 patch applied")


if __name__ == "__main__":
    main()
