"""Plain HTML operational tables with stable, native task selection.

The score form and workflow stay in their existing role pages. This renderer
does not load Streamlit's lazy DataFrame module, write data or change scope.
"""
from __future__ import annotations

import ast
import html
import math

TABLE_CSS = """<style>
.ops-review-scroll{width:100%;max-width:100%;overflow:auto;border:1px solid #4E7771;border-radius:8px}
.ops-review-table{width:100%;min-width:900px;table-layout:fixed;border-collapse:collapse;font-size:14px}
.ops-review-table th,.ops-review-table td{white-space:normal;overflow-wrap:anywhere;word-break:normal;
  padding:10px 8px;border:1px solid #4E7771;vertical-align:top;line-height:1.5}
.ops-review-table th{background:#17312F;color:#6FD6C4;font-weight:800;position:sticky;top:0;z-index:1}
.ops-review-table tr.selected td{box-shadow:inset 0 3px #F4B41A,inset 0 -3px #F4B41A}
html.khdn-light .ops-review-table th{background:#F0F7F3;color:#0B2A25}
</style>"""


def render_readonly_table(st, frame, *, height=560, **_ignored):
    height = max(180, min(900, int(height or 560)))
    st.html(TABLE_CSS + f"<div class='ops-review-scroll' style='max-height:{height}px'>"
            + frame.to_html(index=False, escape=True, border=0, classes="ops-review-table") + "</div>")


def _text(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return "—"
    return str(value)


def _identity(row, columns):
    return ":".join(str(int(row[column])) for column in columns)


def choose_row(st, rows, display, key, *, id_columns=("id",), height=540,
               label="Chọn công việc để thao tác", logger=None, review=False):
    """Select by database identity, never by the position in a changing table."""
    widget_key = key + "_record"
    target_key = key + "_review_target"
    if rows is None or rows.empty:
        st.session_state.pop(widget_key, None)
        st.session_state.pop(target_key, None)
        return None
    identities = [_identity(row, id_columns) for _, row in rows.iterrows()]
    if len(set(identities)) != len(identities) or len(display) != len(rows):
        raise ValueError("Danh sách hồ sơ chưa đồng nhất. Vui lòng tải lại màn hình.")
    previous = st.session_state.get(widget_key)
    if previous is not None and previous not in identities:
        st.session_state.pop(widget_key, None)
        previous = None
    labels = {}
    for identity, (_, row) in zip(identities, rows.iterrows()):
        parts = [_text(row.get("task_code") or f"Hồ sơ #{row.get('id', row.get('task_id'))}"),
                 _text(row.get("cif")), _text(row.get("customer_name")),
                 _text(row.get("task_type")), _text(row.get("support_name"))]
        if "round_no" in row:
            parts.append(f"Vòng {int(row.round_no)}")
        labels[identity] = " · ".join(parts)
    # Actions belong before the long table, where they remain easy to find on
    # small screens. The review form opens only after the explicit action.
    selected = st.selectbox(label, identities, index=None, key=widget_key,
                            placeholder="Chọn hồ sơ theo mã, khách hàng hoặc công việc",
                            format_func=lambda identity: labels[identity])
    active_review = False
    if review:
        token = None
        if selected is not None:
            record = rows.iloc[identities.index(selected)]
            token = (selected, int(record.get("current_round", 1)))
        if st.session_state.get(target_key) != token:
            st.session_state.pop(target_key, None)
        if st.button("⭐ Đánh giá công việc", key=key + "_open_review", type="primary",
                     use_container_width=True, disabled=selected is None,
                     help="Mở phần chấm điểm và nhận xét cho công việc đã chọn.") and token is not None:
            st.session_state[target_key] = token
            if logger:
                logger.info("OPS_REVIEW_FORM_OPEN key=%s task=%s round=%s", key, token[0], token[1])
        active_review = token is not None and st.session_state.get(target_key) == token
        if not active_review:
            st.caption("Chọn hồ sơ rồi bấm Đánh giá công việc để mở phần chấm điểm và nhận xét.")
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
        selected_class = " class='selected'" if identity == selected else ""
        body.append(f"<tr{selected_class}>" + "".join(cells) + "</tr>")
    height = max(180, min(900, int(height or 540)))
    table_html = (TABLE_CSS + f"<div class='ops-review-scroll' style='max-height:{height}px'>"
            + "<table class='ops-review-table'><thead><tr>" + head + "</tr></thead><tbody>"
            + "".join(body) + "</tbody></table></div>")
    if active_review:
        with st.expander(f"Danh sách công việc chờ đánh giá ({len(rows)})", expanded=False):
            st.html(table_html)
    else:
        st.html(table_html)
    if logger:
        log_key = key + "_render_log"
        signature = (tuple(identities), selected, active_review)
        if st.session_state.get(log_key) != signature:
            logger.info("OPS_HTML_TASK_TABLE key=%s rows=%s selected=%s", key, len(rows), selected)
            st.session_state[log_key] = signature
    if selected is None or review and not active_review:
        return None
    return rows.iloc[identities.index(selected)]


def selectable_task_table(app_ns, df, key, *, include_status=True, include_phase=False, height=None):
    if df is None or df.empty:
        app_ns["st"].session_state.pop(key + "_record", None)
        app_ns["st"].session_state.pop(key + "_review_target", None)
        return None
    rows = app_ns["enrich_tasks"](df.copy()).reset_index(drop=True)
    if include_phase:
        targets = app_ns["_workflow_delay_targets"]()
        info = [app_ns["_phase_delay_info"](row, targets) for _, row in rows.iterrows()]
        rows["phase_name"] = [value["phase"] for value in info]
        rows["wait_minutes"] = [value["elapsed"] for value in info]
        rows["delay_level"] = [value["level"] for value in info]
    columns = ["task_code", "cif", "customer_name", "support_name", "qlkh_name", "task_type", "amount_vnd", "assigned_at"]
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
    history_text = history_text.replace("def task_history(task_id):\n",
        "def task_history(task_id):\n    from khdn_apps.operational_review_table import render_readonly_table as _html_history_table\n", 1)
    history_lines[history.lineno - 1:history.end_lineno] = [history_text]
    result = "".join(history_lines)
    # Selection and the explicit review action now precede the long HTML table.
    for old in ("Chọn trực tiếp một dòng hồ sơ", "Chọn trực tiếp một dòng công việc"):
        result = result.replace(old, "Chọn công việc ở danh sách phía trên bảng")
    return result
