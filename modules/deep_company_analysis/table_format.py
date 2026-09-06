from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
import hashlib
import inspect

import pandas as pd
import streamlit as st


_PERIOD_COLUMNS = ("Kỳ", "Period", "period", "Kỳ dữ liệu")
_DELETE_COLUMN = "__trecapital_delete_row__"


def infer_numeric_kind(column: str) -> str:
    """Infer only explicit/known Trecapital display units.

    Unknown labels stay text so the renderer never invents a financial unit.
    """
    name = str(column or "").strip()
    low = name.casefold()
    if "(tỷ)" in low or " tỷ" in low or low.endswith("tỷ"):
        return "amount_bil"
    if "(ngày)" in low or " ngày" in low or low in {"dso", "dio", "dpo", "ccc"} or low.startswith(("dso ", "dio ", "dpo ", "ccc ")):
        return "days"
    if "(x)" in low or "/ebit" in low or "/interest" in low or "current ratio" in low or "turnover" in low or "turns" in low:
        return "ratio"
    pct_tokens = (
        "%", "margin", "roic", "yield", "growth", "tăng trưởng", "revenue share",
        "market share", "retention rate", "churn rate", "drawdown", "percentile",
    )
    if any(token in low for token in pct_tokens):
        return "percent"
    if any(token in low for token in ("shares", "share count", "share-count", "cổ phiếu", "co phieu")):
        return "shares"
    return "text"


def _format_vi_number(number: float, decimals: int) -> str:
    """Vietnamese display convention: '.' thousands and ',' decimals."""
    rendered = f"{float(number):,.{int(decimals)}f}"
    return rendered.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def format_numeric(value: Any, kind: str) -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        number = float(value)
    except Exception:
        return escape(str(value or ""))
    if kind == "amount_bil":
        return _format_vi_number(number, 0)
    if kind == "percent":
        return f"{_format_vi_number(number, 1)}%"
    if kind == "ratio":
        return f"{_format_vi_number(number, 1)}x"
    if kind in {"days", "shares", "number"}:
        return _format_vi_number(number, 1)
    if kind == "integer":
        return _format_vi_number(number, 0)
    return escape(str(value))


def _heat_eligible(column: str) -> bool:
    """Apply sign/intensity heat to every explicitly financial numeric column.

    The heat is a visual sign/magnitude aid only: red means negative and emerald means
    positive. It is deliberately *not* a good/bad investment judgement.
    """
    return infer_numeric_kind(str(column)) in {
        "amount_bil", "percent", "ratio", "days", "shares", "number"
    }

def _heat_style(value: Any, max_abs: float) -> str:
    try:
        number = float(value)
    except Exception:
        return ""
    if pd.isna(number) or number == 0:
        return ""
    scale = min(1.0, abs(number) / max_abs) if max_abs > 0 else 0.0
    alpha = 0.07 + 0.23 * scale
    if number < 0:
        return f"color:#991B1B;font-weight:700;background:rgba(185,28,28,{alpha:.3f});"
    return f"color:#047857;font-weight:700;background:rgba(4,120,87,{alpha:.3f});"


def _coerce_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    data = getattr(value, "data", None)
    if isinstance(data, pd.DataFrame):
        return data.copy()
    try:
        return pd.DataFrame(value)
    except Exception:
        return pd.DataFrame()


def _period_column(frame: pd.DataFrame) -> str | None:
    return next((column for column in _PERIOD_COLUMNS if column in frame.columns), None)


def _is_ttm_label(value: Any) -> bool:
    label = str(value or "").strip().upper()
    return label == "TTM" or label.startswith("TTM ") or label.endswith(" TTM")


def default_latest_period_index(options: Any) -> int:
    """Return the default index for a period selector.

    TTM is always preferred when it is actually present. If canonical data does not contain TTM,
    the last available period is used. No TTM value is ever fabricated.
    """
    try:
        values = list(options)
    except Exception:
        values = []
    if not values:
        return 0
    for index in range(len(values) - 1, -1, -1):
        if _is_ttm_label(values[index]):
            return index
    return len(values) - 1


def default_latest_period(options: Any) -> Any:
    """Return the actual default period value, preferring a real TTM value."""
    try:
        values = list(options)
    except Exception:
        values = []
    if not values:
        return None
    return values[default_latest_period_index(values)]


def _period_sort_rank(value: Any) -> tuple[int, float]:
    """Return a display-only recency rank; it never fabricates a financial period."""
    import re

    label = str(value or "").strip()
    upper = label.upper()
    if _is_ttm_label(label):
        return 3, float("inf")

    q1 = re.search(r"(20\d{2})\D*Q([1-4])", upper)
    q2 = re.search(r"Q([1-4])\D*(20\d{2})", upper)
    if q1:
        return 2, float(int(q1.group(1)) * 10 + int(q1.group(2)))
    if q2:
        return 2, float(int(q2.group(2)) * 10 + int(q2.group(1)))

    year = re.search(r"(?<!\d)(20\d{2})(?!\d)", upper)
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

def static_table_html(value: Any, *, height: int | None = None) -> str:
    """Legacy export/preview HTML formatter.

    Production interactive tables must be rendered with render_static_table/sortable_data_editor so
    the header itself is the sort control. This formatter is retained only for non-interactive
    export/preview compatibility.
    """
    frame = _coerce_frame(value)
    if frame.empty:
        return ""
    cols = list(frame.columns)
    max_abs: dict[str, float] = {}
    for column in cols:
        kind = infer_numeric_kind(column)
        if kind == "text" or not _heat_eligible(column):
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()
        max_abs[column] = float(numeric.max()) if not numeric.empty else 0.0

    head = "".join(f"<th>{escape(str(column))}</th>" for column in cols)
    body: list[str] = []
    for _, row in frame.iterrows():
        cells: list[str] = []
        for column in cols:
            kind = infer_numeric_kind(column)
            raw = row.get(column)
            if kind == "text":
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    text = "—"
                else:
                    text = escape(str(raw))
                cells.append(f"<td>{text}</td>")
            else:
                style = _heat_style(raw, max_abs.get(column, 0.0)) if _heat_eligible(column) else ""
                cells.append(f'<td class="num" style="{style}">{format_numeric(raw, kind)}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

    max_height = f"max-height:{int(height)}px;" if height else ""
    return (
        '<div class="tre-dca-static-table"><style>'
        '.tre-dca-static-table{overflow:auto;width:100%;' + max_height + '}'
        '.tre-dca-static-table table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.92rem;}'
        '.tre-dca-static-table th,.tre-dca-static-table td{border:1px solid rgba(148,163,184,.35);padding:7px 8px;'
        'white-space:normal;overflow-wrap:anywhere;vertical-align:top;}'
        '.tre-dca-static-table th{position:sticky;top:0;z-index:1;background:#F0FDF4;color:#065F46;font-weight:800;}'
        '.tre-dca-static-table td.num{text-align:right;font-variant-numeric:tabular-nums;}'
        '</style><table><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
    )


def _default_editor_column_config(frame: pd.DataFrame) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for column in frame.columns:
        kind = infer_numeric_kind(str(column))
        if kind == "amount_bil":
            config[column] = st.column_config.NumberColumn(str(column), format="%.0f", help="Đơn vị: tỷ đồng; 0 số lẻ.")
        elif kind == "percent":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f%%", help="Đơn vị: %; 1 số lẻ.")
        elif kind == "ratio":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Hệ số; 1 số lẻ.")
        elif kind == "days":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Số ngày; 1 số lẻ.")
        elif kind == "shares":
            config[column] = st.column_config.NumberColumn(str(column), format="%.1f", help="Số lượng cổ phiếu; hiển thị 1 số lẻ nếu dữ liệu có phần thập phân.")
    return config


def _stable_editor_key(frame: pd.DataFrame, explicit: str | None) -> str:
    """Build a rerun-stable editor key when a caller did not provide one."""
    if explicit:
        return str(explicit)
    caller = "unknown"
    for info in inspect.stack()[2:]:
        if Path(info.filename).resolve() != Path(__file__).resolve():
            caller = f"{info.filename}:{info.lineno}"
            break
    seed = f"{caller}|{list(frame.columns)}"
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:14]
    return f"tre_editor_{digest}"


def _frame_signature(frame: pd.DataFrame) -> str:
    try:
        payload = frame.to_json(orient="split", date_format="iso", default_handler=str)
    except Exception:
        payload = repr((list(frame.columns), frame.shape, frame.astype(str).values.tolist()))
    return hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()


def _dynamic_editor(value: pd.DataFrame, *, key: str, kwargs: dict[str, Any]) -> pd.DataFrame:
    """Stable dynamic editor with native add/delete and form-batched reruns.

    Streamlit reruns a script on normal widget changes. A large eight-chapter research page
    therefore becomes slow if every cell edit immediately causes a full rerun. The editor is
    placed inside a form: analysts can edit/add/delete several rows locally, then commit once
    with the submit button. Native ``num_rows='dynamic'`` removes the previous custom
    add/delete + widget-generation + forced-rerun race.
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
    # Some chapter editors already live inside an expander. Streamlit 1.40.x forbids
    # nested expanders, so show the formatted heatmap preview only after an explicit
    # table commit and render it directly in the current container.
    if (
        submitted
        and any(infer_numeric_kind(str(column)) != "text" for column in committed.columns)
        and not committed.empty
    ):
        st.caption("🌡️ Format số liệu / heatmap sau khi áp dụng thay đổi")
        render_static_table(committed, use_container_width=True, hide_index=True)
    return committed

def sortable_data_editor(value: Any, **kwargs: Any):
    """Editable table whose column headers are the only sorting controls.

    The old external sort selectors are gone. Dynamic analyst-input tables use Streamlit's native
    add/delete rows inside a form to avoid a rerun on every cell edit. Read-only tables retain
    native click-on-header sorting; dynamic editors prioritise stable row management.
    """
    frame = prefer_ttm_latest(value)
    requested_num_rows = str(kwargs.pop("num_rows", "fixed") or "fixed").strip().lower()
    explicit_key = kwargs.pop("key", None)

    if requested_num_rows == "dynamic":
        return _dynamic_editor(frame, key=_stable_editor_key(frame, explicit_key), kwargs=kwargs)

    defaults = _default_editor_column_config(frame)
    provided = kwargs.get("column_config")
    if isinstance(provided, dict):
        defaults.update(provided)
    if defaults:
        kwargs["column_config"] = defaults
    if explicit_key is not None:
        kwargs["key"] = explicit_key
    return st.data_editor(frame, num_rows="fixed", **kwargs)


def _native_table_styler(frame: pd.DataFrame):
    """Apply the display contract without converting sortable numeric cells to strings."""
    styler = frame.style
    formatters: dict[str, Any] = {}
    for column in frame.columns:
        kind = infer_numeric_kind(str(column))
        if kind != "text":
            formatters[column] = (lambda value, k=kind: format_numeric(value, k))
        if not _heat_eligible(str(column)):
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce").abs().dropna()
        max_abs = float(numeric.max()) if not numeric.empty else 0.0
        styler = styler.map(lambda value, m=max_abs: _heat_style(value, m), subset=[column])
    if formatters:
        styler = styler.format(formatters, na_rep="—")
    return styler


def render_static_table(value: Any, **kwargs: Any) -> None:
    """Read-only native grid: click a column header to sort ascending/descending.

    No separate sort function/control exists. If TTM is present, its initial/default position is the
    latest row; users remain free to sort any column directly from its header.
    """
    frame = prefer_ttm_latest(value)
    if frame.empty:
        st.caption("Chưa có dữ liệu.")
        return
    kwargs.pop("sort_key", None)
    kwargs.pop("key", None)
    height = kwargs.pop("height", None)
    hide_index = kwargs.pop("hide_index", True)
    use_container_width = kwargs.pop("use_container_width", True)
    provided = kwargs.pop("column_config", None)
    # Static grids use Pandas Styler for localized display (1.234 / 12,3%). Passing a
    # Streamlit NumberColumn printf format here would override the localized Styler text.
    # The underlying frame remains numeric, so native click-on-header sorting still works.
    column_config = provided if isinstance(provided, dict) else None
    st.dataframe(
        _native_table_styler(frame),
        use_container_width=use_container_width,
        hide_index=hide_index,
        height=int(height) if height else None,
        column_config=column_config,
        **kwargs,
    )


__all__ = [
    "default_latest_period", "default_latest_period_index", "format_numeric", "infer_numeric_kind",
    "prefer_ttm_latest", "render_static_table", "sortable_data_editor", "static_table_html",
]
