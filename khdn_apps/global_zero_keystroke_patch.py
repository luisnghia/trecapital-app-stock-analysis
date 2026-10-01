"""Final rerun-safe zero-keystroke input layer for KHDN Apps.

Why this exists
---------------
Several older installers intentionally run on every Streamlit script rerun.  In
particular ``planning_usability_v3_hotfix`` rebinds Customer Work/Catalog pages to
native Streamlit forms.  The earlier mobile performance installer is version
 guarded, so after the next rerun native text widgets can silently return.  On
large pages (tables + forms) that makes browser typing expensive again.

This module is deliberately called *after every other installer on every rerun*.
It performs no business-data migration.  It only rebinds live render functions so
text drafts stay inside a browser component and cross the Streamlit bridge once,
when the user explicitly presses the form action button.
"""
from __future__ import annotations

from datetime import date, datetime, time
import json

from khdn_apps.legacy_fast_form import legacy_fast_form
from khdn_apps import mobile_legacy_ui_perf_patch as legacy_ui
from khdn_apps import planning_operational_phase10_patch as p10
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3
from khdn_apps import planning_week_board_focus_patch as weekfocus
from khdn_apps import potential_customer_patch as prospects

VERSION = "1.0.0"


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _options(rows, label, *, blank="— Chọn —"):
    out = [{"value": "", "label": blank}]
    for row in rows or []:
        out.append({"value": str(int(row["id"])), "label": str(label(row))})
    return out


def _fast_quick_add(st, u, get_conn, key, logger=None, select_state_key=None):
    """Prospect quick-add with browser-local draft values and unchanged duplicate flow."""
    uid = int(_uget(u, "id", 0) or 0)
    pending_key = f"{key}_pending"
    dup_key = f"{key}_dups"
    epoch_key = f"{key}_fast_epoch"
    with st.expander("＋ Khách hàng mới / chưa có CIF", expanded=bool(st.session_state.get(pending_key))):
        payload = legacy_fast_form(
            [
                {"name":"name","label":"Tên khách hàng","type":"text","required":True,"full":True},
                {"name":"tax_id","label":"MST (nếu có)","type":"text"},
                {"name":"contact_phone","label":"SĐT liên hệ (nếu có)","type":"text"},
                {"name":"contact_name","label":"Người liên hệ (nếu có)","type":"text","full":True},
            ],
            "Kiểm tra & thêm khách hàng",
            key=f"{key}_prospect_fast",
            reset_token=str(st.session_state.get(epoch_key, 0)),
            help_text="Tạo khách hàng tiềm năng để lập kế hoạch ngay. Không sinh CIF giả; Admin bổ sung CIF thật sau.",
            columns=2,
        )
        if payload is not None:
            clean = {
                "name": str(payload.get("name") or "").strip(),
                "tax_id": str(payload.get("tax_id") or "").strip(),
                "contact_name": str(payload.get("contact_name") or "").strip(),
                "contact_phone": str(payload.get("contact_phone") or "").strip(),
            }
            if not clean["name"]:
                st.error("Tên khách hàng không được để trống.")
            else:
                prospects.ensure_customer_master(get_conn, logger)
                with get_conn() as c:
                    dup = prospects.find_similar(c, clean["name"], tax_id=clean["tax_id"])
                st.session_state[pending_key] = clean
                st.session_state[dup_key] = dup
                if not dup:
                    qid = uid if str(_uget(u, "role", "")) == "Cán bộ QLKH" else None
                    cid, _ = prospects.create_prospect(
                        get_conn, uid, qlkh_user_id=qid, force=True, logger=logger, **clean
                    )
                    st.session_state.pop(pending_key, None)
                    st.session_state.pop(dup_key, None)
                    st.session_state[epoch_key] = int(st.session_state.get(epoch_key, 0)) + 1
                    if select_state_key:
                        st.session_state[select_state_key] = cid
                    st.toast("Đã thêm khách hàng tiềm năng vào danh mục chung.", icon="✅")
                    st.rerun()

        dup = st.session_state.get(dup_key) or []
        pending = st.session_state.get(pending_key)
        if pending and dup:
            st.warning("Có khách hàng có thể đã tồn tại. Hãy dùng bản ghi cũ nếu đúng khách hàng.")
            for row in dup:
                with st.container(border=True):
                    st.markdown(f"**{prospects._label(row)}**")
                    st.caption(str(row.get("match_reason") or "Có khả năng trùng"))
                    if st.button("Dùng khách hàng này", key=f"{key}_use_{row['id']}", use_container_width=True):
                        if select_state_key:
                            st.session_state[select_state_key] = int(row["id"])
                        st.session_state.pop(pending_key, None)
                        st.session_state.pop(dup_key, None)
                        st.session_state[epoch_key] = int(st.session_state.get(epoch_key, 0)) + 1
                        st.rerun()
            if st.button("Vẫn tạo mới", key=f"{key}_force", use_container_width=True):
                qid = uid if str(_uget(u, "role", "")) == "Cán bộ QLKH" else None
                cid, _ = prospects.create_prospect(
                    get_conn, uid, qlkh_user_id=qid, force=True, logger=logger, **pending
                )
                if select_state_key:
                    st.session_state[select_state_key] = cid
                st.session_state.pop(pending_key, None)
                st.session_state.pop(dup_key, None)
                st.session_state[epoch_key] = int(st.session_state.get(epoch_key, 0)) + 1
                st.toast("Đã tạo khách hàng tiềm năng mới.", icon="✅")
                st.rerun()


def _customer_create_fast(policy, st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
    """Phase-10 Customer Work create flow without native per-keystroke text widgets."""
    worktype.ensure_worktype_scope(get_conn, logger)
    v3._ensure_controller_schema(get_conn, customer_core, logger)
    prospects.ensure_customer_master(get_conn, logger)
    weekfocus._ensure_case_focus_schema(get_conn)
    p10._ensure_contact_schema(get_conn, customer_core, worktype, logger)

    uid = int(v3._uget(u, "id") or 0)
    manager = customer_ui._manager(u)
    epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)

    _fast_quick_add(
        st, u, get_conn, f"cw_new_customer_{epoch}", logger,
        select_state_key="cw_customer_pick",
    )

    with get_conn() as c:
        customers = prospects.planning_customers(c, uid)
        stages = customer_core.active_stages(c)
        users = customer_core.staff_users(c) if manager else []
        types = worktype.planning_task_types(c)
        leaders = v3._leader_users(c)
        focus_rows = weekfocus._focus_rows(policy, c, uid)

    if not customers:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error("Chưa có Loại công việc thuộc Kế hoạch. Admin hãy tạo tại Quản trị hệ thống → Loại công việc.")
        return
    if not leaders:
        st.error("Chưa có Lãnh đạo phòng đang hoạt động để chọn Lãnh đạo kiểm soát.")
        return

    preferred = st.session_state.get("cw_customer_pick")
    preferred_index = next(
        (i for i, x in enumerate(customers) if int(x.get("id") or 0) == int(preferred or -1)),
        None,
    )
    customer = st.selectbox(
        "Khách hàng *", customers, index=preferred_index,
        placeholder="— Chọn khách hàng để tự động nạp thông tin liên hệ —",
        format_func=prospects._label, key=f"p17_customer_{epoch}",
        help="Sau khi chọn khách hàng, hệ thống tự nạp tối đa 3 liên hệ đã lưu từ các công việc khách hàng trước đó.",
    )
    if customer is None:
        st.info("Chọn khách hàng trước. Thông tin liên hệ đã có sẽ được tự động nạp, không cần nhập lại.")
        return

    customer_id = int(customer["id"])
    with get_conn() as c:
        defaults = p10._load_contact_defaults(c, customer_id)
    existing_count = sum(
        1 for x in defaults
        if all((p10._clean(x.get("name")), p10._clean(x.get("phone")), p10._clean(x.get("role"))))
    )
    if existing_count:
        st.success(f"Đã tự động nạp {existing_count} thông tin liên hệ đã lưu của khách hàng. Có thể sửa trước khi tạo công việc.")
    else:
        st.caption("Khách hàng này chưa có thông tin liên hệ đã lưu. Nhập tối thiểu 1 dòng liên hệ.")

    role_values = p10._role_options(defaults)
    role_options = [{"value":"","label":"— Để trống —"}] + [
        {"value":x,"label":x} for x in role_values
    ]
    focus_options = [{"value":"","label":"— Chọn công việc trọng tâm —"}, {"value":"NONE","label":"Không thuộc công việc trọng tâm"}]
    focus_options += [
        {"value":str(int(x["id"])),"label":f"{x.get('code')} · {x.get('name')}"} for x in focus_rows
    ]
    current_owner = {
        "id": uid,
        "full_name": str(v3._uget(u,"full_name") or v3._uget(u,"username") or f"CB {uid}"),
        "role": str(v3._uget(u,"role") or ""),
    }
    owner_rows = users if manager else [current_owner]
    owner_default = "" if manager else str(uid)

    fields = [
        {"name":"case_type","label":"Nhóm công việc / Loại công việc","type":"select","required":True,"options":_options(types,lambda x:x["name"],blank="— Chọn loại công việc —"),"full":True},
        {"name":"title","label":"Công việc","type":"text","required":True,"placeholder":"Ví dụ: Cấp hạn mức tín dụng / Tiếp thị tiền gửi / Dự án A","full":True},
        {"type":"section","label":"Thông tin liên hệ · tối đa 3 người","help":"Hệ thống tự nạp thông tin đã lưu của khách hàng. Có thể sửa trực tiếp. Tối thiểu 1 dòng phải có đủ Người liên hệ, SĐT và Chức vụ; các dòng không dùng để trống."},
    ]
    for slot in (1, 2, 3):
        d = defaults[slot - 1] if slot - 1 < len(defaults) else {"name":"","phone":"","role":""}
        fields.extend([
            {"name":f"contact_{slot}_name","label":f"Người liên hệ {slot}","type":"text","default":p10._clean(d.get("name"))},
            {"name":f"contact_{slot}_phone","label":f"SĐT {slot}","type":"text","default":p10._clean(d.get("phone"))},
            {"name":f"contact_{slot}_role","label":f"Chức vụ {slot}","type":"select","options":role_options,"default":p10._clean(d.get("role"))},
        ])
    fields.extend([
        {"name":"focus","label":"Công việc ưu tiên","type":"select","required":True,"options":focus_options,"full":True},
        {"name":"due_date","label":"Dự kiến hoàn thành","type":"date","required":True},
        {"name":"stage","label":"Mục công việc bắt đầu","type":"select","required":True,"options":_options(stages,lambda x:x["name"],blank="— Chọn mục công việc —"),"span":2},
        {"name":"owner","label":"Cán bộ phụ trách","type":"select","required":True,"options":_options(owner_rows,lambda x:f"{x['full_name']} · {x['role']}",blank="— Chọn cán bộ phụ trách —"),"default":owner_default,"disabled":not manager},
        {"name":"controller","label":"Lãnh đạo kiểm soát","type":"select","required":True,"options":_options(leaders,lambda x:x["full_name"],blank="— Chọn lãnh đạo kiểm soát —"),"span":2},
        {"name":"note","label":"Ghi chú","type":"textarea","full":True},
    ])

    contact_sig = "|".join(
        f"{p10._clean(x.get('name'))}:{p10._clean(x.get('phone'))}:{p10._clean(x.get('role'))}" for x in defaults
    )
    payload = legacy_fast_form(
        fields,
        "Tạo công việc",
        key=f"p17_customer_work_create_{epoch}_{customer_id}",
        reset_token=f"{epoch}|{customer_id}|{contact_sig}|{len(types)}|{len(focus_rows)}|{len(leaders)}",
        columns=3,
    )
    if payload is None:
        return

    by_type = {str(int(x["id"])): x for x in types}
    by_stage = {str(int(x["id"])): x for x in stages}
    by_owner = {str(int(x["id"])): x for x in owner_rows}
    by_leader = {str(int(x["id"])): x for x in leaders}
    by_focus = {str(int(x["id"])): x for x in focus_rows}
    case_type = by_type.get(str(payload.get("case_type") or ""))
    stage = by_stage.get(str(payload.get("stage") or ""))
    owner = by_owner.get(str(payload.get("owner") or ""))
    controller = by_leader.get(str(payload.get("controller") or ""))
    focus_raw = str(payload.get("focus") or "")
    focus = by_focus.get(focus_raw) if focus_raw not in {"", "NONE"} else None
    title = p10._clean(payload.get("title"))
    due_raw = str(payload.get("due_date") or "").strip()

    raw_contacts = [
        {
            "name":payload.get(f"contact_{slot}_name"),
            "phone":payload.get(f"contact_{slot}_phone"),
            "role":payload.get(f"contact_{slot}_role"),
        }
        for slot in (1, 2, 3)
    ]
    contacts, partial = p10._normalize_contact_rows(raw_contacts)
    errors = []
    if not case_type: errors.append("Loại công việc")
    if not title: errors.append("Công việc")
    if focus_raw == "": errors.append("Công việc ưu tiên")
    if not due_raw: errors.append("Dự kiến hoàn thành")
    if not stage: errors.append("Mục công việc bắt đầu")
    if not owner: errors.append("Cán bộ phụ trách")
    if not controller: errors.append("Lãnh đạo kiểm soát")
    if not contacts: errors.append("Tối thiểu 1 thông tin liên hệ hoàn chỉnh")
    if partial: errors.append("Dòng liên hệ chưa nhập đủ: " + ", ".join(map(str, partial)))
    if errors:
        st.error("Vui lòng hoàn thiện: " + "; ".join(errors) + ".")
        return

    try:
        due_date = date.fromisoformat(due_raw)
    except Exception:
        st.error("Ngày dự kiến hoàn thành không hợp lệ.")
        return

    priority_q = 2 if focus else 4
    due = datetime.combine(due_date, time(17, 0)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cid, state = customer_core.create_case(
            get_conn, uid, customer_id, title, due,
            owner_uid=int(owner["id"]), case_type=case_type["name"],
            note=str(payload.get("note") or ""), stage_id=stage["id"], logger=logger,
        )
        ts = customer_core.now_str()
        with get_conn() as c:
            legacy_id = int(focus.get("legacy_category_id")) if focus and focus.get("legacy_category_id") else None
            c.execute(
                """UPDATE customer_work_cases SET controller_user_id=?,important_category_id=?,is_important=?,
                   focus_category_id=?,focus_code_snapshot=?,focus_name_snapshot=?,updated_at=? WHERE id=?""",
                (
                    int(controller["id"]), legacy_id, 1 if focus else 0,
                    int(focus["id"]) if focus else None,
                    p10._clean(focus.get("code")) if focus else None,
                    p10._clean(focus.get("name")) if focus else None,
                    ts, int(cid),
                ),
            )
            p10._write_case_contacts(c, cid, contacts, ts)
            p10._sync_customer_contacts(c, customer_id, contacts, uid, ts, cid)
            v2._set_case_priority(c, cid, priority_q, ts)
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (
                    int(cid), uid, "CREATE_METADATA_CONTACTS_P17",
                    json.dumps({
                        "contact_count":len(contacts),
                        "customer_contact_master_synced":True,
                        "focus_category_id":int(focus["id"]) if focus else None,
                        "priority_quadrant":priority_q,
                        "owner_user_id":int(owner["id"]),
                        "controller_user_id":int(controller["id"]),
                        "due_date_only":True,
                        "zero_keystroke_form":True,
                    }, ensure_ascii=False),
                    ts,
                ),
            )
        if logger:
            logger.info("P17_CUSTOMER_WORK_CREATED case_id=%s contact_count=%s zero_keystroke=1 pii_logged=0", int(cid), len(contacts))
        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        st.session_state.pop("cw_case_id", None)
        st.session_state["cw_view"] = "processing"
        st.toast(
            "Đã tạo công việc và lưu thông tin liên hệ dùng chung cho khách hàng."
            if state == "APPROVED" else
            "Đã gửi công việc chờ phê duyệt và lưu thông tin liên hệ dùng chung cho khách hàng.",
            icon="✅",
        )
        st.rerun()
    except Exception as exc:
        if logger:
            logger.exception("P17_CUSTOMER_WORK_CREATE_FAILED")
        st.error(str(exc))


def install(app_ns, policy, customer_core, customer_ui, worktype, logger=None):
    """Rebind live renderers every script run; intentionally has no early return."""
    log = logger or app_ns.get("LOGGER")

    # The V3 hotfix rebinds this renderer on every rerun. Re-assert the submit-only
    # catalog renderer after it, every time, so native text inputs cannot return.
    legacy_ui._install_customer_catalog(customer_core, customer_ui, log)

    # Quick-add is shared by Customer Work and other planning entry points.
    prospects.render_quick_add = _fast_quick_add

    def create_form(st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg, logger=None):
        return _customer_create_fast(
            policy, st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg,
            logger or log,
        )

    # These globals are resolved dynamically by all currently installed Customer
    # Work page wrappers, so rebinding them here covers every role/page route.
    v2._create_form = create_form
    v3._create_form = create_form
    weekfocus._customer_create_form = lambda policy_arg, st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg, logger=None: _customer_create_fast(
        policy, st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg, logger or log
    )

    app_ns["_GLOBAL_ZERO_KEYSTROKE_VERSION"] = VERSION
    if log:
        log.info(
            "GLOBAL_ZERO_KEYSTROKE_REBOUND version=%s catalog_stage=1 catalog_important=1 customer_work_create=1 prospect_quick_add=1 rerun_safe=1 data_migration=0",
            VERSION,
        )
