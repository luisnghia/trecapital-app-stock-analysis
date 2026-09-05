from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "modules" / "deep_company_analysis" / "chapter7.py"
PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter7_page_support.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase7C integration marker not found: {label}")
    return text.replace(old, new, 1)


def patch_core() -> None:
    text = CORE.read_text(encoding="utf-8")
    old = '        "phase7b_bridge_note": "Structured official disclosure bridge uses Raw → Candidate → Analyst Apply; registered != executed; actual shares != options/RSU/ESOP; no auto management conclusion.",\n'
    new = old + '        "phase7c_research_note": "Web/PDF/HTML Research Assistant produces candidate evidence and research gaps only; analyst must explicitly Promote; no auto classification, Management Quality conclusion or insider trading signal.",\n'
    text = replace_once(text, old, new, "phase7c payload note")
    CORE.write_text(text, encoding="utf-8")


def patch_page() -> None:
    text = PAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from modules.deep_company_analysis.chapter7_data_bridge_ui import render_structured_management_bridge\n",
        "from modules.deep_company_analysis.chapter7_data_bridge_ui import render_structured_management_bridge\n"
        "from modules.deep_company_analysis.chapter7_research_ui import render_chapter7_research_assistant\n",
        "research UI import",
    )
    text = text.replace(
        "- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7B chỉ tự động hóa structured disclosure bridge; research assistant web/PDF sâu vẫn để Phase 7C.",
        "- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7B xử lý structured disclosure; Phase 7C research web/PDF/HTML chỉ tạo candidate evidence + research gaps và yêu cầu analyst Promote.",
    )
    text = text.replace(
        "Phase 7B phát hiện event từ structured disclosures và đưa vào Review Queue; Phase 7C mới research/extract sâu từ nguồn unstructured/web.",
        "Phase 7B phát hiện event từ structured disclosures; Phase 7C research/extract web/PDF/HTML chỉ đưa candidate vào Evidence Matrix khi analyst Promote.",
    )
    text = text.replace(
        "Phase 7A chưa có Chapter 7 Completion Gate chính thức; gate source-closure sẽ được khóa ở Phase 7D sau khi 7B/7C hoàn tất. Phase 7B cũng không tạo Completion Gate; final source-closure vẫn thuộc Phase 7D.",
        "Phase 7A chưa có Chapter 7 Completion Gate chính thức; Phase 7B/7C cũng không tự khóa chương. Final source-closure vẫn thuộc Phase 7D.",
    )
    text = text.replace(
        "Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A + 7B structured data bridge",
        "Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A + 7B structured bridge + 7C Evidence Research Assistant",
    )
    marker = "    with st.container(border=True):\n        payload = render_structured_management_bridge(ticker, payload)\n\n"
    insert = marker + "    with st.container(border=True):\n        payload = render_chapter7_research_assistant(ticker, payload)\n\n"
    text = replace_once(text, marker, insert, "render research assistant after structured bridge")
    text = text.replace("💾 Lưu Chapter 7 — Phase 7A+7B", "💾 Lưu Chapter 7 — Phase 7A+7B+7C")
    text = text.replace(
        "Đã lưu Phase 7A+7B. Structured bridge không ghi đè classification/conclusion của analyst.",
        "Đã lưu Phase 7A+7B+7C. Structured bridge/Research Assistant không ghi đè classification/conclusion của analyst.",
    )
    PAGE.write_text(text, encoding="utf-8")


def main() -> None:
    patch_core()
    patch_page()
    print("Chapter 7 Phase 7C V36 integration applied")


if __name__ == "__main__":
    main()
