"""Last-mile UX fixes for customer work and Weekly Plan.

Guarantees:
- all native date inputs use DD/MM/YYYY;
- Customer Work uses "Công việc ưu tiên", no user-entered due time;
- required fields are persisted/highlighted red after failed submit;
- Weekly Plan linked-work labels omit internal CVKH case codes;
- Customer Work cards use render-context keys to avoid duplicate Streamlit keys;
- managers can approve/reject pending Customer Work directly from attention cards.
"""
from __future__ import annotations

from datetime import datetime, time
import html
import sys
import os
import re

from khdn_apps import planning_final_defaults_patch as defaults
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3
from khdn_apps import weekly_plan_form_refinement_patch as wref

VERSION = "1.0.0"
_FLAG = "_PLANNING_FINAL_UX_PATCH_VERSION"


def _install_dmy_date_format():
    """Force DD/MM/YYYY on native Streamlit date inputs without touching stored ISO dates."""
    try:
        import streamlit as stlib
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(stlib, "_KHDN_DMY_DATE_FORMAT_INSTALLED", False):
        return

    original_module = stlib.date_input
    original_dg = DeltaGenerator.date_input

    def module_date_input(*args, **kwargs):
        kwargs.setdefault("format", "DD/MM/YYYY")
        return original_module(*args, **kwargs)

    def dg_date_input(self, *args, **kwargs):
        kwargs.setdefault("format", "DD/MM/YYYY")
        return original_dg(self, *args, **kwargs)

    stlib.date_input = module_date_input
    DeltaGenerator.date_input = dg_date_input
    stlib._KHDN_DMY_DATE_FORMAT_INSTALLED = True


def _missing_css(st, keys):
    """Highlight invalid required widgets after validation and after the rerun."""
    clean = [str(k) for k in (keys or []) if k]
    if not clean:
        return
    rules = []
    for key in clean:
        esc = key.replace("\\", "\\\\").replace('"', '\\"')
        root = f'div[class*="st-key-{esc}"]'
        rules.append(
            f"""
            {root} [data-baseweb="input"] > div,
            {root} [data-baseweb="select"] > div,
            {root} [data-testid="stDateInput"] > div,
            {root} [data-testid="stDateInput"] input,
            {root} [data-testid="stSelectbox"] [data-baseweb="select"] > div,
            {root} input,
            {root} textarea {{
                border-color:#FF4B4B!important;
                outline-color:#FF4B4B!important;
                box-shadow:0 0 0 2px rgba(255,75,75,.34)!important;
                background:rgba(255,75,75,.07)!important;
            }}
            {root} label,
            {root} label p,
            {root} [data-testid="stWidgetLabel"] p {{
                color:#FF6B6B!important;
                -webkit-text-fill-color:#FF6B6B!important;
                font-weight:950!important;
            }}
            """
        )
    st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)


def _render_validation(st, state_key):
    keys = st.session_state.get(state_key) or []
    _missing_css(st, keys)
    msg = st.session_state.get(state_key + "_message")
    if msg:
        st.error(str(msg))


def _fail_validation(st, state_key, missing, keys):
    st.session_state[state_key] = list(dict.fromkeys(k for k in keys if k))
    st.session_state[state_key + "_message"] = (
        "Vui lòng nhập/chọn đầy đủ các ô viền đỏ: " + ", ".join(missing) + "."
    )
    st.rerun()


def _clear_validation(st, state_key):
    st.session_state.pop(state_key, None)
    st.session_state.pop(state_key + "_message", None)


def _case_option_label(x):
    """Business-facing label: title + current stage, never internal case code."""
    parts = [
        str(x.get("title") or "").strip(),
        str(x.get("stage_name") or "").strip(),
    ]
    return " · ".join(p for p in parts if p) or "Công việc đang xử lý"


def _weekly_add_form(policy, st, u, core, conn_fn, ws, focus_rows, emergent=False,
                     logger=None, logger_arg=None, **kwargs):
    uid = int(policy._uget(u, "id"))
    active_logger = logger or logger_arg
    epoch_key = f"wp_refine_epoch_{ws.isoformat()}_{'ps' if emergent else 'plan'}"
    epoch = int(st.session_state.get(epoch_key, 0) or 0)
    prefix = f"wp_refined_{ws.isoformat()}_{'ps' if emergent else 'plan'}_{epoch}"
    invalid_state = f"{prefix}_invalid"
    _render_validation(st, invalid_state)

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
            format_func=_case_option_label,
            key=f"{prefix}_case",
            help="Danh sách chỉ gồm công việc khách hàng đang còn dang dở; mã nội bộ CVKH được ẩn để dễ chọn.",
        )
        title = str(linked_case.get("title") or "").strip() if linked_case else ""
        if linked_case:
            st.caption(
                "Đã liên kết: "
                + " · ".join(
                    p for p in [
                        str(linked_case.get("title") or "").strip(),
                        str(linked_case.get("stage_name") or "").strip(),
                    ] if p
                )
            )
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
        max_value=ws + defaults.timedelta(days=6),
        format="DD/MM/YYYY",
        key=f"{prefix}_day",
    )
    due = st.date_input(
        "Ngày dự kiến hoàn thành *",
        value=None,
        min_value=day or ws,
        format="DD/MM/YYYY",
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
    focus, due7, risk, q = defaults._focus_picker(st, policy, live_focus_rows, prefix, due)

    ok = st.button(
        "Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch",
        key=f"{prefix}_save",
        type="primary",
        use_container_width=True,
    )
    if not ok:
        return

    missing = []
    missing_keys = []
    if customer_choice is None:
        missing.append("Khách hàng/Không gắn khách hàng")
        missing_keys.append(f"{prefix}_customer")
    if not str(title or "").strip():
        missing.append("Công việc")
        missing_keys.append(f"{prefix}_case" if cases else f"{prefix}_title")
    if day is None:
        missing.append("Ngày thực hiện")
        missing_keys.append(f"{prefix}_day")
    if due is None:
        missing.append("Ngày dự kiến hoàn thành")
        missing_keys.append(f"{prefix}_due")
    if day is not None and due is not None and due < day:
        missing.append("Ngày dự kiến hoàn thành")
        missing_keys.append(f"{prefix}_due")
    if not leader:
        missing.append("Lãnh đạo phòng phụ trách")
        missing_keys.append(f"{prefix}_leader")
    if q is None:
        missing.append("Căn cứ phân loại Q1–Q4")
        focus_value = st.session_state.get(f"{prefix}_focus")
        if focus_value is None:
            missing_keys.append(f"{prefix}_focus")
        else:
            missing_keys.append(f"{prefix}_risk")
    if cases and not linked_case:
        if "Công việc" not in missing:
            missing.append("Công việc đang xử lý")
        missing_keys.append(f"{prefix}_case")
    if missing:
        _fail_validation(st, invalid_state, missing, missing_keys)
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
    _clear_validation(st, invalid_state)
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
    invalid_state = f"cwuv3_invalid_{epoch}"
    _render_validation(st, invalid_state)

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
    p = f"cwuv3_{epoch}_"

    with st.form(f"cwuv3_create_{epoch}", clear_on_submit=False):
        customer = st.selectbox(
            "Khách hàng *", customers,
            index=None, placeholder="— Chọn khách hàng —",
            format_func=prospects._label, key=p + "customer",
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
            "Công việc ưu tiên *", [1, 2, 3, 4],
            index=None, placeholder="— Chọn Q1 / Q2 / Q3 / Q4 —",
            format_func=v2._priority_label, key=p + "priority",
            help="Chọn mức ưu tiên Q1–Q4 cho công việc khách hàng.",
        )
        due_date = st.date_input(
            "Dự kiến hoàn thành *",
            value=None,
            format="DD/MM/YYYY",
            key=p + "due_date",
        )
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
        ("Công việc ưu tiên", priority is None, p + "priority"),
        ("Dự kiến hoàn thành", due_date is None, p + "due_date"),
        ("Mục công việc bắt đầu", stage is None, p + "stage"),
        ("Cán bộ phụ trách", owner is None, p + "owner"),
        ("Lãnh đạo kiểm soát", controller is None, p + "controller"),
    ]
    missing = [label for label, failed, _ in checks if failed]
    missing_keys = [key for _, failed, key in checks if failed]
    if missing:
        _fail_validation(st, invalid_state, missing, missing_keys)
        return

    _clear_validation(st, invalid_state)
    try:
        # Business UI is date-only; keep a deterministic end-of-day timestamp internally.
        due = datetime.combine(due_date, time(17, 0)).strftime("%Y-%m-%d %H:%M:%S")
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
                    int(cid), uid, "CREATE_METADATA_FINAL_UX",
                    defaults.json.dumps({
                        "contact_name": str(contact_name).strip(),
                        "contact_phone": str(contact_phone).strip(),
                        "contact_role": contact_role,
                        "priority_quadrant": int(priority),
                        "owner_user_id": int(owner["id"]),
                        "controller_user_id": int(controller["id"]),
                        "due_date_only": True,
                    }, ensure_ascii=False),
                    ts,
                ),
            )
        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        st.session_state.pop("cw_case_id", None)
        st.session_state["cw_view"] = "processing"
        st.toast(
            "Đã tạo công việc." if state == "APPROVED"
            else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.",
            icon="✅",
        )
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def _render_context():
    """Stable call-site token so the same case may render in multiple Today sections."""
    skip = {
        os.path.basename(__file__),
        "planning_usability_v3_patch.py",
        "planning_ui_v4_patch.py",
    }
    frame = None
    try:
        frame = sys._getframe(2)
        while frame is not None:
            name = os.path.basename(frame.f_code.co_filename)
            if name in skip:
                frame = frame.f_back
                continue
            raw = f"{name}_{frame.f_code.co_name}_{frame.f_lineno}"
            return re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    except Exception:
        pass
    finally:
        del frame
    return "default"


def _customer_card(st, customer_ui, refinement, x, get_conn, uid, manager, logger=None, compact=False):
    q = v2._q(x.get("quadrant")) or 4
    heat = refinement._HEAT[q]
    status_text, status_color, status_bg = refinement._status_meta(x)
    customer = html.escape(str(x.get("customer_name") or "—"))
    case_type = html.escape(str(x.get("case_type") or x.get("title") or "Công việc"))
    title = html.escape(str(x.get("title") or ""))
    code = html.escape(str(x.get("case_code") or ""))
    owner = html.escape(str(x.get("owner_name") or "—"))
    controller = html.escape(str(x.get("controller_name") or "—"))
    stage = html.escape(str(x.get("stage_name") or "—"))
    elapsed = html.escape(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    created = html.escape(customer_ui._dt_text(x.get("created_at")))
    due = html.escape(customer_ui._date_text(x.get("expected_complete_at")))
    issues = int(x.get("open_issue_count") or 0)
    contact = html.escape(str(x.get("contact_name") or ""))
    contact_phone = html.escape(str(x.get("contact_phone") or ""))
    contact_role = html.escape(str(x.get("contact_role") or ""))
    approval = str(x.get("plan_approval_status") or "PENDING")
    cid = int(x["id"])
    ctx = _render_context()
    card_key = f"cwux_card_{cid}_{ctx}"

    with st.container(key=card_key, border=True):
        c1, c2, c3 = st.columns([5.5, 1.5, 3.0], vertical_alignment="top")
        with c1:
            st.markdown(
                f"<div class='cwux-title'>{customer} <span>·</span> {case_type}</div>"
                + (
                    f"<div class='cwux-work'>📌 {title}</div>"
                    if title and title.casefold() != case_type.casefold()
                    else ""
                ),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"<div class='cwux-code'>{code}</div>", unsafe_allow_html=True)
        with c3:
            if not compact and st.button(
                "🔎 Chi tiết", key=f"cwux_open_{cid}_{ctx}", use_container_width=True
            ):
                st.session_state["cw_case_id"] = cid
                st.rerun()

        st.markdown(
            f"<div class='cwux-row'><span>🕒 <b>Tạo lúc:</b> {created}</span>"
            f"<span>👤 <b>Phụ trách:</b> {owner}</span>"
            f"<span>🛡️ <b>Kiểm soát:</b> {controller}</span></div>"
            f"<div class='cwux-row'><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span>"
            f"<span class='cwux-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>"
            f"<div class='cwux-row'><span>🎯 <b>Dự kiến:</b> {due}</span>"
            f"<span>⚠ <b>Vướng mắc:</b> {issues}</span>"
            f"<span class='cwux-pill' style='color:{heat['accent']};background:{heat['bg']};"
            f"border:1px solid {heat['border']}'>{v2._priority_label(q)}</span></div>"
            + (
                f"<div class='cwux-contact'>☎ <b>{contact}</b> · {contact_role} · {contact_phone}</div>"
                if contact or contact_phone else ""
            )
            + f"""
            <style>
            div[class*='st-key-{card_key}']{{
                border-left:6px solid {heat['accent']}!important;
                background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;
                box-shadow:0 6px 16px rgba(0,0,0,.09)
            }}
            div[class*='st-key-cwux_open_{cid}_{ctx}'] button{{
                background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
                color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
                border:2px solid #FFE589!important;font-weight:950!important;
            }}
            .cwux-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}
            .cwux-title span{{opacity:.7}}
            .cwux-work{{font-size:.82rem;font-weight:750;margin-top:3px}}
            .cwux-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .cwux-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px}}
            .cwux-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}
            .cwux-contact{{font-size:.80rem;margin-top:7px;opacity:.94}}
            @media(max-width:760px){{
                .cwux-title{{font-size:.96rem}} .cwux-row,.cwux-contact{{font-size:.76rem}}
                .cwux-code{{text-align:left}}
            }}
            </style>""",
            unsafe_allow_html=True,
        )

        if approval == "PENDING":
            st.warning("Kế hoạch công việc đang chờ phê duyệt.")
            if manager:
                approve_col, reject_col = st.columns(2)
                if approve_col.button(
                    "✅ Phê duyệt",
                    key=f"cwux_approve_{cid}_{ctx}",
                    type="primary",
                    use_container_width=True,
                ):
                    customer_ui.core.approve_case_plan(
                        get_conn, cid, int(uid), approve=True, note=None, logger=logger
                    )
                    st.toast("Đã phê duyệt công việc.", icon="✅")
                    st.rerun()
                if reject_col.button(
                    "↩ Từ chối",
                    key=f"cwux_reject_{cid}_{ctx}",
                    use_container_width=True,
                ):
                    customer_ui.core.approve_case_plan(
                        get_conn, cid, int(uid), approve=False, note=None, logger=logger
                    )
                    st.toast("Đã từ chối công việc.", icon="↩")
                    st.rerun()
        elif approval == "REJECTED":
            st.error(
                "Kế hoạch đã bị từ chối."
                + (f" {x.get('approval_note')}" if x.get("approval_note") else "")
            )
    return None


def install(policy, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    _install_dmy_date_format()
    v3._missing_css = _missing_css

    policy._add_item_form = (
        lambda st, u, core, get_conn, ws, focus_rows, emergent=False,
               logger=None, logger_arg=None, **kwargs:
        _weekly_add_form(
            policy, st, u, core, get_conn, ws, focus_rows,
            emergent=emergent, logger=logger, logger_arg=logger_arg, **kwargs
        )
    )

    v3._create_form = _customer_create_form
    v2._create_form = _customer_create_form
    v3._card = _customer_card
    v2._card = _customer_card

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_FINAL_UX_PATCH_INSTALLED version=%s date_dmy=1 no_due_time=1 red_validation=1 no_case_code=1 unique_cards=1 inline_approval=1",
            VERSION,
        )
