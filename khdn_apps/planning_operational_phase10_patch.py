"""Operational phase 10: reusable three-row customer contact information.

Requirements:
- Customer Work creation exposes three contact rows: contact person, phone,
  position. At least one row must be complete; unused rows may stay blank.
- Existing customer contact information is automatically carried forward when
  another Customer Work item is created for the same customer. Staff may edit
  the prefilled values before saving.
- Contact edits on an existing case are allowed for the case owner, the selected
  controlling leader, and Admin. The edited rows become the defaults for the
  next Customer Work item of that customer.
- Legacy single-contact cases are migrated lazily into the customer contact
  master without changing historical workflow/approval rules.
"""
from __future__ import annotations

from datetime import date, datetime, time
import hashlib
import html
import json

from khdn_apps.legacy_fast_form import legacy_fast_form
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3
from khdn_apps import planning_week_board_focus_patch as weekfocus

VERSION = "1.0.1"
_FLAG = "_PLANNING_OPERATIONAL_PHASE10_VERSION"

_EXTRA_CASE_CONTACT_COLUMNS = (
    ("contact2_name", "TEXT"), ("contact2_phone", "TEXT"), ("contact2_role", "TEXT"),
    ("contact3_name", "TEXT"), ("contact3_phone", "TEXT"), ("contact3_role", "TEXT"),
)


def _cols(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _clean(value):
    return str(value or "").strip()


def _normalize_contact_rows(rows):
    """Return compact complete rows plus indexes of partially filled rows."""
    complete = []
    partial = []
    seen = set()
    for idx, row in enumerate(rows, 1):
        item = {
            "name": _clean(row.get("name")),
            "phone": _clean(row.get("phone")),
            "role": _clean(row.get("role")),
        }
        values = (item["name"], item["phone"], item["role"])
        if not any(values):
            continue
        if not all(values):
            partial.append(idx)
            continue
        key = tuple(v.casefold() for v in values)
        if key in seen:
            continue
        seen.add(key)
        complete.append(item)
        if len(complete) == 3:
            break
    return complete, partial


def _case_contact_values(row):
    if not row:
        return []
    d = dict(row)
    out = []
    for slot in (1, 2, 3):
        prefix = "contact" if slot == 1 else f"contact{slot}"
        item = {
            "name": _clean(d.get(f"{prefix}_name")),
            "phone": _clean(d.get(f"{prefix}_phone")),
            "role": _clean(d.get(f"{prefix}_role")),
        }
        if any(item.values()):
            out.append(item)
    complete, _ = _normalize_contact_rows(out)
    return complete


def _write_case_contacts(c, case_id, contacts, ts):
    padded = list(contacts[:3]) + [{"name": "", "phone": "", "role": ""}] * (3 - len(contacts[:3]))
    c.execute(
        """UPDATE customer_work_cases SET
           contact_name=?,contact_phone=?,contact_role=?,
           contact2_name=?,contact2_phone=?,contact2_role=?,
           contact3_name=?,contact3_phone=?,contact3_role=?,updated_at=?
           WHERE id=?""",
        (
            padded[0]["name"] or None, padded[0]["phone"] or None, padded[0]["role"] or None,
            padded[1]["name"] or None, padded[1]["phone"] or None, padded[1]["role"] or None,
            padded[2]["name"] or None, padded[2]["phone"] or None, padded[2]["role"] or None,
            str(ts), int(case_id),
        ),
    )


def _sync_customer_contacts(c, customer_id, contacts, actor_uid, ts, source_case_id=None):
    c.execute("DELETE FROM customer_contact_master WHERE customer_id=?", (int(customer_id),))
    for slot, item in enumerate(contacts[:3], 1):
        c.execute(
            """INSERT INTO customer_contact_master(
               customer_id,slot,contact_name,contact_phone,contact_role,
               updated_by,updated_at,source_case_id)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                int(customer_id), int(slot), item["name"], item["phone"], item["role"],
                int(actor_uid), str(ts), int(source_case_id) if source_case_id else None,
            ),
        )


def _load_contact_defaults(c, customer_id):
    rows = [dict(r) for r in c.execute(
        """SELECT slot,contact_name,contact_phone,contact_role
           FROM customer_contact_master WHERE customer_id=? ORDER BY slot""",
        (int(customer_id),),
    ).fetchall()]
    by_slot = {int(r["slot"]): r for r in rows}
    result = []
    for slot in (1, 2, 3):
        r = by_slot.get(slot, {})
        result.append({
            "name": _clean(r.get("contact_name")),
            "phone": _clean(r.get("contact_phone")),
            "role": _clean(r.get("contact_role")),
        })
    return result


def _ensure_contact_schema(get_conn, customer_core, worktype, logger=None):
    worktype.ensure_case_contacts(get_conn, logger)
    customer_core.ensure_schema(get_conn, logger)
    migrated_customers = 0
    with get_conn() as c:
        cols = _cols(c, "customer_work_cases")
        for name, ddl in _EXTRA_CASE_CONTACT_COLUMNS:
            if name not in cols:
                c.execute(f"ALTER TABLE customer_work_cases ADD COLUMN {name} {ddl}")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_contact_master(
                customer_id INTEGER NOT NULL,
                slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),
                contact_name TEXT NOT NULL,
                contact_phone TEXT NOT NULL,
                contact_role TEXT NOT NULL,
                updated_by INTEGER,
                updated_at TEXT NOT NULL,
                source_case_id INTEGER,
                PRIMARY KEY(customer_id,slot),
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(updated_by) REFERENCES users(id),
                FOREIGN KEY(source_case_id) REFERENCES customer_work_cases(id)
            );
            CREATE INDEX IF NOT EXISTS idx_customer_contact_master_customer
                ON customer_contact_master(customer_id,slot);
            """
        )

        # Backfill only customers that do not yet have shared contacts. This
        # preserves later user edits and keeps reruns cheap.
        missing = [int(r[0]) for r in c.execute(
            """SELECT DISTINCT w.customer_id FROM customer_work_cases w
               WHERE w.customer_id IS NOT NULL
                 AND NOT EXISTS(
                   SELECT 1 FROM customer_contact_master m WHERE m.customer_id=w.customer_id
                 )"""
        ).fetchall()]
        for customer_id in missing:
            historical = c.execute(
                """SELECT id,contact_name,contact_phone,contact_role,
                          contact2_name,contact2_phone,contact2_role,
                          contact3_name,contact3_phone,contact3_role,
                          COALESCE(updated_at,created_at,'') AS touched_at
                   FROM customer_work_cases WHERE customer_id=?
                   ORDER BY touched_at DESC,id DESC""",
                (customer_id,),
            ).fetchall()
            found = []
            seen = set()
            source_case = None
            for row in historical:
                for item in _case_contact_values(row):
                    key = (item["name"].casefold(), item["phone"].casefold(), item["role"].casefold())
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(item)
                    source_case = source_case or int(row["id"])
                    if len(found) == 3:
                        break
                if len(found) == 3:
                    break
            if found:
                _sync_customer_contacts(
                    c, customer_id, found, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), source_case
                )
                migrated_customers += 1
    if logger:
        logger.info(
            "P10_CONTACT_SCHEMA_READY max_contacts=3 migrated_customers=%s pii_logged=0",
            migrated_customers,
        )


def _role_options(default_rows):
    values = [str(x) for x in v2.CONTACT_ROLES]
    for row in default_rows:
        role = _clean(row.get("role"))
        if role and role not in values:
            values.append(role)
    return values


def _render_contact_inputs(st, prefix, defaults):
    roles = _role_options(defaults)
    rows = []
    st.markdown("**Thông tin liên hệ · tối đa 3 người**")
    st.caption(
        "Hệ thống tự nạp thông tin đã lưu của khách hàng. Có thể sửa trực tiếp. "
        "Tối thiểu 1 dòng phải có đủ Người liên hệ, SĐT và Chức vụ; các dòng không dùng để trống."
    )
    for slot in (1, 2, 3):
        default = defaults[slot - 1] if slot - 1 < len(defaults) else {"name": "", "phone": "", "role": ""}
        c1, c2, c3 = st.columns([1.35, 1, 1.15])
        name = c1.text_input(
            f"Người liên hệ {slot}", value=_clean(default.get("name")), key=f"{prefix}_contact_{slot}_name"
        )
        phone = c2.text_input(
            f"SĐT {slot}", value=_clean(default.get("phone")), key=f"{prefix}_contact_{slot}_phone"
        )
        current_role = _clean(default.get("role"))
        options = [None] + roles
        index = options.index(current_role) if current_role in options else 0
        role = c3.selectbox(
            f"Chức vụ {slot}", options, index=index,
            format_func=lambda x: "— Để trống —" if x is None else str(x),
            key=f"{prefix}_contact_{slot}_role",
        )
        rows.append({"name": name, "phone": phone, "role": role or ""})
    return rows


def _contact_token(data):
    """Compare contact values, independent of changes to other case fields."""
    values = [_clean(data.get("customer_id"))] + [_clean(data.get(f"{prefix}_{field}"))
              for prefix in ("contact", "contact2", "contact3")
              for field in ("name", "phone", "role")]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def _render_contact_edit_fast(st, case_id, uid, data, defaults, logger=None):
    """Names, phones and positions stay in the iframe until its Save action."""
    token = _contact_token(data)
    # A saved contact change gets a different widget identity, so an event from
    # the old browser form cannot overwrite newer contact data on the next run.
    key = f"p10_contact_edit_fast_{int(case_id)}_{int(uid)}_{token}"
    roles = [{"value": "", "label": "— Để trống —"}]
    roles += [{"value": role, "label": role} for role in _role_options(defaults)]
    fields = []
    for slot in (1, 2, 3):
        default = defaults[slot - 1]
        fields.extend([
            {"name": f"contact_{slot}_name", "label": f"Người liên hệ {slot}",
             "type": "text", "default": _clean(default.get("name")), "span": 2},
            {"name": f"contact_{slot}_phone", "label": f"SĐT {slot}",
             "type": "text", "default": _clean(default.get("phone"))},
            {"name": f"contact_{slot}_role", "label": f"Chức vụ {slot}",
             "type": "select", "options": roles, "default": _clean(default.get("role"))},
        ])
    payload = legacy_fast_form(
        fields, "Lưu thông tin liên hệ", key=key, reset_token=token, columns=4,
        title="Thông tin liên hệ · tối đa 3 người",
        help_text="Tối thiểu 1 dòng phải có đủ Người liên hệ, SĐT và Chức vụ; các dòng không dùng để trống.",
    )
    log_key = f"p10_contact_edit_render_{int(case_id)}_{int(uid)}"
    if logger and st.session_state.get(log_key) != token:
        logger.info("P10_CONTACT_EDIT_RENDER case_id=%s actor=%s zero_keystroke=1 fields=9 pii_logged=0",
                    int(case_id), int(uid))
        st.session_state[log_key] = token
    if payload is None:
        return None
    return [{field: payload.get(f"contact_{slot}_{field}") for field in ("name", "phone", "role")}
            for slot in (1, 2, 3)]


def _save_contact_edit(get_conn, customer_core, case_id, uid, contacts, expected_token):
    """Recheck ownership, actor and contacts while holding the write lock."""
    ts = customer_core.now_str()
    with get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
        actor = c.execute("SELECT * FROM users WHERE id=? AND active=1", (int(uid),)).fetchone()
        if not row or not actor:
            raise PermissionError("Bạn không còn quyền sửa thông tin liên hệ của công việc này.")
        data, user = dict(row), dict(actor)
        allowed = (int(data.get("owner_user_id") or 0) == int(uid)
                   or bool(user.get("is_admin"))
                   or str(user.get("role")) == "Lãnh đạo phòng"
                   and int(data.get("controller_user_id") or 0) == int(uid))
        if not allowed:
            raise PermissionError("Bạn không còn quyền sửa thông tin liên hệ của công việc này.")
        if _contact_token(data) != expected_token:
            raise ValueError("Thông tin liên hệ đã được cập nhật ở phiên khác. Vui lòng tải lại trước khi sửa.")
        _write_case_contacts(c, int(case_id), contacts, ts)
        _sync_customer_contacts(c, int(data["customer_id"]), contacts, int(uid), ts, int(case_id))
        c.execute(
            "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
            (int(case_id), int(uid), "CONTACT_UPDATE_P10",
             json.dumps({"contact_count": len(contacts), "customer_contact_master_synced": True,
                         "zero_keystroke_form": True}, ensure_ascii=False), ts),
        )


def _contact_validation(st, invalid_state, prefix, raw_rows):
    complete, partial = _normalize_contact_rows(raw_rows)
    errors = []
    bad_keys = []
    if not complete:
        errors.append("Tối thiểu 1 thông tin liên hệ hoàn chỉnh")
        if not partial:
            bad_keys.extend([
                f"{prefix}_contact_1_name", f"{prefix}_contact_1_phone", f"{prefix}_contact_1_role"
            ])
    for slot in partial:
        errors.append(f"Dòng liên hệ {slot} phải nhập đủ Người liên hệ, SĐT và Chức vụ")
        bad_keys.extend([
            f"{prefix}_contact_{slot}_name", f"{prefix}_contact_{slot}_phone", f"{prefix}_contact_{slot}_role"
        ])
    if errors:
        finalux._fail_validation(st, invalid_state, errors, bad_keys)
        return None
    return complete


def _customer_create_form(policy, st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
    prospects = refinement.prospects
    worktype.ensure_worktype_scope(get_conn, logger)
    v3._ensure_controller_schema(get_conn, customer_core, logger)
    prospects.ensure_customer_master(get_conn, logger)
    weekfocus._ensure_case_focus_schema(get_conn)
    _ensure_contact_schema(get_conn, customer_core, worktype, logger)

    uid = int(v3._uget(u, "id") or 0)
    manager = customer_ui._manager(u)
    epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)
    invalid_state = f"p10_cw_invalid_{epoch}"
    finalux._render_validation(st, invalid_state)

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
        format_func=prospects._label, key=f"p10_customer_{epoch}",
        help="Sau khi chọn khách hàng, hệ thống tự nạp tối đa 3 liên hệ đã lưu từ các công việc khách hàng trước đó.",
    )
    if customer is None:
        st.info("Chọn khách hàng trước. Thông tin liên hệ đã có sẽ được tự động nạp, không cần nhập lại.")
        return

    with get_conn() as c:
        defaults = _load_contact_defaults(c, int(customer["id"]))
    existing_count = sum(1 for x in defaults if all((_clean(x.get("name")), _clean(x.get("phone")), _clean(x.get("role")))))
    if existing_count:
        st.success(f"Đã tự động nạp {existing_count} thông tin liên hệ đã lưu của khách hàng. Có thể sửa trước khi tạo công việc.")
    else:
        st.caption("Khách hàng này chưa có thông tin liên hệ đã lưu. Nhập tối thiểu 1 dòng liên hệ.")

    customer_id = int(customer["id"])
    p = f"p10_cw_{epoch}_{customer_id}"
    with st.form(f"p10_create_{epoch}_{customer_id}", clear_on_submit=False):
        case_type = st.selectbox(
            "Nhóm công việc / Loại công việc *", types, index=None,
            placeholder="— Chọn loại công việc —", format_func=lambda x: x["name"], key=p+"_type",
        )
        title = st.text_input(
            "Công việc *", value="", placeholder="Ví dụ: Cấp hạn mức tín dụng / Tiếp thị tiền gửi / Dự án A",
            key=p+"_title",
        )
        raw_contacts = _render_contact_inputs(st, p, defaults)

        focus_options = list(focus_rows) + ["NONE"]
        focus_choice = st.selectbox(
            "Công việc ưu tiên *", focus_options, index=None,
            placeholder="— Chọn công việc trọng tâm —",
            format_func=lambda x: "Không thuộc công việc trọng tâm" if x == "NONE" else f"{x.get('code')} · {x.get('name')}",
            key=p+"_priority",
            help="Danh sách lấy trực tiếp từ Danh mục công việc trọng tâm của phòng. Chọn một mục sẽ tự phân loại Q2 · Trọng tâm.",
        )
        due_date = st.date_input(
            "Dự kiến hoàn thành *", value=None, format="DD/MM/YYYY", key=p+"_due_date"
        )
        stage = st.selectbox(
            "Mục công việc bắt đầu *", stages, index=None,
            placeholder="— Chọn mục công việc —", format_func=lambda x:x["name"], key=p+"_stage",
        )

        if manager:
            owner = st.selectbox(
                "Cán bộ phụ trách *", users, index=None,
                placeholder="— Chọn cán bộ phụ trách —",
                format_func=lambda x:f"{x['full_name']} · {x['role']}", key=p+"_owner",
            )
        else:
            current_owner = {
                "id": uid,
                "full_name": str(v3._uget(u,"full_name") or v3._uget(u,"username") or f"CB {uid}"),
                "role": str(v3._uget(u,"role") or ""),
            }
            owner = st.selectbox(
                "Cán bộ phụ trách *", [current_owner], index=0,
                format_func=lambda x:f"{x['full_name']} · {x['role']}", key=p+"_owner", disabled=True,
            )

        controller = st.selectbox(
            "Lãnh đạo kiểm soát *", leaders, index=None,
            placeholder="— Chọn lãnh đạo kiểm soát —", format_func=lambda x:x["full_name"], key=p+"_controller",
        )
        note = st.text_area("Ghi chú", value="", height=80, key=p+"_note")
        ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

    if not ok:
        return

    checks = [
        ("Loại công việc", case_type is None, p+"_type"),
        ("Công việc", not _clean(title), p+"_title"),
        ("Công việc ưu tiên", focus_choice is None, p+"_priority"),
        ("Dự kiến hoàn thành", due_date is None, p+"_due_date"),
        ("Mục công việc bắt đầu", stage is None, p+"_stage"),
        ("Cán bộ phụ trách", owner is None, p+"_owner"),
        ("Lãnh đạo kiểm soát", controller is None, p+"_controller"),
    ]
    missing = [label for label, failed, _ in checks if failed]
    missing_keys = [key for _, failed, key in checks if failed]
    if missing:
        finalux._fail_validation(st, invalid_state, missing, missing_keys)
        return
    contacts = _contact_validation(st, invalid_state, p, raw_contacts)
    if contacts is None:
        return

    finalux._clear_validation(st, invalid_state)
    focus = focus_choice if isinstance(focus_choice, dict) else None
    priority_q = 2 if focus else 4
    due = datetime.combine(due_date, time(17, 0)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cid, state = customer_core.create_case(
            get_conn, uid, customer_id, _clean(title), due,
            owner_uid=int(owner["id"]), case_type=case_type["name"], note=note,
            stage_id=stage["id"], logger=logger,
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
                    _clean(focus.get("code")) if focus else None,
                    _clean(focus.get("name")) if focus else None,
                    ts, int(cid),
                ),
            )
            _write_case_contacts(c, cid, contacts, ts)
            _sync_customer_contacts(c, customer_id, contacts, uid, ts, cid)
            v2._set_case_priority(c, cid, priority_q, ts)
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (
                    int(cid), uid, "CREATE_METADATA_CONTACTS_P10",
                    json.dumps({
                        "contact_count": len(contacts),
                        "customer_contact_master_synced": True,
                        "focus_category_id": int(focus["id"]) if focus else None,
                        "priority_quadrant": priority_q,
                        "owner_user_id": int(owner["id"]),
                        "controller_user_id": int(controller["id"]),
                        "due_date_only": True,
                    }, ensure_ascii=False),
                    ts,
                ),
            )
        if logger:
            logger.info("P10_CUSTOMER_WORK_CREATED case_id=%s contact_count=%s pii_logged=0", int(cid), len(contacts))
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
            logger.exception("P10_CUSTOMER_WORK_CREATE_FAILED")
        st.error(str(exc))


def _contact_table(st, contacts, editable=False):
    if not contacts:
        st.caption("Chưa có thông tin liên hệ.")
        return
    rows = []
    for idx, item in enumerate(contacts, 1):
        rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td>{html.escape(item['phone'])}</td>"
            f"<td>{html.escape(item['role'])}</td>"
            "</tr>"
        )
    st.html(
        "<div class='p10-contact-table'><table><thead><tr>"
        "<th>#</th><th>Người liên hệ</th><th>SĐT</th><th>Chức vụ</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        "<style>.p10-contact-table{width:100%;overflow-x:auto}.p10-contact-table table{width:100%;table-layout:fixed;border-collapse:collapse}"
        ".p10-contact-table th,.p10-contact-table td{padding:7px 9px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere}"
        ".p10-contact-table th{font-weight:900}.p10-contact-table th:first-child,.p10-contact-table td:first-child{width:7%;text-align:center}</style>"
    )


def _install_detail_editor(customer_ui, customer_core, worktype, logger=None):
    if getattr(customer_ui, "_P10_CONTACT_DETAIL_EDITOR", False):
        return
    original = customer_ui._case_detail

    def case_detail(st, u, get_conn, case_id, logger=None):
        active_logger = logger
        result = original(st, u, get_conn, case_id, active_logger)
        _ensure_contact_schema(get_conn, customer_core, worktype, active_logger)
        uid = int(v3._uget(u, "id") or 0)
        with get_conn() as c:
            cols = _cols(c, "customer_work_cases")
            wanted = [
                "id", "customer_id", "owner_user_id", "controller_user_id",
                "contact_name", "contact_phone", "contact_role",
                "contact2_name", "contact2_phone", "contact2_role",
                "contact3_name", "contact3_phone", "contact3_role",
            ]
            available = [x for x in wanted if x in cols]
            row = c.execute(
                "SELECT " + ",".join(available) + " FROM customer_work_cases WHERE id=?",
                (int(case_id),),
            ).fetchone()
        if not row:
            return result
        data = dict(row)
        owner = int(data.get("owner_user_id") or 0) == uid
        admin = bool(v3._uget(u, "is_admin", False))
        leader = str(v3._uget(u, "role", "")) == "Lãnh đạo phòng"
        controller = int(data.get("controller_user_id") or 0) == uid
        can_view = owner or admin or leader
        if not can_view:
            return result
        contacts = _case_contact_values(data)
        st.divider()
        st.subheader("☎ Thông tin liên hệ khách hàng")
        can_edit = owner or admin or (leader and controller)
        if not can_edit:
            st.caption("Bạn được xem thông tin liên hệ nhưng không thuộc phạm vi được sửa của công việc này.")
            _contact_table(st, contacts)
            return result

        with st.expander("✏️ Sửa thông tin liên hệ", expanded=False):
            defaults = contacts + [{"name":"", "phone":"", "role":""}] * (3 - len(contacts))
            raw = _render_contact_edit_fast(st, int(case_id), uid, data, defaults[:3], active_logger)
            if raw is not None:
                complete, partial = _normalize_contact_rows(raw)
                if not complete:
                    st.error("Phải có tối thiểu 1 dòng liên hệ nhập đủ Người liên hệ, SĐT và Chức vụ.")
                elif partial:
                    st.error("Các dòng đã nhập phải đủ cả Người liên hệ, SĐT và Chức vụ. Dòng chưa đủ: " + ", ".join(map(str, partial)) + ".")
                else:
                    try:
                        _save_contact_edit(get_conn, customer_core, int(case_id), uid, complete, _contact_token(data))
                    except (PermissionError, ValueError) as exc:
                        st.error(str(exc))
                        if active_logger:
                            active_logger.warning("P10_CONTACT_UPDATE_BLOCKED case_id=%s actor=%s", int(case_id), uid)
                        return result
                    except Exception:
                        st.error("Chưa lưu được thông tin liên hệ. Vui lòng thử lại.")
                        if active_logger:
                            active_logger.exception("P10_CONTACT_UPDATE_FAILED case_id=%s actor=%s", int(case_id), uid)
                        return result
                    if active_logger:
                        active_logger.info("P10_CONTACT_UPDATE case_id=%s contact_count=%s zero_keystroke=1 pii_logged=0", int(case_id), len(complete))
                    st.toast("Đã cập nhật thông tin liên hệ. Lần tạo công việc tiếp theo sẽ tự động dùng thông tin mới.", icon="✅")
                    st.rerun()
        return result

    customer_ui._case_detail = case_detail
    customer_ui._P10_CONTACT_DETAIL_EDITOR = True
    if logger:
        logger.info("P10_CONTACT_DETAIL_EDITOR_INSTALLED owner=1 controller=1 admin=1 out_of_scope_leader_readonly=1 zero_keystroke=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    app_logger = logger or app_ns.get("LOGGER")
    get_conn = app_ns["get_conn"]
    refinement = __import__("khdn_apps.customer_work_refinement_patch", fromlist=["*"])

    _ensure_contact_schema(get_conn, customer_core, worktype, app_logger)

    def create_form(st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg, logger=None):
        return _customer_create_form(
            policy, st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg,
            logger or app_logger,
        )

    # v2 render_cases_page resolves its module-global _create_form at call time.
    # v3/customer_ui closures also resolve v3._create_form dynamically.
    v2._create_form = create_form
    v3._create_form = create_form
    weekfocus._customer_create_form = lambda policy_arg, st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg, logger=None: _customer_create_form(
        policy, st, u, get_conn_arg, core, ui, refinement_arg, worktype_arg, logger or app_logger
    )

    _install_detail_editor(customer_ui, customer_core, worktype, app_logger)

    setattr(policy, _FLAG, VERSION)
    if app_logger:
        app_logger.info(
            "PLANNING_OPERATIONAL_PHASE10_INSTALLED version=%s contacts=3 auto_carry=1 editable=1 min_complete=1 approval_scope_unchanged=1",
            VERSION,
        )
