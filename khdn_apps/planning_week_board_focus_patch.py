"""Final planning UX requested for Weekly Plan and Customer Work.

- Weekly Plan renders as a Monday-Friday board.
- Customer Work priority selector uses the room focus catalog (Q2-first).
- QLKH/CBHT self-own newly created customer work by default.
- Customer Work cards always expose the detail action, including attention cards.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import date, datetime, time, timedelta
import html
import json

from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3

VERSION = "1.0.0"
_FLAG = "_PLANNING_WEEK_BOARD_FOCUS_PATCH_VERSION"
_BOARD_CTX = ContextVar("khdn_week_board_ctx", default=None)
_SUPPRESS_ITEMS = ContextVar("khdn_week_board_suppress_items", default=False)

_HEAT = {
    2: {"accent": "#FF9F1C", "bg": "rgba(255,159,28,.12)", "label": "Q2 · Trọng tâm"},
    1: {"accent": "#FF4B55", "bg": "rgba(255,75,85,.12)", "label": "Q1 · Cấp thiết"},
    3: {"accent": "#F2D35E", "bg": "rgba(242,211,94,.12)", "label": "Q3 · Phân tâm"},
    4: {"accent": "#38C172", "bg": "rgba(56,193,114,.11)", "label": "Q4 · Giá trị thấp"},
}


def _dmy(value):
    if not value:
        return "—"
    s = str(value)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        try:
            return date.fromisoformat(s[:10]).strftime("%d/%m/%Y")
        except Exception:
            return s


def _ensure_case_focus_schema(get_conn):
    with get_conn() as c:
        cols = {str(r[1]) for r in c.execute("PRAGMA table_info(customer_work_cases)").fetchall()}
        for name, ddl in (
            ("focus_category_id", "INTEGER"),
            ("focus_code_snapshot", "TEXT"),
            ("focus_name_snapshot", "TEXT"),
        ):
            if name not in cols:
                c.execute(f"ALTER TABLE customer_work_cases ADD COLUMN {name} {ddl}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cw_focus_category ON customer_work_cases(focus_category_id)")


def _focus_rows(policy, c, uid):
    scope = policy._scope_key(c, int(uid))
    return policy._focus_categories(c, scope, date.today().year, False)


def _render_week_board(st, policy, get_conn, uid, ws, items, status):
    st.markdown("### 🗓 Kế hoạch Thứ 2 → Thứ 6")
    live = [x for x in items if str(x.get("status") or "") != "CANCELLED"]
    day_cols = st.columns(5, gap="small")
    labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"]

    for idx, (col, label) in enumerate(zip(day_cols, labels)):
        d = ws + timedelta(days=idx)
        day_items = [x for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()]
        day_items.sort(key=lambda x: (
            policy.PRIORITY_ORDER.index(int(x.get("priority_quadrant") or 4))
            if int(x.get("priority_quadrant") or 4) in policy.PRIORITY_ORDER else 9,
            int(x.get("id") or 0),
        ))
        with col:
            st.markdown(
                f"<div class='wkday-head'><b>{label}</b><span>{d:%d/%m}</span><em>{len(day_items)} việc</em></div>",
                unsafe_allow_html=True,
            )
            if not day_items:
                st.caption("Chưa có công việc")
            for x in day_items:
                iid = int(x.get("id") or 0)
                q = int(x.get("priority_quadrant") or 4)
                heat = _HEAT.get(q, _HEAT[4])
                title = html.escape(str(x.get("title") or "Công việc"))
                customer = html.escape(str(x.get("customer_text") or "Không gắn KH"))
                due = html.escape(_dmy(x.get("expected_complete_date")))
                focus = html.escape(str(x.get("focus_name_snapshot") or ""))
                emergent = " · ⚡ Phát sinh" if int(x.get("is_emergent") or 0) else ""
                with st.container(key=f"wkday_card_{iid}", border=True):
                    st.markdown(
                        f"<div class='wkday-title'>{title}</div>"
                        f"<div class='wkday-customer'>{customer}</div>"
                        f"<div class='wkday-meta' style='color:{heat['accent']}'>{heat['label']}{emergent}</div>"
                        f"<div class='wkday-due'>🎯 Hạn: {due}</div>"
                        + (f"<div class='wkday-focus'>📌 {focus}</div>" if focus else ""),
                        unsafe_allow_html=True,
                    )
                    if status in ("NHAP", "TRA_LAI") and not int(x.get("is_emergent") or 0):
                        if st.button("🗑 Bỏ", key=f"wkday_remove_{iid}", use_container_width=True):
                            with get_conn() as c:
                                c.execute(
                                    "UPDATE weekly_plan_items SET status='CANCELLED',updated_at=? WHERE id=? AND user_id=?",
                                    (policy._now(), iid, int(uid)),
                                )
                                c.execute(
                                    "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'DRAFT_REMOVE','Bỏ khỏi bản nháp',?)",
                                    (iid, int(uid), policy._now()),
                                )
                            st.rerun()
                    st.markdown(
                        f"<style>div[class*='st-key-wkday_card_{iid}']{{border-left:5px solid {heat['accent']}!important;background:{heat['bg']}!important}}"
                        ".wkday-title{font-weight:950;font-size:.88rem;line-height:1.25}.wkday-customer{font-size:.75rem;opacity:.82;margin-top:3px}"
                        ".wkday-meta{font-size:.73rem;font-weight:900;margin-top:6px}.wkday-due,.wkday-focus{font-size:.72rem;margin-top:5px}</style>",
                        unsafe_allow_html=True,
                    )

    weekend = [x for x in live if str(x.get("work_date") or "")[:10] in {
        (ws + timedelta(days=5)).isoformat(), (ws + timedelta(days=6)).isoformat()
    }]
    if weekend:
        with st.expander(f"Ngoài khung Thứ 2–Thứ 6 · {len(weekend)} việc", expanded=False):
            for x in weekend:
                st.write(f"• {_dmy(x.get('work_date'))} · {x.get('title')}")

    st.markdown(
        """<style>
        .wkday-head{display:flex;flex-direction:column;gap:2px;padding:9px 10px;margin-bottom:8px;border-radius:12px;
          background:linear-gradient(135deg,#075C57,#0F746B);border:1px solid #F4B41A;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,.12)}
        .wkday-head b{font-size:.96rem}.wkday-head span{font-size:.78rem;opacity:.9}.wkday-head em{font-size:.70rem;opacity:.82;font-style:normal}
        @media(max-width:900px){.wkday-head{margin-top:5px}}
        </style>""",
        unsafe_allow_html=True,
    )


class _StProxy:
    def __init__(self, st):
        self._st = st
    def __getattr__(self, name):
        return getattr(self._st, name)
    def button(self, label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        if _SUPPRESS_ITEMS.get() and key.startswith("draft_del_"):
            return False
        return self._st.button(label, *args, **kwargs)


def _customer_create_form(policy, st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
    prospects = refinement.prospects
    worktype.ensure_worktype_scope(get_conn, logger)
    worktype.ensure_case_contacts(get_conn, logger)
    v3._ensure_controller_schema(get_conn, customer_core, logger)
    prospects.ensure_customer_master(get_conn, logger)
    _ensure_case_focus_schema(get_conn)

    uid = int(v3._uget(u, "id") or 0)
    manager = customer_ui._manager(u)
    epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)
    invalid_state = f"cwuv3_invalid_{epoch}"
    finalux._render_validation(st, invalid_state)

    prospects.render_quick_add(st, u, get_conn, f"cw_new_customer_{epoch}", logger, select_state_key="cw_customer_pick")

    with get_conn() as c:
        customers = prospects.planning_customers(c, uid)
        stages = customer_core.active_stages(c)
        users = customer_core.staff_users(c) if manager else []
        types = worktype.planning_task_types(c)
        leaders = v3._leader_users(c)
        focus_rows = _focus_rows(policy, c, uid)

    if not customers:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error("Chưa có Loại công việc thuộc Kế hoạch. Admin hãy tạo tại Quản trị hệ thống → Loại công việc.")
        return
    if not leaders:
        st.error("Chưa có Lãnh đạo phòng đang hoạt động để chọn Lãnh đạo kiểm soát.")
        return

    p = f"cwuv3_{epoch}_"
    with st.form(f"cwuv3_create_{epoch}", clear_on_submit=False):
        customer = st.selectbox("Khách hàng *", customers, index=None, placeholder="— Chọn khách hàng —", format_func=prospects._label, key=p+"customer")
        case_type = st.selectbox("Nhóm công việc / Loại công việc *", types, index=None, placeholder="— Chọn loại công việc —", format_func=lambda x:x["name"], key=p+"type")
        title = st.text_input("Công việc *", value="", placeholder="Ví dụ: Cấp hạn mức tín dụng / Tiếp thị tiền gửi / Dự án A", key=p+"title")
        st.markdown("**Thông tin liên hệ bắt buộc**")
        c0,c1,c2 = st.columns([1.35,1,1.15])
        contact_name = c0.text_input("Người liên hệ *", value="", key=p+"contact_name")
        contact_phone = c1.text_input("SĐT liên hệ *", value="", key=p+"contact_phone")
        contact_role = c2.selectbox("Chức vụ *", v2.CONTACT_ROLES, index=None, placeholder="— Chọn chức vụ —", key=p+"contact_role")

        focus_options = list(focus_rows) + ["NONE"]
        focus_choice = st.selectbox(
            "Công việc ưu tiên *", focus_options, index=None, placeholder="— Chọn công việc trọng tâm —",
            format_func=lambda x: "Không thuộc công việc trọng tâm" if x == "NONE" else f"{x.get('code')} · {x.get('name')}",
            key=p+"priority", help="Danh sách lấy trực tiếp từ Danh mục công việc trọng tâm của phòng. Chọn một mục sẽ tự phân loại Q2 · Trọng tâm.",
        )
        due_date = st.date_input("Dự kiến hoàn thành *", value=None, format="DD/MM/YYYY", key=p+"due_date")
        stage = st.selectbox("Mục công việc bắt đầu *", stages, index=None, placeholder="— Chọn mục công việc —", format_func=lambda x:x["name"], key=p+"stage")

        if manager:
            owner = st.selectbox("Cán bộ phụ trách *", users, index=None, placeholder="— Chọn cán bộ phụ trách —", format_func=lambda x:f"{x['full_name']} · {x['role']}", key=p+"owner")
        else:
            current_owner = {"id":uid,"full_name":str(v3._uget(u,"full_name") or v3._uget(u,"username") or f"CB {uid}"),"role":str(v3._uget(u,"role") or "")}
            owner = st.selectbox("Cán bộ phụ trách *", [current_owner], index=0, format_func=lambda x:f"{x['full_name']} · {x['role']}", key=p+"owner", disabled=True)

        controller = st.selectbox("Lãnh đạo kiểm soát *", leaders, index=None, placeholder="— Chọn lãnh đạo kiểm soát —", format_func=lambda x:x["full_name"], key=p+"controller")
        note = st.text_area("Ghi chú", value="", height=80, key=p+"note")
        ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

    if not ok:
        return
    checks = [
        ("Khách hàng", customer is None, p+"customer"), ("Loại công việc", case_type is None, p+"type"),
        ("Công việc", not str(title or "").strip(), p+"title"), ("Người liên hệ", not str(contact_name or "").strip(), p+"contact_name"),
        ("SĐT liên hệ", not str(contact_phone or "").strip(), p+"contact_phone"), ("Chức vụ", contact_role is None, p+"contact_role"),
        ("Công việc ưu tiên", focus_choice is None, p+"priority"), ("Dự kiến hoàn thành", due_date is None, p+"due_date"),
        ("Mục công việc bắt đầu", stage is None, p+"stage"), ("Cán bộ phụ trách", owner is None, p+"owner"),
        ("Lãnh đạo kiểm soát", controller is None, p+"controller"),
    ]
    missing = [a for a,b,_ in checks if b]
    missing_keys = [k for _,b,k in checks if b]
    if missing:
        finalux._fail_validation(st, invalid_state, missing, missing_keys)
        return

    finalux._clear_validation(st, invalid_state)
    focus = focus_choice if isinstance(focus_choice, dict) else None
    priority_q = 2 if focus else 4
    due = datetime.combine(due_date, time(17,0)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cid, state = customer_core.create_case(
            get_conn, uid, customer["id"], str(title).strip(), due,
            owner_uid=int(owner["id"]), case_type=case_type["name"], note=note, stage_id=stage["id"], logger=logger,
        )
        ts = customer_core.now_str()
        with get_conn() as c:
            legacy_id = int(focus.get("legacy_category_id")) if focus and focus.get("legacy_category_id") else None
            c.execute(
                """UPDATE customer_work_cases SET contact_name=?,contact_phone=?,contact_role=?,controller_user_id=?,
                   important_category_id=?,is_important=?,focus_category_id=?,focus_code_snapshot=?,focus_name_snapshot=?,updated_at=? WHERE id=?""",
                (str(contact_name).strip(), str(contact_phone).strip(), str(contact_role), int(controller["id"]),
                 legacy_id, 1 if focus else 0, int(focus["id"]) if focus else None,
                 str(focus.get("code") or "") if focus else None, str(focus.get("name") or "") if focus else None, ts, int(cid)),
            )
            v2._set_case_priority(c, cid, priority_q, ts)
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (int(cid), uid, "CREATE_METADATA_FOCUS_UX", json.dumps({
                    "focus_category_id": int(focus["id"]) if focus else None,
                    "focus_code": str(focus.get("code") or "") if focus else None,
                    "priority_quadrant": priority_q, "owner_user_id": int(owner["id"]),
                    "controller_user_id": int(controller["id"]), "due_date_only": True,
                }, ensure_ascii=False), ts),
            )
        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        st.session_state.pop("cw_case_id", None)
        st.session_state["cw_view"] = "processing"
        st.toast("Đã tạo công việc." if state == "APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.", icon="✅")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def install(policy, customer_core, customer_ui, refinement, worktype, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    original_summary = policy._summary
    original_item_card = policy._item_card
    original_staff = policy._render_staff_week
    original_card = v3._card

    def summary(st, items):
        result = original_summary(st, items)
        ctx = _BOARD_CTX.get()
        if ctx:
            _render_week_board(ctx["st"], policy, ctx["get_conn"], ctx["uid"], ctx["ws"], items, ctx["status"])
        return result

    def item_card(st, x, editable=False):
        if _SUPPRESS_ITEMS.get():
            return False
        return original_item_card(st, x, editable)

    def render_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows, logger=None, logger_arg=None, **kwargs):
        uid = int(policy._uget(u, "id"))
        status = str(plan.get("workflow_status") or "NHAP")
        board_token = _BOARD_CTX.set({"st":st,"get_conn":get_conn,"uid":uid,"ws":ws,"status":status})
        suppress_token = _SUPPRESS_ITEMS.set(True)
        try:
            return original_staff(_StProxy(st), u, core, get_conn, ws, plan, items, focus_rows, logger=logger or logger_arg)
        finally:
            _SUPPRESS_ITEMS.reset(suppress_token)
            _BOARD_CTX.reset(board_token)

    def create_form(st, u, get_conn, core, ui, refinement_arg, worktype_arg, logger=None):
        return _customer_create_form(policy, st, u, get_conn, core, ui, refinement_arg, worktype_arg, logger)

    def card(st, ui, refinement_arg, x, get_conn, uid, manager, logger=None, compact=False):
        # Attention/backlog cards must keep the same quick-detail action as regular cards.
        return original_card(st, ui, refinement_arg, x, get_conn, uid, manager, logger, compact=False)

    policy._summary = summary
    policy._item_card = item_card
    policy._render_staff_week = render_staff_week
    v3._create_form = create_form
    v2._create_form = create_form
    v3._card = card
    v2._card = card

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info("PLANNING_WEEK_BOARD_FOCUS_INSTALLED version=%s mon_fri=1 focus_customer=1 self_owner=1 attention_detail=1", VERSION)
