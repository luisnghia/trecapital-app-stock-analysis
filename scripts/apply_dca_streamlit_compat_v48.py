from __future__ import annotations

"""Apply V48 compatibility + unified-Chapter-8 contract migrations.

The project pins Streamlit 1.40.2. ``st.dataframe`` in that version does not accept
``row_height``. The shared table renderer is used across the Deep Company Analysis
chapters, so one unsupported keyword can break every tab during a single Streamlit run.

V48 also moves Chapter 8 into the unified DCA page only, so the older Phase-8D routing
test must follow the approved embedded-tab architecture rather than requiring a standalone
page/sidebar route.

Finally, ``st.set_page_config`` is moved immediately after ``import streamlit as st`` so it
is guaranteed to be the first Streamlit command. Chapter 6's shared editor preview also uses
a bordered container instead of an expander because the editor is frequently rendered from
inside a question expander, and Streamlit 1.40.x forbids nested expanders.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE_FORMAT = ROOT / "modules" / "deep_company_analysis" / "table_format.py"
PHASE8D_TEST = ROOT / "modules" / "deep_company_analysis" / "test_chapter8_phase8d.py"
UNIFIED_PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
CHAPTER6_PAGE = ROOT / "modules" / "deep_company_analysis" / "chapter6_page_support.py"


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

PAGE_CONFIG_BLOCK = '''st.set_page_config(
    page_title="Phân tích chuyên sâu doanh nghiệp | Trecapital",
    page_icon="🔬",
    layout="wide",
)

'''

OLD_CH6_PREVIEW = '''    if has_financial_numeric_columns(columns) and isinstance(edited, pd.DataFrame) and not edited.empty:
        with st.expander(f"🔎 Preview format số liệu — {label}", expanded=False):
            st.caption(
                "Quy chuẩn: tỷ đồng 0 số lẻ; % và hệ số 1 số lẻ; số âm đỏ, số dương xanh ngọc; "
                "cường độ màu tăng theo độ lớn tuyệt đối."
            )
            render_static_table(edited, height=min(360, 90 + 30 * len(edited)), sort_key=f"{key}_formatted_preview")
'''

NEW_CH6_PREVIEW = '''    if has_financial_numeric_columns(columns) and isinstance(edited, pd.DataFrame) and not edited.empty:
        # _editor is commonly called from inside a question expander. Streamlit 1.40.x forbids
        # nested expanders, so the formatted preview uses a plain bordered container.
        with st.container(border=True):
            st.caption(f"🔎 Preview format số liệu — {label}")
            st.caption(
                "Quy chuẩn: tỷ đồng 0 số lẻ; % và hệ số 1 số lẻ; số âm đỏ, số dương xanh ngọc; "
                "cường độ màu tăng theo độ lớn tuyệt đối."
            )
            render_static_table(edited, height=min(360, 90 + 30 * len(edited)), sort_key=f"{key}_formatted_preview")
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


def patch_page_config_order() -> bool:
    text = UNIFIED_PAGE.read_text(encoding="utf-8")
    import_marker = "import streamlit as st\n"
    desired_marker = import_marker + "\n" + PAGE_CONFIG_BLOCK
    if desired_marker in text:
        print("Unified page already sets page config before project imports.")
        return False
    if PAGE_CONFIG_BLOCK not in text:
        raise SystemExit("Unified page set_page_config block not found; refusing blind edit.")
    if import_marker not in text:
        raise SystemExit("Unified page Streamlit import not found; refusing blind edit.")
    text = text.replace(PAGE_CONFIG_BLOCK, "", 1)
    text = text.replace(import_marker, desired_marker, 1)
    UNIFIED_PAGE.write_text(text, encoding="utf-8")
    print("Patched unified page: st.set_page_config is now the first Streamlit command.")
    return True


def patch_chapter6_nested_preview() -> bool:
    text = CHAPTER6_PAGE.read_text(encoding="utf-8")
    if OLD_CH6_PREVIEW in text:
        CHAPTER6_PAGE.write_text(text.replace(OLD_CH6_PREVIEW, NEW_CH6_PREVIEW, 1), encoding="utf-8")
        print("Patched Chapter 6 editor preview: nested expander replaced by bordered container.")
        return True
    if NEW_CH6_PREVIEW in text:
        print("Chapter 6 nested-preview compatibility patch already applied.")
        return False
    raise SystemExit("Chapter 6 editor preview did not match expected old/new block; refusing blind edit.")


def main() -> None:
    patch_table_format()
    patch_phase8d_route_contract()
    patch_page_config_order()
    patch_chapter6_nested_preview()


if __name__ == "__main__":
    main()
