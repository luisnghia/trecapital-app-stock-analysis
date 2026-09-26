"""Planning usability V2.

Final runtime patch for the planning area.  It intentionally installs after all
previous weekly/customer-work patches and owns the last-mile UX requested by the
business:
- Loại công việc lives in System Admin, not Operational Admin;
- required Customer Work selectors start blank and include Q1..Q4 priority;
- Customer Work always enters at Processing and uses system-style button subnav;
- Catalog and Weekly inner views use the same system-style button navigation;
- Customer Work cards use a larger yellow detail action on the first row;
- prospect creation is visually prominent and duplicate detection uses name,
  token containment, MST, CIF and normalized phone; hard-key duplicates cannot
  be force-created.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher
import html
import json
import re

VERSION = "2.0.0"
CONTACT_ROLES = ["Giám đốc", "Chủ doanh nghiệp", "Kế toán trưởng/GĐ Tài chính", "Khác"]
PRIORITY = {
    1: "🔴 I · Quan trọng & Khẩn cấp",
    2: "🟠 II · Quan trọng & Chưa khẩn cấp",
    3: "🟡 III · Khẩn cấp & Không quan trọng",
    4: "🟢 IV · Không quan trọng & Chưa khẩn cấp",
}


def _cols(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _q(v):
    try:
        q = int(v)
    except Exception:
        return None
    return q if q in (1, 2, 3, 4) else None


def _priority_label(v):
    return PRIORITY.get(_q(v), "— Chọn mức ưu tiên —")


def _phone_key(v):
    d = re.sub(r"\D+", "", str(v or ""))
    if d.startswith("84") and len(d) >= 11:
        d = "0" + d[2:]
    return d


def _name_tokens(norm_text):
    stop = {
        "cong", "ty", "co", "phan", "tnhh", "mot", "thanh", "vien", "tap", "doan",
        "doanh", "nghiep", "tu", "nhan", "joint", "stock", "company", "limited", "ltd", "jsc",
    }
    return [x for x in str(norm_text or "").split() if x and x not in stop]


def _enhanced_find_similar(prospects, c, name, tax_id=None, cif=None, contact_phone=None, limit=8, exclude_id=None):
    nn = prospects._norm(name)
    ntax = prospects._norm(tax_id)
    ncif = prospects._norm(cif)
    nphone = _phone_key(contact_phone)
    nt = _name_tokens(nn)
    ns = set(nt)
    out = []
    for raw in prospects._candidate_rows(c):
        if exclude_id is not None and int(raw.get("id") or 0) == int(exclude_id):
            continue
        r = dict(raw)
        rn = prospects._norm(r.get("customer_name"))
        rt = _name_tokens(rn)
        rs = set(rt)
        seq = SequenceMatcher(None, nn, rn).ratio() if nn and rn else 0.0
        hard = False
        reasons = []
        score = seq

        if ncif and prospects._norm(r.get("cif")) == ncif:
            score = 1.0; hard = True; reasons.append("trùng CIF")
        if ntax and prospects._norm(r.get("tax_id")) == ntax:
            score = max(score, 0.995); hard = True; reasons.append("trùng MST")
        rp = _phone_key(r.get("contact_phone"))
        if nphone and rp and nphone == rp:
            score = max(score, 0.995); hard = True; reasons.append("trùng SĐT")

        if nn and rn == nn:
            score = max(score, 0.99); reasons.append("trùng tên")
        elif nt and rt:
            # Catch practical variants such as "Quang Đại Việt" vs "Đại Việt".
            short = ns if len(ns) <= len(rs) else rs
            long = rs if len(ns) <= len(rs) else ns
            contained = len(short) >= 2 and short.issubset(long)
            if contained:
                score = max(score, 0.96); reasons.append("tên chứa cùng cụm từ chính")
            else:
                inter = len(ns & rs)
                union = max(1, len(ns | rs))
                jaccard = inter / union
                if jaccard >= 0.72:
                    score = max(score, 0.93); reasons.append(f"tên có {jaccard:.0%} từ khóa trùng")
                elif seq >= 0.84:
                    reasons.append(f"tên gần giống {seq:.0%}")
        elif nn and rn and seq >= 0.84:
            reasons.append(f"tên gần giống {seq:.0%}")

        if reasons or score >= 0.90:
            r["match_score"] = score
            r["match_reason"] = ", ".join(dict.fromkeys(reasons)) or f"tên gần giống {score:.0%}"
            r["hard_duplicate"] = bool(hard)
            out.append(r)
    out.sort(key=lambda x: (not bool(x.get("hard_duplicate")), -float(x.get("match_score") or 0), str(x.get("customer_name") or "")))
    return out[:limit]


def _install_prospect_dedupe(prospects, logger=None):
    if getattr(prospects, "_PLANNING_USABILITY_DEDUPE", False):
        return
    original_create = prospects.create_prospect
    original_activate = prospects.activate_customer

    def find_similar(c, name, tax_id=None, cif=None, contact_phone=None, limit=8):
        return _enhanced_find_similar(prospects, c, name, tax_id, cif, contact_phone, limit)

    def create_prospect(get_conn, actor_uid, name, tax_id=None, contact_name=None, contact_phone=None,
                        qlkh_user_id=None, force=False, logger=None):
        name = str(name or "").strip()
        if not name:
            raise ValueError("Tên khách hàng không được để trống")
        prospects.ensure_customer_master(get_conn, logger)
        with get_conn() as c:
            dup = _enhanced_find_similar(prospects, c, name, tax_id, None, contact_phone, 8)
        hard = [x for x in dup if x.get("hard_duplicate")]
        if hard:
            return None, dup
        if dup and not force:
            return None, dup
        # Force only after the stronger guard above has passed.
        return original_create(
            get_conn, actor_uid, name, tax_id=tax_id, contact_name=contact_name,
            contact_phone=contact_phone, qlkh_user_id=qlkh_user_id, force=True, logger=logger,
        )

    def activate_customer(get_conn, actor_uid, customer_id, cif, name=None, tax_id=None,
                          contact_name=None, contact_phone=None, qlkh_user_id=None, logger=None):
        prospects.ensure_customer_master(get_conn, logger)
        with get_conn() as c:
            dup = _enhanced_find_similar(
                prospects, c, name or "", tax_id, cif, contact_phone, 8, exclude_id=customer_id
            )
        hard = [x for x in dup if x.get("hard_duplicate")]
        if hard:
            sample = hard[0]
            raise ValueError(f"Không thể kích hoạt vì trùng dữ liệu với khách hàng: {sample.get('customer_name')} ({sample.get('match_reason')}).")
        return original_activate(
            get_conn, actor_uid, customer_id, cif, name=name, tax_id=tax_id,
            contact_name=contact_name, contact_phone=contact_phone,
            qlkh_user_id=qlkh_user_id, logger=logger,
        )

    def render_quick_add(st, u, get_conn, key, logger=None, select_state_key=None):
        uid = int(u["id"])
        pending_key = f"{key}_pending"
        dup_key = f"{key}_dups"
        with st.container(key=f"prospect_quick_{key}"):
            st.markdown(
                f"""<style>
                div[class*='st-key-prospect_quick_{key}'] details{{border:2px solid #F4B41A!important;border-radius:13px!important;box-shadow:0 6px 18px rgba(244,180,26,.18)!important}}
                div[class*='st-key-prospect_quick_{key}'] details summary{{background:linear-gradient(90deg,rgba(244,180,26,.22),rgba(244,180,26,.08))!important;font-weight:950!important;color:#FFD45A!important}}
                div[class*='st-key-prospect_quick_{key}'] details summary:hover{{background:linear-gradient(90deg,rgba(244,180,26,.34),rgba(244,180,26,.13))!important}}
                </style>""",
                unsafe_allow_html=True,
            )
            with st.expander("➕  KHÁCH HÀNG MỚI / CHƯA CÓ CIF", expanded=bool(st.session_state.get(pending_key))):
                st.caption("App kiểm tra đồng thời tên gần giống, MST, CIF và SĐT trước khi cho tạo mới.")
                name = st.text_input("Tên khách hàng *", key=f"{key}_name")
                c1, c2 = st.columns(2)
                tax = c1.text_input("MST (nếu có)", key=f"{key}_tax")
                phone = c2.text_input("SĐT liên hệ (nếu có)", key=f"{key}_phone")
                contact = st.text_input("Người liên hệ (nếu có)", key=f"{key}_contact")
                if st.button("🔎 Kiểm tra & thêm khách hàng", key=f"{key}_check", type="primary", use_container_width=True):
                    if not str(name or "").strip():
                        st.error("Phải nhập tên khách hàng.")
                    else:
                        prospects.ensure_customer_master(get_conn, logger)
                        with get_conn() as c:
                            dup = _enhanced_find_similar(prospects, c, name, tax, None, phone, 8)
                        payload = {"name": name, "tax_id": tax, "contact_name": contact, "contact_phone": phone}
                        st.session_state[pending_key] = payload
                        st.session_state[dup_key] = dup
                        if not dup:
                            qid = uid if str(u.get("role") or "") == "Cán bộ QLKH" else None
                            cid, dup2 = create_prospect(get_conn, uid, qlkh_user_id=qid, force=True, logger=logger, **payload)
                            if cid:
                                st.session_state.pop(pending_key, None); st.session_state.pop(dup_key, None)
                                if select_state_key:
                                    st.session_state[select_state_key] = cid
                                st.toast("Đã thêm khách hàng tiềm năng vào danh mục chung.", icon="✅")
                                st.rerun()
                            elif dup2:
                                st.session_state[dup_key] = dup2

                dup = st.session_state.get(dup_key) or []
                pending = st.session_state.get(pending_key)
                if pending and dup:
                    hard = any(bool(x.get("hard_duplicate")) for x in dup)
                    if hard:
                        st.error("Phát hiện khách hàng trùng theo CIF/MST/SĐT. Hệ thống không cho tạo bản ghi mới; hãy dùng khách hàng đã có.")
                    else:
                        st.warning("Có khách hàng tên trùng/gần giống. Hãy kiểm tra kỹ trước khi xác nhận đây là khách hàng khác.")
                    for r in dup:
                        with st.container(border=True):
                            badge = "⛔ TRÙNG KHÓA" if r.get("hard_duplicate") else "⚠ CÓ THỂ TRÙNG"
                            st.markdown(f"**{badge} · {prospects._label(r)}**")
                            st.caption(str(r.get("match_reason") or "Có khả năng trùng"))
                            if st.button("✓ Dùng khách hàng này", key=f"{key}_use_{r['id']}", use_container_width=True):
                                if select_state_key:
                                    st.session_state[select_state_key] = int(r["id"])
                                st.session_state.pop(pending_key, None); st.session_state.pop(dup_key, None)
                                st.rerun()
                    if not hard and st.button("Tôi xác nhận đây là KH khác – vẫn tạo mới", key=f"{key}_force", use_container_width=True):
                        qid = uid if str(u.get("role") or "") == "Cán bộ QLKH" else None
                        cid, dup2 = create_prospect(get_conn, uid, qlkh_user_id=qid, force=True, logger=logger, **pending)
                        if cid:
                            if select_state_key:
                                st.session_state[select_state_key] = cid
                            st.session_state.pop(pending_key, None); st.session_state.pop(dup_key, None)
                            st.toast("Đã tạo khách hàng tiềm năng mới.", icon="✅")
                            st.rerun()
                        else:
                            st.session_state[dup_key] = dup2
                            st.error("Không thể tạo mới vì phát hiện khóa nhận diện bị trùng.")

    prospects.find_similar = find_similar
    prospects.create_prospect = create_prospect
    prospects.activate_customer = activate_customer
    prospects.render_quick_add = render_quick_add
    prospects._PLANNING_USABILITY_DEDUPE = True
    if logger:
        logger.info("PLANNING_USABILITY_DEDUPE_INSTALLED version=%s", VERSION)


def _ensure_case_priority(get_conn, customer_core, logger=None):
    customer_core.ensure_schema(get_conn, logger)
    with get_conn() as c:
        cols = _cols(c, "customer_work_cases")
        if "priority_quadrant" not in cols:
            c.execute("ALTER TABLE customer_work_cases ADD COLUMN priority_quadrant INTEGER")
        c.execute("""UPDATE customer_work_cases
                     SET priority_quadrant=CASE
                         WHEN COALESCE(is_important,0)=1 AND COALESCE(urgent_override,0)=1 THEN 1
                         WHEN COALESCE(is_important,0)=1 THEN 2
                         WHEN COALESCE(urgent_override,0)=1 THEN 3
                         ELSE 4 END
                     WHERE priority_quadrant IS NULL OR priority_quadrant NOT IN (1,2,3,4)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cw_priority ON customer_work_cases(priority_quadrant,status)")


def _set_case_priority(c, case_id, q, ts):
    q = int(q)
    important = 1 if q in (1, 2) else 0
    urgent = 1 if q in (1, 3) else 0
    c.execute(
        "UPDATE customer_work_cases SET priority_quadrant=?,is_important=?,urgent_override=?,updated_at=? WHERE id=?",
        (q, important, urgent, ts, int(case_id)),
    )


def _install_case_priority(customer_core, get_conn, logger=None):
    if getattr(customer_core, "_PLANNING_USABILITY_PRIORITY", False):
        return
    _ensure_case_priority(get_conn, customer_core, logger)
    original_ensure = customer_core.ensure_schema
    original_enrich = customer_core.enrich_case
    original_importance = customer_core.set_importance

    def ensure_schema(conn_fn, logger_arg=None):
        original_ensure(conn_fn, logger_arg or logger)
        with conn_fn() as c:
            if "priority_quadrant" not in _cols(c, "customer_work_cases"):
                c.execute("ALTER TABLE customer_work_cases ADD COLUMN priority_quadrant INTEGER")
            c.execute("""UPDATE customer_work_cases SET priority_quadrant=CASE
                WHEN COALESCE(is_important,0)=1 AND COALESCE(urgent_override,0)=1 THEN 1
                WHEN COALESCE(is_important,0)=1 THEN 2
                WHEN COALESCE(urgent_override,0)=1 THEN 3 ELSE 4 END
                WHERE priority_quadrant IS NULL OR priority_quadrant NOT IN (1,2,3,4)""")

    def enrich_case(x, reference=None):
        y = original_enrich(x, reference)
        pq = _q(y.get("priority_quadrant"))
        if pq:
            y["quadrant"] = pq
            y["is_important"] = 1 if pq in (1, 2) else 0
            y["is_urgent"] = pq in (1, 3)
        return y

    def set_importance(conn_fn, case_id, actor_uid, category_id=None, urgent_override=None, logger=None):
        result = original_importance(conn_fn, case_id, actor_uid, category_id, urgent_override, logger)
        if result:
            if category_id:
                q = 1 if bool(urgent_override) else 2
            elif urgent_override is not None:
                q = 3 if bool(urgent_override) else 4
            else:
                q = None
            if q:
                with conn_fn() as c:
                    _set_case_priority(c, case_id, q, customer_core.now_str())
        return result

    customer_core.ensure_schema = ensure_schema
    customer_core.enrich_case = enrich_case
    customer_core.set_importance = set_importance
    customer_core._PLANNING_USABILITY_PRIORITY = True


def _create_form(st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
    prospects = refinement.prospects
    worktype.ensure_worktype_scope(get_conn, logger)
    worktype.ensure_case_contacts(get_conn, logger)
    _ensure_case_priority(get_conn, customer_core, logger)
    prospects.ensure_customer_master(get_conn, logger)

    uid = int(u["id"])
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

    if not customers:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error("Chưa có Loại công việc thuộc **Kế hoạch**. Admin hãy tạo tại **Quản trị hệ thống → Loại công việc**.")
        return

    st.caption(f"Nhóm công việc lấy từ **Quản trị hệ thống → Loại công việc → Kế hoạch** · {len(types)} loại đang sử dụng.")
    preferred = st.session_state.get("cw_customer_pick")
    preferred_index = next((i for i, x in enumerate(customers) if int(x["id"]) == int(preferred or -1)), None)
    p = f"cwuv2_{epoch}_"

    with st.form(f"cwuv2_create_{epoch}", clear_on_submit=False):
        customer = st.selectbox(
            "Khách hàng *", customers, index=preferred_index,
            placeholder="— Chọn khách hàng —", format_func=prospects._label, key=p+"customer",
        )
        case_type = st.selectbox(
            "Nhóm công việc / Loại công việc *", types, index=None,
            placeholder="— Chọn loại công việc —", format_func=lambda x: x["name"], key=p+"type",
        )
        title = st.text_input("Công việc *", placeholder="Ví dụ: Cấp hạn mức tín dụng / Tiếp thị tiền gửi / Dự án A", key=p+"title")

        st.markdown("**Thông tin liên hệ bắt buộc**")
        c0, c1, c2 = st.columns([1.35, 1, 1.15])
        contact_name = c0.text_input("Người liên hệ *", key=p+"contact_name")
        contact_phone = c1.text_input("SĐT liên hệ *", key=p+"contact_phone")
        contact_role = c2.selectbox(
            "Chức vụ *", CONTACT_ROLES, index=None,
            placeholder="— Chọn chức vụ —", key=p+"contact_role",
        )

        priority = st.selectbox(
            "Ưu tiên góc phần tư *", [1, 2, 3, 4], index=None,
            placeholder="— Chọn Q1 / Q2 / Q3 / Q4 —", format_func=_priority_label, key=p+"priority",
            help="CBKH đề xuất mức ưu tiên khi tạo công việc; Lãnh đạo/Admin có thể điều chỉnh khi phê duyệt.",
        )
        c3, c4 = st.columns(2)
        due_date = c3.date_input("Dự kiến hoàn thành", value=date.today()+timedelta(days=7), key=p+"due_date")
        due_time = c4.time_input("Giờ dự kiến", value=time(17, 0), key=p+"due_time")
        stage = st.selectbox(
            "Mục công việc bắt đầu *", stages, index=None,
            placeholder="— Chọn mục công việc —", format_func=lambda x: x["name"], key=p+"stage",
        )
        owner = None
        if manager:
            owner = st.selectbox(
                "Cán bộ phụ trách *", users, index=None,
                placeholder="— Chọn cán bộ phụ trách —",
                format_func=lambda x: f"{x['full_name']} · {x['role']}", key=p+"owner",
            )
        note = st.text_area("Ghi chú", height=80, key=p+"note")
        ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

    if not ok:
        return
    errors = []
    if customer is None: errors.append("Khách hàng")
    if case_type is None: errors.append("Loại công việc")
    if not str(title or "").strip(): errors.append("Công việc")
    if not str(contact_name or "").strip(): errors.append("Người liên hệ")
    if not str(contact_phone or "").strip(): errors.append("SĐT liên hệ")
    if contact_role is None: errors.append("Chức vụ")
    if priority is None: errors.append("Ưu tiên góc phần tư")
    if stage is None: errors.append("Mục công việc bắt đầu")
    if manager and owner is None: errors.append("Cán bộ phụ trách")
    if errors:
        st.error("Vui lòng chọn/nhập đầy đủ: " + ", ".join(errors) + ".")
        return

    try:
        due = datetime.combine(due_date, due_time).strftime("%Y-%m-%d %H:%M:%S")
        cid, state = customer_core.create_case(
            get_conn, uid, customer["id"], str(title).strip(), due,
            owner_uid=owner["id"] if owner else uid,
            case_type=case_type["name"], note=note, stage_id=stage["id"], logger=logger,
        )
        ts = customer_core.now_str()
        with get_conn() as c:
            c.execute(
                "UPDATE customer_work_cases SET contact_name=?,contact_phone=?,contact_role=? WHERE id=?",
                (str(contact_name).strip(), str(contact_phone).strip(), str(contact_role), int(cid)),
            )
            _set_case_priority(c, cid, int(priority), ts)
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (int(cid), uid, "CREATE_METADATA", json.dumps({
                    "contact_name": str(contact_name).strip(),
                    "contact_phone": str(contact_phone).strip(),
                    "contact_role": contact_role,
                    "priority_quadrant": int(priority),
                }, ensure_ascii=False), ts),
            )

        # State-safe reset: the next create page gets a completely new widget namespace.
        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        st.session_state.pop("cw_case_id", None)
        st.session_state["cw_view"] = "processing"
        st.toast("Đã tạo công việc." if state == "APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.", icon="✅")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def _card(st, customer_ui, refinement, x, get_conn, uid, manager, logger=None, compact=False):
    q = _q(x.get("quadrant")) or 4
    heat = refinement._HEAT[q]
    status_text, status_color, status_bg = refinement._status_meta(x)
    customer = html.escape(str(x.get("customer_name") or "—"))
    case_type = html.escape(str(x.get("case_type") or x.get("title") or "Công việc"))
    title = html.escape(str(x.get("title") or ""))
    code = html.escape(str(x.get("case_code") or ""))
    owner = html.escape(str(x.get("owner_name") or "—"))
    stage = html.escape(str(x.get("stage_name") or "—"))
    elapsed = html.escape(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    due = html.escape(customer_ui._dt_text(x.get("expected_complete_at")))
    issues = int(x.get("open_issue_count") or 0)
    contact = html.escape(str(x.get("contact_name") or ""))
    contact_phone = html.escape(str(x.get("contact_phone") or ""))
    contact_role = html.escape(str(x.get("contact_role") or ""))
    approval = str(x.get("plan_approval_status") or "PENDING")
    cid = int(x["id"])

    with st.container(key=f"cwuv2_card_{cid}", border=True):
        c1, c2, c3 = st.columns([5.5, 1.5, 3.0], vertical_alignment="top")
        with c1:
            st.markdown(
                f"<div class='cwuv2-title'>{customer} <span>·</span> {case_type}</div>"
                + (f"<div class='cwuv2-work'>📌 {title}</div>" if title and title.casefold() != case_type.casefold() else ""),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"<div class='cwuv2-code'>{code}</div>", unsafe_allow_html=True)
        with c3:
            if not compact and st.button("🔎 Chi tiết", key=f"cwuv2_open_{cid}", use_container_width=True):
                st.session_state["cw_case_id"] = cid
                st.rerun()

        st.markdown(
            f"<div class='cwuv2-row'><span>👤 <b>{owner}</b></span><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span>"
            f"<span class='cwuv2-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>"
            f"<div class='cwuv2-row'><span>🎯 <b>Dự kiến:</b> {due}</span><span>⚠ <b>Vướng mắc:</b> {issues}</span>"
            f"<span class='cwuv2-pill' style='color:{heat['accent']};background:{heat['bg']};border:1px solid {heat['border']}'>{_priority_label(q)}</span></div>"
            + (f"<div class='cwuv2-contact'>☎ <b>{contact}</b> · {contact_role} · {contact_phone}</div>" if contact or contact_phone else "")
            + f"""<style>
            div[class*='st-key-cwuv2_card_{cid}']{{border-left:6px solid {heat['accent']}!important;background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;box-shadow:0 6px 16px rgba(0,0,0,.09)}}
            div[class*='st-key-cwuv2_card_{cid}'] button{{background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #FFE589!important;font-weight:950!important;min-height:2.25rem!important}}
            div[class*='st-key-cwuv2_card_{cid}'] button *{{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important}}
            .cwuv2-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}.cwuv2-title span{{opacity:.7}}
            .cwuv2-work{{font-size:.82rem;font-weight:750;margin-top:3px}}.cwuv2-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .cwuv2-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px}}.cwuv2-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}
            .cwuv2-contact{{font-size:.80rem;margin-top:7px;opacity:.94}}
            @media(max-width:760px){{.cwuv2-title{{font-size:.96rem}}.cwuv2-row,.cwuv2-contact{{font-size:.76rem}}.cwuv2-code{{text-align:left}}}}
            </style>""",
            unsafe_allow_html=True,
        )
        if approval == "PENDING":
            st.warning("Kế hoạch công việc đang chờ phê duyệt.")
        elif approval == "REJECTED":
            st.error("Kế hoạch đã bị từ chối." + (f" {x.get('approval_note')}" if x.get("approval_note") else ""))


def _render_cases_page(st, u, get_conn, customer_core, customer_ui, refinement, worktype, pill_nav, page_title=None, logger=None):
    _ensure_case_priority(get_conn, customer_core, logger)
    uid = int(u["id"]); manager = customer_ui._manager(u)
    if page_title:
        page_title("Công việc khách hàng", "Theo dõi xuyên suốt từ tiếp cận đến hoàn thành")
    else:
        st.title("👥 Công việc khách hàng")
    if st.session_state.get("cw_case_id"):
        customer_ui._case_detail(st, u, get_conn, int(st.session_state["cw_case_id"]), logger)
        customer_ui._glossary(st)
        return

    view = pill_nav(
        "cw_view",
        [("processing", "📋 Đang xử lý"), ("new", "➕ Tạo công việc mới")],
        default="processing", prefix="subnav_customer_work_v2",
    )
    if view == "new":
        _create_form(st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger)
        customer_ui._glossary(st)
        return

    with get_conn() as c:
        data = customer_core.list_cases(c, uid=uid, manager=manager, include_completed=False)
    f1, f2 = st.columns(2)
    stages = sorted({x.get("stage_name") for x in data if x.get("stage_name")})
    sf = f1.selectbox("Lọc mục công việc", ["Tất cả"] + stages, key="cw_filter_stage_v2")
    search = f2.text_input("Tìm khách hàng/công việc", key="cw_filter_text_v2")
    ss = str(search or "").lower().strip()
    shown = [x for x in data if (sf == "Tất cả" or x.get("stage_name") == sf) and (
        not ss or ss in str(x.get("customer_name") or "").lower() or ss in str(x.get("cif") or "").lower()
        or ss in str(x.get("title") or "").lower() or ss in str(x.get("case_type") or "").lower()
    )]
    def due_key(x):
        return customer_core.parse_dt(x.get("expected_complete_at")) or datetime.max
    shown.sort(key=lambda x: (
        _q(x.get("quadrant")) or 4,
        0 if x.get("is_overdue") else 1,
        0 if x.get("is_stage_delayed") else 1,
        -int(x.get("open_issue_count") or 0), due_key(x), int(x.get("id") or 0),
    ))
    if not shown:
        st.info("Không có công việc phù hợp.")
    for x in shown:
        customer_ui._case_card(st, x, get_conn, uid, manager, logger)
    customer_ui._glossary(st)


def _render_catalog(st, u, get_conn, customer_core, customer_ui, pill_nav, page_title=None, logger=None):
    customer_core.ensure_schema(get_conn, logger)
    uid = int(u["id"])
    if not customer_ui._manager(u):
        st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục."); return
    if page_title:
        page_title("Danh mục quy trình", "Mục công việc, SLA và danh mục công việc quan trọng")
    else:
        st.title("⚙️ Danh mục quy trình")
    view = pill_nav(
        "cw_catalog_view_v2",
        [("stages", "Mục công việc / SLA"), ("important", "Danh mục công việc quan trọng")],
        default="stages", prefix="subnav_catalog_v2",
    )

    if view == "stages":
        with get_conn() as c:
            stages = customer_core.active_stages(c, include_inactive=True)
        customer_ui._html_table(
            st, ["Thứ tự", "Mục công việc", "SLA (giờ)", "Kết thúc quy trình", "Trạng thái"],
            [[s["sort_order"], s["name"], f"{float(s['sla_hours']):.1f}", "Có" if s["is_completion"] else "Không", "Đang dùng" if s["active"] else "Ngưng"] for s in stages],
        )
        opts = [None] + stages
        edit = st.selectbox("Chọn mục công việc để sửa", opts, format_func=lambda x: "＋ Tạo mới" if x is None else x["name"], key="cw_stage_edit_v2")
        eid = int(edit["id"]) if edit else 0
        with st.form(f"cw_stage_form_v2_{eid}"):
            name = st.text_input("Tên mục công việc", value=edit["name"] if edit else "", key=f"cw_stage_name_v2_{eid}")
            order = st.number_input("Thứ tự", min_value=1, value=int(edit["sort_order"] if edit else len(stages)+1), step=1, key=f"cw_stage_order_v2_{eid}")
            sla = st.number_input("SLA cảnh báo (giờ)", min_value=0.0, value=float(edit["sla_hours"] if edit else 48), step=1.0, key=f"cw_stage_sla_v2_{eid}")
            done = st.checkbox("Đây là bước kết thúc quy trình", value=bool(edit["is_completion"]) if edit else False, key=f"cw_stage_done_v2_{eid}")
            active = st.checkbox("Đang sử dụng", value=bool(edit["active"]) if edit else True, key=f"cw_stage_active_v2_{eid}")
            save = st.form_submit_button("Lưu danh mục", type="primary")
        if save:
            try:
                customer_core.save_stage_catalog(get_conn, uid, edit["id"] if edit else None, name, order, sla, done, active, logger)
                st.toast("Đã lưu mục công việc.", icon="✅"); st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if edit and st.button("Xóa/Ngưng sử dụng mục này", key=f"cw_stage_del_v2_{eid}"):
            mode = customer_core.delete_stage_catalog(get_conn, uid, edit["id"], logger)
            st.toast("Đã xóa." if mode == "DELETE" else "Mục đã có lịch sử nên được ngưng sử dụng.", icon="✅"); st.rerun()
    else:
        st.info("Danh mục quan trọng là danh sách nhóm. Khi gán vào công việc, mặc định là **Q2 – Quan trọng & Chưa khẩn cấp**.")
        with get_conn() as c:
            cats = customer_core.active_important_categories(c, include_inactive=True)
        customer_ui._html_table(
            st, ["Thứ tự", "Danh mục quan trọng", "Diễn giải", "Trạng thái"],
            [[x["sort_order"], x["name"], x.get("description") or "—", "Đang dùng" if x["active"] else "Ngưng"] for x in cats],
        )
        opts = [None] + cats
        edit = st.selectbox("Chọn danh mục để sửa", opts, format_func=lambda x: "＋ Tạo mới" if x is None else x["name"], key="cw_cat_edit_v2")
        eid = int(edit["id"]) if edit else 0
        with st.form(f"cw_cat_form_v2_{eid}"):
            name = st.text_input("Tên danh mục", value=edit["name"] if edit else "", key=f"cw_cat_name_v2_{eid}")
            desc = st.text_area("Diễn giải", value=(edit.get("description") or "") if edit else "", key=f"cw_cat_desc_v2_{eid}")
            order = st.number_input("Thứ tự", min_value=1, value=int(edit["sort_order"] if edit else len(cats)+1), step=1, key=f"cw_cat_order_v2_{eid}")
            active = st.checkbox("Đang sử dụng", value=bool(edit["active"]) if edit else True, key=f"cw_cat_active_v2_{eid}")
            save = st.form_submit_button("Lưu danh mục", type="primary")
        if save:
            try:
                customer_core.save_important_category(get_conn, uid, edit["id"] if edit else None, name, desc, order, active, logger)
                st.toast("Đã lưu danh mục quan trọng.", icon="✅"); st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if edit and st.button("Xóa/Ngưng sử dụng danh mục", key=f"cw_cat_del_v2_{eid}"):
            mode = customer_core.delete_important_category(get_conn, uid, edit["id"], logger)
            st.toast("Đã xóa." if mode == "DELETE" else "Danh mục đã được dùng nên được ngưng sử dụng.", icon="✅"); st.rerun()
    customer_ui._glossary(st)


def _install_admin_location(ns, logger=None):
    st = ns["st"]
    original_pill = ns["pill_nav"]
    original_admin = ns["admin_page"]
    original_sidebar = ns["sidebar_navigation"]

    def pill_nav(state_key, options, default=None, prefix="subnav"):
        if state_key == "admin_view":
            page = st.session_state.get("main_page")
            bridge = bool(st.session_state.get("_system_type_bridge"))
            if page == "admin" or bridge:
                desired = [("users", "👥 Người dùng"), ("customers", "🏢 Khách hàng CIF"), ("types", "🧩 Loại công việc")]
                value = original_pill("system_admin_view_v2", desired, default="users", prefix="subnav_system_admin_v2")
                st.session_state["admin_view"] = value
                return value
            if page == "ops_admin":
                allowed = {"reasons", "audit", "backup"}
                filtered = [x for x in options if x[0] in allowed]
                if not filtered:
                    filtered = [("reasons", "🧩 Nhóm nguyên nhân")]
                value = original_pill("ops_admin_view_v2", filtered, default=filtered[0][0], prefix="subnav_ops_admin_v2")
                st.session_state["admin_view"] = value
                return value
        return original_pill(state_key, options, default=default, prefix=prefix)

    ns["pill_nav"] = pill_nav

    def sidebar_navigation(u):
        before = st.session_state.get("main_page")
        try:
            return original_sidebar(u)
        finally:
            page = st.session_state.get("main_page")
            if page == "admin":
                st.session_state["admin_scope"] = "system"
                desired = st.session_state.get("system_admin_view_v2", "users")
                st.session_state["admin_view"] = desired if desired in {"users", "customers", "types"} else "users"
            elif page == "ops_admin":
                st.session_state["admin_scope"] = "ops"
                allowed = {"reasons", "audit", "backup"} if bool(u.get("is_admin")) else {"reasons"}
                desired = st.session_state.get("ops_admin_view_v2", "reasons")
                st.session_state["admin_view"] = desired if desired in allowed else "reasons"
            if page == "customer_work" and before != "customer_work":
                st.session_state["cw_view"] = "processing"
                st.session_state.pop("cw_case_id", None)
    ns["sidebar_navigation"] = sidebar_navigation

    def admin_page(u):
        page = st.session_state.get("main_page")
        if page == "ops_admin":
            if st.session_state.get("admin_view") == "types":
                st.session_state["admin_view"] = "reasons"
                st.session_state["ops_admin_view_v2"] = "reasons"
            return original_admin(u)
        if page == "admin" and st.session_state.get("admin_view") == "types":
            # Existing type editor is already proven and includes module_scope.
            # Bridge it through its legacy operational route only for rendering;
            # navigation/title remain System Admin.
            old_page = page
            old_scope = st.session_state.get("admin_scope")
            old_title = ns.get("page_title")
            st.session_state["_system_type_bridge"] = True
            st.session_state["main_page"] = "ops_admin"
            st.session_state["admin_scope"] = "ops"
            st.session_state["admin_view"] = "types"
            if old_title:
                def system_title(_title, _subtitle):
                    return old_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF và loại công việc dùng chung cho Tác nghiệp/Kế hoạch.")
                ns["page_title"] = system_title
            try:
                return original_admin(u)
            finally:
                if old_title:
                    ns["page_title"] = old_title
                st.session_state["main_page"] = old_page
                st.session_state["admin_scope"] = old_scope or "system"
                st.session_state["admin_view"] = "types"
                st.session_state["system_admin_view_v2"] = "types"
                st.session_state.pop("_system_type_bridge", None)
        return original_admin(u)
    ns["admin_page"] = admin_page
    if logger:
        logger.info("PLANNING_USABILITY_ADMIN_LOCATION_INSTALLED version=%s", VERSION)


def _install_weekly_subnav(ns, weekly_ui, logger=None):
    if getattr(weekly_ui, "_PLANNING_USABILITY_SUBNAV", False):
        return
    st = ns["st"]
    pill_nav = ns["pill_nav"]
    original = weekly_ui.render_page

    def render_page(st_arg, u, get_conn, page_title=None, logger=None):
        original_radio = st_arg.radio
        def radio(label, options, *args, **kwargs):
            if label == "Chế độ xem":
                opts = [(str(x), str(x)) for x in list(options)]
                key = kwargs.get("key") or "wp_view"
                return pill_nav(key, opts, default=opts[0][0], prefix="subnav_weekly_v2")
            return original_radio(label, options, *args, **kwargs)
        st_arg.radio = radio
        try:
            return original(st_arg, u, get_conn, page_title=page_title, logger=logger)
        finally:
            st_arg.radio = original_radio

    weekly_ui.render_page = render_page
    weekly_ui._PLANNING_USABILITY_SUBNAV = True
    if logger:
        logger.info("PLANNING_USABILITY_WEEKLY_SUBNAV_INSTALLED version=%s", VERSION)


def _install_approval_priority(customer_core, customer_ui, weekly_core, get_conn, logger=None):
    def render_approvals_page(st, u, get_conn_arg, page_title=None, logger=None):
        _ensure_case_priority(get_conn_arg, customer_core, logger)
        weekly_core.ensure_schema(get_conn_arg, logger)
        uid = int(u["id"])
        if not customer_ui._manager(u):
            st.error("Chỉ Lãnh đạo/Admin được phê duyệt."); return
        if page_title:
            page_title("Phê duyệt", "Kế hoạch mới và các đề nghị dời thời gian")
        else:
            st.title("✅ Phê duyệt")
        with get_conn_arg() as c:
            plans, reschedules = customer_core.pending_case_approvals(c)
            try:
                weekly = [dict(r) for r in c.execute("""SELECT w.*,u.full_name,c.customer_name FROM weekly_plan_items w
                    JOIN users u ON u.id=w.user_id LEFT JOIN customers c ON c.id=w.customer_id
                    WHERE w.approval_status='PENDING' ORDER BY w.work_date,w.id""").fetchall()]
                weekly_moves = [dict(r) for r in c.execute("""SELECT r.*,w.title,w.customer_text,u.full_name AS requester_name
                    FROM weekly_plan_reschedule_requests r JOIN weekly_plan_items w ON w.id=r.item_id
                    JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
            except Exception:
                weekly = []; weekly_moves = []
        st.caption(f"Có {len(plans)+len(reschedules)+len(weekly)+len(weekly_moves)} đề nghị đang chờ xử lý.")

        st.subheader("Công việc khách hàng mới")
        if not plans:
            st.caption("Không có kế hoạch mới chờ phê duyệt.")
        for x in plans:
            with st.container(border=True):
                st.markdown(f"**{x.get('customer_name')} · {x.get('title')}**")
                st.caption(f"{x.get('owner_name')} · {x.get('stage_name')} · Dự kiến {customer_ui._dt_text(x.get('expected_complete_at'))}")
                current = _q(x.get("priority_quadrant")) or _q(x.get("quadrant")) or 4
                priority = st.selectbox("Mức ưu tiên khi duyệt", [1,2,3,4], index=current-1, format_func=_priority_label, key=f"ap_case_priority_v2_{x['id']}")
                note = st.text_input("Ý kiến", key=f"ap_case_note_v2_{x['id']}")
                a, b = st.columns(2)
                if a.button("✓ Phê duyệt", key=f"ap_case_yes_v2_{x['id']}", type="primary", use_container_width=True):
                    with get_conn_arg() as c:
                        _set_case_priority(c, x["id"], int(priority), customer_core.now_str())
                    customer_core.approve_case_plan(get_conn_arg, x["id"], uid, True, note, logger); st.rerun()
                if b.button("✕ Từ chối", key=f"ap_case_no_v2_{x['id']}", use_container_width=True):
                    customer_core.approve_case_plan(get_conn_arg, x["id"], uid, False, note, logger); st.rerun()

        st.subheader("Đề nghị dời thời gian công việc khách hàng")
        if not reschedules: st.caption("Không có đề nghị dời thời gian.")
        for r in reschedules:
            with st.container(border=True):
                st.markdown(f"**{r.get('customer_name')} · {r.get('title')}**")
                st.caption(f"{r.get('requester_name')} · {customer_ui._dt_text(r.get('old_due_at'))} → {customer_ui._dt_text(r.get('proposed_due_at'))}")
                st.write(f"Lý do: {r.get('reason')}")
                note = st.text_input("Ý kiến", key=f"ap_rs_note_v2_{r['id']}")
                a, b = st.columns(2)
                if a.button("✓ Phê duyệt", key=f"ap_rs_yes_v2_{r['id']}", type="primary", use_container_width=True): customer_core.decide_reschedule(get_conn_arg,r["id"],uid,True,note,logger); st.rerun()
                if b.button("✕ Từ chối", key=f"ap_rs_no_v2_{r['id']}", use_container_width=True): customer_core.decide_reschedule(get_conn_arg,r["id"],uid,False,note,logger); st.rerun()

        st.subheader("Kế hoạch tuần/ngày")
        st.caption("Lãnh đạo/Admin có thể điều chỉnh mức ưu tiên trước khi phê duyệt.")
        if not weekly: st.caption("Không có kế hoạch tuần/ngày chờ phê duyệt.")
        for w in weekly:
            with st.container(border=True):
                st.markdown(f"**{w.get('full_name')} · {w.get('title')}**")
                st.caption(f"Ngày {customer_ui._date_text(w.get('work_date'))} · {w.get('customer_name') or w.get('customer_text') or 'Nội bộ'}")
                current = _q(w.get("priority_quadrant")) or 4
                priority = st.selectbox("Mức ưu tiên khi duyệt", [1,2,3,4], index=current-1, format_func=_priority_label, key=f"ap_wp_priority_v2_{w['id']}")
                note = st.text_input("Ý kiến", key=f"ap_wp_note_v2_{w['id']}")
                a, b = st.columns(2)
                if a.button("✓ Phê duyệt", key=f"ap_wp_yes_v2_{w['id']}", type="primary", use_container_width=True):
                    ts = customer_core.now_str(); detail = json.dumps({"note":note,"priority_quadrant":int(priority)},ensure_ascii=False)
                    with get_conn_arg() as c:
                        c.execute("UPDATE weekly_plan_items SET priority_quadrant=?,approval_status='APPROVED',approved_by_user_id=?,approved_at=?,approval_note=? WHERE id=?",(int(priority),uid,ts,note,w["id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_APPROVE',?,?)",(w["id"],uid,detail,ts))
                    st.rerun()
                if b.button("✕ Từ chối", key=f"ap_wp_no_v2_{w['id']}", use_container_width=True):
                    ts = customer_core.now_str()
                    with get_conn_arg() as c:
                        c.execute("UPDATE weekly_plan_items SET approval_status='REJECTED',rejected_by_user_id=?,rejected_at=?,approval_note=? WHERE id=?",(uid,ts,note,w["id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_REJECT',?,?)",(w["id"],uid,note,ts))
                    st.rerun()

        st.subheader("Đề nghị dời kế hoạch tuần/ngày")
        if not weekly_moves: st.caption("Không có đề nghị dời kế hoạch.")
        for r in weekly_moves:
            with st.container(border=True):
                st.markdown(f"**{r.get('requester_name')} · {r.get('title')}**")
                st.caption(f"{customer_ui._date_text(r.get('old_work_date'))} → {customer_ui._date_text(r.get('proposed_work_date'))} · {r.get('customer_text') or 'Nội bộ'}")
                note = st.text_input("Ý kiến", key=f"ap_wpr_note_v2_{r['id']}")
                a, b = st.columns(2)
                if a.button("✓ Phê duyệt", key=f"ap_wpr_yes_v2_{r['id']}", type="primary", use_container_width=True):
                    ts = customer_core.now_str()
                    with get_conn_arg() as c:
                        c.execute("UPDATE weekly_plan_reschedule_requests SET status='APPROVED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",(uid,ts,note,r["id"]))
                        c.execute("UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?",(r["proposed_work_date"],ts,r["item_id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_APPROVE',?,?)",(r["item_id"],uid,note,ts))
                    st.rerun()
                if b.button("✕ Từ chối", key=f"ap_wpr_no_v2_{r['id']}", use_container_width=True):
                    ts = customer_core.now_str()
                    with get_conn_arg() as c:
                        c.execute("UPDATE weekly_plan_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",(uid,ts,note,r["id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_REJECT',?,?)",(r["item_id"],uid,note,ts))
                    st.rerun()
        customer_ui._glossary(st)

    customer_ui.render_approvals_page = render_approvals_page


def install(ns, customer_core, customer_ui, refinement, worktype, weekly_core, weekly_ui, prospects, logger=None):
    if getattr(customer_ui, "_PLANNING_USABILITY_V2_INSTALLED", False):
        return
    app_logger = logger or ns.get("LOGGER")
    get_conn = ns["get_conn"]

    _install_prospect_dedupe(prospects, app_logger)
    _install_case_priority(customer_core, get_conn, app_logger)
    _install_admin_location(ns, app_logger)
    _install_weekly_subnav(ns, weekly_ui, app_logger)
    _install_approval_priority(customer_core, customer_ui, weekly_core, get_conn, app_logger)

    pill_nav = ns["pill_nav"]
    refinement._create_form = lambda st,u,get_conn,customer_core_arg,ui,logger=None: _create_form(
        st,u,get_conn,customer_core_arg,ui,refinement,worktype,logger or app_logger
    )
    refinement._card = lambda st,ui,x,get_conn,uid,manager,logger=None,compact=False: _card(
        st,ui,refinement,x,get_conn,uid,manager,logger or app_logger,compact
    )

    def case_card(st_arg, x, get_conn_arg, uid, manager, logger_arg=None, compact=False):
        return _card(st_arg, customer_ui, refinement, x, get_conn_arg, uid, manager, logger_arg or app_logger, compact)
    customer_ui._case_card = case_card

    def create_case_form(st_arg, u, get_conn_arg, logger_arg=None):
        return _create_form(st_arg, u, get_conn_arg, customer_core, customer_ui, refinement, worktype, logger_arg or app_logger)
    customer_ui._create_case_form = create_case_form

    def render_cases_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return _render_cases_page(st_arg, u, conn_fn, customer_core, customer_ui, refinement, worktype, pill_nav, page_title, logger or app_logger)
    customer_ui.render_cases_page = render_cases_page

    def render_catalog_page(st, u, get_conn, page_title=None, logger=None):
        return _render_catalog(st, u, get_conn, customer_core, customer_ui, pill_nav, page_title, logger or app_logger)
    customer_ui.render_catalog_page = render_catalog_page

    customer_ui._PLANNING_USABILITY_V2_INSTALLED = True
    if app_logger:
        app_logger.info("PLANNING_USABILITY_V2_INSTALLED version=%s", VERSION)
