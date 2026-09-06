from __future__ import annotations

"""Apply V50 interactive-table/runtime performance migration.

Goals:
- remove the custom add/delete + forced-rerun editor race that can surface
  `Tried to use SessionInfo before it was initialized` on Streamlit 1.40.x;
- batch editable-table input in forms so cell typing does not rerun the whole app;
- render only the selected Deep Company Analysis chapter instead of executing all
  eight st.tabs bodies on every interaction;
- apply the shared sign/intensity heatmap to every explicitly financial numeric column;
- default display order to latest period first, with a real TTM row first when present.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FMT = ROOT / "modules" / "deep_company_analysis" / "table_format.py"
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
SORT_TEST = ROOT / "modules" / "deep_company_analysis" / "test_sortable_table_v32.py"


def _replace_function(text: str, name: str, replacement: str) -> str:
    start = text.index(f"def {name}(")
    next_def = text.find("\ndef ", start + 5)
    if next_def < 0:
        raise RuntimeError(f"Could not find end of {name}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[next_def + 1 :]


def patch_table_format() -> None:
    text = FMT.read_text(encoding="utf-8")

    heat = '''def _heat_eligible(column: str) -> bool:
    """Apply sign/intensity heat to every explicitly financial numeric column.

    The heat is a visual sign/magnitude aid only: red means negative and emerald means
    positive. It is deliberately *not* a good/bad investment judgement.
    """
    return infer_numeric_kind(str(column)) in {
        "amount_bil", "percent", "ratio", "days", "shares", "number"
    }
'''
    text = _replace_function(text, "_heat_eligible", heat)

    period = '''def _period_sort_rank(value: Any) -> tuple[int, float]:
    """Return a display-only recency rank; it never fabricates a financial period."""
    import re

    label = str(value or "").strip()
    upper = label.upper()
    if _is_ttm_label(label):
        return 3, float("inf")

    q1 = re.search(r"(20\\d{2})\\D*Q([1-4])", upper)
    q2 = re.search(r"Q([1-4])\\D*(20\\d{2})", upper)
    if q1:
        return 2, float(int(q1.group(1)) * 10 + int(q1.group(2)))
    if q2:
        return 2, float(int(q2.group(2)) * 10 + int(q2.group(1)))

    year = re.search(r"(?<!\\d)(20\\d{2})(?!\\d)", upper)
    if year:
        return 1, float(int(year.group(1)) * 10)

    parsed = pd.to_datetime(label, errors="coerce", dayfirst=True)
    if not pd.isna(parsed):
        return 1, float(pd.Timestamp(parsed).timestamp())
    return 0, float("-inf")


def prefer_ttm_latest(value: Any) -> pd.DataFrame:
    """Default display order: real TTM first, then newest recognised period to oldest.

    This function changes only presentation order. It never creates a TTM row or alters
    the underlying financial calculations. Unrecognised period labels remain after known
    periods in their original relative order.
    """
    frame = _coerce_frame(value)
    if frame.empty:
        return frame
    period_col = _period_column(frame)
    if period_col is None:
        return frame

    work = frame.copy().reset_index(drop=True)
    ranks = work[period_col].map(_period_sort_rank)
    work["__tre_period_group"] = [item[0] for item in ranks]
    work["__tre_period_rank"] = [item[1] for item in ranks]
    work["__tre_original_order"] = range(len(work))
    work = work.sort_values(
        ["__tre_period_group", "__tre_period_rank", "__tre_original_order"],
        ascending=[False, False, True],
        kind="stable",
        na_position="last",
    )
    return work.drop(
        columns=["__tre_period_group", "__tre_period_rank", "__tre_original_order"],
        errors="ignore",
    ).reset_index(drop=True)
'''
    # Replace prefer_ttm_latest and insert the helper directly before it.
    start = text.index("def prefer_ttm_latest(")
    next_def = text.find("\ndef ", start + 5)
    if next_def < 0:
        raise RuntimeError("Could not find end of prefer_ttm_latest")
    text = text[:start] + period.rstrip() + "\n\n" + text[next_def + 1 :]

    dynamic = '''def _dynamic_editor(value: pd.DataFrame, *, key: str, kwargs: dict[str, Any]) -> pd.DataFrame:
    """Stable dynamic editor with native add/delete and form-batched reruns.

    Streamlit reruns a script on normal widget changes. A large eight-chapter research page
    therefore becomes slow if every cell edit immediately causes a full rerun. The editor is
    placed inside a form: analysts can edit/add/delete several rows locally, then commit once
    with the submit button. Native ``num_rows='dynamic'`` removes the previous custom
    add/delete + widget-generation + ``st.rerun()`` race.
    """
    source = prefer_ttm_latest(value).reset_index(drop=True)
    rows_key = f"{key}__rows"
    source_key = f"{key}__source_signature"
    generation_key = f"{key}__generation"
    source_signature = _frame_signature(source)

    if st.session_state.get(source_key) != source_signature or rows_key not in st.session_state:
        st.session_state[rows_key] = source.copy()
        st.session_state[source_key] = source_signature
        st.session_state[generation_key] = int(st.session_state.get(generation_key, 0)) + 1

    working = _coerce_frame(st.session_state.get(rows_key)).reset_index(drop=True)
    for column in source.columns:
        if column not in working.columns:
            working[column] = None
    working = working[list(source.columns)] if len(source.columns) else working

    provided_config = kwargs.pop("column_config", None)
    column_config = _default_editor_column_config(working)
    if isinstance(provided_config, dict):
        column_config.update(provided_config)

    generation = int(st.session_state.get(generation_key, 0))
    disabled = kwargs.get("disabled", False)
    with st.form(f"{key}__form_{generation}", clear_on_submit=False, border=False):
        edited = st.data_editor(
            working,
            num_rows="dynamic",
            key=f"{key}__grid_{generation}",
            column_config=column_config or None,
            **kwargs,
        )
        submitted = st.form_submit_button(
            "✅ Áp dụng thay đổi bảng",
            use_container_width=True,
            disabled=bool(disabled) if isinstance(disabled, bool) else False,
            help="Có thể nhập/thêm/xóa nhiều dòng trước; app chỉ xử lý lại khi bấm nút này.",
        )

    if submitted:
        committed = _coerce_frame(edited).reset_index(drop=True)
        st.session_state[rows_key] = committed.copy()

    committed = _coerce_frame(st.session_state.get(rows_key)).reset_index(drop=True)
    if any(infer_numeric_kind(str(column)) != "text" for column in committed.columns) and not committed.empty:
        with st.expander("🌡️ Xem format số liệu / heatmap", expanded=False):
            render_static_table(committed, use_container_width=True, hide_index=True)
    return committed
'''
    text = _replace_function(text, "_dynamic_editor", dynamic)

    # Update wrapper wording: dynamic editor prioritises stable row editing; read-only tables
    # retain native header sorting.
    old = '''    The old external sort selectors are gone. For tables that previously requested dynamic rows,\n    add/delete is provided by the wrapper while the underlying Streamlit editor stays fixed-row so\n    native header sorting remains enabled on Streamlit 1.40.x.\n'''
    new = '''    The old external sort selectors are gone. Dynamic analyst-input tables use Streamlit's native\n    add/delete rows inside a form to avoid a rerun on every cell edit. Read-only tables retain\n    native click-on-header sorting; dynamic editors prioritise stable row management.\n'''
    text = text.replace(old, new)

    FMT.write_text(text, encoding="utf-8")


def patch_unified_page() -> None:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("# Phase 8E summary is descriptive only.")
    first_body = text.index("\nwith chapter1_tab:", start)
    selector = '''CHAPTER_OPTIONS = (
    "📗 Chương 1 — Cơ hội đầu tư",
    "📘 Chương 2 — Hiểu doanh nghiệp",
    "📙 Chương 3 — Góc nhìn khách hàng",
    "📕 Chương 4 — Lợi thế & ngành",
    "📒 Chương 5 — Hoạt động & tài chính",
    "📓 Chương 6 — Earnings & dòng tiền",
    "👥 Chương 7 — Ban điều hành",
    "🧭 Chương 8 — Năng lực vận hành",
)

# Only the selected chapter is executed. Unlike st.tabs, this avoids rebuilding all eight
# chapter bodies after each analyst interaction and materially reduces edit latency.
active_chapter = st.radio(
    "Chương phân tích",
    CHAPTER_OPTIONS,
    horizontal=True,
    key="dca_active_chapter",
    label_visibility="collapsed",
)
# chapter8_tab compatibility marker: Chapter 8 remains embedded in this unified page.
'''
    text = text[:start] + selector + text[first_body:]

    replacements = {
        "with chapter1_tab:": "if active_chapter == CHAPTER_OPTIONS[0]:",
        "with chapter2_tab:": "if active_chapter == CHAPTER_OPTIONS[1]:",
        "with chapter3_tab:": "if active_chapter == CHAPTER_OPTIONS[2]:",
        "with chapter4_tab:": "if active_chapter == CHAPTER_OPTIONS[3]:",
        "with chapter5_tab:": "if active_chapter == CHAPTER_OPTIONS[4]:",
        "with chapter6_tab:": "if active_chapter == CHAPTER_OPTIONS[5]:",
        "with chapter7_tab:": "if active_chapter == CHAPTER_OPTIONS[6]:",
        "with chapter8_tab:": "if active_chapter == CHAPTER_OPTIONS[7]:",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    ch8_marker = "if active_chapter == CHAPTER_OPTIONS[7]:\n    chapter8_ticker ="
    ch8_replacement = '''if active_chapter == CHAPTER_OPTIONS[7]:
    # Phase 8E summary is descriptive only. It never computes a management score or changes the investment gate.
    _ch8_summary_payload = load_chapter8_record(default_ticker)
    _ch8_summary = build_chapter8_summary(_ch8_summary_payload)
    with st.expander("🧭 Trạng thái nghiên cứu Chương 8 — Q39 đến Q47", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Answered", f"{_ch8_summary['answered']}/{_ch8_summary['total_questions']}")
        c2.metric("Partial", _ch8_summary["partial"])
        c3.metric("Promoted evidence", _ch8_summary["promoted_evidence"])
        c4.metric("Open research gaps", _ch8_summary["research_gaps_open"])
        c5.metric("Analyst conclusions", _ch8_summary["analyst_conclusions"])
        st.caption("Đây là research-completeness summary, không phải Management Quality Score và không tạo BUY/HOLD/SELL.")

    chapter8_ticker ='''
    if ch8_marker not in text:
        raise RuntimeError("Chapter 8 block marker not found")
    text = text.replace(ch8_marker, ch8_replacement, 1)

    PAGE.write_text(text, encoding="utf-8")


def patch_legacy_sort_tests() -> None:
    text = SORT_TEST.read_text(encoding="utf-8")
    old_fn_start = text.index("def test_dynamic_editors_keep_header_sorting_enabled():")
    old_fn_end = text.index("\ndef test_ttm_is_default_latest_period_without_fabrication():", old_fn_start)
    new_fn = '''def test_dynamic_editors_are_form_batched_without_forced_rerun():
    source = inspect.getsource(table_format._dynamic_editor)
    assert "st.form(" in source
    assert 'num_rows="dynamic"' in source
    assert "st.form_submit_button(" in source
    assert "st.rerun(" not in source
    assert "__add_row" not in source
    assert "__delete_rows" not in source

'''
    text = text[:old_fn_start] + new_fn + text[old_fn_end + 1 :]
    text = text.replace(
        'assert out["Kỳ"].tolist() == ["2024", "2025", "TTM"]',
        'assert out["Kỳ"].tolist() == ["TTM", "2025", "2024"]',
    )
    text = text.replace(
        'assert out2["Kỳ"].tolist() == ["2024", "2025"]',
        'assert out2["Kỳ"].tolist() == ["2025", "2024"]',
    )
    SORT_TEST.write_text(text, encoding="utf-8")


def main() -> None:
    patch_table_format()
    patch_unified_page()
    patch_legacy_sort_tests()
    print("V50 interactive table/performance migration applied.")


if __name__ == "__main__":
    main()
