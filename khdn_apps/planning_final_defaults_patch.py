"""Final planning defaults/card patch.

User-facing guarantees:
- all create-form inputs start blank (editing existing data is unaffected);
- "Không thuộc mục trọng tâm nào" is the last real Q2-catalog option;
- Weekly Plan cards visually match Customer Work cards;
- new weekly items snapshot owner/controller names for readable cards.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import html
import json

from khdn_apps import customer_work_refinement_patch as cwref
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3
from khdn_apps import weekly_plan_form_refinement_patch as wref

VERSION = "1.0.0"
_FLAG = "_PLANNING_FINAL_DEFAULTS_PATCH_VERSION"


def _dt_text(value):
    if not value:
        return "—"
    s = str(value).strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.strftime("%d/%m/%Y %H:%M")
    except Exception:
        try:
            d = date.fromisoformat(s[:10])
            return d.strftime("%d/%m/%Y")
        except Exception:
            return s


def _focus_picker(st, policy, focus_rows, prefix, due_date):
    # Blank placeholder first; real focus categories next; explicit "not focus" last.
    options = list(focus_rows or []) + ["NONE"]

    def _fmt(x):
        if x == "NONE":
            return "Không thuộc mục trọng tâm nào"
        return f"{x.get('code')} · {x.get('name')}"

    choice = st.selectbox(
        "1. Việc này thuộc danh mục công việc trọng tâm nào của phòng? *",
        options,
        index=None,
        placeholder="— Chọn —",
        format_func=_fmt,
        key=f"{prefix}_focus",
        help="Danh sách lấy từ Danh mục công việc trọng tâm/quan trọng của phòng đang áp dụng trong năm.",
    )
    if isinstance(choice, dict):
        st.success("→ Tự động phân loại: Q2 · Trọng tâm.")
        return choice, None, None, 2
    if choice is None:
        return None, None, None, None
    if due_date is None:
        st.info("Hãy chọn Ngày dự kiến hoàn thành để hệ thống xác định Q1/Q3/Q4.")
        return None, None, None, None

    today = date.today()
    due7 = bool(due_date <= today + timedelta(days=7))
    if not due7:
        st.info("Ngày dự kiến hoàn thành ngoài 7 ngày tới → Q4 · Giá trị thấp.")
        return None, False, None, 4

    risk_choice = st.selectbox(
        "2. Việc này có gắn với chỉ tiêu được giao hoặc rủi ro trọng yếu không? *",
        [True, False],
        index=None,
        placeholder="— Chọn —",
        format_func=lambda x: "Có" if x else "Không",
        key=f"{prefix}_risk",
    )
    if risk_choice is True:
        st.error("→ Tự động phân loại: Q1 · Cấp thiết.")
        return None, True, True, 1
    if risk_choice is False:
        st.warning("→ Tự động phân loại: Q3 · Phân tâm.")
        return None, True, False, 3
    return None, True, None, None


def _weekly_item_card(policy, st, x, editable=False):
    q = int(x.get("priority_quadrant") or 4)
    heat = cwref._HEAT.get(q, cwref._HEAT[4])
    iid = int(x.get("id") or 0)
    customer = html.escape(str(x.get("customer_text") or "Không gắn khách hàng"))
    title = html.escape(str(x.get("title") or "Công việc"))
    code = f"KHT-{iid:04d}" if iid else "KHT"
    created = html.escape(_dt_text(x.get("created_at")))
    work_date = html.escape(_dt_text(str(x.get("work_date") or "")[:10]))
    due = html.escape(_dt_text(str(x.get("expected_complete_date") or "")[:10]))
    owner = html.escape(str(x.get("owner_name_snapshot") or x.get("owner_name") or "—"))
    controller = html.escape(str(x.get("controller_name_snapshot") or x.get("controller_name") or "—"))
    focus = html.escape(str(x.get("focus_name_snapshot") or ""))
    focus_code = html.escape(str(x.get("focus_code_snapshot") or ""))
    status_map = {
        "PLANNED": "○ Kế hoạch",
        "IN_PROGRESS": "▶ Đang thực hiện",
        "DONE": "✓ Hoàn thành",
        "CANCELLED": "× Đã hủy",
    }
    status = html.escape(status_map.get(str(x.get("status") or "PLANNED"), str(x.get("status") or "")))
    emergent = bool(int(x.get("is_emergent") or 0))
    carry = int(x.get("carryover_count") or 0)
    watch = bool(int(x.get("q2_watch_flag") or 0))
    priority = html.escape(str(policy.PRIORITY.get(q, q)))

    with st.container(key=f"wpfinal_card_{iid}", border=True):
        c1, c2, c3 = st.columns([5.8, 1.6, 2.6], vertical_alignment="top")
        with c1:
            st.markdown(
                f"<div class='wpf-title'>{customer} <span>·</span> Kế hoạch tuần</div>"
                f"<div class='wpf-work'>📌 {title}</div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"<div class='wpf-code'>{code}</div>", unsafe_allow_html=True)
        edited = False
        with c3:
            if editable:
                edited = st.button("✏️ Sửa", key=f"policy_edit_{iid}", use_container_width=True)

        badges = []
        if emergent:
            badges.append("⚡ Phát sinh")
        if carry:
            badges.append(f"↪ Chuyển tiếp {carry} lần")
        if watch:
            badges.append("🚩 Q2 lùi ≥2 tuần")
        badge_html = "".join(f"<span class='wpf-soft'>{html.escape(b)}</span>" for b in badges)

        st.markdown(
            f"<div class='wpf-row'><span>🕒 <b>Tạo lúc:</b> {created}</span>"
            f"<span>👤 <b>Phụ trách:</b> {owner}</span>"
            f"<span>🛡️ <b>Kiểm soát:</b> {controller}</span></div>"
            f"<div class='wpf-row'><span>🗓 <b>Thực hiện:</b> {work_date}</span>"
            f"<span>🎯 <b>Dự kiến hoàn thành:</b> {due}</span>"
            f"<span class='wpf-soft'>{status}</span></div>"
            f"<div class='wpf-row'>{badge_html}"
            f"<span class='wpf-pill' style='color:{heat['accent']};background:{heat['bg']};border:1px solid {heat['border']}'>{heat['icon']} {priority}</span></div>"
            + (f"<div class='wpf-focus'>🎯 <b>Trọng tâm:</b> {focus_code} · {focus}</div>" if focus else "")
            + f"""
            <style>
            div[class*='st-key-wpfinal_card_{iid}']{{
                border-left:6px solid {heat['accent']}!important;
                background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;
                box-shadow:0 6px 16px rgba(0,0,0,.09)
            }}
            div[class*='st-key-wpfinal_card_{iid}'] button{{
                background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
                color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
                border:2px solid #FFE589!important;font-weight:950!important;min-height:2.25rem!important
            }}
            div[class*='st-key-wpfinal_card_{iid}'] button *{{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important}}
            .wpf-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}
            .wpf-title span{{opacity:.7}} .wpf-work{{font-size:.82rem;font-weight:750;margin-top:3px}}
            .wpf-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .wpf-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px}}
            .wpf-pill,.wpf-soft{{padding:2px 7px;border-radius:999px;font-weight:900}}
            .wpf-soft{{background:rgba(99,220,203,.10);border:1px solid rgba(99,220,203,.25)}}
            .wpf-focus{{font-size:.80rem;margin-top:7px;opacity:.94}}
            @media(max-width:760px){{.wpf-title{{font-size:.96rem}}.wpf-row,.wpf-focus{{font-size:.76rem}}.wpf-code{{text-align:left}}}}
            </style>""",
            unsafe_allow_html=True,
        )
        return edited


def _weekly_add_form(policy, st, u, core, conn_fn, ws, focus_rows, emergent=False,
                     logger=None, logger_arg=None, **kwargs):
    uid = int(policy._uget(u, "id"))
    active_logger = logger or logger_arg
    epoch_key = f"wp_refine_epoch_{ws.isoformat()}_{'ps' if emergent else 'plan'}"
    epoch = int(st.session_state.get(epoch_key, 0) or 0)
    prefix = f"wp_refined_{ws.isoformat()}_{'ps' if emergent else 'plan'}_{epoch}"
    st.markdown("#### ⚡ Công việc phát sinh" if emergent else "#### ＋ Thêm công việc kế hoạch")

    with conn_fn() as c:
        customers = core.customers(c, uid)
        leaders = wref._leader_rows(c)

    customer_options = list(customers) + ["NO_CUSTOMER"]
    customer_choice = st.selectbox(
        "Khách hàng *",
        customer_options,
        index=None,
        placeholder="— Chọn khách hàng —",
        format_func=lambda x: (
            "Không gắn khách hàng"
            if x == "NO_CUSTOMER"
            else f"{x.get('customer_name')} · {'CIF '+str(x.get('cif')) if x.get('cif') else 'Chưa có CIF'}"
        ),
        key=f"{prefix}_customer",
    )
    customer = customer_choice if isinstance(customer_choice, dict) else None

    cases = []
    if customer:
        with conn_fn() as c:
            cases = wref._case_rows(c, int(customer["id"]), uid, policy._manager(u))

    linked_case = None
    if cases:
        linked_case = st.selectbox(
            "Công việc *",
            cases,
            index=None,
            placeholder="— Chọn công việc đang xử lý —",
            format_func=lambda x: " · ".join(
                p for p in [str(x.get("case_code") or ""), str(x.get("title") or ""), str(x.get("stage_name") or "")] if p
            ),
            key=f"{prefix}_case",
            help="Danh sách chỉ gồm công việc khách hàng đang còn dang dở; nếu khách hàng chưa có công việc thì nhập mới.",
        )
        title = str(linked_case.get("title") or "").strip() if linked_case else ""
        if linked_case:
            st.caption(f"Đã liên kết {linked_case.get('case_code') or 'CVKH'} · {linked_case.get('stage_name') or 'Đang xử lý'}")
    else:
        title = st.text_input(
            "Công việc *",
            value="",
            key=f"{prefix}_title",
            placeholder="Ví dụ: Gặp Công ty A – tiếp thị tiền gửi",
        )
        if customer:
            st.caption("Khách hàng chưa có công việc đang xử lý; nhập công việc mới cho kế hoạch tuần.")

    day = st.date_input(
        "Ngày thực hiện *",
        value=None,
        min_value=ws,
        max_value=ws + timedelta(days=6),
        key=f"{prefix}_day",
    )
    due = st.date_input(
        "Ngày dự kiến hoàn thành *",
        value=None,
        min_value=day or ws,
        key=f"{prefix}_due",
    )
    leader = st.selectbox(
        "Lãnh đạo phòng phụ trách *",
        leaders,
        index=None,
        placeholder="— Chọn lãnh đạo phụ trách —",
        format_func=lambda x: str(x.get("full_name") or ""),
        key=f"{prefix}_leader",
    )

    with conn_fn() as c:
        scope = policy._scope_key(c, uid)
        live_focus_rows = policy._focus_categories(c, scope, ws.year, False)
    focus, due7, risk, q = _focus_picker(st, policy, live_focus_rows, prefix, due)

    ok = st.button(
        "Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch",
        key=f"{prefix}_save",
        type="primary",
        use_container_width=True,
    )
    if not ok:
        return

    missing = []
    if customer_choice is None:
        missing.append("Khách hàng/Không gắn khách hàng")
    if not str(title or "").strip():
        missing.append("Công việc")
    if day is None:
        missing.append("Ngày thực hiện")
    if due is None:
        missing.append("Ngày dự kiến hoàn thành")
    if day is not None and due is not None and due < day:
        missing.append("Ngày dự kiến hoàn thành")
    if not leader:
        missing.append("Lãnh đạo phòng phụ trách")
    if q is None:
        missing.append("Căn cứ phân loại Q1–Q4")
    if cases and not linked_case:
        missing.append("Công việc đang xử lý")
    if missing:
        st.error("Vui lòng nhập/chọn đầy đủ: " + ", ".join(missing) + ".")
        return

    linked_case_id = int(linked_case["id"]) if linked_case else None
    if linked_case_id:
        with conn_fn() as c:
            duplicate = c.execute(
                """SELECT 1 FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id
                   WHERE p.user_id=? AND p.week_start=? AND w.linked_case_id=? AND w.status<>'CANCELLED' LIMIT 1""",
                (uid, ws.isoformat(), linked_case_id),
            ).fetchone()
        if duplicate:
            st.error("Công việc khách hàng này đã có trong kế hoạch tuần, không tạo trùng.")
            return

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
        return
    owner_name = str(policy._uget(u, "full_name") or policy._uget(u, "username") or f"CB {uid}")
    with conn_fn() as c:
        c.execute(
            """UPDATE weekly_plan_items
               SET expected_complete_date=?,controller_user_id=?,linked_case_id=?,expected_output='',
                   owner_name_snapshot=?,controller_name_snapshot=?
               WHERE id=?""",
            (
                due.isoformat(),
                int(leader["id"]),
                linked_case_id,
                owner_name,
                str(leader.get("full_name") or ""),
                int(iid),
            ),
        )
    st.session_state[epoch_key] = epoch + 1
    st.toast("Đã thêm công việc vào kế hoạch.", icon="✅")
    st.rerun()


def _customer_create_form(st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
    prospects = refinement.prospects
    worktype.ensure_worktype_scope(get_conn, logger)
    worktype.ensure_case_contacts(get_conn, logger)
    v3._ensure_controller_schema(get_conn, customer_core, logger)
    prospects.ensure_customer_master(get_conn, logger)

    uid = int(v3._uget(u, "id") or 0)
    manager = customer_ui._manager(u)
    epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)
    prospects.render_quick_add(
        st, u, get_conn, f"cw_new_customer_{epoch}", logger,
        select_state_key="cw_customer_pick",
    )

    with get_conn() as c:
        customers = prospects.planning_customers(c, uid)
        stages = customer_core.active_stages(c)
        users = customer_core.staff_users(c) if manager else []
        types = worktype.planning_task_types(c)
        leaders = v3._leader_users(c)

    if not customers:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error("Chưa có Loại công việc thuộc **Kế hoạch**. Admin hãy tạo tại **Quản trị hệ thống → Loại công việc**.")
        return
    if not leaders:
        st.error("Chưa có **Lãnh đạo phòng** đang hoạt động để chọn Lãnh đạo kiểm soát.")
        return

    st.caption(
        f"Nhóm công việc lấy từ **Quản trị hệ thống → Loại công việc → Kế hoạch** · {len(types)} loại đang sử dụng."
    )
    preferred = st.session_state.get("cw_customer_pick")
    preferred_index = next((i for i, x in enumerate(customers) if int(x["id"]) == int(preferred or -1)), None)
    p = f"cwuv3_{epoch}_"
    invalid_keys = st.session_state.get(f"cwuv3_invalid_{epoch}") or []
    v3._missing_css(st, invalid_keys)

    with st.form(f"cwuv3_create_{epoch}", clear_on_submit=False):
        customer = st.selectbox(
            "Khách hàng *", customers,
            index=preferred_index,
            placeholder="— Chọn khách hàng —",
            format_func=prospects._label,
            key=p + "customer",
        )
        case_type = st.selectbox(
            "Nhóm công việc / Loại công việc *", types,
            index=None, placeholder="— Chọn loại công việc —",
            format_func=lambda x: x["name"], key=p + "type",
        )
        title = st.text_input(
            "Công việc *", value="",
            placeholder="Ví dụ: Cấp hạn mức tín dụng / Tiếp thị tiền gửi / Dự án A",
            key=p + "title",
        )
        st.markdown("**Thông tin liên hệ bắt buộc**")
        c0, c1, c2 = st.columns([1.35, 1, 1.15])
        contact_name = c0.text_input("Người liên hệ *", value="", key=p + "contact_name")
        contact_phone = c1.text_input("SĐT liên hệ *", value="", key=p + "contact_phone")
        contact_role = c2.selectbox(
            "Chức vụ *", v2.CONTACT_ROLES,
            index=None, placeholder="— Chọn chức vụ —", key=p + "contact_role",
        )
        priority = st.selectbox(
            "Ưu tiên góc phần tư *", [1, 2, 3, 4],
            index=None, placeholder="— Chọn Q1 / Q2 / Q3 / Q4 —",
            format_func=v2._priority_label, key=p + "priority",
        )
        c3, c4 = st.columns(2)
        due_date = c3.date_input("Dự kiến hoàn thành *", value=None, key=p + "due_date")
        due_time = c4.time_input("Giờ dự kiến *", value=None, key=p + "due_time")
        stage = st.selectbox(
            "Mục công việc bắt đầu *", stages,
            index=None, placeholder="— Chọn mục công việc —",
            format_func=lambda x: x["name"], key=p + "stage",
        )

        if manager:
            owner = st.selectbox(
                "Cán bộ phụ trách *", users,
                index=None, placeholder="— Chọn cán bộ phụ trách —",
                format_func=lambda x: f"{x['full_name']} · {x['role']}", key=p + "owner",
            )
        else:
            current_owner = {
                "id": uid,
                "full_name": str(v3._uget(u, "full_name") or v3._uget(u, "username") or f"CB {uid}"),
                "role": str(v3._uget(u, "role") or ""),
            }
            owner = st.selectbox(
                "Cán bộ phụ trách *", [current_owner],
                index=None, placeholder="— Chọn cán bộ phụ trách —",
                format_func=lambda x: f"{x['full_name']} · {x['role']}", key=p + "owner",
            )
        controller = st.selectbox(
            "Lãnh đạo kiểm soát *", leaders,
            index=None, placeholder="— Chọn lãnh đạo kiểm soát —",
            format_func=lambda x: x["full_name"], key=p + "controller",
        )
        note = st.text_area("Ghi chú", value="", height=80, key=p + "note")
        ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

    if not ok:
        return
    checks = [
        ("Khách hàng", customer is None, p + "customer"),
        ("Loại công việc", case_type is None, p + "type"),
        ("Công việc", not str(title or "").strip(), p + "title"),
        ("Người liên hệ", not str(contact_name or "").strip(), p + "contact_name"),
        ("SĐT liên hệ", not str(contact_phone or "").strip(), p + "contact_phone"),
        ("Chức vụ", contact_role is None, p + "contact_role"),
        ("Ưu tiên góc phần tư", priority is None, p + "priority"),
        ("Dự kiến hoàn thành", due_date is None, p + "due_date"),
        ("Giờ dự kiến", due_time is None, p + "due_time"),
        ("Mục công việc bắt đầu", stage is None, p + "stage"),
        ("Cán bộ phụ trách", owner is None, p + "owner"),
        ("Lãnh đạo kiểm soát", controller is None, p + "controller"),
    ]
    missing = [label for label, failed, _ in checks if failed]
    missing_keys = [key for _, failed, key in checks if failed]
    if missing:
        st.session_state[f"cwuv3_invalid_{epoch}"] = missing_keys
        v3._missing_css(st, missing_keys)
        st.error("Vui lòng nhập/chọn đầy đủ các ô viền đỏ: " + ", ".join(missing) + ".")
        return
    st.session_state.pop(f"cwuv3_invalid_{epoch}", None)

    try:
        due = datetime.combine(due_date, due_time).strftime("%Y-%m-%d %H:%M:%S")
        cid, state = customer_core.create_case(
            get_conn, uid, customer["id"], str(title).strip(), due,
            owner_uid=int(owner["id"]), case_type=case_type["name"], note=note,
            stage_id=stage["id"], logger=logger,
        )
        ts = customer_core.now_str()
        with get_conn() as c:
            c.execute(
                """UPDATE customer_work_cases
                   SET contact_name=?,contact_phone=?,contact_role=?,controller_user_id=?,updated_at=?
                   WHERE id=?""",
                (
                    str(contact_name).strip(), str(contact_phone).strip(), str(contact_role),
                    int(controller["id"]), ts, int(cid),
                ),
            )
            v2._set_case_priority(c, cid, int(priority), ts)
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (
                    int(cid), uid, "CREATE_METADATA_FINAL",
                    json.dumps({
                        "contact_name": str(contact_name).strip(),
                        "contact_phone": str(contact_phone).strip(),
                        "contact_role": contact_role,
                        "priority_quadrant": int(priority),
                        "owner_user_id": int(owner["id"]),
                        "controller_user_id": int(controller["id"]),
                    }, ensure_ascii=False),
                    ts,
                ),
            )
        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        st.session_state.pop("cw_case_id", None)
        st.session_state["cw_view"] = "processing"
        st.toast("Đã tạo công việc." if state == "APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.", icon="✅")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def install(policy, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    # Preserve existing schema, then add readable card snapshots for new weekly items.
    original_ensure = policy._ensure_schema

    def ensure_schema(core, get_conn, logger_arg=None):
        original_ensure(core, get_conn, logger_arg or logger)
        with get_conn() as c:
            cols = policy._cols(c, "weekly_plan_items")
            if "owner_name_snapshot" not in cols:
                c.execute("ALTER TABLE weekly_plan_items ADD COLUMN owner_name_snapshot TEXT")
            if "controller_name_snapshot" not in cols:
                c.execute("ALTER TABLE weekly_plan_items ADD COLUMN controller_name_snapshot TEXT")

    policy._ensure_schema = ensure_schema

    # Weekly Plan: real focus options first, explicit non-focus last, blank create fields,
    # and Customer-Work-style cards.
    wref._focus_picker = _focus_picker
    policy._add_item_form = lambda st, u, core, get_conn, ws, focus_rows, emergent=False, logger=None, logger_arg=None, **kwargs: _weekly_add_form(
        policy, st, u, core, get_conn, ws, focus_rows, emergent=emergent,
        logger=logger, logger_arg=logger_arg, **kwargs
    )
    policy._item_card = lambda st, x, editable=False: _weekly_item_card(policy, st, x, editable)

    # Customer Work: all create fields blank until the user deliberately selects/enters them.
    def customer_form(st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
        return _customer_create_form(st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger)

    v3._create_form = customer_form
    v2._create_form = customer_form

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info("PLANNING_FINAL_DEFAULTS_PATCH_INSTALLED version=%s blank_create=1 focus_none_last=1 weekly_card_customer_style=1", VERSION)
