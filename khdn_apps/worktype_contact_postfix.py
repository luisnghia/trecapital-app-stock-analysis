"""State-safe final Customer Work create form.

Replaces only the create helper from worktype_contact_card_patch.  A new form
identity (epoch) is used after success; existing widget keys are intentionally
left untouched in the completed run, avoiding Streamlit's widget-state mutation
error while guaranteeing a blank form on the next create operation.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json

from khdn_apps import worktype_contact_card_patch as base

VERSION = "1.0.0"


def install(customer_core, customer_ui, refinement, logger=None):
    def create_form(st, u, get_conn, customer_core_arg, ui, logger_arg=None):
        log = logger_arg or logger
        prospects = refinement.prospects
        base.ensure_worktype_scope(get_conn, log)
        base.ensure_case_contacts(get_conn, log)
        prospects.ensure_customer_master(get_conn, log)
        prospects.render_quick_add(st, u, get_conn, "cw_new_customer", log, select_state_key="cw_customer_pick")

        uid = int(u["id"])
        manager = ui._manager(u)
        with get_conn() as c:
            cs = prospects.planning_customers(c, uid)
            stages = customer_core_arg.active_stages(c)
            users = customer_core_arg.staff_users(c) if manager else []
            types = base.planning_task_types(c)
        if not cs:
            st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
            return
        if not types:
            st.error("Chưa có Loại công việc thuộc **Kế hoạch**. Hãy tạo tại Tác nghiệp → Quản trị → Loại công việc và chọn phân hệ **Kế hoạch**.")
            return

        st.caption(f"Nhóm công việc chỉ lấy danh mục **Loại công việc · Kế hoạch** · {len(types)} loại đang sử dụng.")
        preferred = st.session_state.get("cw_customer_pick")
        idx = next((i for i,x in enumerate(cs) if int(x["id"]) == int(preferred or -1)), 0)
        epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)
        p = f"cwcf_{epoch}_"

        with st.form(f"cw_create_case_{epoch}", clear_on_submit=False):
            customer = st.selectbox("Khách hàng", cs, index=idx, format_func=prospects._label, key=p+"customer")
            case_type = st.selectbox("Nhóm công việc / Loại công việc", types, format_func=lambda x:x["name"], key=p+"type")
            title = st.text_input("Công việc", placeholder="Ví dụ: Hạn mức tín dụng 2026 / Tiếp thị tiền gửi / Dự án A", key=p+"title")
            st.markdown("**Thông tin liên hệ bắt buộc**")
            c0,c1,c2 = st.columns([1.35,1,1.15])
            contact_name = c0.text_input("Người liên hệ *", key=p+"contact_name")
            contact_phone = c1.text_input("SĐT liên hệ *", key=p+"contact_phone")
            contact_role = c2.selectbox("Chức vụ *", base.CONTACT_ROLES, key=p+"contact_role")
            c3,c4 = st.columns(2)
            due_date = c3.date_input("Dự kiến hoàn thành", value=date.today()+timedelta(days=7), key=p+"due_date")
            due_time = c4.time_input("Giờ dự kiến", value=time(17,0), key=p+"due_time")
            stage = st.selectbox("Mục công việc bắt đầu", stages, format_func=lambda x:x["name"], key=p+"stage")
            owner = st.selectbox("Cán bộ phụ trách", users, format_func=lambda x:f"{x['full_name']} · {x['role']}", key=p+"owner") if manager else None
            note = st.text_area("Ghi chú", height=80, key=p+"note")
            ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

        if not ok:
            return
        contact_name = str(contact_name or "").strip()
        contact_phone = str(contact_phone or "").strip()
        if not contact_name:
            st.error("Người liên hệ là thông tin bắt buộc."); return
        if not contact_phone:
            st.error("SĐT liên hệ là thông tin bắt buộc."); return
        try:
            due = datetime.combine(due_date,due_time).strftime("%Y-%m-%d %H:%M:%S")
            cid,state = customer_core_arg.create_case(
                get_conn,uid,customer["id"],title,due,
                owner_uid=owner["id"] if owner else uid,
                case_type=case_type["name"],note=note,stage_id=stage["id"],logger=log,
            )
            ts = customer_core_arg.now_str()
            with get_conn() as c:
                c.execute("UPDATE customer_work_cases SET contact_name=?,contact_phone=?,contact_role=?,updated_at=? WHERE id=?",
                          (contact_name,contact_phone,str(contact_role),ts,int(cid)))
                c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                          (int(cid),uid,"CONTACT_SET",json.dumps({"name":contact_name,"phone":contact_phone,"role":contact_role},ensure_ascii=False),ts))

            # Do NOT mutate already-instantiated widget keys in this run.  The
            # next form uses a new key namespace and is therefore completely blank.
            st.session_state["cw_create_epoch"] = epoch + 1
            st.session_state.pop("cw_customer_pick", None)
            st.session_state["cw_case_id"] = int(cid)
            st.toast("Đã tạo công việc." if state=="APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.",icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    refinement._create_form = create_form
    if logger:
        logger.info("WORKTYPE_CONTACT_POSTFIX_INSTALLED version=%s", VERSION)
