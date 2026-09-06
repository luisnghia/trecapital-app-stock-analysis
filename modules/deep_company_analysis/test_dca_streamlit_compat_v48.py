from __future__ import annotations

import ast
import inspect
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
DCA_DIR = ROOT / "modules" / "deep_company_analysis"
UNIFIED_PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
SIDEBAR = ROOT / "tre_sidebar_nav.py"
STANDALONE_CH8 = ROOT / "pages" / "09_Phan_tich_chuyen_sau_Chuong_8.py"


def _direct_streamlit_calls(path: Path, names: set[str]):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "st"
            and func.attr in names
        ):
            continue
        yield node.lineno, func.attr, [kw.arg for kw in node.keywords if kw.arg is not None]


def test_streamlit_dataframe_editor_keywords_match_pinned_runtime():
    signatures = {
        "dataframe": inspect.signature(st.dataframe),
        "data_editor": inspect.signature(st.data_editor),
    }
    allowed = {name: set(sig.parameters) for name, sig in signatures.items()}
    problems: list[str] = []

    paths = list(DCA_DIR.glob("*.py")) + [UNIFIED_PAGE]
    for path in paths:
        for line, name, keywords in _direct_streamlit_calls(path, set(signatures)):
            unsupported = sorted(set(keywords) - allowed[name])
            if unsupported:
                problems.append(f"{path.relative_to(ROOT)}:{line} st.{name} unsupported={unsupported}")

    assert not problems, "Unsupported Streamlit kwargs for pinned runtime:\n" + "\n".join(problems)


def test_shared_table_renderer_has_no_row_height_kwarg():
    text = (DCA_DIR / "table_format.py").read_text(encoding="utf-8")
    assert "row_height=" not in text


def test_chapter8_is_embedded_in_unified_page_only():
    page = UNIFIED_PAGE.read_text(encoding="utf-8")
    sidebar = SIDEBAR.read_text(encoding="utf-8")
    assert "render_chapter8_tab" in page
    assert "🧭 Chương 8 — Năng lực vận hành" in page
    assert "chapter8_tab" in page
    assert "09_Phan_tich_chuyen_sau_Chuong_8.py" not in sidebar
    assert not STANDALONE_CH8.exists()
