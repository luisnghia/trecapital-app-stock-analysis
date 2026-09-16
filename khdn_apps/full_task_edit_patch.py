"""KHDN Ops V2.31.3 - full dossier editor for Leader/Admin.

Adds an audited full-record editor for all tasks, including CLOSED/CANCELLED rows.
Business/audit history stays append-only; edits create new audit events instead of
rewriting historical action rows.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

PATCH_VERSION = "2.31.3"
_INSTALL_FLAG = "_KHDN_FULL_TASK_EDIT_V2313"


def _dt_text(ns: dict[str, Any], value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        dt = ns["parse_dt"](value)
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
    except Exception:
        return str(value or "")


def _normalize_dt(ns: dict[str, Any], value: str, field_label: str) -> tuple[str | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return None, None
    try:
        dt = ns["parse_dt"](text)
        if dt is None:
            return None, f"{field_label}: thời gian không hợp lệ."
        return dt.strftime("%Y-%m-%d %H:%M:%S"), None
    except Exception:
        return None, f"{field_label}: dùng định dạng YYYY-MM-DD HH:MM:SS hoặc DD/MM/YYYY HH:MM."


def _raw_task(ns: dict[str, Any], task_id: int) -> dict[str, Any] | None:
    with ns["get_conn"]() as c:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (int(task_id),)).fetchone()
        return dict(r) if r else None


def _task_list(ns: dict[str, Any], query: str, statuses: list[str]):
    sql = """SELECT t.id,t.task_code,t.status,t.task_type,t.amount,t.currency,t.updated_at,
                    c.cif,c.customer_name,s.full_name AS support_name,q.full_name AS qlkh_name
             FROM tasks t
             JOIN customers c ON c.id=t.customer_id
             JOIN users s ON s.id=t.support_user_id
             JOIN users q ON q.id=t.qlkh_user_id
             WHERE 1=1"""
    params: list[Any] = []
    if statuses:
        marks = ",".join("?" for _ in statuses)
        sql += f" AND t.status IN ({marks})"
        params.extend(statuses)
    text = str(query or "").strip().lower()
    if text:
        like = f"%{text}%"
        sql += " AND (LOWER(COALESCE(t.task_code,'')) LIKE ? OR LOWER(COALESCE(c.cif,'')) LIKE ? OR LOWER(COALESCE(c.customer_name,'')) LIKE ? OR LOWER(COALESCE(t.task_type,'')) LIKE ?)"
        params.extend([like, like, like, like])
    sql += " ORDER BY COALESCE(t.updated_at,t.created_at) DESC,t.id DESC"
    return ns["qdf"](sql, tuple(params))


def _lookup_frames(ns: dict[str, Any], row: dict[str, Any]):
    customers = ns["qdf"]("SELECT id,cif,customer_name,active FROM customers ORDER BY active DESC,cif,customer_name")
    support = ns["qdf"]("SELECT id,username,full_name,active FROM users WHERE role='Cán bộ hỗ trợ' AND deleted_at IS NULL ORDER BY active DESC,full_name")
    qlkh = ns["qdf"]("SELECT id,username,full_name,active FROM users WHERE role='Cán bộ QLKH' AND deleted_at IS NULL ORDER BY active DESC,full_name")
    all_users = ns["qdf"]("SELECT id,username,full_name,role,active FROM users WHERE deleted_at IS NULL ORDER BY active DESC,full_name")
    types = ns["qdf"]("SELECT name,active FROM task_types ORDER BY active DESC,name")
    return customers, support, qlkh, all_users, types


def _id_options(df, current_id: int) -> list[int]:
    vals = [int(x) for x in df["id"].tolist()] if df is not None and not df.empty else []
    if int(current_id) not in vals:
        vals.insert(0, int(current_id))
    return vals


def _user_label(df, uid: int) -> str:
    try:
        r = df[df.id.eq(int(uid))].iloc[0]
        suffix = "" if int(r.get("active", 1)) else " · ngừng hoạt động"
        role = f" · {r.get('role','')}" if "role" in r.index else ""
        return f"{r.full_name} ({r.username}){role}{suffix}"
    except Exception:
        return f"ID {uid}"


def _customer_label(df, cid: int) -> str:
    try:
        r = df[df.id.eq(int(cid))].iloc[0]
        suffix = "" if int(r.get("active", 1)) else " · ngừng hoạt động"
        return f"{r.cif} - {r.customer_name}{suffix}"
    except Exception:
        return f"ID {cid}"


def _changed(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        if key in {"updated_at"}:
            continue
        a, b = before.get(key), after.get(key)
        if a != b:
            out[key] = {"before": a, "after": b}
    return out


def _audit_task_edit(ns: dict[str, Any], c, task_id: int, actor_id: int, changes: dict[str, Any], ts: str) -> None:
    detail = json.dumps(changes, ensure_ascii=False, default=str, separators=(",", ":"))
    summary = ", ".join(changes.keys()) if changes else "Không có thay đổi nghiệp vụ"
    c.execute(
        "INSERT INTO task_actions(task_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
        (task_id, actor_id, "LEADER_ADMIN_EDIT", f"Sửa toàn bộ hồ sơ: {summary}; snapshot={detail}", ts),
    )
    c.execute(
        "INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
        (actor_id, "TASK_FULL_EDIT", "task", str(task_id), detail, ts),
    )


def _render_task_form(ns: dict[str, Any], user: dict[str, Any], task_id: int) -> None:
    st = ns["st"]
    row = _raw_task(ns, task_id)
    if not row:
        st.error("Không tìm thấy hồ sơ.")
        return
    customers, support, qlkh, all_users, types = _lookup_frames(ns, row)

    # Summary chips use the canonical app renderer.
    summary = ns["qdf"]("""SELECT t.*,c.cif,c.customer_name,s.full_name support_name,q.full_name qlkh_name
                           FROM tasks t JOIN customers c ON c.id=t.customer_id
                           JOIN users s ON s.id=t.support_user_id JOIN users q ON q.id=t.qlkh_user_id
                           WHERE t.id=?""", (task_id,))
    if not summary.empty and callable(ns.get("render_task_chips")):
        ns["render_task_chips"](summary.iloc[0], time_label="Cập nhật", time_field="updated_at")

    st.info("Có thể sửa cả hồ sơ đang xử lý, đã kết thúc hoặc đã hủy. Mỗi lần lưu đều ghi thêm nhật ký/audit; lịch sử cũ không bị xóa hoặc ghi đè.")

    customer_ids = _id_options(customers, int(row["customer_id"]))
    support_ids = _id_options(support, int(row["support_user_id"]))
    qlkh_ids = _id_options(qlkh, int(row["qlkh_user_id"]))
    task_types = sorted(set(types["name"].astype(str).tolist() + [str(row["task_type"])])) if not types.empty else [str(row["task_type"])]
    status_options = list(ns.get("STATUS_LABEL", {}).keys())
    if str(row["status"]) not in status_options:
        status_options.append(str(row["status"]))
    source_options = ["SUPPORT", "QLKH"]
    if str(row.get("request_source") or "") not in source_options:
        source_options.append(str(row.get("request_source") or ""))

    with st.form(key=f"full_task_edit_form_{task_id}", clear_on_submit=False):
        st.markdown("#### Thông tin nghiệp vụ")
        c1, c2 = st.columns(2)
        task_code = c1.text_input("Mã tác nghiệp", value=str(row.get("task_code") or ""))
        customer_id = c2.selectbox("Khách hàng", customer_ids, index=customer_ids.index(int(row["customer_id"])), format_func=lambda x: _customer_label(customers, x))
        c3, c4 = st.columns(2)
        support_id = c3.selectbox("Cán bộ hỗ trợ", support_ids, index=support_ids.index(int(row["support_user_id"])), format_func=lambda x: _user_label(support, x))
        qlkh_id = c4.selectbox("Cán bộ QLKH", qlkh_ids, index=qlkh_ids.index(int(row["qlkh_user_id"])), format_func=lambda x: _user_label(qlkh, x))
        c5, c6 = st.columns(2)
        task_type = c5.selectbox("Loại công việc", task_types, index=task_types.index(str(row["task_type"])))
        request_source = c6.selectbox("Nguồn tạo hồ sơ", source_options, index=source_options.index(str(row.get("request_source") or "SUPPORT")))

        c7, c8, c9 = st.columns([1, 1.5, 1.5])
        currencies = ["VND", "USD", "EUR"]
        if str(row.get("currency") or "VND") not in currencies:
            currencies.append(str(row.get("currency")))
        currency = c7.selectbox("Đơn vị", currencies, index=currencies.index(str(row.get("currency") or "VND")))
        amount_text = c8.text_input("Giá trị", value=ns["money"](row.get("amount") or 0), help="Có thể nhập 23.834,18 hoặc 23,834.18.")
        fx_text = c9.text_input("Tỷ giá", value=ns["money"](row.get("fx_rate") or 1))
        auto_vnd = st.checkbox("Tự tính lại Quy đổi VND = Giá trị × Tỷ giá", value=True, key=f"full_edit_auto_vnd_{task_id}")
        amount_vnd_text = st.text_input("Quy đổi VND", value=ns["money"](row.get("amount_vnd") or 0), disabled=auto_vnd)

        c10, c11, c12 = st.columns(3)
        status = c10.selectbox("Trạng thái", status_options, index=status_options.index(str(row["status"])), format_func=lambda x: ns.get("STATUS_LABEL", {}).get(x, x))
        current_round = int(c11.number_input("Vòng hiện tại", min_value=1, value=int(row.get("current_round") or 1), step=1))
        rework_count = int(c12.number_input("Số lần làm lại", min_value=0, value=int(row.get("rework_count") or 0), step=1))
        note = st.text_area("Ghi chú / yêu cầu xử lý", value=str(row.get("note") or ""), height=110)

        st.markdown("#### Toàn bộ mốc thời gian")
        st.caption("Để trống nếu mốc chưa phát sinh. Có thể nhập YYYY-MM-DD HH:MM:SS hoặc DD/MM/YYYY HH:MM.")
        dt_fields = [
            ("assigned_at", "Giao hồ sơ"), ("accepted_at", "Tiếp nhận gần nhất"), ("first_accepted_at", "Tiếp nhận lần đầu"),
            ("returned_to_qlkh_at", "CBHT trả lại QLKH"), ("cancelled_at", "Hủy hồ sơ"), ("evaluated_at", "QLKH đánh giá"),
            ("last_rework_at", "Yêu cầu làm lại gần nhất"), ("start_time", "Bắt đầu xử lý"), ("due_time", "Hạn xử lý"),
            ("end_time", "CBHT hoàn thành"), ("closed_time", "Kết thúc hồ sơ"), ("created_at", "Tạo hồ sơ"),
        ]
        dt_values: dict[str, str] = {}
        for i in range(0, len(dt_fields), 2):
            cols = st.columns(2)
            for j, (field, label) in enumerate(dt_fields[i:i+2]):
                dt_values[field] = cols[j].text_input(label, value=_dt_text(ns, row.get(field)), key=f"full_edit_{field}_{task_id}")

        save = st.form_submit_button("💾 Lưu toàn bộ thay đổi", type="primary", use_container_width=True)

    if save:
        errors: list[str] = []
        normalized_dt: dict[str, str | None] = {}
        for field, label in dt_fields:
            val, err = _normalize_dt(ns, dt_values.get(field, ""), label)
            normalized_dt[field] = val
            if err:
                errors.append(err)

        amount = float(ns["parse_amount_text"](amount_text))
        fx_rate = float(ns["parse_amount_text"](fx_text))
        amount_vnd = amount * fx_rate if auto_vnd else float(ns["parse_amount_text"](amount_vnd_text))
        if amount < 0:
            errors.append("Giá trị hồ sơ không được âm.")
        if currency == "VND":
            fx_rate = 1.0
            if auto_vnd:
                amount_vnd = amount
        elif fx_rate <= 0:
            errors.append("Tỷ giá ngoại tệ phải lớn hơn 0.")
        if not str(task_type).strip():
            errors.append("Loại công việc không được để trống.")
        if errors:
            for err in errors:
                st.error(err)
            return

        before = _raw_task(ns, task_id) or {}
        ts = ns["now_str"]()
        try:
            with ns["get_conn"]() as c:
                c.execute("""UPDATE tasks SET task_code=?,customer_id=?,support_user_id=?,qlkh_user_id=?,request_source=?,
                             task_type=?,amount=?,currency=?,fx_rate=?,amount_vnd=?,status=?,current_round=?,rework_count=?,note=?,
                             assigned_at=?,accepted_at=?,first_accepted_at=?,returned_to_qlkh_at=?,cancelled_at=?,evaluated_at=?,last_rework_at=?,
                             start_time=?,due_time=?,end_time=?,closed_time=?,created_at=?,updated_at=? WHERE id=?""",
                          (task_code.strip() or None, int(customer_id), int(support_id), int(qlkh_id), request_source,
                           str(task_type).strip(), amount, currency, fx_rate, amount_vnd, status, current_round, rework_count, note.strip(),
                           normalized_dt["assigned_at"], normalized_dt["accepted_at"], normalized_dt["first_accepted_at"],
                           normalized_dt["returned_to_qlkh_at"], normalized_dt["cancelled_at"], normalized_dt["evaluated_at"], normalized_dt["last_rework_at"],
                           normalized_dt["start_time"], normalized_dt["due_time"], normalized_dt["end_time"], normalized_dt["closed_time"], normalized_dt["created_at"], ts, task_id))
                after_row = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
                after = dict(after_row) if after_row else {}
                changes = _changed(before, after)
                _audit_task_edit(ns, c, task_id, int(user["id"]), changes, ts)
            st.success("Đã lưu toàn bộ thay đổi và ghi audit.")
            st.rerun()
        except sqlite3.IntegrityError as exc:
            if "task_code" in str(exc).lower() or "unique" in str(exc).lower():
                st.error("Mã tác nghiệp bị trùng với hồ sơ khác.")
            else:
                st.error(f"Không thể lưu do ràng buộc dữ liệu: {exc}")
        except Exception as exc:
            logging.getLogger("khdn_ops").exception("FULL_TASK_EDIT_FAILED task_id=%s", task_id)
            st.error(f"Không thể lưu hồ sơ: {exc}")

    _render_evaluation_editor(ns, user, task_id, all_users)


def _render_evaluation_editor(ns: dict[str, Any], user: dict[str, Any], task_id: int, all_users) -> None:
    st = ns["st"]
    evaluations = ns["qdf"]("SELECT id,round_no,evaluator_user_id,quality_score,progress_score,comment,created_at FROM evaluations WHERE task_id=? ORDER BY round_no", (task_id,))
    with st.expander("⭐ Sửa điểm/đánh giá của hồ sơ", expanded=False):
        if evaluations.empty:
            st.caption("Hồ sơ chưa có bản ghi đánh giá.")
            return
        eval_ids = evaluations["id"].astype(int).tolist()
        eid = st.selectbox("Vòng đánh giá", eval_ids, format_func=lambda x: f"Vòng {int(evaluations[evaluations.id.eq(x)].iloc[0].round_no)}", key=f"full_edit_eval_select_{task_id}")
        e = evaluations[evaluations.id.eq(int(eid))].iloc[0]
        user_ids = _id_options(all_users, int(e.evaluator_user_id))
        with st.form(key=f"full_edit_eval_form_{task_id}_{eid}"):
            evaluator = st.selectbox("Người đánh giá", user_ids, index=user_ids.index(int(e.evaluator_user_id)), format_func=lambda x: _user_label(all_users, x))
            c1, c2 = st.columns(2)
            quality = float(c1.number_input("Chất lượng", min_value=0.0, max_value=10.0, value=float(e.quality_score), step=0.1))
            progress = float(c2.number_input("Tiến độ", min_value=0.0, max_value=10.0, value=float(e.progress_score), step=0.1))
            comment = st.text_area("Nhận xét đánh giá", value=str(e.comment or ""))
            created = st.text_input("Thời gian đánh giá", value=_dt_text(ns, e.created_at))
            save_eval = st.form_submit_button("Lưu đánh giá", use_container_width=True)
        if save_eval:
            created_at, err = _normalize_dt(ns, created, "Thời gian đánh giá")
            if err:
                st.error(err)
                return
            ts = ns["now_str"]()
            with ns["get_conn"]() as c:
                old = c.execute("SELECT * FROM evaluations WHERE id=?", (int(eid),)).fetchone()
                c.execute("UPDATE evaluations SET evaluator_user_id=?,quality_score=?,progress_score=?,comment=?,created_at=? WHERE id=? AND task_id=?",
                          (int(evaluator), quality, progress, comment.strip(), created_at or ts, int(eid), task_id))
                new = c.execute("SELECT * FROM evaluations WHERE id=?", (int(eid),)).fetchone()
                changes = _changed(dict(old) if old else {}, dict(new) if new else {})
                detail = json.dumps(changes, ensure_ascii=False, default=str, separators=(",", ":"))
                c.execute("INSERT INTO task_actions(task_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                          (task_id, int(user["id"]), "LEADER_ADMIN_EDIT", f"Sửa đánh giá: {detail}", ts))
                c.execute("INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
                          (int(user["id"]), "EVALUATION_EDIT", "evaluation", str(int(eid)), detail, ts))
            st.success("Đã cập nhật đánh giá và ghi audit.")
            st.rerun()


def render_full_task_editor(ns: dict[str, Any], user: dict[str, Any]) -> None:
    st = ns["st"]
    if not (bool(user.get("is_admin")) or user.get("role") == "Lãnh đạo phòng"):
        st.error("Chỉ Admin hoặc Lãnh đạo phòng có quyền sửa toàn bộ hồ sơ.")
        return
    st.markdown("### ✏️ Sửa toàn bộ hồ sơ")
    st.caption("Phạm vi gồm toàn bộ hồ sơ đang xử lý, đã kết thúc và đã hủy. Nhật ký/audit là bất biến và chỉ được bổ sung thêm dấu vết sửa đổi.")
    status_options = list(ns.get("STATUS_LABEL", {}).keys())
    c1, c2 = st.columns([1.6, 1.4])
    query = c1.text_input("Tìm hồ sơ", placeholder="Mã tác nghiệp, CIF, khách hàng, loại công việc", key="full_edit_search")
    statuses = c2.multiselect("Trạng thái", status_options, default=[], format_func=lambda x: ns.get("STATUS_LABEL", {}).get(x, x), key="full_edit_status")
    rows = _task_list(ns, query, statuses)
    if rows.empty:
        st.info("Không có hồ sơ phù hợp.")
        return
    ids = rows["id"].astype(int).tolist()
    selected = st.selectbox(
        "Chọn hồ sơ cần sửa",
        ids,
        format_func=lambda x: _task_choice_label(rows, x, ns),
        key="full_edit_task_select",
    )
    _render_task_form(ns, user, int(selected))


def _task_choice_label(rows, task_id: int, ns: dict[str, Any]) -> str:
    r = rows[rows.id.eq(int(task_id))].iloc[0]
    status = ns.get("STATUS_LABEL", {}).get(str(r.status), str(r.status))
    return f"{r.task_code or ('TN-'+str(task_id))} · {r.cif} · {r.customer_name} · {r.task_type} · {status}"


def install(ns: dict[str, Any]) -> None:
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True
    ns["ACTION_LABEL"]["LEADER_ADMIN_EDIT"] = "Lãnh đạo/Admin sửa hồ sơ"

    original_pill_nav = ns["pill_nav"]
    def pill_nav_with_full_edit(state_key, options, default=None, prefix="subnav"):
        options = list(options)
        if state_key == "leader_view" and not any(v == "full_edit" for v, _ in options):
            options.append(("full_edit", "✏️ Sửa toàn bộ hồ sơ"))
        if state_key == "admin_view" and not any(v == "full_edit" for v, _ in options):
            options.append(("full_edit", "✏️ Sửa hồ sơ"))
        return original_pill_nav(state_key, options, default=default, prefix=prefix)
    ns["pill_nav"] = pill_nav_with_full_edit

    original_leader_page = ns["leader_page"]
    def leader_page_with_full_edit(user):
        original_leader_page(user)
        if ns["st"].session_state.get("leader_view") == "full_edit":
            render_full_task_editor(ns, user)
    ns["leader_page"] = leader_page_with_full_edit

    original_admin_page = ns["admin_page"]
    def admin_page_with_full_edit(user):
        original_admin_page(user)
        if ns["st"].session_state.get("admin_view") == "full_edit":
            render_full_task_editor(ns, user)
    ns["admin_page"] = admin_page_with_full_edit

    ns["APP_VERSION"] = PATCH_VERSION
    logging.getLogger("khdn_ops").info("PATCH_INSTALL version=%s full_task_editor=leader_admin", PATCH_VERSION)
