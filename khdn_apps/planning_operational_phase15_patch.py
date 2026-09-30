"""Operational phase 15: Planning-style customer picker for every Operations role.

Requirements:
- Use one searchable dropdown list like Weekly Planning instead of result cards.
- Show official CIF customers and shared PROSPECT customers in the same list.
- New/no-CIF customer creation asks for customer name only in Operations.
- Additional identity/contact fields are completed later in Customer Work.
- Apply to CBHT, QLKH, Lanh dao phong and Admin/leader mode.

This is a runtime/UI overlay. It does not rewrite existing tasks/customer IDs and
it preserves the established rule that an Operations-only QLKH assignment must
not silently rewrite the customer master.
"""
from __future__ import annotations

VERSION = "1.2.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE15_VERSION"
_NEW = "__CREATE_NEW_PROSPECT__"


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _eligible_customer(active, status):
    return int(active or 0) == 1 or str(status or "").upper() == "PROSPECT"


def _label(row):
    cif = str(row.get("cif") or "").strip()
    name = str(row.get("customer_name") or "").strip()
    return f"{name} · CIF {cif}" if cif else f"{name} · Chưa có CIF"


def _prospect_owner_id(u, key, state):
    """Set master owner only where ownership is explicit before prospect creation."""
    role = str(_uget(u, "role", "") or "")
    uid = _uget(u, "id")
    if role == "Cán bộ QLKH" and uid:
        return int(uid)
    if str(key).startswith("leader_ql_new_cust"):
        owner = state.get("leader_ql_new_owner")
        try:
            return int(owner) if owner not in (None, "") else None
        except Exception:
            return None
    # CBHT chooses QLKH for the task after customer selection. That per-task
    # choice does not modify customer master ownership.
    return None


def _customer_rows(get_conn):
    with get_conn() as c:
        rows = c.execute(
            """SELECT c.id,c.cif,c.customer_name,c.qlkh_user_id,c.active,
                      c.customer_status,c.tax_id,c.contact_name,c.contact_phone,
                      u.full_name AS qlkh_name
               FROM customers c LEFT JOIN users u ON u.id=c.qlkh_user_id
               WHERE (c.active=1 OR c.customer_status='PROSPECT')
               ORDER BY CASE WHEN c.customer_status='PROSPECT' THEN 1 ELSE 0 END,
                        c.customer_name,c.id"""
        ).fetchall()
    return [dict(r) for r in rows]


def _clear_picker_state(st, key):
    for suffix in (
        "_selected_id", "_dropdown", "_new_name", "_prospect_pending", "_prospect_dups"
    ):
        st.session_state.pop(f"{key}{suffix}", None)
    # Old Phase 15 search UI keys are removed as well so stale mobile sessions do
    # not rehydrate the previous search-card state after deployment.
    for suffix in ("_query", "_prospect_tax", "_prospect_phone", "_prospect_contact"):
        st.session_state.pop(f"{key}{suffix}", None)


def _render_duplicate_choice(st, u, app_ns, potential, key, pending, duplicates, logger=None):
    selected_key = f"{key}_selected_id"
    dropdown_key = f"{key}_dropdown"
    st.warning("Có khách hàng có thể đã tồn tại. Hãy dùng bản ghi hiện có nếu đúng khách hàng.")
    for row in duplicates:
        rid = int(row["id"])
        if st.button(
            f"Dùng: {_label(row)}",
            key=f"{key}_dup_use_{rid}",
            use_container_width=True,
        ):
            st.session_state[selected_key] = rid
            st.session_state[f"{key}_set_dropdown"] = rid
            st.session_state.pop(f"{key}_prospect_pending", None)
            st.session_state.pop(f"{key}_prospect_dups", None)
            st.rerun()
    if st.button(
        f"Vẫn tạo mới: {str(pending.get('name') or '').strip()}",
        key=f"{key}_prospect_force",
        use_container_width=True,
    ):
        owner = _prospect_owner_id(u, key, st.session_state)
        cid, _ = potential.create_prospect(
            app_ns["get_conn"], int(_uget(u, "id")), str(pending.get("name") or "").strip(),
            qlkh_user_id=owner, force=True, logger=logger,
        )
        st.session_state[selected_key] = int(cid)
        st.session_state[f"{key}_set_dropdown"] = int(cid)
        st.session_state.pop(f"{key}_prospect_pending", None)
        st.session_state.pop(f"{key}_prospect_dups", None)
        st.toast("Đã tạo khách hàng chưa có CIF và chọn để tác nghiệp.", icon="✅")
        st.rerun()


def _customer_selector(st, u, app_ns, potential, key="cust", required_message=None, logger=None):
    """Native searchable selectbox matching the Planning customer-list pattern."""
    rows = _customer_rows(app_ns["get_conn"])
    by_id = {int(r["id"]): r for r in rows}
    ids = list(by_id)
    selected_key = f"{key}_selected_id"
    dropdown_key = f"{key}_dropdown"
    pending_key = f"{key}_prospect_pending"
    dup_key = f"{key}_prospect_dups"

    # After create/duplicate-selection we may need to move a pre-existing widget
    # away from the NEW sentinel. This assignment occurs before widget creation.
    forced = st.session_state.pop(f"{key}_set_dropdown", None)
    if forced in by_id:
        st.session_state[dropdown_key] = int(forced)

    previous_id = st.session_state.get(selected_key)
    if previous_id in by_id and dropdown_key not in st.session_state:
        st.session_state[dropdown_key] = int(previous_id)

    options = [None, _NEW] + ids

    def _fmt(value):
        if value is None:
            return "— Chọn khách hàng —"
        if value == _NEW:
            return "＋ Tạo khách hàng mới / chưa có CIF"
        row = by_id.get(int(value))
        return _label(row) if row else "—"

    choice = st.selectbox(
        "Khách hàng *",
        options,
        index=0,
        format_func=_fmt,
        key=dropdown_key,
        help="Danh sách dùng chung với Kế hoạch. Có thể gõ CIF hoặc tên ngay trong ô danh sách để lọc nhanh.",
    )

    if required_message and choice is None:
        try:
            app_ns["required_error"](required_message)
        except Exception:
            st.error(str(required_message))

    if choice is None:
        st.session_state.pop(selected_key, None)
        st.session_state.pop(pending_key, None)
        st.session_state.pop(dup_key, None)
        return None

    if choice != _NEW:
        rid = int(choice)
        st.session_state[selected_key] = rid
        st.session_state.pop(pending_key, None)
        st.session_state.pop(dup_key, None)
        return by_id.get(rid)

    # Operations intentionally collects NAME ONLY. MST/contact/phone belong to
    # Customer Work, where users can complete richer customer information later.
    st.session_state.pop(selected_key, None)
    st.caption("Khách hàng chưa có CIF: tại Tác nghiệp chỉ cần nhập tên. Thông tin khác bổ sung sau ở Công việc khách hàng.")
    name = st.text_input(
        "Tên khách hàng mới *",
        key=f"{key}_new_name",
        placeholder="Nhập tên khách hàng",
    )
    if st.button(
        "Tạo & chọn khách hàng",
        key=f"{key}_prospect_create",
        type="primary",
        use_container_width=True,
    ):
        clean_name = str(name or "").strip()
        if not clean_name:
            st.error("Vui lòng nhập tên khách hàng.")
        else:
            with app_ns["get_conn"]() as c:
                duplicates = potential.find_similar(c, clean_name)
            st.session_state[pending_key] = {"name": clean_name}
            st.session_state[dup_key] = duplicates
            if not duplicates:
                owner = _prospect_owner_id(u, key, st.session_state)
                cid, _ = potential.create_prospect(
                    app_ns["get_conn"], int(_uget(u, "id")), clean_name,
                    qlkh_user_id=owner, force=True, logger=logger,
                )
                st.session_state[selected_key] = int(cid)
                st.session_state[f"{key}_set_dropdown"] = int(cid)
                st.session_state.pop(pending_key, None)
                st.session_state.pop(dup_key, None)
                st.toast("Đã tạo khách hàng chưa có CIF và chọn để tác nghiệp.", icon="✅")
                st.rerun()

    pending = st.session_state.get(pending_key)
    duplicates = st.session_state.get(dup_key) or []
    if pending and duplicates:
        _render_duplicate_choice(st, u, app_ns, potential, key, pending, duplicates, logger)
    return None


def install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger=None):
    """Install after phase 14 so every final Operations role page gets parity."""
    if app_ns.get(_FLAG) == VERSION:
        return

    from khdn_apps import potential_customer_patch as potential

    # Shared no-CIF schema is prepared once at runtime installation, never on each
    # selectbox keystroke/rerun.
    potential.ensure_customer_master(app_ns["get_conn"], logger or app_ns.get("LOGGER"))

    original_support = app_ns.get("support_page")
    original_qlkh = app_ns.get("qlkh_page")
    original_leader = app_ns.get("leader_page")
    original_selector = app_ns.get("customer_selector")

    def _run_with_selector(page_func, u, *args, **kwargs):
        if page_func is None:
            return None
        previous = app_ns.get("customer_selector", original_selector)
        app_ns["customer_selector"] = lambda key="cust", required_message=None: _customer_selector(
            app_ns["st"], u, app_ns, potential, key, required_message, logger or app_ns.get("LOGGER")
        )
        try:
            return page_func(u, *args, **kwargs)
        finally:
            app_ns["customer_selector"] = previous

    if original_support:
        def support_page(u, *args, **kwargs):
            st = app_ns["st"]
            if st.session_state.get("reset_new_task_fields"):
                _clear_picker_state(st, "new_cust")
            return _run_with_selector(original_support, u, *args, **kwargs)
        app_ns["support_page"] = support_page

    if original_qlkh:
        def qlkh_page(u, *args, **kwargs):
            st = app_ns["st"]
            if st.session_state.get("reset_ql_create_fields"):
                _clear_picker_state(st, "ql_new_cust")
            return _run_with_selector(original_qlkh, u, *args, **kwargs)
        app_ns["qlkh_page"] = qlkh_page

    if original_leader:
        def leader_page(u, *args, **kwargs):
            st = app_ns["st"]
            if st.session_state.get("leader_ql_reset_create"):
                _clear_picker_state(st, "leader_ql_new_cust")
            return _run_with_selector(original_leader, u, *args, **kwargs)
        app_ns["leader_page"] = leader_page

    app_ns[_FLAG] = VERSION
    if logger or app_ns.get("LOGGER"):
        (logger or app_ns.get("LOGGER")).info(
            "PLANNING_OPERATIONAL_PHASE15_INSTALLED dropdown_list=1 native_search=1 name_only_create=1 prospects_in_operations=1 roles=CBHT,QLKH,LEADER,ADMIN duplicate_guard=1 no_task_rewrite=1"
        )
