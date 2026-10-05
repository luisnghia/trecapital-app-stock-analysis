"""Plain HTML operational tables with direct, stable row selection.

The score form and workflow stay in their existing role pages. This renderer
does not load Streamlit's lazy DataFrame module, write data or change scope.
"""
from __future__ import annotations

import ast
import hashlib
import html
import json
import math
import weakref

TABLE_CSS = """<style>
.ops-review-scroll{width:100%;max-width:100%;overflow:auto;border:1px solid #4E7771;border-radius:8px}
.ops-review-table{width:100%;min-width:900px;table-layout:fixed;border-collapse:collapse;font-size:14px}
.ops-review-table th,.ops-review-table td{white-space:normal;overflow-wrap:anywhere;word-break:normal;
  padding:10px 8px;border:1px solid #4E7771;vertical-align:top;line-height:1.5}
.ops-review-table th{background:#17312F;color:#6FD6C4;font-weight:800;position:sticky;top:0;z-index:1}
.ops-review-table tr.selected td{box-shadow:inset 0 3px #F4B41A,inset 0 -3px #F4B41A}
.ops-review-table tr[data-ops-row]{cursor:pointer}
.ops-review-table tr[data-ops-row]:not(.selected):hover td{box-shadow:inset 0 2px #6FD6C4,inset 0 -2px #6FD6C4}
.ops-review-table tr[data-ops-row]:focus-visible{outline:3px solid #F4B41A;outline-offset:-3px}
html.khdn-light .ops-review-table th{background:#F0F7F3;color:#0B2A25}
.ops-review-table.ops-history-table{min-width:0}
.ops-history-table th{text-align:left}
.ops-history-table td{white-space:pre-wrap}
.ops-history-value{min-width:0;overflow-wrap:anywhere}
@media(max-width:640px){
  .ops-history-table,.ops-history-table tbody,.ops-history-table tr{display:block;width:100%}
  .ops-history-table colgroup{display:none}
  .ops-history-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
  .ops-history-table tr{border-bottom:2px solid #4E7771}
  .ops-history-table td{display:grid;grid-template-columns:7rem minmax(0,1fr);gap:8px;border:0;padding:7px 10px}
  .ops-history-table td::before{content:attr(data-label);color:#6FD6C4;font-weight:800;white-space:normal}
  .ops-history-table td.ops-history-detail{display:block;border-top:1px solid #4E7771}
  .ops-history-table td.ops-history-detail::before{display:block;margin-bottom:4px}
  html.khdn-light .ops-history-table td::before{color:#0B2A25}
}
</style>"""

# The table itself is rendered through st.html. A JS-only v2 component handles
# its row events using Streamlit's supported one-rerun trigger API. Delegation
# works even when the table DOM arrives after the bridge or is replaced on rerun.
ROW_CLICK_JS = """
export default function({data, setTriggerValue}) {
  const activate = (event) => {
    if (event.type === 'click' && event.button !== undefined && event.button !== 0) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target?.closest ? event.target : event.target?.parentElement;
    const row = target?.closest('tr[data-ops-row]');
    const table = row?.closest('table[data-ops-table]');
    if (!table || table.dataset.opsTable !== data.table_id || table.dataset.opsVersion !== data.version) return;
    if (event.type === 'keydown') {
      if (event.target !== row || !['Enter', ' '].includes(event.key) || event.repeat) return;
    } else {
      const selection = document.getSelection();
      if (selection && !selection.isCollapsed && row.contains(selection.anchorNode)) return;
    }
    event.preventDefault();
    setTriggerValue('row_clicked', {
      table_id: data.table_id, version: data.version,
      identity: row.dataset.opsRow, round: Number(row.dataset.opsRound)
    });
  };
  document.addEventListener('click', activate);
  document.addEventListener('keydown', activate);
  return () => {
    document.removeEventListener('click', activate);
    document.removeEventListener('keydown', activate);
  };
}
"""
_ROW_BRIDGES = weakref.WeakKeyDictionary()


def _row_click_event(st, key, table_id, version):
    from streamlit.runtime import Runtime
    registry = Runtime.instance().bidi_component_registry
    if registry not in _ROW_BRIDGES:
        _ROW_BRIDGES[registry] = st.components.v2.component(
            "khdn_operational_row_click_v1", js=ROW_CLICK_JS, isolate_styles=False)
    result = _ROW_BRIDGES[registry](
        key=key + "_row_click", data={"table_id": table_id, "version": version},
        on_row_clicked_change=lambda: None, height=0)
    return result.row_clicked


def render_readonly_table(st, frame, *, height=560, logger=None, **_ignored):
    height = max(180, min(900, int(height or 560)))
    # History uses the available width, rather than the 900px task-list minimum.
    # Metadata stays compact; the audit text/comment gets the remaining space.
    weights = ({"Thời gian": 14, "Người thực hiện": 18, "Hành động": 13, "Chi tiết": 55}
               if "Chi tiết" in frame.columns else
               {"Vòng": 6, "Người đánh giá": 18, "Chất lượng": 10, "Tiến độ": 10,
                "Góp ý": 42, "Thời gian": 14})
    total = sum(weights.get(column, 15) for column in frame.columns) or 1
    widths = "".join(f"<col style='width:{100 * weights.get(column, 15) / total:.2f}%'>"
                     for column in frame.columns)
    head = "".join("<th scope='col'>" + html.escape(str(column)) + "</th>" for column in frame.columns)
    body = []
    for _, row in frame.iterrows():
        cells = []
        for column, value in row.items():
            detail_class = " class='ops-history-detail'" if column in {"Chi tiết", "Góp ý"} else ""
            cells.append(f"<td{detail_class} data-label='{html.escape(str(column), quote=True)}'>"
                         + "<span class='ops-history-value'>" + html.escape(_text(value)) + "</span></td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.html(TABLE_CSS + f"<div class='ops-review-scroll' style='max-height:{height}px'>"
            + "<table class='ops-review-table ops-history-table'><colgroup>" + widths + "</colgroup>"
            + "<thead><tr>" + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")
    if logger:
        logger.info("OPS_HISTORY_TABLE_RENDER rows=%s columns=%s fit_width=1 full_detail=1",
                    len(frame), len(frame.columns))


def _text(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return "—"
    return str(value)


def _identity(row, columns):
    return ":".join(str(int(row[column])) for column in columns)


def choose_row(st, rows, display, key, *, id_columns=("id",), height=540,
               label="Chọn công việc để thao tác", logger=None, review=False):
    """Open a row by database ID/round; never trust its table position."""
    selected_key = key + "_selected_row"
    # Remove state from the superseded menu/action workflow.
    st.session_state.pop(key + "_record", None)
    st.session_state.pop(key + "_review_target", None)
    if rows is None or rows.empty:
        st.session_state.pop(selected_key, None)
        return None
    identities = [_identity(row, id_columns) for _, row in rows.iterrows()]
    if len(set(identities)) != len(identities) or len(display) != len(rows):
        raise ValueError("Danh sách hồ sơ chưa đồng nhất. Vui lòng tải lại màn hình.")
    rounds = {identity: int(row.get("current_round", row.get("round_no", 0)))
              for identity, (_, row) in zip(identities, rows.iterrows())}
    statuses = {identity: _text(row.get("status"))
                for identity, (_, row) in zip(identities, rows.iterrows())}
    table_id = "ops-" + hashlib.sha256(key.encode()).hexdigest()[:20]
    version = hashlib.sha256(json.dumps(sorted(
        (identity, rounds[identity], statuses[identity]) for identity in identities
    )).encode()).hexdigest()
    selected = st.session_state.get(selected_key)
    if not isinstance(selected, tuple) or len(selected) != 2 or rounds.get(selected[0]) != selected[1]:
        st.session_state.pop(selected_key, None)
        selected = None
    clicked = _row_click_event(st, key, table_id, version)
    if clicked is not None:
        valid = (isinstance(clicked, dict) and clicked.get("table_id") == table_id
                 and clicked.get("version") == version and isinstance(clicked.get("identity"), str)
                 and clicked.get("identity") in rounds
                 and clicked.get("round") == rounds.get(clicked.get("identity")))
        if valid:
            selected = (clicked["identity"], rounds[clicked["identity"]])
            st.session_state[selected_key] = selected
            if logger:
                logger.info("OPS_ROW_SELECTED key=%s task=%s round=%s review=%s", key, *selected, review)
        else:
            st.session_state.pop(selected_key, None)
            selected = None
            st.warning("Danh sách đã thay đổi. Vui lòng chọn lại dòng công việc.")
            if logger:
                logger.warning("OPS_ROW_SELECTION_REJECTED key=%s reason=stale_or_out_of_scope", key)
    selected_id = selected[0] if selected else None
    styles = {
        "Khách hàng": "background:#EAF2FF;color:#164E9A;font-weight:750",
        "Công việc": "background:#FFF3CD;color:#7A4B00;font-weight:800",
        "Giá trị (tỷ đồng)": "background:#E7F7EF;color:#0B684F;font-weight:800",
        "Cán bộ hỗ trợ": "background:#F1EAFE;color:#5A3A91;font-weight:700",
        "Cán bộ quản lý khách hàng": "background:#E6F7F5;color:#08645D;font-weight:700",
    }
    head = "".join("<th scope='col'>" + html.escape(str(column)) + "</th>" for column in display.columns)
    body = []
    for identity, (_, row) in zip(identities, display.iterrows()):
        cells = []
        for column, value in row.items():
            style = styles.get(column, "")
            if column == "Mức độ trễ":
                for icon, color, ink in [("🔴", "#FECACA", "#7F1D1D"), ("🟠", "#FED7AA", "#7C2D12"),
                                         ("🟡", "#FEF3C7", "#713F12"), ("🟢", "#DCFCE7", "#14532D")]:
                    if icon in _text(value):
                        style = f"background:{color};color:{ink};font-weight:800"
                        break
            cells.append(f"<td style='{style}'>" + html.escape(_text(value)) + "</td>")
        is_selected = identity == selected_id
        selected_class = " class='selected'" if is_selected else ""
        action = "đánh giá" if review else "xem chi tiết"
        accessible = "Chọn " + " · ".join(_text(value) for value in row.iloc[:3]) + " để " + action
        body.append(f"<tr{selected_class} data-ops-row='{html.escape(identity, quote=True)}' "
                    f"data-ops-round='{rounds[identity]}' tabindex='0' aria-selected='{str(is_selected).lower()}' "
                    f"aria-label='{html.escape(accessible, quote=True)}'>" + "".join(cells) + "</tr>")
    height = max(180, min(900, int(height or 540)))
    table_html = (TABLE_CSS + f"<div class='ops-review-scroll' style='max-height:{height}px'>"
            + f"<table class='ops-review-table' data-ops-table='{table_id}' data-ops-version='{version}'>"
            + "<thead><tr>" + head + "</tr></thead><tbody>"
            + "".join(body) + "</tbody></table></div>")
    st.html(table_html)
    if logger:
        log_key = key + "_render_log"
        signature = (tuple(identities), selected)
        if st.session_state.get(log_key) != signature:
            logger.info("OPS_HTML_TASK_TABLE key=%s rows=%s selected=%s", key, len(rows), selected_id)
            st.session_state[log_key] = signature
    if selected_id is None:
        return None
    return rows.iloc[identities.index(selected_id)]


def selectable_task_table(app_ns, df, key, *, include_status=True, include_phase=False, height=None):
    if df is None or df.empty:
        app_ns["st"].session_state.pop(key + "_selected_row", None)
        return None
    rows = app_ns["enrich_tasks"](df.copy()).reset_index(drop=True)
    if include_phase:
        targets = app_ns["_workflow_delay_targets"]()
        info = [app_ns["_phase_delay_info"](row, targets) for _, row in rows.iterrows()]
        rows["phase_name"] = [value["phase"] for value in info]
        rows["wait_minutes"] = [value["elapsed"] for value in info]
        rows["delay_level"] = [value["level"] for value in info]
    columns = ["cif", "customer_name", "support_name", "qlkh_name", "task_type", "amount_vnd", "assigned_at"]
    columns += [name for name in ("start_time", "end_time") if name in rows.columns]
    if include_phase:
        columns += ["phase_name", "wait_minutes", "delay_level"]
    if include_status:
        columns.append("status_label")
    display = rows[[column for column in columns if column in rows.columns]].copy()
    if "amount_vnd" in display:
        def billions(value):
            try:
                number = float(value) / 1_000_000_000
                return f"{number:,.0f}".replace(",", ".") if math.isfinite(number) else "—"
            except (TypeError, ValueError):
                return "—"
        display["amount_vnd"] = display["amount_vnd"].map(billions)
    for name in ("assigned_at", "start_time", "end_time"):
        if name in display:
            display[name] = display[name].map(app_ns["fmt_dt"])
    if "wait_minutes" in display:
        display["wait_minutes"] = display["wait_minutes"].map(app_ns["_minutes_human"])
    display = display.rename(columns={
        "task_code": "Mã tác nghiệp", "cif": "CIF", "customer_name": "Khách hàng",
        "support_name": "Cán bộ hỗ trợ", "qlkh_name": "Cán bộ quản lý khách hàng", "task_type": "Công việc",
        "amount_vnd": "Giá trị (tỷ đồng)", "assigned_at": "Thời gian giao", "start_time": "Bắt đầu",
        "end_time": "Kết thúc", "phase_name": "Mốc đang chờ", "wait_minutes": "Thời gian đang chờ",
        "delay_level": "Mức độ trễ", "status_label": "Trạng thái",
    })
    app_ns["st"].caption("CIF là mã khách hàng. Giá trị trong bảng được quy đổi sang tỷ đồng.")
    review = "eval" in key
    label = "Chọn công việc cần đánh giá" if review else "Chọn công việc để thao tác"
    return choose_row(app_ns["st"], rows, display, key, height=height or app_ns["_task_list_height"](len(rows)),
                      label=label, logger=app_ns.get("LOGGER"), review=review)


def patch_source(source):
    """Replace the actual common renderer in the compressed online/offline engine."""
    marker = "from khdn_apps.operational_review_table import selectable_task_table as _html_task_table"
    if marker in source:
        return source
    tree = ast.parse(source)
    targets = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "selectable_task_table"]
    if len(targets) != 1:
        raise RuntimeError("Operational HTML table patch requires one selectable_task_table")
    node = targets[0]
    lines = source.splitlines(keepends=True)
    replacement = '''def selectable_task_table(df, key, *, include_status=True, include_phase=False, height=None):
    from khdn_apps.operational_review_table import selectable_task_table as _html_task_table
    return _html_task_table(globals(), df, key, include_status=include_status, include_phase=include_phase, height=height)
'''
    lines[node.lineno - 1:node.end_lineno] = [replacement]
    result = "".join(lines)
    # Detail history must also work after saving a review, without the same
    # failing DataFrame asset being requested in its two history columns.
    history = next(node for node in ast.parse(result).body
                   if isinstance(node, ast.FunctionDef) and node.name == "task_history")
    history_lines = result.splitlines(keepends=True)
    history_text = "".join(history_lines[history.lineno - 1:history.end_lineno])
    if history_text.count("st.dataframe(") != 2:
        raise RuntimeError("Operational HTML history patch requires two history tables")
    history_text = history_text.replace("st.dataframe(", "_html_history_table(st,")
    # The audit table needs the full page width; evaluation history follows it.
    history_text = history_text.replace("    c1, c2 = st.columns(2)\n", "")
    history_text = history_text.replace("    with c1:\n", "    with st.container():\n")
    history_text = history_text.replace("    with c2:\n", "    with st.container():\n")
    history_text = history_text.replace("use_container_width=True, hide_index=True, height=",
                                        "logger=LOGGER, use_container_width=True, hide_index=True, height=")
    history_text = history_text.replace("def task_history(task_id):\n",
        "def task_history(task_id):\n    from khdn_apps.operational_review_table import render_readonly_table as _html_history_table\n", 1)
    history_lines[history.lineno - 1:history.end_lineno] = [history_text]
    result = "".join(history_lines)
    # Restore the row-selection guidance in the installed role pages.
    for old in ("Chọn công việc ở danh sách phía trên bảng",
                "Chọn hồ sơ ở danh sách phía trên bảng"):
        result = result.replace(old, "Chọn trực tiếp một dòng công việc")
    return result
