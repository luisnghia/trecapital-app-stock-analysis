"""Planning UX consolidation requested for the leader dashboard.

Guarantees:
- the regular Weekly Plan add form is hidden until a weekday quick-add button is clicked;
- the manager command strip no longer exposes a separate approval page;
- all plan/reschedule approval workflows render at the bottom of the leader dashboard;
- approval cards show the full business context needed before a decision.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import html

from khdn_apps import customer_work_patch as customer_nav
from khdn_apps import planning_week_board_focus_patch as weekboard

VERSION = "1.0.0"
_FLAG = "_PLANNING_DASHBOARD_CONSOLIDATION_VERSION"


def _dmy(value):
    if not value:
        return "—"
    s = str(value).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        try:
            return date.fromisoformat(s[:10]).strftime("%d/%m/%Y")
        except Exception:
            return s


def _dt(value):
    if not value:
        return "—"
    s = str(value).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return s


def _esc(value):
    return html.escape("—" if value is None or value == "" else str(value))


def _user_name(c, uid):
    if not uid:
        return "—"
    row = c.execute("SELECT full_name FROM users WHERE id=?", (int(uid),)).fetchone()
    return str(row[0]) if row and row[0] else f"ID {uid}"


def _info_grid(st, rows, key):
    """Render complete card metadata with st.html and wrapped cells."""
    cells = []
    for label, value in rows:
        cells.append(
            f"<div class='pd-info-cell'><span>{_esc(label)}</span><b>{_esc(value)}</b></div>"
        )
    st.html(
        f"""
        <div class="pd-info-grid pd-info-{_esc(key)}">{''.join(cells)}</div>
        <style>
          .pd-info-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:.45rem 0 .2rem 0;}}
          .pd-info-cell{{min-width:0;padding:8px 10px;border:1px solid rgba(120,160,150,.28);border-radius:9px;background:rgba(99,220,203,.035);white-space:normal;overflow-wrap:anywhere;}}
          .pd-info-cell span{{display:block;font-size:.70rem;opacity:.72;margin-bottom:2px;white-space:normal;overflow-wrap:anywhere;}}
          .pd-info-cell b{{display:block;font-size:.82rem;line-height:1.25;white-space:normal;overflow-wrap:anywhere;}}
          @media(max-width:900px){{.pd-info-grid{{grid-template-columns:repeat(2,minmax(0,1fr));}}}}
          @media(max-width:620px){{.pd-info-grid{{grid-template-columns:1fr;}}}}
        </style>
        """
    )


class _BoardOpenProxy:
    """Observe weekday quick-add clicks without changing the board implementation."""
    def __init__(self, st, ws):
        self._st = st
        self._ws = ws

    def __getattr__(self, name):
        return getattr(self._st, name)

    def button(self, label, *args, **kwargs):
        clicked = self._st.button(label, *args, **kwargs)
        key = str(kwargs.get("key") or "")
        if clicked and key.startswith("wkday_quick_add_"):
            self._st.session_state[f"wp_add_open_{self._ws.isoformat()}"] = True
        return clicked


def _render_case_approval_card(st, policy, customer_core, get_conn, x, uid, logger=None):
    with get_conn() as c:
        controller_name = _user_name(c, x.get("controller_user_id"))
    q = x.get("priority_quadrant") or x.get("quadrant")
    priority = customer_core.quadrant_label(q) if q else "—"
    focus = " · ".join(v for v in [str(x.get("focus_code_snapshot") or "").strip(), str(x.get("focus_name_snapshot") or "").strip()] if v) or "—"
    contact = " · ".join(v for v in [str(x.get("contact_name") or "").strip(), str(x.get("contact_role") or "").strip(), str(x.get("contact_phone") or "").strip()] if v) or "—"
    iid = int(x.get("id") or 0)
    with st.container(key=f"pd_case_approval_{iid}", border=True):
        st.markdown(f"**{_esc(x.get('customer_name'))} · {_esc(x.get('title'))}**")
        _info_grid(st, [
            ("Mã công việc", x.get("case_code") or f"CVKH-{iid}"),
            ("Khách hàng / CIF", " · ".join(v for v in [str(x.get("customer_name") or "").strip(), str(x.get("cif") or "").strip()] if v) or "—"),
            ("Nhóm / Loại công việc", x.get("case_type") or "—"),
            ("Mục công việc", x.get("stage_name") or "—"),
            ("Cán bộ phụ trách", x.get("owner_name") or "—"),
            ("Lãnh đạo kiểm soát", controller_name),
            ("Ngày tạo", _dt(x.get("created_at"))),
            ("Ngày dự kiến hoàn thành", _dmy(x.get("expected_complete_at"))),
            ("Ngày gửi phê duyệt", _dt(x.get("plan_requested_at"))),
            ("Phân loại ưu tiên", priority),
            ("Công việc trọng tâm", focus),
            ("Người liên hệ", contact),
            ("Ghi chú", x.get("note") or "—"),
        ], f"case-{iid}")
        note = st.text_input("Ý kiến phê duyệt", key=f"pd_case_note_{iid}")
        a, b = st.columns(2)
        if a.button("✓ Phê duyệt", key=f"pd_case_yes_{iid}", type="primary", use_container_width=True):
            customer_core.approve_case_plan(get_conn, iid, uid, True, note, logger)
            st.rerun()
        if b.button("✕ Từ chối", key=f"pd_case_no_{iid}", use_container_width=True):
            customer_core.approve_case_plan(get_conn, iid, uid, False, note, logger)
            st.rerun()


def _render_case_move_card(st, customer_core, get_conn, req, uid, logger=None):
    rid = int(req.get("id") or 0)
    with get_conn() as c:
        case = customer_core.get_case(c, int(req.get("case_id") or 0)) or {}
        requester_name = req.get("requester_name") or _user_name(c, req.get("requested_by"))
        controller_name = _user_name(c, case.get("controller_user_id"))
    q = case.get("priority_quadrant") or case.get("quadrant")
    priority = customer_core.quadrant_label(q) if q else "—"
    with st.container(key=f"pd_case_move_{rid}", border=True):
        st.markdown(f"**{_esc(case.get('customer_name') or req.get('customer_name'))} · {_esc(case.get('title') or req.get('title'))}**")
        _info_grid(st, [
            ("Mã công việc", case.get("case_code") or "—"),
            ("Cán bộ phụ trách", case.get("owner_name") or "—"),
            ("Lãnh đạo kiểm soát", controller_name),
            ("Mục công việc", case.get("stage_name") or "—"),
            ("Phân loại ưu tiên", priority),
            ("Người đề nghị", requester_name),
            ("Ngày dự kiến hiện tại", _dmy(req.get("old_due_at"))),
            ("Ngày đề nghị mới", _dmy(req.get("proposed_due_at"))),
            ("Thời điểm đề nghị", _dt(req.get("requested_at"))),
            ("Lý do dời", req.get("reason") or "—"),
            ("Ghi chú công việc", case.get("note") or "—"),
        ], f"case-move-{rid}")
        note = st.text_input("Ý kiến phê duyệt", key=f"pd_cr_note_{rid}")
        a, b = st.columns(2)
        if a.button("✓ Phê duyệt", key=f"pd_cr_yes_{rid}", type="primary", use_container_width=True):
            customer_core.decide_reschedule(get_conn, rid, uid, True, note, logger)
            st.rerun()
        if b.button("✕ Từ chối", key=f"pd_cr_no_{rid}", use_container_width=True):
            customer_core.decide_reschedule(get_conn, rid, uid, False, note, logger)
            st.rerun()


def _render_weekly_item_full(st, policy, x):
    iid = int(x.get("id") or 0)
    q = int(x.get("priority_quadrant") or 4)
    focus = " · ".join(v for v in [str(x.get("focus_code_snapshot") or "").strip(), str(x.get("focus_name_snapshot") or "").strip()] if v) or "—"
    with st.container(border=True):
        st.markdown(f"**{_esc(x.get('customer_text') or 'Không gắn khách hàng')} · {_esc(x.get('title') or 'Công việc')}**")
        _info_grid(st, [
            ("Mã kế hoạch", f"KHT-{iid:04d}" if iid else "KHT"),
            ("Phân loại ưu tiên", policy.PRIORITY_SHORT.get(q, str(q))),
            ("Công việc trọng tâm", focus),
            ("Cán bộ phụ trách", x.get("owner_name_snapshot") or x.get("owner_name") or "—"),
            ("Lãnh đạo kiểm soát", x.get("controller_name_snapshot") or x.get("controller_name") or "—"),
            ("Ngày tạo", _dt(x.get("created_at"))),
            ("Ngày thực hiện", _dmy(x.get("work_date"))),
            ("Ngày dự kiến hoàn thành", _dmy(x.get("expected_complete_date"))),
            ("Trạng thái", x.get("status") or "PLANNED"),
            ("Kết quả đầu ra", x.get("expected_output") or "—"),
            ("Nhóm công việc", x.get("category") or "—"),
            ("Liên kết công việc KH", f"CVKH #{int(x.get('linked_case_id'))}" if x.get("linked_case_id") else "—"),
            ("Căn cứ phân loại", x.get("priority_basis") or "—"),
            ("Số lần dời", int(x.get("reschedule_count") or 0)),
            ("Số lần chuyển tiếp", int(x.get("carryover_count") or 0)),
            ("Nguồn / Nội dung gốc", x.get("source_text") or "—"),
            ("Ghi chú", x.get("note") or "—"),
        ], f"weekly-{iid}")


def _render_approval_center(st, u, policy, weekly_core, customer_core, get_conn, logger=None):
    if not policy._manager(u):
        return
    policy._ensure_schema(weekly_core, get_conn, logger)
    customer_core.ensure_schema(get_conn, logger)
    uid = int(policy._uget(u, "id"))
    admin = policy._is_admin(u)

    with get_conn() as c:
        cases, moves = customer_core.pending_case_approvals(c)
        cases = [x for x in cases if policy._direct_scope_ok(c, uid, int(x.get("owner_user_id") or 0), admin)]
        plans = [dict(r) for r in c.execute(
            """SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id
               WHERE p.workflow_status='DA_NOP' ORDER BY p.week_start,u.full_name"""
        ).fetchall()]
        plans = [p for p in plans if policy._direct_scope_ok(c, uid, int(p.get("user_id") or 0), admin)]
        wmoves = [dict(r) for r in c.execute(
            """SELECT r.*,w.user_id,u.full_name AS requester_name
               FROM weekly_plan_reschedule_requests r
               JOIN weekly_plan_items w ON w.id=r.item_id
               JOIN users u ON u.id=r.requested_by
               WHERE r.status='PENDING' ORDER BY r.requested_at,r.id"""
        ).fetchall()]
        wmoves = [r for r in wmoves if policy._direct_scope_ok(c, uid, int(r.get("user_id") or r.get("requested_by") or 0), admin)]
        scoped_moves = []
        for r in moves:
            owner = c.execute("SELECT owner_user_id FROM customer_work_cases WHERE id=?", (int(r.get("case_id") or 0),)).fetchone()
            if owner and policy._direct_scope_ok(c, uid, int(owner[0]), admin):
                scoped_moves.append(r)
        moves = scoped_moves

    total = len(cases) + len(moves) + len(plans) + len(wmoves)
    st.divider()
    st.markdown("## ✅ Phê duyệt kế hoạch / dời hạn")
    st.caption(f"Toàn bộ đề nghị phê duyệt được xử lý ngay tại Điều hành kế hoạch phòng · {total} nội dung đang chờ.")

    st.subheader("Công việc khách hàng mới")
    if not cases:
        st.caption("Không có công việc khách hàng chờ phê duyệt.")
    for x in cases:
        _render_case_approval_card(st, policy, customer_core, get_conn, x, uid, logger)

    st.subheader("Kế hoạch tuần đã nộp")
    if not plans:
        st.caption("Không có kế hoạch tuần chờ duyệt.")
    for p in plans:
        ws = date.fromisoformat(str(p.get("week_start"))[:10])
        with get_conn() as c:
            items = [dict(r) for r in c.execute(
                "SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id",
                (int(p["id"]),),
            ).fetchall()]
            scope = policy._scope_key(c, int(p["user_id"]))
            cats = policy._focus_categories(c, scope, ws.year, False)
        with st.expander(f"{p.get('full_name')} · tuần {ws:%d/%m/%Y} · {len(items)} việc", expanded=True):
            _info_grid(st, [
                ("Cán bộ lập kế hoạch", p.get("full_name") or "—"),
                ("Tuần kế hoạch", f"{ws:%d/%m/%Y} – {(ws + timedelta(days=6)):%d/%m/%Y}"),
                ("Thời điểm nộp", _dt(p.get("submitted_at"))),
                ("Số công việc", len(items)),
            ], f"plan-{int(p['id'])}")
            policy._summary(st, items)
            policy._inline_focus_create(st, u, get_conn, ws.year, logger)
            for x in items:
                _render_weekly_item_full(st, policy, x)
                policy._manager_classification_editor(st, u, weekly_core, get_conn, p, x, cats, logger)
            decision = st.text_area("Ý kiến duyệt / lý do trả lại", key=f"pd_plan_note_{p['id']}")
            a, b = st.columns(2)
            if a.button("✓ Phê duyệt kế hoạch", key=f"pd_plan_yes_{p['id']}", type="primary", use_container_width=True):
                ts = policy._now()
                with get_conn() as c:
                    c.execute(
                        "UPDATE weekly_plans SET workflow_status='DA_DUYET',approved_at=?,approved_by=?,return_note=NULL,updated_at=? WHERE id=?",
                        (ts, uid, ts, int(p["id"])),
                    )
                    c.execute(
                        "UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE plan_id=? AND status<>'CANCELLED'",
                        (uid, ts, int(p["id"])),
                    )
                    policy._notify(c, int(p["user_id"]), "✅ Kế hoạch tuần đã được duyệt", f"Tuần {ws:%d/%m/%Y}. {decision or ''}".strip())
                st.rerun()
            if b.button("↩ Trả lại điều chỉnh", key=f"pd_plan_back_{p['id']}", use_container_width=True, disabled=not decision.strip()):
                ts = policy._now()
                with get_conn() as c:
                    c.execute(
                        "UPDATE weekly_plans SET workflow_status='TRA_LAI',returned_at=?,returned_by=?,return_note=?,updated_at=? WHERE id=?",
                        (ts, uid, decision.strip(), ts, int(p["id"])),
                    )
                    policy._notify(c, int(p["user_id"]), "↩ Kế hoạch tuần được trả lại", decision.strip())
                st.rerun()

    st.subheader("Đề nghị dời công việc khách hàng")
    if not moves:
        st.caption("Không có đề nghị dời ngày công việc khách hàng.")
    for r in moves:
        _render_case_move_card(st, customer_core, get_conn, r, uid, logger)

    st.subheader("Đề nghị dời kế hoạch tuần")
    if not wmoves:
        st.caption("Không có đề nghị dời kế hoạch tuần.")
    for r in wmoves:
        rid = int(r.get("id") or 0)
        with get_conn() as c:
            item_row = c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (int(r.get("item_id") or 0),)).fetchone()
            item = dict(item_row) if item_row else {}
        with st.container(key=f"pd_week_move_{rid}", border=True):
            _render_weekly_item_full(st, policy, item)
            _info_grid(st, [
                ("Người đề nghị", r.get("requester_name") or "—"),
                ("Ngày thực hiện hiện tại", _dmy(r.get("old_work_date"))),
                ("Ngày thực hiện đề nghị", _dmy(r.get("proposed_work_date"))),
                ("Thời điểm đề nghị", _dt(r.get("requested_at"))),
                ("Lý do dời", r.get("reason") or "—"),
            ], f"week-move-{rid}")
            note = st.text_input("Ý kiến phê duyệt", key=f"pd_wr_note_{rid}")
            a, b = st.columns(2)
            if a.button("✓ Phê duyệt", key=f"pd_wr_yes_{rid}", type="primary", use_container_width=True):
                ts = policy._now()
                with get_conn() as c:
                    c.execute(
                        "UPDATE weekly_plan_reschedule_requests SET status='APPROVED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",
                        (uid, ts, note, rid),
                    )
                    c.execute(
                        "UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?",
                        (r.get("proposed_work_date"), ts, int(r.get("item_id") or 0)),
                    )
                    c.execute(
                        "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_APPROVE',?,?)",
                        (int(r.get("item_id") or 0), uid, note, ts),
                    )
                st.rerun()
            if b.button("✕ Từ chối", key=f"pd_wr_no_{rid}", use_container_width=True):
                ts = policy._now()
                with get_conn() as c:
                    c.execute(
                        "UPDATE weekly_plan_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",
                        (uid, ts, note, rid),
                    )
                    c.execute(
                        "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_REJECT',?,?)",
                        (int(r.get("item_id") or 0), uid, note, ts),
                    )
                st.rerun()


def install(policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    # 1) Regular weekly create form stays hidden until a weekday quick-add button opens it.
    original_board = weekboard._render_week_board
    original_add = policy._add_item_form

    def render_week_board(st, policy_arg, get_conn, uid, ws, items, status):
        return original_board(_BoardOpenProxy(st, ws), policy_arg, get_conn, uid, ws, items, status)

    def add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False,
                      logger=None, logger_arg=None, **kwargs):
        if emergent:
            return original_add(st, u, core, get_conn, ws, focus_rows, emergent=True,
                                logger=logger, logger_arg=logger_arg, **kwargs)
        gate_key = f"wp_add_open_{ws.isoformat()}"
        if not st.session_state.get(gate_key):
            return None
        head, close = st.columns([6, 1])
        with head:
            st.caption("Biểu mẫu chỉ mở sau khi chọn ＋ Thêm công việc tại một ngày trong tuần.")
        with close:
            if st.button("✕ Đóng", key=f"wp_add_close_{ws.isoformat()}", use_container_width=True):
                st.session_state.pop(gate_key, None)
                st.session_state.pop(f"wp_quick_day_{ws.isoformat()}", None)
                st.rerun()
        return original_add(st, u, core, get_conn, ws, focus_rows, emergent=False,
                            logger=logger, logger_arg=logger_arg, **kwargs)

    weekboard._render_week_board = render_week_board
    policy._add_item_form = add_item_form

    # 2) Remove the separate manager approval command tab.
    original_plan_options = customer_nav._plan_options

    def plan_options(role, admin):
        return [(route, label) for route, label in original_plan_options(role, admin) if route != "work_approvals"]

    customer_nav._plan_options = plan_options

    # 3) Append the complete approval workflow to the bottom of the leader dashboard.
    original_dashboard = customer_ui.render_leader_dashboard

    def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None, **kwargs):
        result = original_dashboard(st=st, u=u, get_conn=get_conn, page_title=page_title, logger=logger, **kwargs)
        _render_approval_center(st, u, policy, weekly_core, customer_core, get_conn, logger)
        return result

    customer_ui.render_leader_dashboard = render_leader_dashboard

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_DASHBOARD_CONSOLIDATION_INSTALLED version=%s gated_weekly_add=1 approvals_embedded=1 approval_tab_removed=1 full_approval_cards=1",
            VERSION,
        )
