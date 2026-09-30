"""Operational phase 15: Planning-style customer search for every Operations role.

Goals:
- Reuse the shared customer master used by Planning/Customer Work.
- Search both official CIF customers and PROSPECT customers without CIF.
- Let users type a customer name and create a shared PROSPECT directly from the
  Operations customer search, with duplicate protection and no fake CIF.
- Apply the same behavior to CBHT, QLKH, Lanh dao phong and Admin/leader mode.

This is a runtime/UI overlay. It does not rewrite existing tasks or customer IDs.
"""
from __future__ import annotations

import json

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE15_VERSION"


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
    return f"{cif} — {name}" if cif else f"Chưa có CIF — {name}"


def _prospect_owner_id(u, key, state):
    """Best owner for the shared master without impersonating another user."""
    role = str(_uget(u, "role", "") or "")
    uid = _uget(u, "id")
    if role == "Cán bộ QLKH" and uid:
        return int(uid)
    # In the leader parity create screen the QLKH owner is chosen before customer.
    if str(key).startswith("leader_ql_new_cust"):
        owner = state.get("leader_ql_new_owner")
        try:
            return int(owner) if owner not in (None, "") else None
        except Exception:
            return None
    return None


def _row_dict(row):
    if row is None:
        return None
    try:
        return dict(row)
    except Exception:
        return row


def _load_customer(get_conn, customer_id):
    if not customer_id:
        return None
    with get_conn() as c:
        row = c.execute(
            """SELECT c.id,c.cif,c.customer_name,c.qlkh_user_id,c.active,
                      c.customer_status,c.tax_id,c.contact_name,c.contact_phone,
                      u.full_name AS qlkh_name
               FROM customers c LEFT JOIN users u ON u.id=c.qlkh_user_id
               WHERE c.id=? AND (c.active=1 OR c.customer_status='PROSPECT')""",
            (int(customer_id),),
        ).fetchone()
    return _row_dict(row)


def _search_customers(get_conn, query, limit=20):
    q = str(query or "").strip().lower()
    if not q:
        return []
    like = f"%{q}%"
    with get_conn() as c:
        rows = c.execute(
            """SELECT c.id,c.cif,c.customer_name,c.qlkh_user_id,c.active,
                      c.customer_status,c.tax_id,c.contact_name,c.contact_phone,
                      u.full_name AS qlkh_name
               FROM customers c LEFT JOIN users u ON u.id=c.qlkh_user_id
               WHERE (c.active=1 OR c.customer_status='PROSPECT')
                 AND (lower(COALESCE(CAST(c.cif AS TEXT),'')) LIKE ?
                      OR lower(c.customer_name) LIKE ?)
               ORDER BY
                 CASE WHEN lower(COALESCE(CAST(c.cif AS TEXT),''))=? THEN 0
                      WHEN lower(c.customer_name)=? THEN 1 ELSE 2 END,
                 CASE WHEN c.customer_status='PROSPECT' THEN 1 ELSE 0 END,
                 c.customer_name
               LIMIT ?""",
            (like, like, q, q, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def _bind_support_prospect_owner(st, u, key, row, get_conn, app_ns, logger=None):
    """If CBHT chooses QLKH after creating a prospect, bind only blank master owner."""
    if not row or str(_uget(u, "role", "") or "") != "Cán bộ hỗ trợ" or str(key) != "new_cust":
        return row
    if str(row.get("customer_status") or "") != "PROSPECT" or row.get("qlkh_user_id") not in (None, ""):
        return row
    state_key = f"new_task_qlkh_{int(row['id'])}"
    qid = st.session_state.get(state_key)
    if qid in (None, ""):
        return row
    try:
        qid = int(qid)
    except Exception:
        return row
    ts = app_ns["now_str"]()
    with get_conn() as c:
        c.execute(
            "UPDATE customers SET qlkh_user_id=?,updated_at=? WHERE id=? AND customer_status='PROSPECT' AND qlkh_user_id IS NULL",
            (qid, ts, int(row["id"])),
        )
        changed = int(c.execute("SELECT changes()").fetchone()[0] or 0)
        if changed:
            try:
                c.execute(
                    "INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        int(_uget(u, "id")), "PROSPECT_ASSIGN_QLKH_FROM_OPERATIONS", "customer",
                        str(int(row["id"])), json.dumps({"qlkh_user_id": qid}, ensure_ascii=False), ts,
                    ),
                )
            except Exception:
                pass
    if changed:
        row = dict(row)
        row["qlkh_user_id"] = qid
        if logger:
            logger.info("P15_PROSPECT_OWNER_BOUND customer=%s qlkh=%s actor=%s", row["id"], qid, _uget(u, "id"))
    return row


def _render_duplicate_choice(st, u, app_ns, potential, key, pending, duplicates, logger=None):
    selected_key = f"{key}_selected_id"
    st.warning("Có khách hàng có thể đã tồn tại. Hãy chọn bản ghi hiện có nếu đúng khách hàng.")
    for row in duplicates:
        rid = int(row["id"])
        with st.container(border=True):
            st.markdown(f"**{_label(row)}**")
            reason = str(row.get("match_reason") or "Có khả năng trùng")
            st.caption(reason)
            if st.button("Dùng khách hàng này", key=f"{key}_dup_use_{rid}", use_container_width=True):
                st.session_state[selected_key] = rid
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
            app_ns["get_conn"], int(_uget(u, "id")), qlkh_user_id=owner,
            force=True, logger=logger, **pending,
        )
        st.session_state[selected_key] = int(cid)
        st.session_state.pop(f"{key}_prospect_pending", None)
        st.session_state.pop(f"{key}_prospect_dups", None)
        st.toast("Đã tạo khách hàng mới chưa có CIF và chọn để tác nghiệp.", icon="✅")
        st.rerun()


def _customer_selector(st, u, app_ns, potential, key="cust", required_message=None, logger=None):
    """Search-first selector with inline PROSPECT creation from the typed name."""
    get_conn = app_ns["get_conn"]
    potential.ensure_customer_master(get_conn, logger)
    selected_key = f"{key}_selected_id"
    query_key = f"{key}_query"
    pending_key = f"{key}_prospect_pending"
    dup_key = f"{key}_prospect_dups"

    selected_id = st.session_state.get(selected_key)
    if selected_id:
        chosen = _load_customer(get_conn, selected_id)
        if not chosen or not _eligible_customer(chosen.get("active"), chosen.get("customer_status")):
            st.session_state.pop(selected_key, None)
        else:
            chosen = _bind_support_prospect_owner(st, u, key, chosen, get_conn, app_ns, logger)
            st.success(f"Đã chọn: **{_label(chosen)}**")
            if not str(chosen.get("cif") or "").strip():
                st.caption("Khách hàng chưa có CIF · dùng chung với Kế hoạch. Admin có thể bổ sung CIF sau mà không đổi ID/lịch sử.")
            if st.button("Đổi khách hàng", key=f"{key}_clear"):
                st.session_state.pop(selected_key, None)
                st.session_state.pop(query_key, None)
                st.session_state.pop(pending_key, None)
                st.session_state.pop(dup_key, None)
                st.rerun()
            return chosen

    with st.container(key=f"customer_search_{key}"):
        query = st.text_input(
            "🔎 Tìm theo CIF hoặc Tên khách hàng",
            key=query_key,
            placeholder="Nhập CIF hoặc tên; nếu chưa có CIF có thể nhập tên để tạo khách hàng mới…",
        )
        if required_message:
            try:
                app_ns["required_error"](required_message)
            except Exception:
                st.error(str(required_message))

        q = str(query or "").strip()
        if not q:
            st.caption("Tìm khách hàng hiện có hoặc nhập tên khách hàng chưa có CIF để tạo mới.")
            return None

        hits = _search_customers(get_conn, q, limit=20)
        if hits:
            st.caption(f"Tìm thấy {len(hits)} kết quả. Khách hàng chưa có CIF được hiển thị cùng danh mục Kế hoạch.")
            for row in hits:
                rid = int(row["id"])
                cif_text = str(row.get("cif") or "").strip() or "Chưa có CIF"
                qlkh_text = str(row.get("qlkh_name") or "").strip()
                c1, c2, c3 = st.columns([1.4, 4.8, 1.2])
                c1.write(cif_text)
                c2.write(str(row.get("customer_name") or ""))
                if qlkh_text:
                    c2.caption(f"QLKH: {qlkh_text}")
                if c3.button("Chọn", key=f"{key}_pick_{rid}", use_container_width=True):
                    st.session_state[selected_key] = rid
                    st.session_state.pop(pending_key, None)
                    st.session_state.pop(dup_key, None)
                    st.rerun()
        else:
            st.info("Chưa có khách hàng phù hợp trong danh mục chung.")

        # Use the search phrase itself as the new customer name. Optional fields
        # stay compact so mobile users do not need a second name input.
        with st.expander("＋ Tạo khách hàng mới / chưa có CIF", expanded=not bool(hits)):
            st.caption(f"Tên sẽ tạo: **{q}** · Không sinh CIF giả.")
            a, b = st.columns(2)
            tax = a.text_input("MST (nếu có)", key=f"{key}_prospect_tax")
            phone = b.text_input("SĐT liên hệ (nếu có)", key=f"{key}_prospect_phone")
            contact = st.text_input("Người liên hệ (nếu có)", key=f"{key}_prospect_contact")
            if st.button(
                f"Tạo & chọn khách hàng: {q}",
                key=f"{key}_prospect_create",
                type="primary",
                use_container_width=True,
            ):
                payload = {
                    "name": q,
                    "tax_id": str(tax or "").strip(),
                    "contact_name": str(contact or "").strip(),
                    "contact_phone": str(phone or "").strip(),
                }
                with get_conn() as c:
                    duplicates = potential.find_similar(c, q, tax_id=tax)
                st.session_state[pending_key] = payload
                st.session_state[dup_key] = duplicates
                if not duplicates:
                    owner = _prospect_owner_id(u, key, st.session_state)
                    cid, _ = potential.create_prospect(
                        get_conn, int(_uget(u, "id")), qlkh_user_id=owner,
                        force=True, logger=logger, **payload,
                    )
                    st.session_state[selected_key] = int(cid)
                    st.session_state.pop(pending_key, None)
                    st.session_state.pop(dup_key, None)
                    st.toast("Đã tạo khách hàng mới chưa có CIF và chọn để tác nghiệp.", icon="✅")
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
            return _run_with_selector(original_support, u, *args, **kwargs)
        app_ns["support_page"] = support_page

    if original_qlkh:
        def qlkh_page(u, *args, **kwargs):
            return _run_with_selector(original_qlkh, u, *args, **kwargs)
        app_ns["qlkh_page"] = qlkh_page

    if original_leader:
        def leader_page(u, *args, **kwargs):
            return _run_with_selector(original_leader, u, *args, **kwargs)
        app_ns["leader_page"] = leader_page

    app_ns[_FLAG] = VERSION
    if logger or app_ns.get("LOGGER"):
        (logger or app_ns.get("LOGGER")).info(
            "PLANNING_OPERATIONAL_PHASE15_INSTALLED customer_search_parity=1 prospects_in_operations=1 roles=CBHT,QLKH,LEADER,ADMIN no_fake_cif=1 duplicate_guard=1"
        )
