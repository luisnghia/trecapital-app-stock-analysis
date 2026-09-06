from __future__ import annotations

"""Apply V49 Deep Company Analysis numeric-display contract migrations.

Display rules locked for Vietnamese UI:
- VND billions: 0 decimals
- percentages: 1 decimal
- ratios/days: 1 decimal
- thousands separator: '.'
- decimal separator: ','
- negative financial values: red; positive/growth values: emerald

The patch keeps underlying DataFrame cells numeric so native Streamlit header sorting remains usable.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == "scripts" else Path.cwd()
MOD = ROOT / "modules" / "deep_company_analysis"


def replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return False
    if old not in text:
        raise SystemExit(f"{label}: expected source block not found; refusing blind patch")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: patched")
    return True


def patch_table_format() -> None:
    path = MOD / "table_format.py"
    replace_once(
        path,
        '''    if any(token in low for token in pct_tokens):\n        return "percent"\n    return "text"\n\n\ndef format_numeric(value: Any, kind: str) -> str:\n''',
        '''    if any(token in low for token in pct_tokens):\n        return "percent"\n    if any(token in low for token in ("shares", "share count", "share-count", "cổ phiếu", "co phieu")):\n        return "shares"\n    return "text"\n\n\ndef _format_vi_number(number: float, decimals: int) -> str:\n    """Vietnamese display convention: '.' thousands and ',' decimals."""\n    rendered = f"{float(number):,.{int(decimals)}f}"\n    return rendered.replace(",", "\\u0000").replace(".", ",").replace("\\u0000", ".")\n\n\ndef format_numeric(value: Any, kind: str) -> str:\n''',
        "table_format inference/locale helper",
    )
    replace_once(
        path,
        '''    if kind == "amount_bil":\n        return f"{number:,.0f}"\n    if kind == "percent":\n        return f"{number:,.1f}%"\n    if kind == "ratio":\n        return f"{number:,.1f}x"\n    if kind == "days":\n        return f"{number:,.1f}"\n    return escape(str(value))\n''',
        '''    if kind == "amount_bil":\n        return _format_vi_number(number, 0)\n    if kind == "percent":\n        return f"{_format_vi_number(number, 1)}%"\n    if kind == "ratio":\n        return f"{_format_vi_number(number, 1)}x"\n    if kind in {"days", "shares", "number"}:\n        return _format_vi_number(number, 1)\n    if kind == "integer":\n        return _format_vi_number(number, 0)\n    return escape(str(value))\n''',
        "table_format numeric output",
    )
    replace_once(
        path,
        '''        elif kind == "days":\n            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Số ngày; 1 số lẻ.")\n    return config\n''',
        '''        elif kind == "days":\n            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Số ngày; 1 số lẻ.")\n        elif kind == "shares":\n            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Số lượng cổ phiếu; hiển thị 1 số lẻ nếu dữ liệu có phần thập phân.")\n    return config\n''',
        "table_format editor shares",
    )
    replace_once(
        path,
        '''def _native_table_styler(frame: pd.DataFrame):\n    styler = frame.style\n    for column in frame.columns:\n        if not _heat_eligible(str(column)):\n            continue\n        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()\n        max_abs = float(numeric.max()) if not numeric.empty else 0.0\n        styler = styler.map(lambda value, m=max_abs: _heat_style(value, m), subset=[column])\n    return styler\n''',
        '''def _native_table_styler(frame: pd.DataFrame):\n    """Apply the display contract without converting sortable numeric cells to strings."""\n    styler = frame.style\n    formatters: dict[str, Any] = {}\n    for column in frame.columns:\n        kind = infer_numeric_kind(str(column))\n        if kind != "text":\n            formatters[column] = (lambda value, k=kind: format_numeric(value, k))\n        if not _heat_eligible(str(column)):\n            continue\n        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()\n        max_abs = float(numeric.max()) if not numeric.empty else 0.0\n        styler = styler.map(lambda value, m=max_abs: _heat_style(value, m), subset=[column])\n    if formatters:\n        styler = styler.format(formatters, na_rep="—")\n    return styler\n''',
        "table_format native styler",
    )
    replace_once(
        path,
        '''    provided = kwargs.pop("column_config", None)\n    column_config = _default_editor_column_config(frame)\n    if isinstance(provided, dict):\n        column_config.update(provided)\n    st.dataframe(\n        _native_table_styler(frame),\n        use_container_width=use_container_width,\n        hide_index=hide_index,\n        height=int(height) if height else None,\n        column_config=column_config or None,\n        **kwargs,\n    )\n''',
        '''    provided = kwargs.pop("column_config", None)\n    # Static grids use Pandas Styler for localized display (1.234 / 12,3%). Passing a\n    # Streamlit NumberColumn printf format here would override the localized Styler text.\n    # The underlying frame remains numeric, so native click-on-header sorting still works.\n    column_config = provided if isinstance(provided, dict) else None\n    st.dataframe(\n        _native_table_styler(frame),\n        use_container_width=use_container_width,\n        hide_index=hide_index,\n        height=int(height) if height else None,\n        column_config=column_config,\n        **kwargs,\n    )\n''',
        "table_format static localized display",
    )


def patch_chapter6_format() -> None:
    path = MOD / "chapter6_format.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind"
    if import_line in text:
        print("chapter6_format shared contract: already applied")
        return
    start = text.find("def infer_numeric_kind")
    end = text.find("def has_financial_numeric_columns")
    if start < 0 or end < 0 or end <= start:
        raise SystemExit("chapter6_format shared contract: expected duplicate formatter not found")
    patched = text[:start] + import_line + "\n\n\n" + text[end:]
    path.write_text(patched, encoding="utf-8")
    print("chapter6_format shared contract: patched")


def patch_chapter6_caption() -> None:
    replace_once(
        MOD / "chapter6_page_support.py",
        '''                "Quy chuẩn: tỷ đồng 0 số lẻ; % và hệ số 1 số lẻ; số âm đỏ, số dương xanh ngọc; "\n                "cường độ màu tăng theo độ lớn tuyệt đối."\n''',
        '''                "Quy chuẩn: tỷ đồng 0 số lẻ; % và hệ số 1 số lẻ; dấu chấm ngăn cách hàng nghìn, "\n                "dấu phẩy thập phân; số âm đỏ, số dương xanh ngọc; cường độ màu tăng theo độ lớn tuyệt đối."\n''',
        "chapter6 format caption",
    )


def patch_test_expectations() -> None:
    replacements = {
        "test_table_format.py": {
            "'1,235'": "'1.235'", "'12.3%'": "'12,3%'", "'2.3x'": "'2,3x'", "'45.7'": "'45,7'",
            "'10.2%'": "'10,2%'", "'-5.4%'": "'-5,4%'",
        },
        "test_chapter6_format.py": {
            '"1,235"': '"1.235"', '"12.3%"': '"12,3%"', '"1.2x"': '"1,2x"',
            '"-5.2%"': '"-5,2%"', '"10.2%"': '"10,2%"',
        },
        "test_sortable_table_v32.py": {
            '"1,235"': '"1.235"', '"12.3%"': '"12,3%"', '"2.3x"': '"2,3x"', '"45.7"': '"45,7"',
        },
    }
    for name, pairs in replacements.items():
        path = MOD / name
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in pairs.items():
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            print(f"{name}: localized expectations patched")
        else:
            print(f"{name}: expectations already localized")


def main() -> None:
    patch_table_format()
    patch_chapter6_format()
    patch_chapter6_caption()
    patch_test_expectations()


if __name__ == "__main__":
    main()
