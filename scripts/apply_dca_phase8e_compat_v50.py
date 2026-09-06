from __future__ import annotations

"""Make the legacy Chapter 8 Phase 8E migrator idempotent on the V50 lazy-chapter page."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "apply_chapter8_phase8e_v46.py"

ANCHOR = "def patch_dca_page(text: str) -> str:\n"
GUARD = '''def patch_dca_page(text: str) -> str:
    # V50 replaced eager st.tabs with lazy chapter selection. If Chapter 8 is already
    # integrated in that architecture, Phase 8E is complete and this legacy migrator
    # must be a no-op rather than trying to recreate the obsolete tab anchors.
    if (
        "CHAPTER_OPTIONS = (" in text
        and "active_chapter = st.radio(" in text
        and "render_chapter8_tab(chapter8_ticker)" in text
        and "from modules.deep_company_analysis.chapter8_page_support import render_chapter8_tab" in text
        and "from modules.deep_company_analysis.chapter8_integration import build_chapter8_summary" in text
        and "from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record" in text
    ):
        return text
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if "V50 replaced eager st.tabs with lazy chapter selection" in text:
        print("Phase 8E V50 compatibility already applied.")
        return
    if ANCHOR not in text:
        raise RuntimeError("Phase 8E patch_dca_page anchor not found")
    text = text.replace(ANCHOR, GUARD, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("Phase 8E V50 compatibility applied.")


if __name__ == "__main__":
    main()
