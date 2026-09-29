"""Operational planning Phase 5 refinements.

Adds:
- Admin-only unified System Admin navigation and dedicated Backup page behavior.
- Weekly-plan save fast path and auto-close after successful add.
- Weekly progress history and richer progress/late cards.
- Room weekly plan Monday-Friday board.
- Leader review/performance blocks moved to the bottom of Room Control.
- Compact in-card detail/progress actions and Planning-before-Operations sidebar order.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import time

from khdn_apps import backup_management_patch as backup
from khdn_apps import customer_work_patch as customer_nav
from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase3_weekly as p3week
from khdn_apps import planning_operational_phase4_patch as p4
from khdn_apps import weekly_performance_phase2_patch as phase2

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE5_VERSION"


def _fmt_action(action, detail):
    label = {
        "EXEC_UPDATE_PHASE3": "Cập nhật tiến độ",
        "EXEC_UPDATE_PHASE2": "Cập nhật tiến độ",
        "EXEC_UPDATE": "Cập nhật tiến độ",
        "RESCHEDULE_APPROVE": "Dời lịch được duyệt",
        "RESCHEDULE_REJECT": "Dời lịch bị từ chối",
        "PHAT_SINH": "Công việc phát sinh",
        "CLASSIFICATION_CHANGE": "Điều chỉnh phân loại",
        "DRAFT_REMOVE": "Bỏ khỏi bản nháp",
    }.get(str(action or ""), str(action or "Cập nhật"))
    txt = str(detail or "").strip()
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            old_s = obj.get("old_status")
            new_s = obj.get("new_status") or obj.get("status")
            note = obj.get("actual_result") or obj.get("note") or ""
            parts = []
            if old_s or new_s:
                parts.append(f"{old_s or '—'} → {new_s or '—'}")
            if note:
                parts.append(str(note))
            if parts:
                txt = " · ".join(parts)
    except Exception:
        pass
    return label, txt or "—"


def _fast_save_extended_item(policy, weekly_core, logger=None):
    def save_extended(core, get_conn, uid, ws, item, logger_arg=None):
        started = time.perf_counter()
        ts = policy._now()
        try:
            with get_conn() as c:
                pid = weekly_core.ensure_plan(c, int(uid), ws)
                cols = {str(r[1]) for r in c.execute("PRAGMA table_info(weekly_plan_items)").fetchall()}
                values = {
                    "plan_id": int(pid),
                    "user_id": int(uid),
                    "work_date": item["work_date"],
                    "start_time": item.get("start_time"),
                    "daypart": item.get("daypart"),
                    "title": str(item.get("title") or "").strip(),
                    "customer_id": item.get("customer_id"),
                    "customer_text": item.get("customer_text", ""),
                    "category": item.get("category", "Công việc khác"),
                    "purposes_json": json.dumps(item.get("purposes", []), ensure_ascii=False),
                    "source_text": item.get("source_text") or item.get("title"),
                    "linked_task_id": item.get("linked_task_id"),
                    "status": "PLANNED",
                    "reschedule_count": 0,
                    "note": item.get("note"),
                    "created_at": ts,
                    "updated_at": ts,
                    "estimated_hours": float(item.get("estimated_hours") or 1),
                    "actual_hours": float(item.get("actual_hours") or 0),
                    "expected_output": str(item.get("expected_output") or ""),
                    "is_emergent": int(bool(item.get("is_emergent"))),
                    "carryover_count": int(item.get("carryover_count") or 0),
                    "carried_from_item_id": item.get("carried_from_item_id"),
                }
                for name in (
                    "expected_complete_date", "controller_user_id", "linked_case_id",
                    "owner_name_snapshot", "controller_name_snapshot",
                ):
                    if name in item:
                        values[name] = item.get(name)

                values = {k: v for k, v in values.items() if k in cols}
                names = list(values)
                sql = (
                    "INSERT INTO weekly_plan_items(" + ",".join(names) + ") VALUES(" +
                    ",".join("?" for _ in names) + ")"
                )
                cur = c.execute(sql, tuple(values[n] for n in names))
                iid = int(cur.lastrowid)
                c.execute("UPDATE weekly_plans SET updated_at=? WHERE id=?", (ts, pid))
                policy._set_classification(
                    c, iid, int(uid), item.get("focus_category_id"),
                    item.get("deadline_within_7d"), item.get("kpi_risk_flag"),
                    reason="Phân loại khi tạo kế hoạch",
                )
                if int(item.get("is_emergent") or 0):
                    if "approval_status" in cols:
                        c.execute(
                            "UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE id=?",
                            (int(uid), ts, iid),
                        )
                    c.execute(
                        "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) "
                        "VALUES(?,?,'PHAT_SINH','Công việc phát sinh trong tuần',?)",
                        (iid, int(uid), ts),
                    )
            elapsed_ms = (time.perf_counter() - started) * 1000
            active_logger = logger_arg or logger
            if active_logger:
                active_logger.info("WEEKLY_PLAN_FAST_SAVE item=%s elapsed_ms=%.1f", iid, elapsed_ms)
            return iid, []
        except Exception as exc:
            active_logger = logger_arg or logger
            if active_logger:
                active_logger.exception("WEEKLY_PLAN_FAST_SAVE_FAILED")
            return None, [str(exc)]
    policy._save_extended_item = save_extended


class _AddCloseProxy:
    def __init__(self, st, ws):
        self._st = st
        self._ws = ws
        self._saved = False

    def __getattr__(self, name):
        return getattr(self._st, name)

    def toast(self, body, *args, **kwargs):
        if "Đã thêm công việc" in str(body):
            self._saved = True
        return self._st.toast(body, *args, **kwargs)

    def rerun(self, *args, **kwargs):
        if self._saved:
            self._st.session_state.pop(f"wp_add_open_{self._ws.isoformat()}", None)
            self._st.session_state.pop(f"wp_quick_day_{self._ws.isoformat()}", None)
            self._st.session_state.pop(f"p3_emergent_open_{self._ws.isoformat()}", None)
        return self._st.rerun(*args, **kwargs)


def _install_auto_close_add(policy, logger=None):
    original = policy._add_item_form

    def add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False,
                      logger=None, logger_arg=None, **kwargs):
        return original(
            _AddCloseProxy(st, ws), u, core, get_conn, ws, focus_rows,
            emergent=emergent, logger=logger, logger_arg=logger_arg, **kwargs
        )

    policy._add_item_form = add_item_form
    if logger:
        logger.info("P5_WEEK_ADD_AUTOCLOSE_INSTALLED")


def _parse_day(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def _enhanced_weekly_card(st, policy, weekly_core, item, prefix, can_update=False, can_edit=False):
    iid = int(item.get("id") or 0)
    q = int(item.get("priority_quadrant") or 4)
    heat = p3week.weekboard._HEAT.get(q, p3week.weekboard._HEAT[4])
    key = f"p5_wcard_{prefix}_{iid}"
    customer = item.get("customer_text") or item.get("master_customer_name") or "Công việc nội bộ"
    owner = item.get("owner_name_snapshot") or item.get("owner_name") or "—"
    controller = item.get("controller_name_snapshot") or item.get("controller_name") or "—"
    focus = item.get("focus_name_snapshot") or "Không thuộc trọng tâm"
    actual = item.get("actual_result") or ""
    status = str(item.get("status") or "PLANNED")
    due = _parse_day(item.get("expected_complete_date")) or _parse_day(item.get("work_date"))
    overdue = bool(due and due < date.today() and status not in {"DONE", "CANCELLED"})
    changed = bool(
        status not in {"PLANNED", "CANCELLED"}
        or actual
        or int(item.get("reschedule_count") or 0)
        or int(item.get("carryover_count") or 0)
        or int(item.get("q2_watch_flag") or 0)
    )
    accent = "#F04438" if overdue else "#F79009" if changed else heat["accent"]
    flags = []
    if overdue:
        flags.append("🔴 QUÁ HẠN")
    if status == "IN_PROGRESS":
        flags.append("🔄 ĐANG LÀM")
    if status == "DONE":
        flags.append("✅ HOÀN THÀNH")
    if int(item.get("reschedule_count") or 0):
        flags.append(f"↪ DỜI {int(item.get('reschedule_count') or 0)} LẦN")
    if int(item.get("carryover_count") or 0):
        flags.append(f"⏩ CHUYỂN TIẾP {int(item.get('carryover_count') or 0)} LẦN")
    if int(item.get("q2_watch_flag") or 0):
        flags.append("🚩 Q2 CẦN CHÚ Ý")

    with st.container(key=key, border=True):
        st.html(
            f"""
            <div class='p5w-title'>{p3dash.esc(item.get('title') or 'Công việc')}</div>
            <div class='p5w-customer'>🏢 {p3dash.esc(customer)}</div>
            <div class='p5w-row'><span style='color:{heat["accent"]};font-weight:950'>{p3dash.esc(heat["label"])}</span>
              <span>📅 {p3dash.esc(p3dash.dmy(item.get('work_date')))}</span>
              <span>🎯 Hạn {p3dash.esc(p3dash.dmy(item.get('expected_complete_date')))}</span></div>
            <div class='p5w-row'><span>👤 {p3dash.esc(owner)}</span><span>🛡️ {p3dash.esc(controller)}</span></div>
            <div class='p5w-row'><span>📌 {p3dash.esc(focus)}</span><span>📍 {p3dash.esc(p3week._status_label(weekly_core,status))}</span></div>
            {f"<div class='p5w-flags'>{p3dash.esc(' · '.join(flags))}</div>" if flags else ""}
            {f"<div class='p5w-result'>📝 {p3dash.esc(actual)}</div>" if actual else ""}
            <style>
            div[class*='st-key-{key}']{{border-left:6px solid {accent}!important;background:linear-gradient(120deg,{heat["bg"]},rgba(6,78,72,.06))!important}}
            .p5w-title{{font-weight:950;font-size:.90rem;line-height:1.25}}
            .p5w-customer{{font-size:.78rem;color:#63DCCB;font-weight:850;margin-top:4px}}
            .p5w-row{{display:flex;gap:7px 12px;flex-wrap:wrap;font-size:.72rem;margin-top:6px;white-space:normal;overflow-wrap:anywhere}}
            .p5w-flags{{font-size:.72rem;margin-top:6px;color:#FFD166;font-weight:950;white-space:normal;overflow-wrap:anywhere}}
            .p5w-result{{font-size:.72rem;margin-top:6px;color:#63DCCB;font-weight:850;white-space:normal;overflow-wrap:anywhere}}
            </style>
            """
        )
        if can_update:
            left, right = st.columns([3.4, 1.2])
            left.caption("Cập nhật trực tiếp trên công việc này.")
            with right:
                btn_key = f"p5_update_btn_{prefix}_{iid}"
                if st.button("🔄 Cập nhật", key=btn_key, use_container_width=True):
                    st.session_state["p3_update_week_item"] = iid
                    st.rerun()
                st.html(
                    f"""<style>div[class*='st-key-{btn_key}'] button{{
                    background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
                    color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
                    border:2px solid #FFE589!important;font-weight:950!important}}
                    div[class*='st-key-{btn_key}'] button *{{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}}</style>"""
                )
        if can_edit:
            left, right = st.columns([3.4, 1.2])
            left.caption("Lãnh đạo có thể điều chỉnh trực tiếp.")
            with right:
                if st.button("✏️ Điều chỉnh", key=f"p5_edit_btn_{prefix}_{iid}", use_container_width=True):
                    st.session_state["p3_manager_edit_week_item"] = iid
                    st.rerun()


def _history_rows(get_conn, iid):
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            """SELECT a.*,u.full_name AS actor_name
               FROM weekly_plan_actions a LEFT JOIN users u ON u.id=a.actor_user_id
               WHERE a.item_id=? ORDER BY a.id DESC LIMIT 30""",
            (int(iid),),
        ).fetchall()]


def _enhanced_update_form(st, u, policy, weekly_core, get_conn, item, logger=None):
    iid = int(item["id"])
    uid = int(policy._uget(u, "id"))
    if int(item.get("user_id") or 0) != uid:
        return
    history = _history_rows(get_conn, iid)
    with st.container(border=True):
        st.markdown(f"#### 🔄 Cập nhật tiến độ · {item.get('title')}")
        st.markdown("##### 🕘 Lịch sử thay đổi / cập nhật tiến độ")
        if not history:
            st.caption("Chưa có lịch sử cập nhật.")
        else:
            for row in history[:6]:
                label, detail = _fmt_action(row.get("action"), row.get("detail"))
                st.html(
                    f"""<div class='p5hist'><b>{p3dash.esc(label)}</b> · {p3dash.esc(row.get('actor_name') or '—')} ·
                    {p3dash.esc(p3dash.dt(row.get('created_at')))}<br><span>{p3dash.esc(detail)}</span></div>
                    <style>.p5hist{{padding:7px 9px;margin:5px 0;border-left:4px solid #F4B41A;background:rgba(244,180,26,.08);
                    border-radius:7px;font-size:.76rem;white-space:normal;overflow-wrap:anywhere}}.p5hist span{{color:#63DCCB;font-weight:750}}</style>"""
                )
            if len(history) > 6:
                with st.expander(f"Xem toàn bộ {len(history)} cập nhật", expanded=False):
                    for row in history[6:]:
                        label, detail = _fmt_action(row.get("action"), row.get("detail"))
                        st.caption(f"{p3dash.dt(row.get('created_at'))} · {row.get('actor_name') or '—'} · {label} · {detail}")

        labels = {"PLANNED":"Chưa làm","IN_PROGRESS":"Đang làm","DONE":"Hoàn thành","CANCELLED":"Hủy"}
        opts = list(labels)
        cur = str(item.get("status") or "PLANNED")
        stat = st.selectbox(
            "Trạng thái", opts, index=opts.index(cur) if cur in opts else 0,
            format_func=lambda z: labels[z], key=f"p5_status_{iid}"
        )
        result = st.text_area(
            "Kết quả thực tế / ghi chú", value=str(item.get("actual_result") or ""),
            max_chars=1000, key=f"p5_result_{iid}"
        )
        a,b = st.columns(2)
        if a.button("Lưu cập nhật", key=f"p5_update_save_{iid}", type="primary", use_container_width=True):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            completed = item.get("completed_at")
            if stat == "DONE" and not completed:
                completed = ts
            if stat != "DONE":
                completed = None
            detail = json.dumps(
                {"old_status": cur, "new_status": stat, "actual_result": str(result or "").strip()},
                ensure_ascii=False,
            )
            with get_conn() as c:
                c.execute(
                    "UPDATE weekly_plan_items SET status=?,actual_result=?,completed_at=?,updated_at=? WHERE id=? AND user_id=?",
                    (stat, str(result or "").strip(), completed, ts, iid, uid),
                )
                c.execute(
                    "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'EXEC_UPDATE_PHASE3',?,?)",
                    (iid, uid, detail, ts),
                )
            if logger:
                logger.info("P5_WEEK_PROGRESS_UPDATE item=%s actor=%s status=%s", iid, uid, stat)
            st.session_state.pop("p3_update_week_item", None)
            st.rerun()
        if b.button("Đóng", key=f"p5_update_close_{iid}", use_container_width=True):
            st.session_state.pop("p3_update_week_item", None)
            st.rerun()


def _install_weekly_card_and_history(logger=None):
    p3week.weekly_card = _enhanced_weekly_card
    p3week.render_week_update_form = _enhanced_update_form
    if logger:
        logger.info("P5_WEEKLY_CARD_HISTORY_INSTALLED")


def _room_week_dashboard(st, u, policy, weekly_core, get_conn, ws, logger=None):
    leader_uid = int(policy._uget(u, "id"))
    admin = policy._is_admin(u)
    with get_conn() as c:
        plans = [dict(r) for r in c.execute(
            """SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id
               WHERE p.week_start=? AND u.active=1 ORDER BY u.full_name""",
            (ws.isoformat(),),
        ).fetchall()]
        plans = [p for p in plans if policy._direct_scope_ok(c, leader_uid, p["user_id"], admin)]
        cats = policy._focus_categories(c, policy._scope_key(c, leader_uid), ws.year, False)

    st.subheader("👥 Kế hoạch phòng · Thứ 2 → Thứ 6")
    if not plans:
        st.info("Chưa có kế hoạch của cán bộ trong tuần này.")
    total_items = 0
    emergent = 0
    for p in plans:
        with get_conn() as c:
            items = [dict(r) for r in c.execute(
                "SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id",
                (int(p["id"]),),
            ).fetchall()]
        total_items += len(items)
        emergent += sum(int(x.get("is_emergent") or 0) for x in items)
        status = str(p.get("workflow_status") or "NHAP")
        with st.expander(
            f"{p.get('full_name')} · {policy.PLAN_STATUS.get(status,status)} · {len(items)} việc",
            expanded=True,
        ):
            policy._summary(st, items)
            can_adjust = status in ("DA_NOP", "DA_DUYET") or (
                status == "DA_CHOT" and not int(p.get("classification_locked") or 0)
            )
            p3week.render_week_board(
                st, policy, weekly_core, get_conn, int(p["user_id"]), ws,
                items, status, manager_edit=can_adjust,
            )
            selected = st.session_state.get("p3_manager_edit_week_item")
            if selected and can_adjust:
                item = next((x for x in items if int(x.get("id") or 0) == int(selected)), None)
                if item:
                    p3week.manager_edit_item(st, u, policy, weekly_core, get_conn, p, item, cats, logger)
            if status == "DA_CHOT" and admin and int(p.get("classification_locked") or 0):
                reason = st.text_input("Lý do mở khóa phân loại", key=f"p5_unlock_reason_{p['id']}")
                if st.button("🔓 Admin mở khóa phân loại", key=f"p5_unlock_{p['id']}", disabled=not reason.strip()):
                    ts = policy._now()
                    with get_conn() as c:
                        c.execute(
                            "UPDATE weekly_plans SET classification_locked=0,unlocked_at=?,unlocked_by=?,unlock_reason=?,updated_at=? WHERE id=?",
                            (ts, leader_uid, reason.strip(), ts, int(p["id"])),
                        )
                        c.execute("UPDATE weekly_plan_items SET classification_locked=0 WHERE plan_id=?", (int(p["id"]),))
                        c.execute(
                            "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'CLASSIFICATION_UNLOCK',?,?)",
                            (leader_uid, reason.strip(), ts),
                        )
                    st.rerun()

    pct = emergent / total_items * 100 if total_items else 0
    st.metric("Tỷ lệ công việc phát sinh / tổng công việc", f"{pct:.1f}%", f"{emergent}/{total_items}")
    cutoff = (date.today() - timedelta(weeks=8)).isoformat()
    with get_conn() as c:
        stale = []
        for cat in cats:
            hit = c.execute(
                "SELECT 1 FROM weekly_plan_items WHERE focus_category_id=? AND work_date>=? LIMIT 1",
                (int(cat["id"]), cutoff),
            ).fetchone()
            if not hit:
                stale.append(cat)
        watch = [dict(r) for r in c.execute(
            """SELECT w.title,u.full_name,w.carryover_count FROM weekly_plan_items w
               JOIN users u ON u.id=w.user_id
               WHERE w.q2_watch_flag=1 AND w.status NOT IN ('DONE','CANCELLED')
               ORDER BY w.carryover_count DESC,w.id DESC LIMIT 50"""
        ).fetchall()]
    if stale:
        st.warning(
            "📌 Danh mục trọng tâm không có công việc trong 8 tuần: " +
            ", ".join(f"{x['code']} · {x['name']}" for x in stale) +
            ". Hãy xem lại danh mục hoặc việc triển khai trọng tâm."
        )
    if watch:
        st.error(
            "🚩 Q2 bị lùi quá 2 tuần liên tiếp: " +
            "; ".join(f"{x['full_name']} – {x['title']} ({x['carryover_count']} lần)" for x in watch)
        )


def _install_room_week_board(policy, weekly_core, logger=None):
    policy._room_dashboard = lambda st,u,core,get_conn,ws,logger=None: _room_week_dashboard(
        st,u,policy,weekly_core,get_conn,ws,logger
    )
    if logger:
        logger.info("P5_ROOM_WEEKDAY_BOARD_INSTALLED")


def _install_leader_bottom_reviews(policy, weekly_core, customer_core, customer_ui, logger=None):
    def top_queue(st, u, policy_arg, customer_core_arg, get_conn, logger=None):
        uid, cases, moves, plans, wmoves = p4._pending_approval_data(
            u, policy, weekly_core, customer_core, get_conn
        )
        attention = p4._attention_rows(u, policy, get_conn)
        approval_total = len(cases) + len(moves) + len(plans) + len(wmoves)
        st.markdown("## 🔔 Trung tâm việc chờ lãnh đạo xử lý")
        t1, t2 = st.tabs([
            f"✅ Phê duyệt kế hoạch / dời hạn ({approval_total})",
            f"🔄 Cập nhật tiến độ / vướng mắc ({len(attention)})",
        ])
        with t1:
            p4._render_approval_items(
                st, u, policy, weekly_core, customer_core, customer_ui, get_conn, logger
            )
        with t2:
            p4._render_attention_items(st, u, policy, customer_core, get_conn, logger)
        st.divider()

    p3dash._attention_dashboard = top_queue
    original = customer_ui.render_leader_dashboard

    def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None, **kwargs):
        result = original(
            st=st, u=u, get_conn=get_conn, page_title=page_title, logger=logger, **kwargs
        )
        st.divider()
        phase2._render_manager_reviews(st, u, policy, weekly_core, get_conn, logger)
        phase2._render_room_performance(st, u, policy, weekly_core, get_conn)
        return result

    customer_ui.render_leader_dashboard = render_leader_dashboard
    if logger:
        logger.info("P5_LEADER_REVIEWS_MOVED_BOTTOM")


def _install_admin_backup_gate(app_ns, logger=None):
    st = app_ns["st"]
    if not getattr(backup, "_P5_BACKUP_PAGE_GATE", False):
        original_render = backup.render_backup_admin

        def render_backup_admin(st_arg, u, app_ns_arg, logger=None):
            if str(st_arg.session_state.get("admin_view") or "") != "backup":
                return None
            return original_render(st_arg, u, app_ns_arg, logger)

        backup.render_backup_admin = render_backup_admin
        backup._P5_BACKUP_PAGE_GATE = True

    original_admin = app_ns.get("admin_page")
    if callable(original_admin) and not app_ns.get("_P5_ADMIN_ONLY_WRAPPED"):
        def admin_page(u):
            if not bool(u.get("is_admin")):
                st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")
                return
            st.session_state["admin_scope"] = "system"
            return original_admin(u)
        app_ns["admin_page"] = admin_page
        app_ns["_P5_ADMIN_ONLY_WRAPPED"] = True
    if logger:
        logger.info("P5_ADMIN_BACKUP_GATE_INSTALLED")


def _sidebar_css(st):
    st.markdown(
        """
        <style>
        div[class*="st-key-cw_open_"],
        div[class*="st-key-p4_room_case_detail_"],
        div[class*="st-key-room_case_detail_"]{
            max-width:240px!important;margin-left:auto!important;
        }
        div[class*="st-key-cw_open_"] button,
        div[class*="st-key-p4_room_case_detail_"] button,
        div[class*="st-key-room_case_detail_"] button{
            min-height:34px!important;padding:.28rem .75rem!important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _install_sidebar_order(app_ns, logger=None):
    st = app_ns["st"]

    def sidebar_navigation(u):
        _sidebar_css(st)
        role = str(customer_nav._uget(u, "role") or "")
        admin = bool(customer_nav._uget(u, "is_admin"))
        uid = int(customer_nav._uget(u, "id") or 0)
        ops_options = [(r,l) for r,l in customer_nav._ops_options(role, admin) if r != "ops_admin"]
        plan_options = customer_nav._plan_options(role, admin)
        ops_values = customer_nav._route_values(ops_options)
        plan_values = customer_nav._route_values(plan_options)
        plan_landing = customer_nav._landing_for(role, admin)

        login_token = f"{uid}:{customer_nav._uget(u,'last_login_at','')}"
        if st.session_state.get("cw_landing_token") != login_token:
            st.session_state["cw_landing_token"] = login_token
            st.session_state["main_section"] = "plan"
            st.session_state["main_page"] = plan_landing

        current = st.session_state.get("main_page", plan_landing)
        if current == "ops_admin":
            current = "admin" if admin else plan_landing
            st.session_state["main_page"] = current
        section = st.session_state.get("main_section", "plan")
        if current in ops_values or current == "dashboard":
            section = "ops"
        elif current in plan_values or current in customer_nav.PLAN_PAGES:
            section = "plan"
        st.session_state["main_section"] = section

        st.sidebar.markdown("#### Chức năng chính")
        if st.sidebar.button(
            "📅  KẾ HOẠCH", key="mainsection_plan", use_container_width=True,
            type="primary" if section == "plan" else "secondary",
        ):
            st.session_state["main_section"] = "plan"
            st.session_state["main_page"] = plan_landing
            st.rerun()

        if st.sidebar.button(
            "🧾  TÁC NGHIỆP", key="mainsection_ops", use_container_width=True,
            type="primary" if section == "ops" else "secondary",
        ):
            st.session_state["main_section"] = "ops"
            st.session_state["main_page"] = ops_values[0]
            st.rerun()

        st.sidebar.divider()
        with st.sidebar.expander("⋯  Tiện ích", expanded=False):
            if st.button("👤 Tài khoản", key="cwutil_profile", use_container_width=True):
                st.session_state["main_page"] = "profile"; st.rerun()
            if st.button("📘 Hướng dẫn sử dụng", key="cwutil_guide", use_container_width=True):
                st.session_state["main_page"] = "guide"; st.rerun()
            if admin and st.button("🛠️ Quản trị hệ thống", key="cwutil_admin", use_container_width=True):
                st.session_state["main_page"] = "admin"
                st.session_state["admin_scope"] = "system"
                st.rerun()

        current = st.session_state.get("main_page", current)
        section = st.session_state.get("main_section", section)
        if current not in customer_nav.UTILITY_PAGES:
            choices = ops_options if section == "ops" else plan_options
            values = customer_nav._route_values(choices)
            if current not in values:
                current = values[0] if section == "ops" else plan_landing
                st.session_state["main_page"] = current
            customer_nav._render_command_tabs(st, section, current, choices, role, admin)

        current = st.session_state.get("main_page", current)
        return "dashboard" if current in customer_nav.CUSTOM_PAGES or current == "weekly_plan" else current

    app_ns["sidebar_navigation"] = sidebar_navigation
    if logger:
        logger.info("P5_SIDEBAR_ORDER_INSTALLED planning_first=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    _fast_save_extended_item(policy, weekly_core, logger)
    _install_auto_close_add(policy, logger)
    _install_weekly_card_and_history(logger)
    _install_room_week_board(policy, weekly_core, logger)
    _install_leader_bottom_reviews(policy, weekly_core, customer_core, customer_ui, logger)
    _install_admin_backup_gate(app_ns, logger)
    _install_sidebar_order(app_ns, logger)
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE5_INSTALLED version=%s admin_unified=1 backup_page=1 "
            "planning_first=1 compact_actions=1 add_autoclose=1 fast_save=1 history=1 "
            "room_weekdays=1 reviews_bottom=1",
            VERSION,
        )
