from __future__ import annotations

from difflib import SequenceMatcher
from datetime import date, datetime, time, timedelta
import json
import re
import unicodedata

VERSION = "1.0.0"


def _norm(v):
    s = unicodedata.normalize("NFD", str(v or "").strip().lower()).replace("đ", "d")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _cols(c, table):
    return {str(r[1]): dict(name=r[1], type=r[2], notnull=int(r[3] or 0), default=r[4], pk=int(r[5] or 0)) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_customer_master(get_conn, logger=None):
    """Allow a customer master row to exist before CIF is issued.

    Existing IDs are preserved.  Prospects stay in the same `customers` table,
    but active=0/customer_status=PROSPECT keeps them out of legacy Tác nghiệp
    pickers that require an official CIF.  Planning queries explicitly include
    prospects.  Once Admin supplies CIF, the same row becomes ACTIVE_CIF.
    """
    c = get_conn()
    try:
        tables = {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "customers" not in tables:
            return
        cols = _cols(c, "customers")
        cif_notnull = bool(cols.get("cif", {}).get("notnull"))
        if cif_notnull:
            c.commit()
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute("""
                    CREATE TABLE customers_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cif TEXT UNIQUE,
                        customer_name TEXT NOT NULL,
                        qlkh_user_id INTEGER,
                        qlkh_source_text TEXT,
                        active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT,
                        customer_status TEXT NOT NULL DEFAULT 'ACTIVE_CIF',
                        tax_id TEXT,
                        contact_name TEXT,
                        contact_phone TEXT,
                        prospect_created_by INTEGER,
                        prospect_created_at TEXT,
                        FOREIGN KEY(qlkh_user_id) REFERENCES users(id),
                        FOREIGN KEY(prospect_created_by) REFERENCES users(id)
                    )
                """)
                c.execute("""
                    INSERT INTO customers_new(
                        id,cif,customer_name,qlkh_user_id,qlkh_source_text,active,
                        created_at,updated_at,customer_status
                    )
                    SELECT id,cif,customer_name,qlkh_user_id,qlkh_source_text,active,
                           created_at,updated_at,'ACTIVE_CIF'
                    FROM customers
                """)
                c.execute("DROP TABLE customers")
                c.execute("ALTER TABLE customers_new RENAME TO customers")
                c.execute("CREATE INDEX IF NOT EXISTS idx_customers_active_cif ON customers(active,cif)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_customers_active_name ON customers(active,customer_name)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_customers_status_name ON customers(customer_status,customer_name)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_customers_tax_id ON customers(tax_id)")
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.execute("PRAGMA foreign_keys=ON")
        else:
            for name, ddl in [
                ("customer_status", "TEXT NOT NULL DEFAULT 'ACTIVE_CIF'"),
                ("tax_id", "TEXT"),
                ("contact_name", "TEXT"),
                ("contact_phone", "TEXT"),
                ("prospect_created_by", "INTEGER"),
                ("prospect_created_at", "TEXT"),
            ]:
                if name not in cols:
                    c.execute(f"ALTER TABLE customers ADD COLUMN {name} {ddl}")
            c.execute("UPDATE customers SET customer_status='ACTIVE_CIF' WHERE customer_status IS NULL OR trim(customer_status)='' OR cif IS NOT NULL")
            c.execute("CREATE INDEX IF NOT EXISTS idx_customers_status_name ON customers(customer_status,customer_name)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_customers_tax_id ON customers(tax_id)")
            c.commit()
        if logger:
            logger.info("POTENTIAL_CUSTOMER_SCHEMA_READY version=%s", VERSION)
    finally:
        c.close()


def planning_customers(c, uid=None):
    cols = _cols(c, "customers")
    has_status = "customer_status" in cols
    where = "(active=1 OR customer_status='PROSPECT')" if has_status else "active=1"
    fields = "id,cif,customer_name,qlkh_user_id"
    if has_status:
        fields += ",customer_status,tax_id,contact_name,contact_phone"
    if uid is None:
        rows = c.execute(f"SELECT {fields} FROM customers WHERE {where} ORDER BY CASE WHEN customer_status='PROSPECT' THEN 1 ELSE 0 END,customer_name" if has_status else f"SELECT {fields} FROM customers WHERE {where} ORDER BY customer_name").fetchall()
    else:
        order = "CASE WHEN qlkh_user_id=? THEN 0 ELSE 1 END,CASE WHEN customer_status='PROSPECT' THEN 1 ELSE 0 END,customer_name" if has_status else "CASE WHEN qlkh_user_id=? THEN 0 ELSE 1 END,customer_name"
        rows = c.execute(f"SELECT {fields} FROM customers WHERE {where} ORDER BY {order}", (int(uid),)).fetchall()
    return [dict(r) for r in rows]


def _candidate_rows(c):
    cols = _cols(c, "customers")
    fields = "id,cif,customer_name,qlkh_user_id,active"
    if "customer_status" in cols:
        fields += ",customer_status,tax_id,contact_name,contact_phone"
        where = "active=1 OR customer_status='PROSPECT'"
    else:
        where = "active=1"
    return [dict(r) for r in c.execute(f"SELECT {fields} FROM customers WHERE {where} ORDER BY customer_name").fetchall()]


def find_similar(c, name, tax_id=None, cif=None, limit=5):
    nn = _norm(name)
    ntax = _norm(tax_id)
    ncif = _norm(cif)
    out = []
    for r in _candidate_rows(c):
        rn = _norm(r.get("customer_name"))
        score = SequenceMatcher(None, nn, rn).ratio() if nn and rn else 0.0
        reasons = []
        if ncif and _norm(r.get("cif")) == ncif:
            score = 1.0; reasons.append("trùng CIF")
        if ntax and _norm(r.get("tax_id")) == ntax:
            score = max(score, 0.99); reasons.append("trùng MST")
        if nn and rn == nn:
            score = max(score, 0.98); reasons.append("trùng tên")
        elif nn and rn and score >= 0.86:
            reasons.append(f"tên gần giống {score:.0%}")
        if reasons or score >= 0.90:
            r = dict(r); r["match_score"] = score; r["match_reason"] = ", ".join(reasons) or f"tên gần giống {score:.0%}"
            out.append(r)
    out.sort(key=lambda x: (-float(x.get("match_score") or 0), str(x.get("customer_name") or "")))
    return out[:limit]


def create_prospect(get_conn, actor_uid, name, tax_id=None, contact_name=None, contact_phone=None, qlkh_user_id=None, force=False, logger=None):
    name = str(name or "").strip()
    if not name:
        raise ValueError("Tên khách hàng không được để trống")
    ensure_customer_master(get_conn, logger)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        dup = find_similar(c, name, tax_id=tax_id)
        if dup and not force:
            return None, dup
        cur = c.execute(
            """INSERT INTO customers(
                cif,customer_name,qlkh_user_id,qlkh_source_text,active,created_at,updated_at,
                customer_status,tax_id,contact_name,contact_phone,prospect_created_by,prospect_created_at
            ) VALUES(NULL,?,?,NULL,0,?,?, 'PROSPECT',?,?,?,?,?)""",
            (name, qlkh_user_id, ts, ts, str(tax_id or "").strip() or None,
             str(contact_name or "").strip() or None, str(contact_phone or "").strip() or None,
             int(actor_uid), ts),
        )
        cid = int(cur.lastrowid)
        try:
            c.execute("INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
                      (int(actor_uid), "PROSPECT_CUSTOMER_CREATE", "customer", str(cid), json.dumps({"name":name,"tax_id":tax_id},ensure_ascii=False), ts))
        except Exception:
            pass
    if logger:
        logger.info("PROSPECT_CUSTOMER_CREATE id=%s actor=%s", cid, actor_uid)
    return cid, []


def activate_customer(get_conn, actor_uid, customer_id, cif, name=None, tax_id=None, contact_name=None, contact_phone=None, qlkh_user_id=None, logger=None):
    cif = str(cif or "").strip()
    if not cif:
        raise ValueError("CIF chính thức không được để trống")
    ensure_customer_master(get_conn, logger)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        clash = c.execute("SELECT id,customer_name FROM customers WHERE cif=? AND id<>?", (cif, int(customer_id))).fetchone()
        if clash:
            raise ValueError(f"CIF đã tồn tại ở khách hàng: {clash['customer_name']}")
        row = c.execute("SELECT * FROM customers WHERE id=?", (int(customer_id),)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy khách hàng")
        c.execute("""UPDATE customers SET cif=?,customer_name=?,tax_id=?,contact_name=?,contact_phone=?,
                     qlkh_user_id=COALESCE(?,qlkh_user_id),customer_status='ACTIVE_CIF',active=1,updated_at=? WHERE id=?""",
                  (cif, str(name or row["customer_name"]).strip(), str(tax_id or "").strip() or None,
                   str(contact_name or "").strip() or None, str(contact_phone or "").strip() or None,
                   qlkh_user_id, ts, int(customer_id)))
        try:
            c.execute("INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
                      (int(actor_uid), "PROSPECT_CUSTOMER_ACTIVATE", "customer", str(customer_id), json.dumps({"cif":cif},ensure_ascii=False), ts))
        except Exception:
            pass
    if logger:
        logger.info("PROSPECT_CUSTOMER_ACTIVATE id=%s actor=%s cif=%s", customer_id, actor_uid, cif)
    return True


def _label(x):
    if not x:
        return "—"
    cif = str(x.get("cif") or "").strip()
    suffix = f"CIF {cif}" if cif else "Chưa có CIF · Tiềm năng"
    return f"{x.get('customer_name') or ''} · {suffix}"


def render_quick_add(st, u, get_conn, key, logger=None, select_state_key=None):
    """Inline zero-detour prospect creator with duplicate confirmation."""
    uid = int(u["id"])
    pending_key = f"{key}_pending"
    dup_key = f"{key}_dups"
    with st.expander("＋ Khách hàng mới / chưa có CIF", expanded=bool(st.session_state.get(pending_key))):
        st.caption("Tạo khách hàng tiềm năng để lập kế hoạch ngay. Không sinh CIF giả; Admin bổ sung CIF thật sau.")
        name = st.text_input("Tên khách hàng *", key=f"{key}_name")
        c1, c2 = st.columns(2)
        tax = c1.text_input("MST (nếu có)", key=f"{key}_tax")
        phone = c2.text_input("SĐT liên hệ (nếu có)", key=f"{key}_phone")
        contact = st.text_input("Người liên hệ (nếu có)", key=f"{key}_contact")
        if st.button("Kiểm tra & thêm khách hàng", key=f"{key}_check", type="primary", use_container_width=True):
            ensure_customer_master(get_conn, logger)
            with get_conn() as c:
                dup = find_similar(c, name, tax_id=tax)
            payload = {"name":name,"tax_id":tax,"contact_name":contact,"contact_phone":phone}
            st.session_state[pending_key] = payload
            st.session_state[dup_key] = dup
            if not dup:
                qid = uid if str(u.get("role") or "") == "Cán bộ QLKH" else None
                cid, _ = create_prospect(get_conn, uid, qlkh_user_id=qid, force=True, logger=logger, **payload)
                st.session_state.pop(pending_key, None); st.session_state.pop(dup_key, None)
                if select_state_key:
                    st.session_state[select_state_key] = cid
                st.toast("Đã thêm khách hàng tiềm năng vào danh mục chung.", icon="✅")
                st.rerun()
        dup = st.session_state.get(dup_key) or []
        pending = st.session_state.get(pending_key)
        if pending and dup:
            st.warning("Có khách hàng có thể đã tồn tại. Hãy dùng bản ghi cũ nếu đúng khách hàng.")
            for r in dup:
                with st.container(border=True):
                    st.markdown(f"**{_label(r)}**")
                    st.caption(str(r.get("match_reason") or "Có khả năng trùng"))
                    if st.button("Dùng khách hàng này", key=f"{key}_use_{r['id']}", use_container_width=True):
                        if select_state_key:
                            st.session_state[select_state_key] = int(r["id"])
                        st.session_state.pop(pending_key, None); st.session_state.pop(dup_key, None)
                        st.rerun()
            if st.button("Vẫn tạo mới", key=f"{key}_force", use_container_width=True):
                qid = uid if str(u.get("role") or "") == "Cán bộ QLKH" else None
                cid, _ = create_prospect(get_conn, uid, qlkh_user_id=qid, force=True, logger=logger, **pending)
                if select_state_key:
                    st.session_state[select_state_key] = cid
                st.session_state.pop(pending_key, None); st.session_state.pop(dup_key, None)
                st.toast("Đã tạo khách hàng tiềm năng mới.", icon="✅")
                st.rerun()


def render_admin_prospects(st, u, get_conn, logger=None):
    if not bool(u.get("is_admin")):
        return
    ensure_customer_master(get_conn, logger)
    with get_conn() as c:
        prospects = [dict(r) for r in c.execute("""SELECT c.*,u.full_name AS qlkh_name FROM customers c
            LEFT JOIN users u ON u.id=c.qlkh_user_id WHERE c.customer_status='PROSPECT'
            ORDER BY c.created_at DESC,c.id DESC""").fetchall()]
        qlkh = [dict(r) for r in c.execute("SELECT id,full_name FROM users WHERE active=1 AND role='Cán bộ QLKH' ORDER BY full_name").fetchall()]
    st.divider()
    st.subheader("🆕 Khách hàng tiềm năng / chưa có CIF")
    st.caption("Các bản ghi này nằm trong cùng danh mục khách hàng nhưng chưa được đưa vào Tác nghiệp. Bổ sung CIF để kích hoạt chính thức mà không mất lịch sử kế hoạch.")
    if not prospects:
        st.success("Không có khách hàng tiềm năng đang chờ bổ sung CIF.")
        return
    for p in prospects:
        with st.expander(f"{p.get('customer_name')} · Chưa có CIF", expanded=False):
            st.caption(f"MST: {p.get('tax_id') or '—'} · Liên hệ: {p.get('contact_name') or '—'} · {p.get('contact_phone') or '—'}")
            name = st.text_input("Tên khách hàng", value=p.get("customer_name") or "", key=f"pc_admin_name_{p['id']}")
            cif = st.text_input("CIF chính thức *", key=f"pc_admin_cif_{p['id']}")
            tax = st.text_input("MST", value=p.get("tax_id") or "", key=f"pc_admin_tax_{p['id']}")
            c1,c2 = st.columns(2)
            contact = c1.text_input("Người liên hệ", value=p.get("contact_name") or "", key=f"pc_admin_contact_{p['id']}")
            phone = c2.text_input("SĐT", value=p.get("contact_phone") or "", key=f"pc_admin_phone_{p['id']}")
            options = [None] + qlkh
            current = next((x for x in qlkh if int(x["id"]) == int(p.get("qlkh_user_id") or 0)), None)
            idx = options.index(current) if current in options else 0
            owner = st.selectbox("CB QLKH", options, index=idx, format_func=lambda x:"— Chưa gán —" if x is None else x["full_name"], key=f"pc_admin_owner_{p['id']}")
            if st.button("✓ Bổ sung CIF & kích hoạt", key=f"pc_admin_activate_{p['id']}", type="primary", use_container_width=True):
                try:
                    activate_customer(get_conn, int(u["id"]), int(p["id"]), cif, name=name, tax_id=tax, contact_name=contact, contact_phone=phone, qlkh_user_id=owner["id"] if owner else None, logger=logger)
                    st.toast("Đã kích hoạt khách hàng chính thức. Toàn bộ lịch sử kế hoạch được giữ nguyên.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def install(ns, customer_work, customer_ui, weekly_core, weekly_ui, logger=None):
    if getattr(customer_ui, "_POTENTIAL_CUSTOMER_PATCH_INSTALLED", False):
        return

    # App init owns base schema. Wrap it so CIF becomes nullable immediately after
    # base initialization on every runtime, including an empty preview database.
    original_init = ns["init_db"]
    def init_db():
        result = original_init()
        ensure_customer_master(ns["get_conn"], logger or ns.get("LOGGER"))
        return result
    ns["init_db"] = init_db

    # One customer master for both planning modules. Prospects are visible here;
    # legacy Tác nghiệp keeps using active=1 and therefore only official-CIF rows.
    customer_work.customers = planning_customers
    weekly_core.customers = lambda c, uid: planning_customers(c, uid)

    original_case_form = customer_ui._create_case_form
    def _create_case_form(st, u, get_conn, logger=None):
        ensure_customer_master(get_conn, logger)
        render_quick_add(st, u, get_conn, "cw_new_customer", logger, select_state_key="cw_customer_pick")
        uid = int(u["id"]); manager = customer_ui._manager(u)
        with get_conn() as c:
            cs = planning_customers(c, uid)
            stages = customer_work.active_stages(c)
            users = customer_work.staff_users(c) if manager else []
        if not cs:
            st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
            return
        preferred = st.session_state.get("cw_customer_pick")
        idx = next((i for i,x in enumerate(cs) if int(x["id"]) == int(preferred or -1)), 0)
        with st.form("cw_create_case", clear_on_submit=True):
            customer = st.selectbox("Khách hàng", cs, index=idx, format_func=_label)
            title = st.text_input("Công việc", placeholder="Ví dụ: Hạn mức tín dụng 2026 / Dự án A / Tiếp thị tiền gửi")
            c1,c2 = st.columns(2)
            due_date = c1.date_input("Dự kiến hoàn thành", value=date.today()+timedelta(days=7))
            due_time = c2.time_input("Giờ dự kiến", value=time(17,0))
            stage = st.selectbox("Mục công việc bắt đầu", stages, format_func=lambda x:x["name"])
            owner = st.selectbox("Cán bộ phụ trách", users, format_func=lambda x:f"{x['full_name']} · {x['role']}") if manager else None
            case_type = st.text_input("Nhóm công việc", placeholder="Tín dụng / Huy động / Dự án / Chăm sóc KH...")
            note = st.text_area("Ghi chú", height=80)
            ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)
        if ok:
            try:
                due = datetime.combine(due_date,due_time).strftime("%Y-%m-%d %H:%M:%S")
                cid,state = customer_work.create_case(get_conn,uid,customer["id"],title,due,owner_uid=owner["id"] if owner else uid,case_type=case_type,note=note,stage_id=stage["id"],logger=logger)
                st.session_state["cw_case_id"] = cid
                st.session_state.pop("cw_customer_pick", None)
                st.toast("Đã tạo công việc." if state=="APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    customer_ui._create_case_form = _create_case_form

    # Weekly page gets the same fast prospect creator before its normal controls.
    original_weekly_render = weekly_ui.render_page
    def weekly_render_page(st, u, get_conn, page_title=None, logger=None):
        ensure_customer_master(get_conn, logger)
        render_quick_add(st, u, get_conn, "wp_new_customer", logger, select_state_key=None)
        return original_weekly_render(st, u, get_conn, page_title=page_title, logger=logger)
    weekly_ui.render_page = weekly_render_page

    # System Admin keeps its legacy Users/Customer CIF page, with a dedicated
    # activation panel appended only on the Customer CIF destination.
    original_admin = ns["admin_page"]
    def admin_page(u):
        result = original_admin(u)
        if (st := ns["st"]) and bool(u.get("is_admin")) and st.session_state.get("main_page") == "admin" and str(st.session_state.get("admin_scope","system")) == "system" and st.session_state.get("admin_view") == "customers":
            render_admin_prospects(st, u, ns["get_conn"], logger or ns.get("LOGGER"))
        return result
    ns["admin_page"] = admin_page

    customer_ui._POTENTIAL_CUSTOMER_PATCH_INSTALLED = True
    if logger or ns.get("LOGGER"):
        (logger or ns.get("LOGGER")).info("POTENTIAL_CUSTOMER_PATCH_INSTALLED version=%s", VERSION)
