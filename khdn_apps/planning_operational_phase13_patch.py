"""Operational phase 13: weekly-plan UX and room-control consolidation.

Final runtime overlay after phase 12.  It addresses seven concrete production
behaviours reported from the preview UI:
1. render exactly one Monday-Friday weekday/date/count row;
2. keep every add-work form closed until a weekday quick-add button is clicked,
   prefill that clicked date, and clear the gate after save/close;
3. let officers type a different Weekly Plan task for an existing customer even
   when that customer already has active Customer Work cases; linking a case is
   optional;
4. when a Customer Work case is linked, inherit its stored Q1-Q4 priority
   directly (especially Q4) instead of asking the Weekly Plan classifier again;
5. move approved-week progress score cards above the weekday board;
6. render the Customer Work Excel export at the very bottom of Room Control;
7. give weekly-cancel and customer-work-cancel requests their own tabs beside
   approvals and progress/issues in the leader waiting center.

Logs contain identifiers/counts only. Customer names, contacts, work titles and
cancellation reasons are never written to runtime logs.
"""
from __future__ import annotations

from datetime import date, timedelta
import html

from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase3_weekly as p3week
from khdn_apps import planning_operational_phase4_patch as p4
from khdn_apps import planning_operational_phase7_patch as p7
from khdn_apps import planning_operational_phase11_patch as p11
from khdn_apps import planning_operational_phase12_patch as p12
from khdn_apps import planning_week_board_focus_patch as weekfocus
from khdn_apps import weekly_performance_phase2_patch as phase2
from khdn_apps import weekly_plan_form_refinement_patch as form

VERSION = "1.0.1"
_FLAG = "_PLANNING_OPERATIONAL_PHASE13_VERSION"

_Q_LABEL = {
    1: "Q1 · Cấp thiết",
    2: "Q2 · Trọng tâm",
    3: "Q3 · Phân tâm",
    4: "Q4 · Giá trị thấp",
}


def _table_exists(c, name):
    return bool(c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (str(name),)
    ).fetchone())


def _cols(c, table):
    if not _table_exists(c, table):
        return set()
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _day_counts(ws, items):
    live = [dict(x) for x in (items or []) if str(x.get("status") or "") != "CANCELLED"]
    out = []
    for idx in range(5):
        d = ws + timedelta(days=idx)
        out.append(sum(1 for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()))
    return out


def _weekday_strip(ws, items):
    counts = _day_counts(ws, items)
    today = date.today()
    cells = []
    for idx, label in enumerate(("THỨ 2", "THỨ 3", "THỨ 4", "THỨ 5", "THỨ 6")):
        d = ws + timedelta(days=idx)
        current = d == today
        current_cls = " p13-day-current" if current else ""
        today_badge = "<em>HÔM NAY</em>" if current else ""
        cells.append(
            f"<div class='p13-day{current_cls}'>"
            f"<b>{label}</b><span>{d:%d/%m}</span><small>{counts[idx]} việc</small>{today_badge}</div>"
        )
    return (
        "<div class='p13-day-strip'>" + "".join(cells) + "</div>"
        "<style>"
        ".p13-day-strip{display:grid;grid-template-columns:repeat(5,minmax(125px,1fr));gap:8px;margin:.25rem 0 .72rem 0;overflow-x:auto}"
        ".p13-day{min-width:0;border:1px solid rgba(244,180,26,.88);border-radius:12px;padding:10px;text-align:center;background:linear-gradient(135deg,rgba(7,92,87,.96),rgba(15,116,107,.80));box-shadow:0 4px 12px rgba(0,0,0,.14)}"
        ".p13-day b{display:block;color:#FFD45A;font-size:.84rem;letter-spacing:.04em}.p13-day span{display:block;color:#fff;font-size:1.04rem;font-weight:950;margin-top:2px}.p13-day small{display:block;color:#fff;font-size:.70rem;font-weight:850;opacity:.92;margin-top:3px}.p13-day em{display:inline-block;margin-top:5px;padding:2px 7px;border-radius:999px;background:#2B2410;color:#FFD45A;font-size:.63rem;font-style:normal;font-weight:950}"
        ".p13-day-current{background:linear-gradient(135deg,#F4B41A,#FFD45A);border-color:#FFE589}.p13-day-current b,.p13-day-current span,.p13-day-current small{color:#2B2410}"
        "@media(max-width:760px){.p13-day-strip{grid-template-columns:repeat(5,135px)}}"
        "</style>"
    )


def _epoch_key(ws, emergent):
    return f"wp_refine_epoch_{ws.isoformat()}_{'ps' if emergent else 'plan'}"


def _add_day_key(ws):
    return f"p13_week_add_day_{ws.isoformat()}"


def _clear_add_state(state, ws):
    """Clear all legacy and Phase-13 add gates after save/close."""
    for key in (
        f"wp_add_open_{ws.isoformat()}",
        f"wp_quick_day_{ws.isoformat()}",
        f"p3_emergent_open_{ws.isoformat()}",
        _add_day_key(ws),
    ):
        try:
            state.pop(key, None)
        except Exception:
            pass


def _open_quick_add(st, ws, day, status):
    st.session_state.pop("_weekly_entry_edit", None)
    emergent = str(status or "") == "DA_DUYET"
    # New epoch guarantees that a previous date_input widget cannot retain a
    # different day when the officer clicks another weekday.
    ekey = _epoch_key(ws, emergent)
    st.session_state[ekey] = int(st.session_state.get(ekey, 0) or 0) + 1
    st.session_state[f"wp_add_open_{ws.isoformat()}"] = True
    st.session_state[f"wp_quick_day_{ws.isoformat()}"] = day.isoformat()
    st.session_state[_add_day_key(ws)] = day.isoformat()
    if emergent:
        st.session_state[f"p3_emergent_open_{ws.isoformat()}"] = True


def _single_week_board(st, policy, weekly_core, get_conn, uid, ws, items, status, manager_edit=False):
    """One date row only; task/add columns live directly underneath it."""
    st.markdown("### 🗓 Kế hoạch Thứ 2 → Thứ 6")
    live = [dict(x) for x in (items or []) if str(x.get("status") or "") != "CANCELLED"]
    st.html(_weekday_strip(ws, live))

    uid = int(uid)
    cols = st.columns(5, gap="small")
    for idx, col in enumerate(cols):
        d = ws + timedelta(days=idx)
        arr = [x for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()]
        arr.sort(
            key=lambda x: (
                policy.PRIORITY_ORDER.index(int(x.get("priority_quadrant") or 4))
                if int(x.get("priority_quadrant") or 4) in policy.PRIORITY_ORDER else 9,
                int(x.get("id") or 0),
            )
        )
        with col:
            if not manager_edit and str(status or "") in {"NHAP", "DA_DUYET"}:
                key = f"p13_quick_add_{uid}_{ws.isoformat()}_{idx}_{status}"
                if st.button(f"＋ Thêm việc {weekly_core.day_label(d)}", key=key, use_container_width=True):
                    _open_quick_add(st, ws, d, status)
                    st.rerun()
            if not arr:
                st.caption("Chưa có công việc")
            for x in arr:
                p3week.weekly_card(
                    st, policy, weekly_core, x,
                    f"p13_{uid}_{ws.isoformat()}_{idx}_{'mgr' if manager_edit else 'staff'}",
                    can_update=(str(status or "") == "DA_DUYET" and not manager_edit),
                    can_edit=manager_edit,
                )
                if not manager_edit and str(status or "") in {"NHAP", "TRA_LAI"}:
                    if st.button("✏️ Sửa công việc", key=f"weekly_draft_edit_{uid}_{ws.isoformat()}_{x['id']}", use_container_width=True):
                        from khdn_apps import weekly_entry_edit_patch as entry
                        entry.open_editor(st, get_conn, uid, ws, int(x["id"]))
                if not manager_edit and str(status or "") == "NHAP" and not int(x.get("is_emergent") or 0):
                    if st.button("🗑 Bỏ", key=f"p13_remove_{uid}_{x['id']}", use_container_width=True):
                        with get_conn() as c:
                            c.execute(
                                "UPDATE weekly_plan_items SET status='CANCELLED',updated_at=? WHERE id=? AND user_id=?",
                                (policy._now(), int(x["id"]), uid),
                            )
                            c.execute(
                                "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'DRAFT_REMOVE','Bỏ khỏi bản nháp',?)",
                                (int(x["id"]), uid, policy._now()),
                            )
                        st.rerun()


    from khdn_apps import weekly_entry_edit_patch as entry
    entry.render_weekend(st, policy, weekly_core, get_conn, uid, ws, live, str(status or ""), manager_edit)


def _install_single_week_board(weekly_core, logger=None):
    def board(st, policy_arg, weekly_core_arg, get_conn, uid, ws, items, status, manager_edit=False):
        return _single_week_board(
            st, policy_arg, weekly_core_arg, get_conn, uid, ws, items, status,
            manager_edit=manager_edit,
        )

    # Patch every route used by Draft, Approved, Room and legacy wrappers. This
    # intentionally bypasses Phase-11/12 proxy stacking that left p6-day-head
    # visible as a second weekday/date row.
    p3week.render_week_board = board
    p3dash.render_week_board = board
    weekfocus._render_week_board = lambda st, policy_arg, get_conn, uid, ws, items, status: board(
        st, policy_arg, weekly_core, get_conn, uid, ws, items, status, manager_edit=False
    )
    if logger:
        logger.info("P13_WEEK_BOARD_INSTALLED single_header=1 date_counts=1 quick_add_day=1")


def _case_rows(c, customer_id, uid, manager=False):
    if not customer_id or not _table_exists(c, "customer_work_cases"):
        return []
    cols = _cols(c, "customer_work_cases")
    controller = "cw.controller_user_id" if "controller_user_id" in cols else "NULL"
    important = "cw.important_category_id" if "important_category_id" in cols else "NULL"
    priority = "cw.priority_quadrant" if "priority_quadrant" in cols else "NULL"
    sql = f"""
        SELECT cw.id,cw.case_code,cw.title,cw.case_type,cw.owner_user_id,cw.expected_complete_at,
               {controller} AS controller_user_id,
               {important} AS important_category_id,
               {priority} AS priority_quadrant,
               COALESCE(ws.name,'') AS stage_name,
               COALESCE(owner.full_name,'') AS owner_name,
               COALESCE(ctrl.full_name,'') AS controller_name
        FROM customer_work_cases cw
        LEFT JOIN work_stage_catalog ws ON ws.id=cw.current_stage_id
        LEFT JOIN users owner ON owner.id=cw.owner_user_id
        LEFT JOIN users ctrl ON ctrl.id={controller}
        WHERE cw.customer_id=? AND cw.status='ACTIVE'
    """
    params = [int(customer_id)]
    if not manager:
        sql += " AND cw.owner_user_id=?"
        params.append(int(uid))
    sql += " ORDER BY CASE WHEN cw.expected_complete_at IS NULL THEN 1 ELSE 0 END,cw.expected_complete_at,cw.id"
    return [dict(r) for r in c.execute(sql, params).fetchall()]


def _source_defaults(linked_case, leaders, focus_rows):
    due = None
    leader = None
    focus = None
    q = None
    if not linked_case:
        return due, leader, focus, q
    raw_due = linked_case.get("expected_complete_at")
    if raw_due:
        try:
            due = date.fromisoformat(str(raw_due)[:10])
        except Exception:
            due = None
    controller = int(linked_case.get("controller_user_id") or 0)
    if controller:
        leader = next((x for x in leaders or [] if int(x.get("id") or 0) == controller), None)
    important = int(linked_case.get("important_category_id") or 0)
    if important:
        focus = next(
            (x for x in focus_rows or [] if int(x.get("legacy_category_id") or 0) == important),
            None,
        )
    try:
        raw_q = int(linked_case.get("priority_quadrant") or 0)
        q = raw_q if raw_q in {1, 2, 3, 4} else None
    except Exception:
        q = None
    return due, leader, focus, q


def _classification_from_source(q):
    """Return classifier-compatible flags for an authoritative source quadrant."""
    try:
        q = int(q)
    except Exception:
        return None, None
    if q == 1:
        return True, True
    if q == 3:
        return True, False
    if q == 4:
        return False, None
    if q == 2:
        return None, None
    return None, None


def _linked_label(x):
    if not x:
        return "— Không liên kết; nhập công việc khác cho khách hàng —"
    return " · ".join(
        p for p in [str(x.get("case_code") or ""), str(x.get("title") or ""), str(x.get("stage_name") or "")]
        if p
    )


def _install_weekly_add_form(policy, logger=None):
    def add_item_form(st, u, core, conn_fn, ws, focus_rows, emergent=False,
                      logger=None, logger_arg=None, **kwargs):
        active_logger = logger_arg or logger
        gate = bool(st.session_state.get(f"wp_add_open_{ws.isoformat()}"))
        selected_day_raw = st.session_state.get(_add_day_key(ws))
        if not gate or not selected_day_raw:
            return None
        if emergent and not st.session_state.get(f"p3_emergent_open_{ws.isoformat()}"):
            return None
        if not emergent and st.session_state.get(f"p3_emergent_open_{ws.isoformat()}"):
            return None

        try:
            selected_day = date.fromisoformat(str(selected_day_raw)[:10])
        except Exception:
            _clear_add_state(st.session_state, ws)
            return None

        uid = int(policy._uget(u, "id"))
        epoch_key = _epoch_key(ws, emergent)
        epoch = int(st.session_state.get(epoch_key, 0) or 0)
        prefix = f"wp_p13_{ws.isoformat()}_{'ps' if emergent else 'plan'}_{epoch}"

        head, close = st.columns([7, 1])
        with head:
            st.markdown("#### ⚡ Công việc phát sinh" if emergent else "#### ＋ Thêm công việc kế hoạch")
            st.caption(f"Ngày thực hiện được lấy từ nút ＋ Thêm công việc đã chọn: {selected_day:%d/%m/%Y}.")
        with close:
            if st.button("✕ Đóng", key=f"{prefix}_close", use_container_width=True):
                _clear_add_state(st.session_state, ws)
                st.rerun()

        with conn_fn() as c:
            customers = core.customers(c, uid)
            leaders = form._leader_rows(c)
            inferred_leader = policy._leader_for_staff(c, uid)

        customer = st.selectbox(
            "Khách hàng",
            [None] + customers,
            index=0,
            format_func=lambda x: "— Không gắn khách hàng —" if x is None else f"{x.get('customer_name')} · {'CIF '+str(x.get('cif')) if x.get('cif') else 'Chưa có CIF'}",
            key=f"{prefix}_customer",
        )

        cases = []
        if customer:
            with conn_fn() as c:
                cases = _case_rows(c, int(customer["id"]), uid, policy._manager(u))

        linked_case = None
        if cases:
            linked_case = st.selectbox(
                "Liên kết Công việc khách hàng (không bắt buộc)",
                [None] + cases,
                index=0,
                format_func=_linked_label,
                key=f"{prefix}_linked_case",
                help=(
                    "Chỉ chọn khi công việc trong Kế hoạch tuần chính là workflow Công việc khách hàng đang xử lý. "
                    "Nếu tuần này làm một việc khác cho cùng khách hàng, để Không liên kết và nhập nội dung Công việc bên dưới."
                ),
            )

        title_default = str(linked_case.get("title") or "").strip() if linked_case else ""
        title_key = f"{prefix}_title_link_{int(linked_case['id'])}" if linked_case else f"{prefix}_title_manual"
        title = st.text_input(
            "Công việc *",
            value=title_default,
            key=title_key,
            placeholder="Ví dụ: Gặp Công ty A – tiếp thị tiền gửi",
            help="Nội dung luôn có thể nhập/chỉnh sửa; danh sách Công việc khách hàng chỉ là liên kết workflow tùy chọn.",
        )
        if customer and cases and not linked_case:
            st.caption("Bạn đang lập một công việc khác cho khách hàng này; không bắt buộc chọn công việc đang xử lý trong danh sách.")
        elif linked_case:
            st.success(
                f"🔗 Đã liên kết workflow {linked_case.get('case_code') or 'CVKH'} · "
                f"{linked_case.get('stage_name') or 'Đang xử lý'} · linked_case_id={int(linked_case['id'])}"
            )

        # Read-only by design: the clicked weekday is the single source for the
        # initial execution date, preventing accidental add-to-wrong-day.
        day = st.date_input(
            "Ngày thực hiện *",
            value=selected_day,
            min_value=ws,
            max_value=ws + timedelta(days=6),
            key=f"{prefix}_day",
            disabled=True,
            help="Tự động lấy từ cột Thứ/ngày nơi bạn nhấn ＋ Thêm công việc.",
        )

        with conn_fn() as c:
            scope = policy._scope_key(c, uid)
            live_focus_rows = policy._focus_categories(c, scope, ws.year, False)
        auto_due, auto_leader, auto_focus, source_q = _source_defaults(linked_case, leaders, live_focus_rows)

        if linked_case and auto_due:
            due = st.date_input(
                "Ngày dự kiến hoàn thành *",
                value=auto_due,
                key=f"{prefix}_due_link_{int(linked_case['id'])}",
                disabled=True,
                help="Tự động lấy từ Công việc khách hàng đã liên kết.",
            )
            st.caption("🔗 Ngày hoàn thành được đồng bộ từ Công việc khách hàng.")
        else:
            due = st.date_input(
                "Ngày dự kiến hoàn thành *",
                value=day,
                min_value=day,
                key=f"{prefix}_due",
            )

        leader_options = [None] + leaders
        if linked_case and auto_leader:
            leader = st.selectbox(
                "Lãnh đạo phòng phụ trách *",
                [auto_leader],
                index=0,
                format_func=lambda x: str(x.get("full_name") or ""),
                key=f"{prefix}_leader_link_{int(linked_case['id'])}",
                disabled=True,
                help="Tự động lấy từ Lãnh đạo kiểm soát của Công việc khách hàng.",
            )
            st.caption("🔗 Lãnh đạo phụ trách được đồng bộ từ Công việc khách hàng.")
        else:
            leader_idx = 0
            if inferred_leader:
                for i, row in enumerate(leader_options):
                    if isinstance(row, dict) and int(row.get("id") or 0) == int(inferred_leader):
                        leader_idx = i
                        break
            leader = st.selectbox(
                "Lãnh đạo phòng phụ trách *",
                leader_options,
                index=leader_idx,
                format_func=lambda x: "— Chọn lãnh đạo phụ trách —" if x is None else str(x.get("full_name") or ""),
                key=f"{prefix}_leader",
            )

        # A linked Customer Work case is the authoritative workflow source.
        # Its stored Q1-Q4 is inherited as-is; do not ask the officer to classify
        # the same workflow a second time. This is the key Q4 correction.
        if linked_case and source_q in {1, 2, 3, 4}:
            q = int(source_q)
            focus = auto_focus if q == 2 else None
            due7, risk = _classification_from_source(q)
            st.info(f"🔗 Phân loại kế thừa từ Công việc khách hàng: {_Q_LABEL[q]}.")
            if q == 2 and auto_focus:
                st.selectbox(
                    "Danh mục công việc trọng tâm của phòng",
                    [auto_focus],
                    index=0,
                    format_func=lambda x: f"{x.get('code')} · {x.get('name')}",
                    key=f"{prefix}_focus_link_{int(linked_case['id'])}",
                    disabled=True,
                )
            elif q == 2 and not auto_focus:
                st.caption("Công việc nguồn là Q2; danh mục trọng tâm cũ chưa có ánh xạ đang hoạt động nhưng mức Q2 vẫn được giữ theo workflow nguồn.")
        else:
            focus, due7, risk, q = form._focus_picker(st, policy, live_focus_rows, prefix, due)

        ok = st.button(
            "Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch",
            key=f"{prefix}_save",
            type="primary",
            use_container_width=True,
        )
        if not ok:
            return None

        missing = []
        if not str(title or "").strip():
            missing.append("Công việc")
        if not linked_case and due < day:
            missing.append("Ngày dự kiến hoàn thành")
        if not leader:
            missing.append("Lãnh đạo phòng phụ trách")
        if q is None:
            missing.append("Căn cứ phân loại Q1–Q4")
        if missing:
            st.error("Vui lòng nhập/chọn đầy đủ: " + ", ".join(missing) + ".")
            return None

        linked_case_id = int(linked_case["id"]) if linked_case else None
        if linked_case_id:
            with conn_fn() as c:
                duplicate = c.execute(
                    """SELECT 1 FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id
                       WHERE p.user_id=? AND p.week_start=? AND w.linked_case_id=? AND w.status<>'CANCELLED' LIMIT 1""",
                    (uid, ws.isoformat(), linked_case_id),
                ).fetchone()
            if duplicate:
                st.error("Công việc khách hàng này đã có trong kế hoạch tuần; hãy để Không liên kết nếu bạn đang tạo một công việc khác cho cùng khách hàng.")
                return None

        item = {
            "work_date": day.isoformat(),
            "start_time": None,
            "daypart": None,
            "title": str(title).strip(),
            "customer_id": int(customer["id"]) if customer else None,
            "customer_text": str(customer.get("customer_name") or "") if customer else "",
            "category": "Công việc phát sinh" if emergent else "Kế hoạch tuần",
            "purposes": [],
            "source_text": str(title).strip(),
            "linked_task_id": None,
            "note": None,
            "estimated_hours": 1.0,
            "expected_output": "",
            "is_emergent": 1 if emergent else 0,
            "focus_category_id": int(focus["id"]) if focus else None,
            "deadline_within_7d": due7,
            "kpi_risk_flag": risk,
        }
        iid, errs = policy._save_extended_item(core, conn_fn, uid, ws, item, active_logger)
        if not iid:
            st.error("; ".join(str(e) for e in (errs or ["Không thể lưu công việc"])))
            return None

        with conn_fn() as c:
            sets = ["expected_complete_date=?", "controller_user_id=?", "linked_case_id=?", "expected_output=''", "priority_quadrant=?"]
            params = [due.isoformat(), int(leader["id"]), linked_case_id, int(q)]
            if "priority_basis" in _cols(c, "weekly_plan_items") and linked_case_id and source_q in {1, 2, 3, 4}:
                sets.append("priority_basis=?")
                params.append(f"Kế thừa Công việc khách hàng #{linked_case_id}: {_Q_LABEL[int(source_q)]}")
            params.append(int(iid))
            c.execute("UPDATE weekly_plan_items SET " + ",".join(sets) + " WHERE id=?", tuple(params))

        st.session_state[epoch_key] = epoch + 1
        _clear_add_state(st.session_state, ws)
        if active_logger:
            active_logger.info(
                "P13_WEEK_ADD_SAVED item=%s actor=%s linked_case=%s inherited_q=%s emergent=%s",
                int(iid), uid, linked_case_id or 0,
                int(source_q) if linked_case_id and source_q in {1, 2, 3, 4} else 0,
                int(bool(emergent)),
            )
        st.toast("Đã thêm công việc vào kế hoạch.", icon="✅")
        st.rerun()

    policy._add_item_form = add_item_form
    if logger:
        logger.info("P13_WEEK_ADD_FORM_INSTALLED hidden_default=1 optional_case_link=1 source_priority=1 autoclose=1")


def _install_approved_progress_top(policy, weekly_core, logger=None):
    original_staff = policy._render_staff_week

    def render_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows,
                          logger=None, logger_arg=None, **kwargs):
        active_logger = logger_arg or logger
        if str(plan.get("workflow_status") or "NHAP") != "DA_DUYET":
            return original_staff(
                st, u, core, get_conn, ws, plan, items, focus_rows,
                logger=active_logger, **kwargs
            )

        phase2._ensure_schema(policy, weekly_core, get_conn, active_logger)
        with get_conn() as c:
            fresh_plan = dict(c.execute("SELECT * FROM weekly_plans WHERE id=?", (int(plan["id"]),)).fetchone())
            fresh_items = phase2._load_items(c, int(plan["id"]))

        # Requested order: progress information first, then the weekday board.
        metrics = phase2._metrics(fresh_items)
        phase2._score_cards(st, metrics, fresh_plan)
        st.success("Kế hoạch đã duyệt. Cập nhật tiến độ trực tiếp trên từng card công việc.")
        p3week.render_week_board(
            st, policy, weekly_core, get_conn, int(policy._uget(u, "id")),
            ws, fresh_items, "DA_DUYET",
        )

        selected = st.session_state.get("p3_update_week_item")
        if selected:
            item = next((x for x in fresh_items if int(x.get("id") or 0) == int(selected)), None)
            if item:
                p3week.render_week_update_form(st, u, policy, weekly_core, get_conn, item, active_logger)

        # No generic "add during week" button. Only a weekday button can set the
        # Phase-13 day token, so the form always has an unambiguous execution date.
        if st.session_state.get(f"p3_emergent_open_{ws.isoformat()}") and st.session_state.get(_add_day_key(ws)):
            policy._add_item_form(
                st, u, weekly_core, get_conn, ws, focus_rows,
                emergent=True, logger=active_logger,
            )

        st.divider()
        p3week._render_self_close(st, u, policy, get_conn, ws, fresh_plan, metrics)

    policy._render_staff_week = render_staff_week
    if logger:
        logger.info("P13_APPROVED_PROGRESS_TOP_INSTALLED score_cards_before_board=1 generic_emergent_button=0")


def _pending_week_cancel_rows(get_conn, policy, u):
    p7._ensure_cancel_schema(get_conn)
    uid = int(policy._uget(u, "id"))
    admin = bool(policy._is_admin(u))
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT r.*,w.title,w.customer_text,w.user_id,w.work_date,w.expected_complete_date,
                      req.full_name requester_name,ctrl.full_name controller_name
               FROM weekly_plan_cancel_requests r
               JOIN weekly_plan_items w ON w.id=r.item_id
               LEFT JOIN users req ON req.id=r.requested_by
               LEFT JOIN users ctrl ON ctrl.id=w.controller_user_id
               WHERE r.status='PENDING' ORDER BY r.requested_at,r.id"""
        ).fetchall()]
        if not admin:
            rows = [r for r in rows if p7._weekly_controller_allows(c, uid, int(r["item_id"]))]
        return rows


def _install_waiting_tabs(policy, weekly_core, customer_core, get_conn, logger=None):
    # Phase 7 appended weekly-cancel approvals inside p4._render_approval_items.
    # Keep its mature renderer, but remove that append so cancellation can have
    # its own sibling tab exactly as requested.
    weekly_cancel_renderer = p7._render_cancel_approvals
    if not getattr(p7, "_P13_WEEK_CANCEL_DETACHED", False):
        p7._render_cancel_approvals = lambda *args, **kwargs: None
        p7._P13_WEEK_CANCEL_DETACHED = True

    def attention_dashboard(st, u, policy_arg, customer_core_arg, conn_fn, logger=None):
        active_logger = logger
        try:
            _, cases, moves, plans, wmoves = p4._pending_approval_data(
                u, policy, weekly_core, customer_core, conn_fn
            )
            attention = p4._attention_rows(u, policy, conn_fn)
            week_cancels = _pending_week_cancel_rows(conn_fn, policy, u)
            customer_cancels = p12._pending_cancel_rows(conn_fn, policy, u)
        except Exception:
            cases, moves, plans, wmoves, attention, week_cancels, customer_cancels = [], [], [], [], [], [], []

        approval_total = len(cases) + len(moves) + len(plans) + len(wmoves)
        total = approval_total + len(attention) + len(week_cancels) + len(customer_cancels)
        st.markdown("## 🔔 Trung tâm việc chờ lãnh đạo xử lý")
        with st.container(key="p13_leader_waiting_center"):
            if total > 0:
                st.html(
                    "<style>@keyframes p13AttentionPulse{0%{box-shadow:0 0 0 1px rgba(244,180,26,.30)}100%{box-shadow:0 0 0 7px rgba(244,180,26,.10),0 0 28px rgba(244,180,26,.42)}}"
                    "div[class*='st-key-p13_leader_waiting_center']{border:2px solid #F4B41A!important;border-radius:14px!important;padding:8px 12px!important;animation:p13AttentionPulse 1.15s ease-in-out infinite alternate!important}"
                    "@media (prefers-reduced-motion:reduce){div[class*='st-key-p13_leader_waiting_center']{animation:none!important}}</style>"
                )
                st.warning(f"⚠ Có {total} nội dung đang chờ lãnh đạo xử lý.")

            t1, t2, t3, t4 = st.tabs([
                f"✅ Phê duyệt kế hoạch / dời hạn ({approval_total})",
                f"🔄 Cập nhật tiến độ / vướng mắc ({len(attention)})",
                f"🗑 Hủy kế hoạch tuần ({len(week_cancels)})",
                f"🗑 Hủy công việc KH ({len(customer_cancels)})",
            ])
            with t1:
                p4._render_approval_items(
                    st, u, policy, weekly_core, customer_core, customer_core_arg, conn_fn, active_logger
                )
            with t2:
                p4._render_attention_items(st, u, policy, customer_core, conn_fn, active_logger)
            with t3:
                weekly_cancel_renderer(st, u, policy, conn_fn, active_logger)
            with t4:
                p12._render_cancel_approvals(st, u, policy, conn_fn, active_logger)
        st.divider()

    # The sixth positional argument of p4._render_approval_items is customer_ui,
    # not customer_core. The dashboard callback only receives customer_core, so
    # bind the true customer_ui later in install() through a closure attribute.
    attention_dashboard._p13_needs_customer_ui = True
    p3dash._attention_dashboard = attention_dashboard
    if logger:
        logger.info("P13_WAITING_TABS_BASE_INSTALLED tabs=4 pulse=1")
    return weekly_cancel_renderer


def _bind_waiting_tabs_customer_ui(policy, weekly_core, customer_core, customer_ui, get_conn, logger=None):
    weekly_cancel_renderer = getattr(p7, "_P13_SAVED_WEEK_CANCEL_RENDERER", None)
    if weekly_cancel_renderer is None:
        # Save before detaching if another execution path reaches this first.
        weekly_cancel_renderer = p7._render_cancel_approvals
        p7._P13_SAVED_WEEK_CANCEL_RENDERER = weekly_cancel_renderer

    # Ensure the mature p4 approval renderer no longer appends weekly cancellation.
    if not getattr(p7, "_P13_WEEK_CANCEL_DETACHED", False):
        p7._render_cancel_approvals = lambda *args, **kwargs: None
        p7._P13_WEEK_CANCEL_DETACHED = True

    def attention_dashboard(st, u, policy_arg, customer_core_arg, conn_fn, logger=None):
        active_logger = logger
        try:
            _, cases, moves, plans, wmoves = p4._pending_approval_data(
                u, policy, weekly_core, customer_core, conn_fn
            )
            attention = p4._attention_rows(u, policy, conn_fn)
            week_cancels = _pending_week_cancel_rows(conn_fn, policy, u)
            customer_cancels = p12._pending_cancel_rows(conn_fn, policy, u)
        except Exception:
            cases, moves, plans, wmoves, attention, week_cancels, customer_cancels = [], [], [], [], [], [], []

        approval_total = len(cases) + len(moves) + len(plans) + len(wmoves)
        total = approval_total + len(attention) + len(week_cancels) + len(customer_cancels)
        st.markdown("## 🔔 Trung tâm việc chờ lãnh đạo xử lý")
        with st.container(key="p13_leader_waiting_center"):
            if total > 0:
                st.html(
                    "<style>@keyframes p13AttentionPulse{0%{box-shadow:0 0 0 1px rgba(244,180,26,.30)}100%{box-shadow:0 0 0 7px rgba(244,180,26,.10),0 0 28px rgba(244,180,26,.42)}}"
                    "div[class*='st-key-p13_leader_waiting_center']{border:2px solid #F4B41A!important;border-radius:14px!important;padding:8px 12px!important;animation:p13AttentionPulse 1.15s ease-in-out infinite alternate!important}"
                    "@media (prefers-reduced-motion:reduce){div[class*='st-key-p13_leader_waiting_center']{animation:none!important}}</style>"
                )
                st.warning(f"⚠ Có {total} nội dung đang chờ lãnh đạo xử lý.")

            t1, t2, t3, t4 = st.tabs([
                f"✅ Phê duyệt kế hoạch / dời hạn ({approval_total})",
                f"🔄 Cập nhật tiến độ / vướng mắc ({len(attention)})",
                f"🗑 Hủy kế hoạch tuần ({len(week_cancels)})",
                f"🗑 Hủy công việc KH ({len(customer_cancels)})",
            ])
            with t1:
                p4._render_approval_items(
                    st, u, policy, weekly_core, customer_core, customer_ui, conn_fn, active_logger
                )
            with t2:
                p4._render_attention_items(st, u, policy, customer_core, conn_fn, active_logger)
            with t3:
                weekly_cancel_renderer(st, u, policy, conn_fn, active_logger)
            with t4:
                p12._render_cancel_approvals(st, u, policy, conn_fn, active_logger)
        st.divider()

    p3dash._attention_dashboard = attention_dashboard
    if logger:
        logger.info("P13_WAITING_TABS_INSTALLED tabs=4 weekly_cancel_tab=1 customer_cancel_tab=1 pulse=1")


def _install_room_export_bottom(customer_ui, policy, logger=None):
    if getattr(customer_ui, "_P13_EXPORT_BOTTOM", False):
        return
    actual_export = p11._render_customer_work_export

    def deferred_export(st, get_conn, actor, logger_arg=None):
        if st.session_state.get("_p13_defer_room_export"):
            return None
        return actual_export(st, get_conn, actor, logger_arg or logger)

    # Phase 11's title callback resolves this module global at render time.
    p11._render_customer_work_export = deferred_export
    current_dashboard = customer_ui.render_leader_dashboard

    def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None, **kwargs):
        active_logger = logger
        st.session_state["_p13_defer_room_export"] = True
        try:
            result = current_dashboard(
                st=st, u=u, get_conn=get_conn, page_title=page_title,
                logger=active_logger, **kwargs
            )
        finally:
            st.session_state.pop("_p13_defer_room_export", None)
        if p11._customer_work_export_allowed(get_conn, u):
            st.divider()
            try:
                actual_export(st, get_conn, u, active_logger)
            except Exception as exc:
                if active_logger:
                    active_logger.exception("P13_CUSTOMER_WORK_EXPORT_BOTTOM_FAILED")
                st.error(f"Không thể chuẩn bị file Excel Công việc khách hàng: {exc}")
        else:
            st.session_state.pop("p11_customer_work_excel_cache", None)
        return result

    customer_ui.render_leader_dashboard = render_leader_dashboard
    customer_ui._P13_EXPORT_BOTTOM = True
    if logger:
        logger.info("P13_ROOM_EXPORT_BOTTOM_INSTALLED top_export_suppressed=1 bottom_export=1 admin_only=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype=None, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    app_logger = logger or app_ns.get("LOGGER")
    get_conn = app_ns["get_conn"]

    # Save Phase-7's real weekly-cancel renderer before replacing its append hook.
    if not hasattr(p7, "_P13_SAVED_WEEK_CANCEL_RENDERER"):
        p7._P13_SAVED_WEEK_CANCEL_RENDERER = p7._render_cancel_approvals

    _install_single_week_board(weekly_core, app_logger)
    _install_weekly_add_form(policy, app_logger)
    _install_approved_progress_top(policy, weekly_core, app_logger)
    _bind_waiting_tabs_customer_ui(policy, weekly_core, customer_core, customer_ui, get_conn, app_logger)
    _install_room_export_bottom(customer_ui, policy, app_logger)

    setattr(policy, _FLAG, VERSION)
    if app_logger:
        app_logger.info(
            "PLANNING_OPERATIONAL_PHASE13_INSTALLED version=%s single_week_row=1 add_hidden=1 manual_customer_task=1 source_priority=1 progress_top=1 export_bottom=1 waiting_tabs=4",
            VERSION,
        )
