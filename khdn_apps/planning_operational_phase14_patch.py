"""Operational phase 14: give Lãnh đạo phòng full legacy QLKH operations parity.

This is a runtime/UI overlay only. It does not migrate, rewrite, delete, or alter
existing operational tables. Existing leader management remains untouched and a
second leader-only mode exposes the same business capabilities as Cán bộ QLKH:
create/assign, track/reassign, handle returned work, evaluate/close, cancel with
reason, and review evaluation history. All leader actions are audited with the
actual leader user id; task ownership remains the selected QLKH user.
"""
from __future__ import annotations

import html
import sqlite3

VERSION = "1.0.1"
_FLAG = "_PLANNING_OPERATIONAL_PHASE14_VERSION"


def _is_leader(u):
    try:
        return str(u.get("role") or "") == "Lãnh đạo phòng" or int(u.get("is_admin") or 0) == 1
    except Exception:
        try:
            return str(u["role"] or "") == "Lãnh đạo phòng" or int(u["is_admin"] or 0) == 1
        except Exception:
            return False


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _filter_scope(df, qlkh_id):
    if df is None or getattr(df, "empty", True) or not qlkh_id:
        return df
    if "qlkh_user_id" not in df.columns:
        return df.iloc[0:0].copy()
    return df[df["qlkh_user_id"].astype(int).eq(int(qlkh_id))].copy()


def _cancel_required_css(st):
    st.html(
        """
        <style>
        div[class*="st-key-leader_ql_cancel_reason_"] input:placeholder-shown,
        div[class*="st-key-leader_ql_cancel_returned_reason_"] input:placeholder-shown {
            border-color:#ff4b4b !important;
            box-shadow:0 0 0 1px #ff4b4b !important;
            background:rgba(255,75,75,.08) !important;
        }
        div[class*="st-key-leader_ql_cancel_reason_"] label,
        div[class*="st-key-leader_ql_cancel_returned_reason_"] label {
            color:#ff6b6b !important;
            font-weight:900 !important;
        }
        </style>
        """
    )


def _all_visible_tasks(app_ns, u):
    sql, params = app_ns["visible_tasks_sql"](u)
    return app_ns["enrich_tasks"](app_ns["qdf"](sql, params))


def _active_qlkh(app_ns):
    df = app_ns["all_users"]("Cán bộ QLKH", active_only=True)
    return df


def _all_qlkh(app_ns):
    try:
        return app_ns["all_users"]("Cán bộ QLKH", active_only=False)
    except TypeError:
        return app_ns["all_users"]("Cán bộ QLKH", active_only=True)


def _scope_selector(st, app_ns, all_tasks):
    roster = _all_qlkh(app_ns)
    ids = []
    labels = {}
    if roster is not None and not roster.empty:
        for _, row in roster.iterrows():
            uid = int(row.id)
            ids.append(uid)
            name = str(getattr(row, "full_name", "") or f"QLKH #{uid}")
            active = int(getattr(row, "active", 1) or 0)
            labels[uid] = name + ("" if active else " · ngừng hoạt động")
    if all_tasks is not None and not all_tasks.empty and "qlkh_user_id" in all_tasks.columns:
        for _, row in all_tasks[["qlkh_user_id", "qlkh_name"]].drop_duplicates().iterrows():
            try:
                uid = int(row.qlkh_user_id)
            except Exception:
                continue
            if uid not in ids:
                ids.append(uid)
                labels[uid] = str(row.qlkh_name or f"QLKH #{uid}")
    ids = sorted(set(ids), key=lambda x: labels.get(x, str(x)).lower())
    options = [0] + ids
    selected = st.selectbox(
        "Phạm vi Cán bộ QLKH",
        options,
        key="leader_qlkh_scope",
        format_func=lambda x: "Tất cả Cán bộ QLKH" if int(x) == 0 else labels.get(int(x), f"QLKH #{x}"),
    )
    return int(selected or 0), labels


def _create_task(st, app_ns, u, scope_id, labels, logger=None):
    if st.session_state.pop("leader_ql_reset_create", False):
        for key in [
            "leader_ql_new_cust_selected_id", "leader_ql_new_cust_query", "leader_ql_new_amount",
            "leader_ql_new_note", "leader_ql_new_currency", "leader_ql_new_task_type",
            "leader_ql_new_support", "leader_ql_new_owner", "leader_ql_new_validation",
        ]:
            st.session_state.pop(key, None)

    app_ns["page_title"](
        "Tác nghiệp QLKH – Lãnh đạo phòng",
        "Lãnh đạo có đầy đủ thao tác QLKH. Mọi thao tác ghi audit theo chính tài khoản Lãnh đạo; hồ sơ vẫn thuộc Cán bộ QLKH được chọn.",
    )
    st.markdown("### ➕ Tạo / giao hồ sơ")
    validation = st.session_state.get("leader_ql_new_validation", {})
    active_qlkh = _active_qlkh(app_ns)
    if active_qlkh is None or active_qlkh.empty:
        st.error("Chưa có Cán bộ QLKH đang hoạt động.")
        return
    owner_ids = active_qlkh.id.astype(int).tolist()
    owner_default = None
    if scope_id and scope_id in owner_ids:
        owner_default = owner_ids.index(scope_id)
    owner_id = st.selectbox(
        "Cán bộ QLKH phụ trách *",
        owner_ids,
        index=owner_default,
        key="leader_ql_new_owner",
        placeholder="Chọn Cán bộ QLKH",
        format_func=lambda x: str(active_qlkh[active_qlkh.id == x].iloc[0].full_name),
    )
    if validation.get("owner"):
        app_ns["required_error"](validation["owner"])

    cust = app_ns["customer_selector"]("leader_ql_new_cust", validation.get("customer"))
    support_df = app_ns["all_users"]("Cán bộ hỗ trợ", active_only=True)
    sid = None
    if support_df is None or support_df.empty:
        st.error("Chưa có Cán bộ hỗ trợ đang hoạt động.")
    else:
        support_ids = support_df.id.astype(int).tolist()
        sid = st.selectbox(
            "Cán bộ hỗ trợ thực hiện *",
            support_ids,
            index=None,
            key="leader_ql_new_support",
            placeholder="Chọn Cán bộ hỗ trợ",
            format_func=lambda x: f"{support_df[support_df.id == x].iloc[0].full_name} ({support_df[support_df.id == x].iloc[0].username})",
        )
    if validation.get("support"):
        app_ns["required_error"](validation["support"])

    types = app_ns["active_task_types"]()
    task_options = types.name.tolist() if types is not None and not types.empty else app_ns.get("DEFAULT_TASK_TYPES", [])
    task_type = st.selectbox("Công việc *", task_options, key="leader_ql_new_task_type")
    if validation.get("task_type"):
        app_ns["required_error"](validation["task_type"])

    ccur, camt = st.columns([1, 3])
    currency = ccur.selectbox("Đơn vị *", ["VND", "USD", "EUR"], key="leader_ql_new_currency")
    amount_text = camt.text_input("Giá trị *", placeholder="Ví dụ: 1.000.000", key="leader_ql_new_amount")
    amount = app_ns["parse_amount_text"](amount_text)
    if validation.get("currency"):
        app_ns["required_error"](validation["currency"])
    if validation.get("amount"):
        app_ns["required_error"](validation["amount"])

    rates = st.session_state.get("fx_rates", {"VND": 1.0})
    rate = float(rates.get(currency, 0) or 0)
    amount_vnd = amount * rate if rate else 0
    if amount > 0:
        if currency == "VND":
            st.caption(f"Giá trị: **{app_ns['money'](amount)} VND**")
        elif rate > 0:
            st.caption(
                f"Tỷ giá mua chuyển khoản BIDV: **1 {currency} = {app_ns['money'](rate)} VND** → "
                f"Quy đổi: **{app_ns['money'](amount_vnd)} VND**"
            )
        else:
            st.error(f"Chưa có tỷ giá {currency}/VND. Bấm **Cập nhật tỷ giá BIDV** ở thanh bên để thử lại.")
    note = st.text_area("Ghi chú / yêu cầu xử lý (không bắt buộc)", key="leader_ql_new_note")

    if st.button("Giao hồ sơ cho Cán bộ hỗ trợ", type="primary", use_container_width=True, key="leader_ql_create_btn"):
        errors = {}
        if owner_id is None:
            errors["owner"] = "Bắt buộc chọn Cán bộ QLKH phụ trách."
        if not cust:
            errors["customer"] = "Bắt buộc chọn khách hàng theo CIF/Tên khách hàng."
        if sid is None:
            errors["support"] = "Bắt buộc chọn Cán bộ hỗ trợ thực hiện."
        if not task_type:
            errors["task_type"] = "Bắt buộc chọn loại công việc."
        if not currency:
            errors["currency"] = "Bắt buộc chọn đơn vị tiền."
        if amount <= 0:
            errors["amount"] = "Bắt buộc nhập Giá trị lớn hơn 0."
        if currency != "VND" and rate <= 0:
            errors["amount"] = f"Chưa lấy được tỷ giá {currency}/VND từ BIDV nên chưa thể giao tác nghiệp ngoại tệ."
        if errors:
            st.session_state["leader_ql_new_validation"] = errors
            st.rerun()

        actor_uid = int(_uget(u, "id"))
        ts = app_ns["now_str"]()
        tid = app_ns["execute"](
            """INSERT INTO tasks(
               customer_id,support_user_id,qlkh_user_id,request_source,assigned_at,accepted_at,
               task_type,amount,currency,fx_rate,amount_vnd,start_time,due_time,note,status,
               current_round,rework_count,created_at,updated_at)
               VALUES(?,?,?,'QLKH',?,NULL,?,?,?,?,?,?,NULL,?,'PENDING_ACCEPTANCE',1,0,?,?)""",
            (
                int(cust["id"]), int(sid), int(owner_id), ts, task_type, amount, currency,
                rate or 1, amount_vnd, ts, note.strip(), ts, ts,
            ),
        )
        code = app_ns["task_code"](tid)
        app_ns["execute"]("UPDATE tasks SET task_code=? WHERE id=?", (code, tid))
        owner_name = str(active_qlkh[active_qlkh.id == int(owner_id)].iloc[0].full_name)
        support_name = str(support_df[support_df.id == int(sid)].iloc[0].full_name)
        app_ns["log_action"](
            tid, actor_uid, "CREATE",
            f"Lãnh đạo tạo hồ sơ thuộc QLKH {owner_name} lúc {app_ns['fmt_dt'](ts)}; {task_type}; giá trị={app_ns['money'](amount)} {currency}",
        )
        app_ns["log_action"](
            tid, actor_uid, "ASSIGN",
            f"Lãnh đạo giao cho CB hỗ trợ {support_name} lúc {app_ns['fmt_dt'](ts)}; QLKH phụ trách={owner_name}",
        )
        if logger:
            logger.info("P14_LEADER_QLKH_CREATE task=%s actor=%s qlkh=%s support=%s", tid, actor_uid, int(owner_id), int(sid))
        st.session_state["leader_ql_reset_create"] = True
        st.session_state["leader_qlkh_view"] = "create"
        st.session_state["leader_ql_create_flash"] = "Đã giao hồ sơ cho Cán bộ hỗ trợ và giữ đúng QLKH phụ trách."
        st.rerun()


def _review_tasks(st, app_ns, u, pending, logger=None):
    app_ns["page_title"](
        "Tác nghiệp QLKH – Lãnh đạo phòng",
        "Lãnh đạo có thể đánh giá/kết thúc hồ sơ chờ đánh giá trong phạm vi toàn phòng hoặc QLKH đã chọn.",
    )
    st.markdown("### ⭐ Công việc chờ đánh giá")
    if pending is None or pending.empty:
        st.success("Không có công việc đang chờ đánh giá trong phạm vi đã chọn.")
        return
    pending = pending.sort_values(["end_dt", "cif"], ascending=[True, True], kind="stable")
    app_ns["attention_banner"]("Chọn công việc cần đánh giá ở danh sách dưới bảng")
    row = app_ns["selectable_task_table"](
        pending, "leader_ql_eval_task_table", include_phase=True,
        height=app_ns["_task_list_height"](len(pending), 540),
    )
    if row is None:
        return
    tid = int(row.id)
    elapsed_min = 0
    if row.end_time and row.start_time:
        elapsed_min = round((app_ns["parse_dt"](row.end_time) - app_ns["parse_dt"](row.start_time)).total_seconds() / 60)
    app_ns["render_task_chips"](row, time_label="Kết thúc", time_field="end_time")
    st.caption(
        f"QLKH phụ trách: **{getattr(row, 'qlkh_name', '—')}** · Thời gian xử lý: **{app_ns['money'](elapsed_min)} phút**"
        + (f" · Ghi chú: {row.note}" if getattr(row, "note", None) else "")
    )
    scores = [x / 2 for x in range(0, 21)]
    with st.form(f"leader_ql_eval_form_{tid}_{int(row.current_round)}"):
        q = st.select_slider("Chất lượng", options=scores, value=5.0, key=f"leader_ql_q_{tid}_{int(row.current_round)}")
        p = st.select_slider("Tiến độ", options=scores, value=5.0, key=f"leader_ql_p_{tid}_{int(row.current_round)}")
        comment = st.text_area("Góp ý / nhận xét", key=f"leader_ql_comment_{tid}_{int(row.current_round)}")
        submit = st.form_submit_button("⭐ Lưu đánh giá & kết thúc", use_container_width=True, type="primary")
    if not submit:
        return
    if (q < 9 or p < 9) and not comment.strip():
        st.error("Điểm dưới 9 bắt buộc phải nhập Góp ý trước khi lưu.")
        return
    actor_uid = int(_uget(u, "id"))
    ts = app_ns["now_str"]()
    try:
        with app_ns["get_conn"]() as c:
            current = c.execute("SELECT status,current_round FROM tasks WHERE id=?", (tid,)).fetchone()
            if not current or str(current["status"]) != "PENDING_REVIEW" or int(current["current_round"]) != int(row.current_round):
                raise ValueError("Trạng thái hồ sơ đã thay đổi. Vui lòng tải lại màn hình.")
            c.execute(
                "INSERT INTO evaluations(task_id,round_no,evaluator_user_id,quality_score,progress_score,comment,created_at) VALUES(?,?,?,?,?,?,?)",
                (tid, int(row.current_round), actor_uid, q, p, comment.strip(), ts),
            )
            c.execute(
                "UPDATE tasks SET status='CLOSED',closed_time=?,evaluated_at=?,updated_at=? WHERE id=? AND status='PENDING_REVIEW'",
                (ts, ts, ts, tid),
            )
        app_ns["log_action"](
            tid, actor_uid, "EVALUATE",
            f"Lãnh đạo đánh giá thay nghiệp vụ QLKH lúc {app_ns['fmt_dt'](ts)}; Chất lượng={q}; Tiến độ={p}; Góp ý={comment.strip()}; tự động kết thúc",
        )
        if logger:
            logger.info("P14_LEADER_QLKH_EVALUATE task=%s actor=%s round=%s", tid, actor_uid, int(row.current_round))
        st.success("Đã lưu đánh giá và kết thúc tác nghiệp.")
        st.rerun()
    except sqlite3.IntegrityError:
        st.error("Vòng công việc này đã được đánh giá trước đó.")
    except ValueError as exc:
        st.error(str(exc))


def _manage_assignment(st, app_ns, u, rsel, key_prefix, logger=None):
    tid = int(rsel.id)
    actor_uid = int(_uget(u, "id"))
    app_ns["render_task_chips"](rsel, time_label="Giao", time_field="assigned_at")
    app_ns["task_history"](tid)
    status_now = str(rsel.status)
    first_accept = app_ns["parse_dt"](rsel.get("first_accepted_at"))
    if status_now not in ("PENDING_ACCEPTANCE", "RETURNED_TO_QLKH"):
        return
    st.markdown("### Điều phối hồ sơ")
    support_df = app_ns["all_users"]("Cán bộ hỗ trợ", active_only=True)
    if support_df is None or support_df.empty:
        st.error("Không có Cán bộ hỗ trợ đang hoạt động để phân công.")
        return
    sup_ids = support_df.id.astype(int).tolist()
    current_sid = int(rsel.support_user_id)
    idx = sup_ids.index(current_sid) if current_sid in sup_ids else 0
    new_sid = st.selectbox(
        "Cán bộ hỗ trợ xử lý",
        sup_ids,
        index=idx,
        key=f"{key_prefix}_support_{tid}",
        format_func=lambda x: f"{support_df[support_df.id == x].iloc[0].full_name} ({support_df[support_df.id == x].iloc[0].username})",
    )
    reason = st.text_input("Lý do đổi/giao lại (khuyến nghị ghi để audit)", key=f"{key_prefix}_reason_{tid}")
    if status_now == "PENDING_ACCEPTANCE":
        c1, c2 = st.columns([2, 1])
        if c1.button("🔁 Đổi Cán bộ hỗ trợ", use_container_width=True, key=f"{key_prefix}_reassign_{tid}"):
            if int(new_sid) == current_sid:
                st.info("Bạn đang chọn đúng Cán bộ hỗ trợ hiện tại, chưa có thay đổi.")
            else:
                ts = app_ns["now_str"]()
                old_name = str(rsel.support_name)
                new_name = str(support_df[support_df.id == int(new_sid)].iloc[0].full_name)
                app_ns["execute"](
                    "UPDATE tasks SET support_user_id=?,updated_at=? WHERE id=? AND status='PENDING_ACCEPTANCE'",
                    (int(new_sid), ts, tid),
                )
                app_ns["log_action"](
                    tid, actor_uid, "QLKH_REASSIGN",
                    f"Lãnh đạo thực hiện nghiệp vụ QLKH: đổi CBHT khi đang chờ tiếp nhận {old_name} -> {new_name} lúc {app_ns['fmt_dt'](ts)}; lý do={reason.strip() or 'không ghi'}",
                )
                if logger:
                    logger.info("P14_LEADER_QLKH_REASSIGN task=%s actor=%s support=%s", tid, actor_uid, int(new_sid))
                st.success("Đã đổi Cán bộ hỗ trợ. Các mốc thời gian gốc không thay đổi.")
                st.rerun()

        delete_reason = st.text_input(
            "Lý do xóa/hủy hồ sơ chưa tiếp nhận *",
            key=f"leader_ql_cancel_reason_{tid}",
            placeholder="Nhập lý do xóa/hủy...",
        )
        if c2.button("🗑️ Xóa công việc", use_container_width=True, key=f"{key_prefix}_cancel_{tid}"):
            if first_accept is not None:
                st.error("Hồ sơ đã từng được CBHT tiếp nhận nên không được xóa ở trạng thái chờ tiếp nhận.")
            elif not delete_reason.strip():
                st.error("Bắt buộc nhập lý do xóa/hủy để lưu dấu vết audit.")
            else:
                ts = app_ns["now_str"]()
                app_ns["execute"](
                    "UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND status='PENDING_ACCEPTANCE' AND first_accepted_at IS NULL",
                    (ts, ts, tid),
                )
                app_ns["log_action"](
                    tid, actor_uid, "QLKH_CANCEL",
                    f"Lãnh đạo thực hiện nghiệp vụ QLKH: xóa/hủy hồ sơ chưa tiếp nhận lúc {app_ns['fmt_dt'](ts)}; lý do={delete_reason.strip()}; giữ bản ghi để thống kê/audit",
                )
                if logger:
                    logger.info("P14_LEADER_QLKH_CANCEL task=%s actor=%s source=pending", tid, actor_uid)
                st.success("Đã hủy hồ sơ. Bản ghi và mốc thời gian vẫn được giữ để thống kê/audit.")
                st.rerun()
    else:
        st.warning("↩️ Hồ sơ này đã được CBHT trả lại. Khi giao lại, hệ thống giữ nguyên toàn bộ mốc thời gian gốc.")
        if st.button("📤 Giao lại hồ sơ cho Cán bộ hỗ trợ", type="primary", use_container_width=True, key=f"{key_prefix}_reopen_{tid}"):
            ts = app_ns["now_str"]()
            new_name = str(support_df[support_df.id == int(new_sid)].iloc[0].full_name)
            old_name = str(rsel.support_name)
            if int(new_sid) != current_sid:
                app_ns["log_action"](
                    tid, actor_uid, "QLKH_REASSIGN",
                    f"Lãnh đạo thực hiện nghiệp vụ QLKH: đổi CBHT khi giao lại {old_name} -> {new_name} lúc {app_ns['fmt_dt'](ts)}; lý do={reason.strip() or 'không ghi'}",
                )
            app_ns["execute"](
                "UPDATE tasks SET support_user_id=?,status='PENDING_ACCEPTANCE',accepted_at=NULL,updated_at=? WHERE id=? AND status='RETURNED_TO_QLKH'",
                (int(new_sid), ts, tid),
            )
            app_ns["log_action"](
                tid, actor_uid, "REOPEN_ASSIGN",
                f"Lãnh đạo thực hiện nghiệp vụ QLKH: giao lại cho CBHT {new_name} lúc {app_ns['fmt_dt'](ts)}; lý do={reason.strip() or 'không ghi'}; mốc giao ban đầu={app_ns['fmt_dt'](rsel.assigned_at)}",
            )
            if logger:
                logger.info("P14_LEADER_QLKH_REOPEN task=%s actor=%s support=%s", tid, actor_uid, int(new_sid))
            st.success("Đã giao lại hồ sơ. Mốc thời gian ban đầu được giữ nguyên.")
            st.rerun()
        delete_reason = st.text_input(
            "Lý do xóa/hủy hồ sơ CBHT đã trả lại *",
            key=f"leader_ql_cancel_returned_reason_{tid}",
            placeholder="Nhập lý do xóa/hủy...",
        )
        if st.button("🗑️ Xóa / hủy công việc đã trả lại", use_container_width=True, key=f"{key_prefix}_cancel_returned_{tid}"):
            if not delete_reason.strip():
                st.error("Bắt buộc nhập lý do xóa/hủy để lưu dấu vết audit.")
            else:
                ts = app_ns["now_str"]()
                app_ns["execute"](
                    "UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND status='RETURNED_TO_QLKH'",
                    (ts, ts, tid),
                )
                prior_accept = app_ns["fmt_dt"](rsel.first_accepted_at) if first_accept is not None else "chưa từng tiếp nhận"
                app_ns["log_action"](
                    tid, actor_uid, "QLKH_CANCEL",
                    f"Lãnh đạo thực hiện nghiệp vụ QLKH: xóa/hủy hồ sơ sau khi CBHT trả lại lúc {app_ns['fmt_dt'](ts)}; lý do={delete_reason.strip()}; tiếp nhận lần đầu={prior_accept}; giữ nguyên toàn bộ mốc thời gian và lịch sử audit",
                )
                if logger:
                    logger.info("P14_LEADER_QLKH_CANCEL task=%s actor=%s source=returned", tid, actor_uid)
                st.success("Đã hủy hồ sơ CBHT trả lại. Bản ghi và toàn bộ lịch sử audit vẫn được giữ nguyên.")
                st.rerun()


def _assigned_tasks(st, app_ns, u, scope_df, logger=None):
    app_ns["page_title"](
        "Tác nghiệp QLKH – Lãnh đạo phòng",
        "Theo dõi và điều phối hồ sơ bằng đầy đủ chức năng của Cán bộ QLKH.",
    )
    returned_df = scope_df[scope_df.status.eq("RETURNED_TO_QLKH")].copy() if scope_df is not None and not scope_df.empty else scope_df
    tracking = scope_df[~scope_df.status.isin(["CLOSED", "CANCELLED", "RETURNED_TO_QLKH"])].copy() if scope_df is not None and not scope_df.empty else scope_df
    focus = st.session_state.pop("leader_qlkh_focus", None)

    st.markdown("### ↩️ Hồ sơ CBHT trả lại – chờ xử lý")
    if returned_df is None or returned_df.empty:
        st.success("Không có hồ sơ nào đang ở trạng thái CBHT trả lại QLKH.")
    else:
        if focus == "returned":
            st.warning("🔔 Có hồ sơ CBHT trả lại. Lãnh đạo có thể giao lại/điều phối như QLKH.")
        returned_df = returned_df.sort_values(["returned_to_qlkh_at_dt", "cif"], ascending=[True, True], kind="stable", na_position="last")
        app_ns["attention_banner"]("Chọn hồ sơ CBHT trả lại ở danh sách dưới bảng để xử lý")
        rret = app_ns["selectable_task_table"](
            returned_df, "leader_qlkh_returned_table", include_phase=True,
            height=app_ns["_task_list_height"](len(returned_df), 520),
        )
        if rret is not None:
            _manage_assignment(st, app_ns, u, rret, "leader_ql_returned", logger)

    st.markdown("### 📂 Hồ sơ đang theo dõi")
    if tracking is None or tracking.empty:
        st.info("Không có hồ sơ đang chờ tiếp nhận/đang xử lý/chờ đánh giá.")
        return
    ordered = tracking.copy()
    tg = app_ns["_workflow_delay_targets"]()
    ordered["_phase_start"] = [app_ns["_phase_delay_info"](r, tg)["start"] for _, r in ordered.iterrows()]
    ordered = ordered.sort_values(["_phase_start", "cif"], ascending=[True, True], na_position="last")
    app_ns["attention_banner"]("Chọn hồ sơ đang theo dõi ở danh sách dưới bảng để xem mốc thời gian / lịch sử")
    rsel = app_ns["selectable_task_table"](
        ordered, "leader_qlkh_assigned_table", include_phase=True,
        height=app_ns["_task_list_height"](len(ordered), 560),
    )
    if rsel is None:
        return
    if str(rsel.status) == "PENDING_ACCEPTANCE":
        _manage_assignment(st, app_ns, u, rsel, "leader_ql_pending", logger)
    else:
        tid = int(rsel.id)
        app_ns["render_task_chips"](rsel, time_label="Giao", time_field="assigned_at")
        app_ns["task_history"](tid)


def _history(st, app_ns, scope_df):
    app_ns["page_title"](
        "Tác nghiệp QLKH – Lãnh đạo phòng",
        "Lịch sử đánh giá của các hồ sơ thuộc phạm vi QLKH đã chọn.",
    )
    st.markdown("### 🕘 Lịch sử đánh giá")
    if scope_df is None or scope_df.empty:
        st.info("Chưa có dữ liệu hồ sơ trong phạm vi đã chọn.")
        return
    ids = sorted({int(x) for x in scope_df.id.dropna().tolist()})
    if not ids:
        st.info("Chưa có lịch sử đánh giá.")
        return
    marks = ",".join(["?"] * len(ids))
    hist = app_ns["qdf"](
        f"""SELECT t.id task_id,t.task_code,c.cif,c.customer_name,s.full_name support_name,
                   q.full_name qlkh_name,t.task_type,e.round_no,e.quality_score,e.progress_score,
                   e.comment,e.created_at,ev.full_name evaluator_name
            FROM evaluations e
            JOIN tasks t ON t.id=e.task_id
            JOIN customers c ON c.id=t.customer_id
            JOIN users s ON s.id=t.support_user_id
            JOIN users q ON q.id=t.qlkh_user_id
            JOIN users ev ON ev.id=e.evaluator_user_id
            WHERE e.task_id IN ({marks})
            ORDER BY e.created_at DESC,c.cif ASC""",
        ids,
    )
    if hist.empty:
        st.info("Chưa có lịch sử đánh giá trong phạm vi đã chọn.")
        return
    st.markdown("### Bộ lọc lịch sử")
    hist = app_ns["filter_history_controls"](
        hist, "leader_qlkh_history", date_candidates=["created_at"],
        staff_cols=["support_name", "qlkh_name", "evaluator_name"],
    )
    if hist.empty:
        st.info("Không có lịch sử đánh giá theo bộ lọc.")
        return
    raw = hist.reset_index(drop=True).copy()
    show = raw.copy()
    show["Điểm TB"] = (
        app_ns["pd"].to_numeric(show.quality_score, errors="coerce")
        + app_ns["pd"].to_numeric(show.progress_score, errors="coerce")
    ) / 2
    show["created_at"] = show["created_at"].map(app_ns["fmt_dt"])
    show["quality_score"] = show["quality_score"].map(app_ns["fmt_score"])
    show["progress_score"] = show["progress_score"].map(app_ns["fmt_score"])
    show["Điểm TB"] = show["Điểm TB"].map(app_ns["fmt_score"])
    display = show.rename(columns={
        "task_code": "Mã TN", "cif": "CIF", "customer_name": "Khách hàng",
        "support_name": "CB hỗ trợ", "qlkh_name": "CB QLKH", "evaluator_name": "Người đánh giá",
        "task_type": "Công việc", "round_no": "Vòng", "quality_score": "Chất lượng",
        "progress_score": "Tiến độ", "comment": "Góp ý", "created_at": "Thời gian",
    })
    display = display[[
        "Mã TN", "CIF", "Khách hàng", "CB QLKH", "CB hỗ trợ", "Công việc", "Vòng",
        "Chất lượng", "Tiến độ", "Điểm TB", "Góp ý", "Người đánh giá", "Thời gian",
    ]]
    app_ns["attention_banner"]("Chọn hồ sơ ở danh sách dưới bảng để xem toàn bộ lịch sử")
    from khdn_apps.operational_review_table import choose_row
    rr = choose_row(st, raw, display, "leader_qlkh_history_table", id_columns=("task_id", "round_no"),
                    height=app_ns["_history_table_height"](len(display), 620),
                    label="Chọn hồ sơ và vòng đánh giá để xem lịch sử", logger=app_ns.get("LOGGER"))
    if rr is not None:
        task_id = int(rr.task_id)
        current = scope_df[scope_df.id.astype(int).eq(task_id)]
        if current is not None and not current.empty:
            app_ns["render_task_chips"](current.iloc[0], time_label="Kết thúc", time_field="closed_time")
        app_ns["task_history"](task_id)


def _leader_qlkh_page(app_ns, u, logger=None):
    st = app_ns["st"]
    _cancel_required_css(st)
    all_tasks = _all_visible_tasks(app_ns, u)
    scope_id, labels = _scope_selector(st, app_ns, all_tasks)
    scope_df = _filter_scope(all_tasks, scope_id)

    wait = int((scope_df.status == "PENDING_ACCEPTANCE").sum()) if scope_df is not None and not scope_df.empty else 0
    work = int(scope_df.status.isin(["OPEN", "REWORK"]).sum()) if scope_df is not None and not scope_df.empty else 0
    returned = int((scope_df.status == "RETURNED_TO_QLKH").sum()) if scope_df is not None and not scope_df.empty else 0
    pending = scope_df[scope_df.status.eq("PENDING_REVIEW")].copy() if scope_df is not None and not scope_df.empty else app_ns["pd"].DataFrame()
    closed = int((scope_df.status == "CLOSED").sum()) if scope_df is not None and not scope_df.empty else 0

    app_ns["ops_action_cards"](
        "leader_qlkh_view",
        [
            ("create", "➕", "Tạo/giao hồ sơ", None, False, False),
            ("assigned", "📤", "Chờ CBHT tiếp nhận", wait, True, wait > 0),
            ("assigned", "↩️", "CBHT trả lại", returned, True, returned > 0, {"leader_qlkh_focus": "returned"}),
            ("assigned", "🛠️", "CBHT đang xử lý", work, True, False),
            ("review", "⭐", "Chờ đánh giá", len(pending), True, len(pending) > 0),
            ("history", "✅", "Đã kết thúc", closed, False, False),
        ],
    )
    view = st.session_state.get("leader_qlkh_view", "create")
    if view not in ("create", "review", "assigned", "history"):
        view = "create"
        st.session_state["leader_qlkh_view"] = view

    if view == "create":
        flash = st.session_state.pop("leader_ql_create_flash", None)
        if flash:
            st.success(flash)
        _create_task(st, app_ns, u, scope_id, labels, logger)
    elif view == "review":
        _review_tasks(st, app_ns, u, pending, logger)
    elif view == "assigned":
        _assigned_tasks(st, app_ns, u, scope_df, logger)
    else:
        _history(st, app_ns, scope_df)


def install(app_ns, policy=None, weekly_core=None, customer_core=None, customer_ui=None, worktype=None, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return
    original_leader_page = app_ns.get("leader_page")
    if original_leader_page is None:
        raise RuntimeError("Phase14 requires leader_page")

    def leader_page(u):
        if not _is_leader(u):
            return original_leader_page(u)
        st = app_ns["st"]
        mode = app_ns["pill_nav"](
            "leader_role_ops_mode",
            [("leader", "👔 Quản lý lãnh đạo"), ("qlkh", "💼 Tác nghiệp QLKH")],
            default="leader",
            prefix="subnav_leader_role_ops",
        )
        if mode == "qlkh":
            return _leader_qlkh_page(app_ns, u, logger)
        return original_leader_page(u)

    app_ns["leader_page"] = leader_page
    app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "P14_LEADER_QLKH_PARITY_INSTALLED create=1 assign=1 returned=1 review=1 cancel=1 history=1 actor_audit=leader data_migration=0"
        )
