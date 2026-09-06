from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "modules" / "deep_company_analysis" / "table_format.py"
CH1 = ROOT / "modules" / "deep_company_analysis" / "chapter1.py"
TEST = ROOT / "modules" / "deep_company_analysis" / "test_sortable_table_v32.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.2 marker not found: {label}")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, replacement: str, label: str) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"V37.2 regex marker not found: {label}")
    return new_text


def patch_table_format() -> None:
    text = TABLE.read_text(encoding="utf-8")

    legacy = '''def interactive_sort_frame(value: Any, *, key: str | None = None) -> pd.DataFrame:\n    """Render explicit selectable sort controls and return the sorted raw frame."""\n    frame = _coerce_frame(value)\n    if frame.empty or len(frame.columns) == 0:\n        return frame\n    base = _stable_widget_key(frame, key, "sort")\n    cols = [str(c) for c in frame.columns]\n    c1, c2 = st.columns([3, 1])\n    with c1:\n        sort_by = st.selectbox(\n            "Sort theo cột",\n            [ORIGINAL_ORDER_LABEL] + cols,\n            index=0,\n            key=f"{base}_column",\n        )\n    with c2:\n        direction = st.selectbox(\n            "Thứ tự",\n            [ASC_LABEL, DESC_LABEL],\n            index=0,\n            key=f"{base}_direction",\n        )\n    if sort_by == ORIGINAL_ORDER_LABEL:\n        return frame\n    return sort_frame(frame, sort_by, ascending=direction == ASC_LABEL)\n\n\n'''
    replacement = '''def prefer_ttm_latest(value: Any) -> pd.DataFrame:\n    """Keep a valid TTM row as the latest/default period without fabricating one.\n\n    The relative order of all non-TTM rows is preserved. This is a display/default-order helper;\n    it never creates or recalculates TTM data.\n    """\n    frame = _coerce_frame(value)\n    if frame.empty:\n        return frame\n    period_col = next((c for c in ("Kỳ", "Period", "period", "Kỳ dữ liệu") if c in frame.columns), None)\n    if period_col is None:\n        return frame\n    labels = frame[period_col].fillna("").astype(str).str.strip().str.upper()\n    is_ttm = labels.eq("TTM")\n    if not bool(is_ttm.any()):\n        return frame\n    return pd.concat([frame.loc[~is_ttm], frame.loc[is_ttm]], ignore_index=True)\n\n\ndef interactive_sort_frame(value: Any, *, key: str | None = None) -> pd.DataFrame:\n    """Legacy compatibility shim. No visible sort controls are rendered.\n\n    Sorting is handled natively by clicking a table column header. New production callers should use\n    render_static_table / sortable_data_editor directly.\n    """\n    del key\n    return prefer_ttm_latest(value)\n\n\n'''
    text = replace_once(text, legacy, replacement, "remove explicit sort widgets")

    old_editor = '''def sortable_data_editor(value: Any, **kwargs: Any):\n    """Editable table with explicit sort selector plus Trecapital numeric formatting."""\n    frame = _coerce_frame(value)\n    editor_key = kwargs.get("key")\n    sorted_frame = interactive_sort_frame(frame, key=f"editor_{editor_key}" if editor_key else None)\n    defaults = _default_editor_column_config(sorted_frame)\n    provided = kwargs.get("column_config")\n    if isinstance(provided, dict):\n        defaults.update(provided)\n    if defaults:\n        kwargs["column_config"] = defaults\n    return st.data_editor(sorted_frame, **kwargs)\n\n\n'''
    new_editor = '''def sortable_data_editor(value: Any, **kwargs: Any):\n    """Editable table using Streamlit's native click-on-header sorting.\n\n    No separate sort selector is rendered. Dynamic-row editors retain their edit/add/delete behavior;\n    native sorting availability follows Streamlit's editor capabilities.\n    """\n    frame = prefer_ttm_latest(value)\n    defaults = _default_editor_column_config(frame)\n    provided = kwargs.get("column_config")\n    if isinstance(provided, dict):\n        defaults.update(provided)\n    if defaults:\n        kwargs["column_config"] = defaults\n    return st.data_editor(frame, **kwargs)\n\n\n'''
    text = replace_once(text, old_editor, new_editor, "native editor header sort")

    old_static = '''def render_static_table(value: Any, **kwargs: Any) -> None:\n    """Read-only table with explicit user-selectable sort and locked display format."""\n    frame = _coerce_frame(value)\n    if frame.empty:\n        st.caption("Chưa có dữ liệu.")\n        return\n    sort_key = kwargs.pop("sort_key", None) or kwargs.pop("key", None)\n    frame = interactive_sort_frame(frame, key=f"static_{sort_key}" if sort_key else None)\n    height = kwargs.get("height")\n    st.html(static_table_html(frame, height=int(height) if height else None))\n'''
    new_static = '''def _native_table_styler(frame: pd.DataFrame):\n    styler = frame.style\n    for column in frame.columns:\n        if not _heat_eligible(str(column)):\n            continue\n        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()\n        max_abs = float(numeric.max()) if not numeric.empty else 0.0\n        styler = styler.map(lambda value, m=max_abs: _heat_style(value, m), subset=[column])\n    return styler\n\n\ndef render_static_table(value: Any, **kwargs: Any) -> None:\n    """Read-only native grid: click a column header to sort ascending/descending.\n\n    The old separate 'Sort theo cột / Thứ tự' controls are intentionally removed.\n    """\n    frame = prefer_ttm_latest(value)\n    if frame.empty:\n        st.caption("Chưa có dữ liệu.")\n        return\n    kwargs.pop("sort_key", None)\n    kwargs.pop("key", None)\n    height = kwargs.pop("height", None)\n    hide_index = kwargs.pop("hide_index", True)\n    use_container_width = kwargs.pop("use_container_width", True)\n    provided = kwargs.pop("column_config", None)\n    column_config = _default_editor_column_config(frame)\n    if isinstance(provided, dict):\n        column_config.update(provided)\n    st.dataframe(\n        _native_table_styler(frame),\n        use_container_width=use_container_width,\n        hide_index=hide_index,\n        height=int(height) if height else None,\n        column_config=column_config or None,\n        row_height=42,\n        **kwargs,\n    )\n'''
    text = replace_once(text, old_static, new_static, "native dataframe header sort")

    text = text.replace(
        '    "format_numeric", "infer_numeric_kind", "interactive_sort_frame", "render_static_table",\n    "sort_frame", "sortable_data_editor", "static_table_html",\n',
        '    "format_numeric", "infer_numeric_kind", "interactive_sort_frame", "prefer_ttm_latest", "render_static_table",\n    "sort_frame", "sortable_data_editor", "static_table_html",\n',
    )
    TABLE.write_text(text, encoding="utf-8")


def patch_chapter1() -> None:
    text = CH1.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'from modules.deep_company_analysis.table_format import interactive_sort_frame\n',
        'from modules.deep_company_analysis.table_format import render_static_table\n',
        "chapter1 shared table import",
    )
    old_inventory = '''            if not subset.empty:\n                subset = interactive_sort_frame(subset, key=f"ch1_inventory_{gate_key}")\n                for col in ["Giá", "Target"]:\n                    subset[col] = subset[col].map(lambda x: _fmt_number(x, 0))\n                for col in ["MOS %", "FCF Yield %"]:\n                    subset[col] = subset[col].map(lambda x: _fmt_number(x, 1, "%"))\n        if hasattr(st, "html"):\n            st.html(_html_table(subset))\n        else:\n            st.markdown(_html_table(subset), unsafe_allow_html=True)\n'''
    new_inventory = '''        render_static_table(\n            subset,\n            use_container_width=True,\n            hide_index=True,\n            height=min(420, 78 + 38 * max(1, len(subset))),\n        )\n'''
    text = replace_once(text, old_inventory, new_inventory, "chapter1 inventory native table")

    old_history = '''    history = load_gate_history(ticker)\n    st.subheader(f"Gate History — {ticker}")\n    if not history.empty:\n        history = interactive_sort_frame(history, key=f"ch1_gate_history_{ticker}")\n    if hasattr(st, "html"):\n        st.html(_html_table(history))\n    else:\n        st.markdown(_html_table(history), unsafe_allow_html=True)\n'''
    new_history = '''    history = load_gate_history(ticker)\n    st.subheader(f"Gate History — {ticker}")\n    render_static_table(history, use_container_width=True, hide_index=True, height=300)\n'''
    text = replace_once(text, old_history, new_history, "chapter1 gate history native table")
    CH1.write_text(text, encoding="utf-8")


def patch_test() -> None:
    text = TEST.read_text(encoding="utf-8")
    text = text.replace(
        'from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind, sort_frame, static_table_html\n',
        'from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind, prefer_ttm_latest, sort_frame, static_table_html\n',
    )
    old_tail = '''    table_format = (root / "table_format.py").read_text(encoding="utf-8")\n    assert "def sortable_data_editor" in table_format\n    assert "def interactive_sort_frame" in table_format\n    assert "Sort theo cột" in table_format\n    chapter1 = (root / "chapter1.py").read_text(encoding="utf-8")\n    assert "interactive_sort_frame(subset" in chapter1\n'''
    new_tail = '''    table_format = (root / "table_format.py").read_text(encoding="utf-8")\n    assert "def sortable_data_editor" in table_format\n    assert "def interactive_sort_frame" in table_format  # compatibility shim only\n    assert '"Sort theo cột"' not in table_format\n    assert '"Thứ tự"' not in table_format\n    assert "st.dataframe(" in table_format\n    assert "return st.data_editor(frame, **kwargs)" in table_format\n    chapter1 = (root / "chapter1.py").read_text(encoding="utf-8")\n    assert "interactive_sort_frame" not in chapter1\n    assert "render_static_table(" in chapter1\n\n\ndef test_ttm_is_default_latest_period_without_fabrication():\n    frame = pd.DataFrame({"Kỳ": ["TTM", "2024", "2025"], "CFO (tỷ)": [130, 90, 110]})\n    out = prefer_ttm_latest(frame)\n    assert out["Kỳ"].tolist() == ["2024", "2025", "TTM"]\n    no_ttm = pd.DataFrame({"Kỳ": ["2024", "2025"], "CFO (tỷ)": [90, 110]})\n    out2 = prefer_ttm_latest(no_ttm)\n    assert out2["Kỳ"].tolist() == ["2024", "2025"]\n\n\ndef test_no_visible_legacy_sort_controls_anywhere_in_deep_analysis():\n    root = Path(__file__).resolve().parent\n    for path in root.glob("*.py"):\n        if path.name.startswith("test_"):\n            continue\n        text = path.read_text(encoding="utf-8")\n        assert '"Sort theo cột"' not in text, path.name\n        assert '"Thứ tự"' not in text, path.name\n        if path.name != "table_format.py":\n            assert "interactive_sort_frame(" not in text, path.name\n'''
    text = replace_once(text, old_tail, new_tail, "update sortable table regression contract")
    TEST.write_text(text, encoding="utf-8")


def main() -> None:
    patch_table_format()
    patch_chapter1()
    patch_test()
    print("Deep Analysis V37.2 native header-sort + TTM-latest migration applied")


if __name__ == "__main__":
    main()
