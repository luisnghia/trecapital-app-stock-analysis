from __future__ import annotations

"""Apply V48 compatibility + unified-Chapter-8 contract migrations.

The project pins Streamlit 1.40.2. ``st.dataframe`` in that version does not accept
``row_height``. The shared table renderer is used across the Deep Company Analysis
chapters, so one unsupported keyword can break every tab during a single Streamlit run.

V48 also moves Chapter 8 into the unified DCA page only, so the older Phase-8D routing
test must follow the approved embedded-tab architecture rather than requiring a standalone
page/sidebar route.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE_FORMAT = ROOT / "modules" / "deep_company_analysis" / "table_format.py"
PHASE8D_TEST = ROOT / "modules" / "deep_company_analysis" / "test_chapter8_phase8d.py"


OLD_ROUTE_TEST = '''def test_phase8d_route_and_sidebar_are_wired():
    root = Path(__file__).resolve().parents[2]
    page = root / "pages" / "09_Phan_tich_chuyen_sau_Chuong_8.py"
    sidebar = root / "tre_sidebar_nav.py"
    assert page.exists()
    assert "render_chapter8_tab" in page.read_text(encoding="utf-8")
    assert "09_Phan_tich_chuyen_sau_Chuong_8.py" in sidebar.read_text(encoding="utf-8")
'''

NEW_ROUTE_TEST = '''def test_phase8d_route_and_sidebar_are_wired():
    root = Path(__file__).resolve().parents[2]
    unified_page = root / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
    standalone_page = root / "pages" / "09_Phan_tich_chuyen_sau_Chuong_8.py"
    sidebar = root / "tre_sidebar_nav.py"
    page_text = unified_page.read_text(encoding="utf-8")
    sidebar_text = sidebar.read_text(encoding="utf-8")
    assert unified_page.exists()
    assert "render_chapter8_tab" in page_text
    assert "🧭 Chương 8 — Năng lực vận hành" in page_text
    assert not standalone_page.exists()
    assert "09_Phan_tich_chuyen_sau_Chuong_8.py" not in sidebar_text
'''


def patch_table_format() -> bool:
    text = TABLE_FORMAT.read_text(encoding="utf-8")
    old = "        row_height=42,\n"
    if old in text:
        TABLE_FORMAT.write_text(text.replace(old, "", 1), encoding="utf-8")
        print("Patched table_format.py: removed unsupported st.dataframe(row_height=...) for Streamlit 1.40.2.")
        return True
    if "row_height=" in text:
        raise SystemExit("Found an unexpected row_height= usage; refusing an unsafe blind replacement.")
    print("table_format.py compatibility patch already applied.")
    return False


def patch_phase8d_route_contract() -> bool:
    text = PHASE8D_TEST.read_text(encoding="utf-8")
    if OLD_ROUTE_TEST in text:
        PHASE8D_TEST.write_text(text.replace(OLD_ROUTE_TEST, NEW_ROUTE_TEST, 1), encoding="utf-8")
        print("Patched Phase-8D route test: Chapter 8 is embedded in unified DCA page only.")
        return True
    if "standalone_page = root / \"pages\" / \"09_Phan_tich_chuyen_sau_Chuong_8.py\"" in text:
        print("Phase-8D route test already follows the unified-tab contract.")
        return False
    raise SystemExit("Phase-8D route test did not match expected old/new contract; refusing blind edit.")


def main() -> None:
    patch_table_format()
    patch_phase8d_route_contract()


if __name__ == "__main__":
    main()
