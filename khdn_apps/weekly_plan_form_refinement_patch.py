"""Final Weekly Plan create-form refinement.

This layer is intentionally installed after weekly_priority_policy_hotfix so the
live Weekly Plan page cannot fall back to the older form/child-tab semantics.
"""
from __future__ import annotations

from datetime import date, timedelta
import html

from khdn_apps import planning_ui_v4_patch as nav4

VERSION = "1.0.0"


def _table_exists(c, name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (str(name),)).fetchone())


def _sync_legacy_focus_catalog(policy, c, scope, year):
    """Mirror legacy 'Danh mục công việc quan trọng' into the Q2 focus catalog.

    The legacy table remains the source the user already manages.  The mirrored
    row is scoped by leader/year so the Q2-first policy can retain historical
    snapshots without changing the legacy Customer Work schema.
    """
    if not _table_exists(c, "important_categories") or not _table_exists(c, "weekly_focus_categories"):
        return
    cols = policy._cols(c, "weekly_focus_categories")
    if "legacy_category_id" not in cols:
        c.execute("ALTER TABLE weekly_focus_categories ADD COLUMN legacy_category_id INTEGER")
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_wfc_legacy_scope ON weekly_focus_categories(department_key,apply_year,legacy_category_id)"
    )
    rows = [dict(r) for r in c.execute(
        "SELECT id,name,description,sort_order,active FROM important_categories ORDER BY sort_order,id"
    ).fetchall()]
    ts = policy._now()
    for r in rows:
        legacy_id = int(r["id"])
        hit = c.execute(
            "SELECT id,code FROM weekly_focus_categories WHERE department_key=? AND apply_year=? AND legacy_category_id=? LIMIT 1",
            (str(scope), int(year), legacy_id),
        ).fetchone()
        if hit:
            c.execute(
                """UPDATE weekly_focus_categories SET name=?,description=?,sort_order=?,active=?,updated_at=?
                   WHERE id=?""",
                (
                    str(r.get("name") or "").strip(), str(r.get("description") or "").strip(),
                    int(r.get("sort_order") or legacy_id), int(r.get("active") or 0), ts, int(hit["id"]),
                ),
            )
            continue
        code = f"TT{legacy_id:02d}"
        if c.execute(
            "SELECT 1 FROM weekly_focus_categories WHERE department_key=? AND apply_year=? AND code=?",
            (str(scope), int(year), code),
        ).fetchone():
            code = f"DM{legacy_id:03d}"
        c.execute(
            """INSERT INTO weekly_focus_categories(
               department_key,apply_year,code,name,description,sort_order,active,legacy_category_id,
               created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                str(scope), int(year), code, str(r.get("name") or "").strip(),
                str(r.get("description") or "").strip(), int(r.get("sort_order") or legacy_id),
                int(r.get("active") or 0), legacy_id, ts, ts,
            ),
        )


def _case_rows(c, customer_id, uid, manager=False):
    if not customer_id or not _table_exists(c, "customer_work_cases"):
        return []
    sql = """
        SELECT cw.id,cw.case_code,cw.title,cw.case_type,cw.owner_user_id,cw.expected_complete_at,
               COALESCE(ws.name,'') AS stage_name,COALESCE(u.full_name,'') AS owner_name
        FROM customer_work_cases cw
        LEFT JOIN work_stage_catalog ws ON ws.id=cw.current_stage_id
        LEFT JOIN users u ON u.id=cw.owner_user_id
        WHERE cw.customer_id=? AND cw.status='ACTIVE'
    """
    params = [int(customer_id)]
    if not manager:
        sql += " AND cw.owner_user_id=?"
        params.append(int(uid))
    sql += " ORDER BY CASE WHEN cw.expected_complete_at IS NULL THEN 1 ELSE 0 END,cw.expected_complete_at,cw.id"
    return [dict(r) for r in c.execute(sql, params).fetchall()]


def _leader_rows(c):
    return [dict(r) for r in c.execute(
        "SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name,id"
    ).fetchall()]


def _focus_picker(st, policy, focus_rows, prefix, due_date):
    focus_options = [None, "NONE"] + list(focus_rows or [])

    def _fmt(x):
        if x is None:
            return "— Chọn —"
        if x == "NONE":
            return "Không thuộc mục trọng tâm nào"
        return f"{x.get('code')} · {x.get('name')}"

    choice = st.selectbox(
        "1. Việc này thuộc danh mục công việc trọng tâm nào của phòng? *",
        focus_options, index=0, format_func=_fmt, key=f"{prefix}_focus",
        help="Danh sách lấy từ Danh mục công việc trọng tâm/quan trọng của phòng đang áp dụng trong năm.",
    )
    if isinstance(choice, dict):
        st.success("→ Tự động phân loại: Q2 · Trọng tâm.")
        return choice, None, None, 2
    if choice != "NONE":
        return None, None, None, None

    today = date.today()
    due7 = bool(due_date and due_date <= today + timedelta(days=7))
    if not due7:
        st.info("Ngày dự kiến hoàn thành ngoài 7 ngày tới → Q4 · Giá trị thấp.")
        return None, False, None, 4

    risk_choice = st.selectbox(
        "2. Việc này có gắn với chỉ tiêu được giao hoặc rủi ro trọng yếu không? *",
        [None, True, False], index=0,
        format_func=lambda x: "— Chọn —" if x is None else ("Có" if x else "Không"),
        key=f"{prefix}_risk",
    )
    if risk_choice is True:
        st.error("→ Tự động phân loại: Q1 · Cấp thiết.")
        return None, True, True, 1
    if risk_choice is False:
        st.warning("→ Tự động phân loại: Q3 · Phân tâm.")
        return None, True, False, 3
    return None, True, None, None


def _hard_tab_css(st, key, options, current):
    """Re-assert text colors after all theme CSS has been emitted."""
    rules = []
    prefix = nav4._escape_key(key)
    for idx, (value, _label) in enumerate(list(options or [])):
        bkey = f"cmdv4_{prefix}_{idx}_{nav4._escape_key(value)}"
        active = value == current
        fg = "#FFFFFF" if active else "#173B38"
        bg = "linear-gradient(135deg,#075C57 0%,#0F746B 100%)" if active else "#F3F1E3"
        border = "#F4B41A" if active else "#D8C77E"
        root = f"[data-testid='stAppViewContainer'] div[class*='st-key-{bkey}']"
        rules.append(
            f"{root} button{{background:{bg}!important;color:{fg}!important;-webkit-text-fill-color:{fg}!important;border-color:{border}!important;}}"
            f"{root} button *,{root} button p,{root} [data-testid='stMarkdownContainer'],{root} [data-testid='stMarkdownContainer'] *"
            f"{{color:{fg}!important;-webkit-text-fill-color:{fg}!important;opacity:1!important;text-shadow:none!important;}}"
        )
    if rules:
        st.markdown("<style>" + "".join(rules) + "</style>", unsafe_allow_html=True)


def install(policy, weekly_core, get_conn, logger=None):
    if getattr(policy, "_WEEKLY_PLAN_FORM_REFINEMENT_VERSION", None) == VERSION:
        return

    original_ensure = policy._ensure_schema
    original_focus_categories = policy._focus_categories
    original_cmd_nav = policy._cmd_nav

    def ensure_schema(core, conn_fn, logger_arg=None):
        original_ensure(core, conn_fn, logger_arg or logger)
        with conn_fn() as c:
            for name, ddl in (
                ("expected_complete_date", "TEXT"),
                ("controller_user_id", "INTEGER"),
                ("linked_case_id", "INTEGER"),
            ):
                if name not in policy._cols(c, "weekly_plan_items"):
                    c.execute(f"ALTER TABLE weekly_plan_items ADD COLUMN {name} {ddl}")
            c.execute("CREATE INDEX IF NOT EXISTS idx_wpi_linked_case ON weekly_plan_items(linked_case_id)")
            if "legacy_category_id" not in policy._cols(c, "weekly_focus_categories"):
                c.execute("ALTER TABLE weekly_focus_categories ADD COLUMN legacy_category_id INTEGER")
            c.execute("CREATE INDEX IF NOT EXISTS idx_wfc_legacy_scope ON weekly_focus_categories(department_key,apply_year,legacy_category_id)")

    policy._ensure_schema = ensure_schema

    def focus_categories(c, scope, year, include_inactive=False):
        _sync_legacy_focus_catalog(policy, c, scope, year)
        return original_focus_categories(c, scope, year, include_inactive)

    policy._focus_categories = focus_categories

    def cmd_nav(st, key, options, default):
        current = original_cmd_nav(st, key, options, default)
        _hard_tab_css(st, key, options, current)
        return current

    policy._cmd_nav = cmd_nav

    def summary(st, items):
        live = [x for x in items if x.get("status") != "CANCELLED"]
        counts = {q: sum(int(x.get("priority_quadrant") or 4) == q for x in live) for q in policy.PRIORITY_ORDER}
        total = max(1, len(live))
        targets = {2: "≥ 60%", 1: "≤ 20%", 3: "≤ 15%", 4: "≤ 5%"}
        cols = st.columns(4)
        for col, q in zip(cols, policy.PRIORITY_ORDER):
            pct = counts[q] / total * 100 if live else 0
            col.metric(policy.PRIORITY_SHORT[q], counts[q], f"{pct:.0f}% số việc · MT {targets[q]}")
        if live and counts[4] / len(live) > .20:
            st.warning("⚠ Tỷ trọng số việc Q4 vượt 20%. Hãy rà soát xem có việc nào thực chất thuộc danh mục trọng tâm không. Đây là cảnh báo mềm.")
        # Preserve the caller contract, but zero hours disables the legacy hour-based warning.
        return counts, {q: 0.0 for q in policy.PRIORITY_ORDER}, 0.0

    policy._summary = summary

    def item_card(st, x, editable=False):
        q = int(x.get("priority_quadrant") or 4)
        focus = str(x.get("focus_name_snapshot") or "")
        emergent = " · ⚡ PHÁT SINH" if int(x.get("is_emergent") or 0) else ""
        carry = f" · ↪ Chuyển tiếp {int(x.get('carryover_count') or 0)} lần" if int(x.get("carryover_count") or 0) else ""
        watch = " · 🚩 Q2 lùi ≥2 tuần" if int(x.get("q2_watch_flag") or 0) else ""
        with st.container(border=True):
            st.markdown(f"**{html.escape(str(x.get('title') or 'Công việc'))}**  \\n{policy.PRIORITY.get(q, q)}{emergent}{carry}{watch}")
            meta = [str(x.get("work_date") or "")[:10]]
            if x.get("expected_complete_date"):
                meta.append(f"Dự kiến hoàn thành {str(x.get('expected_complete_date'))[:10]}")
            if x.get("customer_text"):
                meta.append(str(x.get("customer_text")))
            if x.get("linked_case_id"):
                meta.append(f"CVKH #{int(x.get('linked_case_id'))}")
            st.caption(" · ".join(meta))
            if focus:
                st.caption(f"🎯 Trọng tâm: {x.get('focus_code_snapshot') or ''} · {focus}")
            if editable:
                return st.button("✏️ Sửa", key=f"policy_edit_{x['id']}")
        return False

    policy._item_card = item_card

    def add_item_form(st, u, core, conn_fn, ws, focus_rows, emergent=False, logger_arg=None):
        uid = int(policy._uget(u, "id"))
        epoch_key = f"wp_refine_epoch_{ws.isoformat()}_{'ps' if emergent else 'plan'}"
        epoch = int(st.session_state.get(epoch_key, 0) or 0)
        prefix = f"wp_refined_{ws.isoformat()}_{'ps' if emergent else 'plan'}_{epoch}"
        st.markdown("#### ⚡ Công việc phát sinh" if emergent else "#### ＋ Thêm công việc kế hoạch")

        with conn_fn() as c:
            customers = core.customers(c, uid)
            leaders = _leader_rows(c)
            inferred_leader = policy._leader_for_staff(c, uid)

        customer = st.selectbox(
            "Khách hàng",
            [None] + customers,
            index=0,
            format_func=lambda x: "— Không gắn khách hàng —" if x is None else f"{x.get('customer_name')} · {'CIF '+str(x.get('cif')) if x.get('cif') else 'Chưa có CIF'}",
            key=f"{prefix}_customer",
        )

        cases = []
        if customer:
            with conn_fn() as c:
                cases = _case_rows(c, int(customer["id"]), uid, policy._manager(u))

        linked_case = None
        if cases:
            linked_case = st.selectbox(
                "Công việc *",
                [None] + cases,
                index=0,
                format_func=lambda x: "— Chọn công việc đang xử lý —" if x is None else " · ".join(
                    p for p in [str(x.get("case_code") or ""), str(x.get("title") or ""), str(x.get("stage_name") or "")] if p
                ),
                key=f"{prefix}_case",
                help="Danh sách chỉ gồm công việc khách hàng đang còn dang dở của cán bộ này; Lãnh đạo/Admin xem được toàn bộ công việc đang xử lý của khách hàng.",
            )
            title = str(linked_case.get("title") or "").strip() if linked_case else ""
            if linked_case:
                st.caption(f"Đã liên kết {linked_case.get('case_code') or 'CVKH'} · {linked_case.get('stage_name') or 'Đang xử lý'}")
        else:
            title = st.text_input(
                "Công việc *", key=f"{prefix}_title",
                placeholder="Ví dụ: Gặp Công ty A – tiếp thị tiền gửi",
            )
            if customer:
                st.caption("Khách hàng chưa có công việc đang xử lý của cán bộ này; nhập công việc mới cho kế hoạch tuần.")

        day = st.date_input(
            "Ngày thực hiện *",
            value=max(ws, date.today()) if ws <= max(ws, date.today()) <= ws + timedelta(days=6) else ws,
            min_value=ws, max_value=ws + timedelta(days=6), key=f"{prefix}_day",
        )
        due_default = day
        if linked_case and linked_case.get("expected_complete_at"):
            try:
                due_default = date.fromisoformat(str(linked_case.get("expected_complete_at"))[:10])
                if due_default < day:
                    due_default = day
            except Exception:
                due_default = day
        due = st.date_input(
            "Ngày dự kiến hoàn thành *", value=due_default, min_value=day,
            key=f"{prefix}_due",
        )

        leader_options = [None] + leaders
        leader_idx = 0
        if inferred_leader:
            for i, row in enumerate(leader_options):
                if isinstance(row, dict) and int(row.get("id") or 0) == int(inferred_leader):
                    leader_idx = i
                    break
        leader = st.selectbox(
            "Lãnh đạo phòng phụ trách *", leader_options, index=leader_idx,
            format_func=lambda x: "— Chọn lãnh đạo phụ trách —" if x is None else str(x.get("full_name") or ""),
            key=f"{prefix}_leader",
        )

        # Refresh from the live source on every rerun so a newly-added catalog item appears immediately.
        with conn_fn() as c:
            scope = policy._scope_key(c, uid)
            live_focus_rows = policy._focus_categories(c, scope, ws.year, False)
        focus, due7, risk, q = _focus_picker(st, policy, live_focus_rows, prefix, due)

        ok = st.button(
            "Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch",
            key=f"{prefix}_save", type="primary", use_container_width=True,
        )
        if not ok:
            return

        missing = []
        if not str(title or "").strip():
            missing.append("Công việc")
        if due < day:
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
            "work_date": day.isoformat(), "start_time": None, "daypart": None,
            "title": str(title).strip(),
            "customer_id": int(customer["id"]) if customer else None,
            "customer_text": str(customer.get("customer_name") or "") if customer else "",
            "category": "Công việc phát sinh" if emergent else "Kế hoạch tuần",
            "purposes": [], "source_text": str(title).strip(), "linked_task_id": None,
            "note": None,
            # Compatibility values only; they are no longer shown/used for the Weekly Plan UX.
            "estimated_hours": 1.0, "expected_output": "",
            "is_emergent": 1 if emergent else 0,
            "focus_category_id": int(focus["id"]) if focus else None,
            "deadline_within_7d": due7, "kpi_risk_flag": risk,
        }
        iid, errs = policy._save_extended_item(core, conn_fn, uid, ws, item, logger_arg or logger)
        if not iid:
            st.error("; ".join(str(e) for e in (errs or ["Không thể lưu công việc"])))
            return
        with conn_fn() as c:
            c.execute(
                "UPDATE weekly_plan_items SET expected_complete_date=?,controller_user_id=?,linked_case_id=?,expected_output='' WHERE id=?",
                (due.isoformat(), int(leader["id"]), linked_case_id, int(iid)),
            )
        st.session_state[epoch_key] = epoch + 1
        st.toast("Đã thêm công việc vào kế hoạch.", icon="✅")
        st.rerun()

    policy._add_item_form = add_item_form
    policy._WEEKLY_PLAN_FORM_REFINEMENT_VERSION = VERSION
    if logger:
        logger.info("WEEKLY_PLAN_FORM_REFINEMENT_INSTALLED version=%s", VERSION)
