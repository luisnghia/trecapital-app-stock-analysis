from __future__ import annotations

"""Apply the Streamlit 1.40.2 compatibility hotfix for the unified DCA workspace.

The project pins Streamlit 1.40.2. ``st.dataframe`` in that version does not accept
``row_height``. The shared table renderer is used across the Deep Company Analysis
chapters, so one unsupported keyword can break every tab during a single Streamlit run.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE_FORMAT = ROOT / "modules" / "deep_company_analysis" / "table_format.py"


def main() -> None:
    text = TABLE_FORMAT.read_text(encoding="utf-8")
    old = "        row_height=42,\n"
    if old in text:
        text = text.replace(old, "", 1)
        TABLE_FORMAT.write_text(text, encoding="utf-8")
        print("Patched table_format.py: removed unsupported st.dataframe(row_height=...) for Streamlit 1.40.2.")
        return

    if "row_height=" in text:
        raise SystemExit("Found an unexpected row_height= usage; refusing an unsafe blind replacement.")

    print("Compatibility patch already applied; no unsupported row_height= usage remains.")


if __name__ == "__main__":
    main()
