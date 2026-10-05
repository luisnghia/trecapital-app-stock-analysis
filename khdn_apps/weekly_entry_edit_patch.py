"""Weekly draft editing and submit-only day/date entry for every active role.

The existing submit/approval lifecycle remains in charge. Selecting Edit on a
returned plan explicitly starts its next draft, just like Return to draft.
All writes recheck the persisted owner, plan state and selected catalog entries
in one transaction. Runtime logs contain IDs only.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
import logging

from khdn_apps import planning_operational_phase13_patch as p13
from khdn_apps import weekly_plan_form_refinement_patch as form
from khdn_apps import weekly_push
from khdn_apps.legacy_fast_form import legacy_fast_form

VERSION = "1.0.0"
EDIT_KEY = "_weekly_entry_edit"
ROLES = {"Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng"}
LOGGER = logging.getLogger("khdn.weekly_entry")


def _actor(c, uid):
    row = c.execute("SELECT * FROM users WHERE id=?", (int(uid),)).fetchone()
    u = dict(row) if row else {}
    if not u.get("active") or not (u.get("is_admin") or u.get("role") in ROLES):
        raise PermissionError("Tài khoản không còn quyền nhập hoặc sửa kế hoạch.")
    return u


def _plan(c, uid, ws):
    row = c.execute("SELECT * FROM weekly_plans WHERE user_id=? AND week_start=?", (int(uid), ws.isoformat())).fetchone()
    if not row:
        raise ValueError("Không tìm thấy kế hoạch tuần của bạn. Hãy tải lại trang.")
    return dict(row)


def item_token(item):
    return hashlib.sha256(json.dumps(dict(item), sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def begin_edit(get_conn, uid, ws, iid, logger=None):
    """Return-to-draft is an explicit Edit action; other owners stay read-only."""
    with get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        _actor(c, uid)
        plan = _plan(c, uid, ws)
        row = c.execute("SELECT * FROM weekly_plan_items WHERE id=? AND plan_id=? AND user_id=?", (int(iid), int(plan["id"]), int(uid))).fetchone()
        item = dict(row) if row else {}
        if not item or item.get("status") == "CANCELLED":
            raise PermissionError("Công việc không thuộc kế hoạch đang sửa hoặc đã bị hủy.")
        if plan.get("workflow_status") not in {"NHAP", "TRA_LAI"} or plan.get("classification_locked") or item.get("classification_locked"):
            raise PermissionError("Chỉ sửa nội dung khi kế hoạch đang nhập hoặc được trả lại.")
        if plan["workflow_status"] == "TRA_LAI":
            ts = weekly_push.local_now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("UPDATE weekly_plans SET workflow_status='NHAP',updated_at=? WHERE id=?", (ts, int(plan["id"])))
            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'RETURN_TO_DRAFT',?,?)", (int(uid), f"week={ws.isoformat()}", ts))
    (logger or LOGGER).info("WEEKLY_DRAFT_EDIT_OPEN actor=%s plan=%s item=%s returned=%s", int(uid), int(plan["id"]), int(iid), int(plan["workflow_status"] == "TRA_LAI"))
    return {"uid": int(uid), "week": ws.isoformat(), "iid": int(iid), "token": item_token(item)}


def open_editor(st, get_conn, uid, ws, iid, logger=None):
    try:
        selected = begin_edit(get_conn, uid, ws, iid, logger)
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
        return
    p13._clear_add_state(st.session_state, ws)
    st.session_state[EDIT_KEY] = selected
    st.rerun()


def _day(value, label):
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError(f"{label} không hợp lệ.") from exc


def _clean_values(c, policy, core, actor, ws, payload, *, iid=0):
    uid = int(actor["id"])
    work_day = _day(payload.get("work_date"), "Thứ / ngày thực hiện")
    if not ws <= work_day <= ws + timedelta(days=6):
        raise ValueError("Ngày thực hiện phải nằm trong tuần đang lập kế hoạch.")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Vui lòng nhập nội dung Công việc.")
    customer_id = int(payload.get("customer_id") or 0)
    customers = {int(x["id"]): x for x in core.customers(c, uid)}
    if customer_id and customer_id not in customers:
        raise ValueError("Khách hàng đã bị khóa hoặc không còn trong danh sách được chọn.")
    customer = customers.get(customer_id)
    leaders = {int(x["id"]): x for x in form._leader_rows(c)}
    scope = policy._scope_key(c, uid)
    focus_rows = policy._focus_categories(c, scope, ws.year, False)
    focus_by_id = {int(x["id"]): x for x in focus_rows}
    linked_id = int(payload.get("linked_case_id") or 0)
    linked = None
    if linked_id:
        if not customer:
            raise ValueError("Công việc liên kết phải thuộc khách hàng đã chọn.")
        cases = p13._case_rows(c, customer_id, uid, policy._manager(actor))
        if linked_id not in {int(x["id"]) for x in cases}:
            raise ValueError("Công việc khách hàng liên kết không còn hoạt động hoặc không thuộc phạm vi của bạn.")
        linked = dict(c.execute("SELECT * FROM customer_work_cases WHERE id=?", (linked_id,)).fetchone())
        duplicate = c.execute("SELECT 1 FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id WHERE p.user_id=? AND p.week_start=? AND w.linked_case_id=? AND w.status<>'CANCELLED' AND w.id<>? LIMIT 1", (uid, ws.isoformat(), linked_id, int(iid))).fetchone()
        if duplicate:
            raise ValueError("Công việc khách hàng đã được liên kết trong tuần này. Chọn Không liên kết nếu đây là một việc khác.")
    auto_due, auto_leader, auto_focus, source_q = p13._source_defaults(linked, list(leaders.values()), focus_rows)
    due = auto_due or _day(payload.get("due_date"), "Ngày dự kiến hoàn thành")
    if not auto_due and due < work_day:
        raise ValueError("Ngày dự kiến hoàn thành không được trước ngày thực hiện.")
    leader_id = int(auto_leader["id"]) if auto_leader else int(payload.get("controller") or 0)
    if leader_id not in leaders:
        raise ValueError("Vui lòng chọn Lãnh đạo phòng phụ trách đang hoạt động.")
    focus = auto_focus
    if linked and source_q in {1, 2, 3, 4}:
        q = int(source_q)
        if q == 2 and not focus:
            focus = focus_by_id.get(int(linked.get("focus_category_id") or 0))
        if q != 2:
            focus = None
        due7, risk = p13._classification_from_source(q)
        basis = f"Kế thừa Công việc khách hàng #{linked_id}: {p13._Q_LABEL[q]}"
    else:
        raw_focus = str(payload.get("focus") or "")
        if raw_focus == "NONE":
            focus = None
        else:
            focus = focus_by_id.get(int(raw_focus)) if raw_focus.isdigit() else None
            if not focus:
                raise ValueError("Vui lòng chọn danh mục trọng tâm đang áp dụng hoặc Không thuộc trọng tâm.")
        due7 = None if focus else due <= weekly_push.local_now().date() + timedelta(days=7)
        risk = None
        if not focus and due7:
            choice = str(payload.get("risk") or "")
            if choice not in {"YES", "NO"}:
                raise ValueError("Vui lòng chọn việc này có gắn với chỉ tiêu hoặc rủi ro trọng yếu không.")
            risk = choice == "YES"
        q, basis = policy._classify(focus, due7, risk)
    # Preserve historical source snapshots if an old linked Q2 has no active mapping.
    snapshot = focus or (linked if linked and q == 2 else {})
    return {
        "work_date": work_day.isoformat(), "title": title,
        "customer_id": customer_id or None, "customer_text": str(customer.get("customer_name") or "") if customer else "",
        "expected_complete_date": due.isoformat(), "controller_user_id": leader_id,
        "controller_name_snapshot": str(leaders[leader_id].get("full_name") or ""), "linked_case_id": linked_id or None,
        "note": str(payload.get("note") or "").strip(),
        "focus_category_id": int(focus["id"]) if focus else None,
        "focus_code_snapshot": snapshot.get("code") or snapshot.get("focus_code_snapshot"),
        "focus_name_snapshot": snapshot.get("name") or snapshot.get("focus_name_snapshot"),
        "focus_desc_snapshot": snapshot.get("description") or snapshot.get("focus_desc_snapshot"),
        "priority_quadrant": int(q), "priority_basis": basis,
        "deadline_within_7d": None if due7 is None else int(due7), "kpi_risk_flag": None if risk is None else int(risk),
    }


def save_item(get_conn, policy, core, uid, ws, payload, *, iid=0, expected_token="", emergent=False, logger=None):
    """Create/edit atomically; never turn an edit into a second work item."""
    with get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        actor = _actor(c, uid)
        plan = _plan(c, uid, ws)
        needed_status = "NHAP" if iid or not emergent else "DA_DUYET"
        if plan.get("workflow_status") != needed_status or plan.get("classification_locked"):
            raise PermissionError("Trạng thái kế hoạch đã thay đổi. Hãy tải lại trang trước khi nhập/sửa.")
        old = {}
        if iid:
            row = c.execute("SELECT * FROM weekly_plan_items WHERE id=? AND plan_id=? AND user_id=?", (int(iid), int(plan["id"]), int(uid))).fetchone()
            old = dict(row) if row else {}
            if not old or old.get("status") == "CANCELLED" or old.get("classification_locked"):
                raise PermissionError("Công việc đã bị khóa, bị hủy hoặc không thuộc kế hoạch của bạn.")
            if not expected_token or item_token(old) != expected_token:
                raise ValueError("Công việc đã được cập nhật ở phiên khác. Đóng form rồi mở Sửa công việc để nạp dữ liệu mới.")
        elif not emergent:
            count = c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' AND COALESCE(is_emergent,0)=0", (int(plan["id"]),)).fetchone()[0]
            if int(count) >= 7:
                raise ValueError("Kế hoạch đã đủ 7 công việc. Hãy sửa công việc hiện có hoặc bỏ một việc trước khi thêm.")
        values = _clean_values(c, policy, core, actor, ws, payload, iid=iid)
        ts = weekly_push.local_now().strftime("%Y-%m-%d %H:%M:%S")
        if iid:
            c.execute("UPDATE weekly_plan_items SET " + ",".join(f"{key}=?" for key in values) + ",updated_at=? WHERE id=? AND user_id=?", (*values.values(), ts, int(iid), int(uid)))
        else:
            values.update({"plan_id": int(plan["id"]), "user_id": int(uid), "status": "PLANNED", "purposes_json": "[]",
                           "source_text": values["title"], "category": "Công việc phát sinh" if emergent else "Kế hoạch tuần",
                           "estimated_hours": 1.0, "expected_output": "", "is_emergent": int(bool(emergent)),
                           "approval_status": "APPROVED" if emergent else "PENDING", "created_at": ts, "updated_at": ts})
            if emergent:
                values.update({"approved_by_user_id": int(uid), "approved_at": ts})
            keys = list(values)
            iid = int(c.execute("INSERT INTO weekly_plan_items(" + ",".join(keys) + ") VALUES(" + ",".join("?" for _ in keys) + ")", tuple(values.values())).lastrowid)
        if old.get("priority_quadrant") != values["priority_quadrant"] or old.get("focus_category_id") != values["focus_category_id"]:
            c.execute("INSERT INTO weekly_classification_audit(item_id,actor_user_id,old_focus_category_id,new_focus_category_id,old_quadrant,new_quadrant,old_basis,new_basis,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (int(iid), int(uid), old.get("focus_category_id"), values["focus_category_id"], old.get("priority_quadrant"), values["priority_quadrant"], old.get("priority_basis"), values["priority_basis"], "Sửa bản nháp" if old else "Tạo công việc", ts))
        after = dict(c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (int(iid),)).fetchone())
        detail = {"week": ws.isoformat(), "before": old, "after": after}
        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (int(iid), int(uid), "DRAFT_EDIT" if old else "PHAT_SINH" if emergent else "CREATE", json.dumps(detail, ensure_ascii=False), ts))
        c.execute("UPDATE weekly_plans SET updated_at=? WHERE id=?", (ts, int(plan["id"])))
    (logger or LOGGER).info("WEEKLY_ENTRY_SAVED actor=%s plan=%s item=%s edit=%s emergent=%s day=%s", int(uid), int(plan["id"]), int(iid), int(bool(old)), int(bool(emergent)), values["work_date"])
    return int(iid)


def _options(rows, label, blank):
    return [{"value": "", "label": blank}] + [{"value": str(int(x["id"])), "label": label(x)} for x in rows]


def render_form(st, u, policy, core, get_conn, ws, *, item=None, selected_day=None, emergent=False, logger=None):
    uid = int(policy._uget(u, "id"))
    item = dict(item or {})
    iid = int(item.get("id") or 0)
    with get_conn() as c:
        actor = _actor(c, uid)
        customers = core.customers(c, uid)
        leaders = form._leader_rows(c)
        focus_rows = policy._focus_categories(c, policy._scope_key(c, uid), ws.year, False)
        inferred = policy._leader_for_staff(c, uid)
    selected = st.session_state.get(EDIT_KEY) or {}
    epoch = str(selected.get("token") or "")[:12] if iid else str(st.session_state.get(p13._epoch_key(ws, emergent), 0))
    prefix = f"weekly_entry_{uid}_{ws.isoformat()}_{iid or ('ps' if emergent else 'new')}_{epoch}"
    with st.container(border=True):
        st.markdown("#### ✏️ Sửa công việc" if iid else "#### ⚡ Công việc phát sinh" if emergent else "#### ＋ Thêm công việc kế hoạch")
        if st.button("Đóng sửa công việc" if iid else "✕ Đóng", key=prefix + "_close", use_container_width=True):
            st.session_state.pop(EDIT_KEY, None)
            p13._clear_add_state(st.session_state, ws)
            st.rerun()
        customer_options = [None] + customers
        current = next((x for x in customers if int(x["id"]) == int(item.get("customer_id") or 0)), None)
        customer = st.selectbox("Khách hàng", customer_options, index=customer_options.index(current), format_func=lambda x: "— Không gắn khách hàng —" if x is None else f"{x.get('customer_name')} · CIF {x.get('cif') or 'Chưa có CIF'}", key=prefix + "_customer")
        with get_conn() as c:
            cases = p13._case_rows(c, int(customer["id"]), uid, policy._manager(actor)) if customer else []
        linked = None
        if cases:
            options = [None] + cases
            current_case = next((x for x in cases if int(x["id"]) == int(item.get("linked_case_id") or 0)), None)
            linked = st.selectbox("Liên kết Công việc khách hàng (không bắt buộc)", options, index=options.index(current_case), format_func=p13._linked_label, key=prefix + "_case")
        auto_due, auto_leader, auto_focus, source_q = p13._source_defaults(linked, leaders, focus_rows)
        chosen_day = selected_day or _day(item.get("work_date") or ws.isoformat(), "Ngày thực hiện")
        if not ws <= chosen_day <= ws + timedelta(days=6):
            chosen_day = ws
        initial_due = auto_due or _day(item.get("expected_complete_date") or chosen_day.isoformat(), "Ngày hoàn thành")
        title = item.get("title") or (linked.get("title") if linked else "") or ""
        inherited = bool(linked and source_q in {1, 2, 3, 4})
        if inherited:
            st.info(f"Phân loại kế thừa từ Công việc khách hàng: {p13._Q_LABEL[int(source_q)]}. Ngày hoàn thành và lãnh đạo được nạp từ công việc liên kết.")
        fields = [
            {"name": "title", "label": "Công việc", "type": "text", "required": True, "default": title, "full": True},
            {"name": "work_date", "label": "Thứ / ngày thực hiện", "type": "select", "required": True,
             "options": [{"value": (ws + timedelta(days=n)).isoformat(), "label": core.day_label(ws + timedelta(days=n))} for n in range(7)], "default": chosen_day.isoformat()},
            {"name": "due_date", "label": "Ngày dự kiến hoàn thành", "type": "date", "required": True, "default": initial_due.isoformat(), "disabled": bool(auto_due),
             **({"minFrom": "work_date"} if not auto_due else {})},
            {"name": "controller", "label": "Lãnh đạo phòng phụ trách", "type": "select", "required": True,
             "options": _options(leaders, lambda x: str(x.get("full_name") or ""), "— Chọn lãnh đạo phụ trách —"),
             "default": str(auto_leader["id"] if auto_leader else item.get("controller_user_id") or inferred or ""), "disabled": bool(auto_leader), "full": True},
            {"name": "focus", "label": "Danh mục công việc trọng tâm", "type": "select", "required": not inherited,
             "options": _options(focus_rows, lambda x: f"{x.get('code')} · {x.get('name')}", "— Chọn danh mục trọng tâm —") + [{"value": "NONE", "label": "Không thuộc công việc trọng tâm"}],
             "default": str(auto_focus["id"] if auto_focus else item.get("focus_category_id") or ("NONE" if item.get("priority_quadrant") else "")), "disabled": inherited, "full": True},
            {"name": "risk", "label": "Gắn với chỉ tiêu hoặc rủi ro trọng yếu?", "type": "select", "options": [{"value": "", "label": "— Chọn —"}, {"value": "YES", "label": "Có"}, {"value": "NO", "label": "Không"}],
             "default": "YES" if item.get("kpi_risk_flag") == 1 else "NO" if item.get("kpi_risk_flag") == 0 else "", "disabled": inherited,
             "help": "Chỉ cần chọn khi không thuộc trọng tâm và hạn hoàn thành trong 7 ngày tới.", "full": True},
            {"name": "note", "label": "Ghi chú", "type": "textarea", "default": str(item.get("note") or ""), "full": True},
        ]
        if inherited:
            fields = [x for x in fields if x["name"] not in {"focus", "risk"}]
        payload = legacy_fast_form(fields, "💾 Lưu sửa công việc" if iid else "Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch", key=prefix + "_form", reset_token=f"{epoch}|{int(customer['id']) if customer else 0}|{int(linked['id']) if linked else 0}", columns=2,
                                   help_text="Chọn Thứ/ngày ngay trong form. Dữ liệu được giữ trên thiết bị cho đến khi bấm Lưu. Trọng tâm là việc thuộc danh mục phòng; ngoài trọng tâm, phân loại theo hạn và chỉ tiêu/rủi ro.")
        if payload is None:
            return
        payload.update({"customer_id": int(customer["id"]) if customer else None, "linked_case_id": int(linked["id"]) if linked else None})
        try:
            save_item(get_conn, policy, core, uid, ws, payload, iid=iid, expected_token=str(selected.get("token") or ""), emergent=emergent, logger=logger)
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
            return
        except Exception:
            (logger or LOGGER).exception("WEEKLY_ENTRY_SAVE_FAILED actor=%s item=%s", uid, iid)
            st.error("Chưa thể lưu công việc. Dữ liệu đang nhập vẫn được giữ; vui lòng thử lưu lại.")
            return
        st.session_state.pop(EDIT_KEY, None)
        p13._clear_add_state(st.session_state, ws)
        ekey = p13._epoch_key(ws, emergent)
        st.session_state[ekey] = int(st.session_state.get(ekey, 0)) + 1
        st.toast("Đã lưu sửa công việc." if iid else "Đã thêm công việc vào kế hoạch.", icon="✅")
        st.rerun()


def render_weekend(st, policy, core, get_conn, uid, ws, items, status, manager_edit=False):
    """Keep Saturday/Sunday work visible and editable after choosing it in a form."""
    weekend = [x for x in items if str(x.get("work_date") or "")[:10] in {(ws + timedelta(days=5)).isoformat(), (ws + timedelta(days=6)).isoformat()}]
    if not weekend:
        return
    from khdn_apps import planning_operational_phase3_weekly as cards
    with st.expander("Thứ 7 / Chủ nhật", expanded=True):
        for n, column in zip((5, 6), st.columns(2)):
            day = ws + timedelta(days=n)
            with column:
                st.markdown(f"**{core.day_label(day)}**")
                for item in [x for x in weekend if str(x.get("work_date") or "")[:10] == day.isoformat()]:
                    cards.weekly_card(st, policy, core, item, f"weekend_{uid}_{ws.isoformat()}_{n}", can_update=status == "DA_DUYET" and not manager_edit, can_edit=manager_edit)
                    if not manager_edit and status in {"NHAP", "TRA_LAI"}:
                        if st.button("✏️ Sửa công việc", key=f"weekly_draft_edit_{uid}_{ws.isoformat()}_{item['id']}", use_container_width=True):
                            open_editor(st, get_conn, uid, ws, int(item["id"]))


def install(policy, logger=None):
    """Reassert final form bindings on rerun without stacking staff wrappers."""
    def add_form(st, u, core, get_conn, ws, focus_rows, emergent=False, logger=None, logger_arg=None, **kwargs):
        gate = st.session_state.get(f"wp_add_open_{ws.isoformat()}")
        raw_day = st.session_state.get(p13._add_day_key(ws))
        if not gate or not raw_day or bool(st.session_state.get(f"p3_emergent_open_{ws.isoformat()}")) != bool(emergent):
            return
        return render_form(st, u, policy, core, get_conn, ws, selected_day=_day(raw_day, "Thứ / ngày thực hiện"), emergent=emergent, logger=logger or logger_arg)
    policy._add_item_form = add_form
    if not getattr(policy._render_staff_week, "_weekly_entry_editor", False):
        original = policy._render_staff_week

        def staff(st, u, core, get_conn, ws, plan, items, focus_rows, logger=None, logger_arg=None, **kwargs):
            uid = int(policy._uget(u, "id"))
            selected = st.session_state.get(EDIT_KEY) or {}
            if selected.get("uid") == uid and selected.get("week") == ws.isoformat():
                with get_conn() as c:
                    fresh_plan = _plan(c, uid, ws)
                    row = c.execute("SELECT * FROM weekly_plan_items WHERE id=? AND plan_id=? AND user_id=?", (int(selected["iid"]), int(fresh_plan["id"]), uid)).fetchone()
                if fresh_plan.get("workflow_status") == "NHAP" and row and row["status"] != "CANCELLED":
                    render_form(st, u, policy, core, get_conn, ws, item=dict(row), logger=logger or logger_arg)
                else:
                    st.session_state.pop(EDIT_KEY, None)
                    st.warning("Kế hoạch/công việc đã đổi trạng thái; form sửa đã đóng.")
            return original(st, u, core, get_conn, ws, plan, items, focus_rows, logger=logger or logger_arg, **kwargs)

        staff._weekly_entry_editor = True
        policy._render_staff_week = staff
    if logger:
        logger.info("WEEKLY_ENTRY_EDIT_INSTALLED version=%s draft_edit=1 returned_edit=1 all_roles=1 day_selector=1 submit_only=1 data_migration=0", VERSION)
