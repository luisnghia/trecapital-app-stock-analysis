from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MON = ROOT / "modules" / "deep_company_analysis" / "monitoring.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.2b marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = MON.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from modules.deep_company_analysis.table_format import interactive_sort_frame\n",
        "from modules.deep_company_analysis.table_format import render_static_table\n",
        "monitoring table import",
    )
    old = '''    queue = load_review_queue(open_only=True)\n    display = queue.drop(columns=["ID", "Trạng thái"], errors="ignore")\n    if not display.empty:\n        display = interactive_sort_frame(display, key=f"dca_review_queue_table_{current_ticker}")\n    if hasattr(st, "html"):\n        st.html(_html_table(display))\n    else:\n        st.markdown(_html_table(display), unsafe_allow_html=True)\n'''
    new = '''    queue = load_review_queue(open_only=True)\n    display = queue.drop(columns=["ID", "Trạng thái"], errors="ignore")\n    render_static_table(display, use_container_width=True, hide_index=True, height=340)\n'''
    text = replace_once(text, old, new, "monitoring review queue native grid")
    MON.write_text(text, encoding="utf-8")
    print("Deep Analysis V37.2b monitoring native header-sort migration applied")


if __name__ == "__main__":
    main()
