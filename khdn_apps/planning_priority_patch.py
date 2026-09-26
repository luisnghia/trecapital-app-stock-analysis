"""Priority governance V2 for KHDN planning.

- Important-category work defaults to Q2 unless a manager explicitly marks it urgent.
- Weekly-plan items persist Q1..Q4 priority per item.
- Weekly preview allows per-item adjustment; plan cards show the priority heat badge.
- Leader/Admin approval can revise weekly priority before approving.
- Leader dashboard renders the four quadrants with an explicit heat scale.
"""
from __future__ import annotations

import html
import json

VERSION = "2.0.0"

PRIORITY = {
    1: {"label": "I · Quan trọng & Khẩn cấp", "icon": "🔴", "accent": "#D92D20", "bg": "rgba(217,45,32,.18)", "border": "rgba(240,68,56,.78)"},
    2: {"label": "II · Quan trọng & Chưa khẩn cấp", "icon": "🟠", "accent": "#F79009", "bg": "rgba(247,144,9,.17)", "border": "rgba(247,144,9,.76)"},
    3: {"label": "III · Khẩn cấp & Không quan trọng", "icon": "🟡", "accent": "#FEC84B", "bg": "rgba(254,200,75,.14)", "border": "rgba(254,200,75,.72)"},
    4: {"label": "IV · Không quan trọng & Chưa khẩn cấp", "icon": "🟢", "accent": "#12B76A", "bg": "rgba(18,183,106,.13)", "border": "rgba(18,183,106,.65)"},
}


def _q(v):
    try:
        q = int(v or 4)
    except Exception:
        q = 4
    return q if q in (1, 2, 3, 4) else 4


def priority_label(q):
    p = PRIORITY[_q(q)]
    return f"{p['icon']} {p['label']}"


def _priority_badge(st, q):
    p = PRIORITY[_q(q)]
    st.markdown(
        f'''<div style="display:inline-block;margin:.08rem 0 .35rem 0;padding:.28rem .56rem;border-radius:999px;
        border:1px solid {p['border']};border-left:5px solid {p['accent']};background:{p['bg']};font-weight:850;">
        {p['icon']} {html.escape(p['label'])}</div>''',
        unsafe_allow_html=True,
    )


def _heat_cards(st, case_counts, weekly_counts):
    cards = []
    for q in range(1, 5):
        p = PRIORITY[q]
        total = int(case_counts.get(q, 0)) + int(weekly_counts.get(q, 0))
        cards.append(
            f'''<div class="pp-heat" style="background:{p['bg']};border-color:{p['border']};border-left-color:{p['accent']}">
            <div class="pp-title"><span>{p['icon']}</span>{html.escape(p['label'])}</div>
            <div class="pp-count" style="color:{p['accent']}">{total}</div>
            <div class="pp-sub">Công việc KH: {int(case_counts.get(q,0))} · Kế hoạch: {int(weekly_counts.get(q,0))}</div>
            </div>'''
        )
    st.html(
        '''<div class="pp-grid">''' + "".join(cards) + '''</div>
        <style>
        .pp-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px;margin:.4rem 0 1rem 0}
        .pp-heat{border:1px solid;border-left:7px solid;border-radius:14px;padding:12px 13px;min-height:112px}
        .pp-title{font-size:.90rem;font-weight:850;line-height:1.25;display:flex;gap:7px;align-items:flex-start}
        .pp-count{font-size:1.75rem;font-weight:950;margin:.48rem 0 .1rem 0}
        .pp-sub{font-size:.76rem;opacity:.88;line-height:1.25}
        @media(max-width:760px){.pp-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.pp-heat{min-height:98px;padding:10px}.pp-title{font-size:.78rem}.pp-count{font-size:1.45rem}.pp-sub{font-size:.68rem}}
        </style>'''
    )


def install(customer_core, customer_ui, weekly_core, weekly_ui, logger=None):
    if getattr(weekly_core, "_PLANNING_PRIORITY_V2_INSTALLED", False):
        return

    # ---------- Customer Work: important category defaults to Q2 ----------
    original_set_importance = customer_core.set_importance

    def set_importance(get_conn, case_id, actor_uid, category_id=None, urgent_override=None, logger=None):
        # A named Important category is a Q2 default.  Q1 is deliberate: the
        # manager must explicitly choose urgent_override=1.
        if category_id and urgent_override is None:
            urgent_override = 0
        return original_set_importance(get_conn, case_id, actor_uid, category_id, urgent_override, logger)

    customer_core.set_importance = set_importance

    # ---------- Weekly Plan schema + persistence ----------
    original_ensure = weekly_core.ensure_schema
    original_save = weekly_core.save_items
    original_copy = weekly_core.copy_prev
    original_add_task = weekly_core.add_task
    original_card = weekly_core.card
    original_preview = weekly_core.preview

    def _cols(c, table):
        return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}

    def ensure_schema(get_conn, logger_arg=None):
        original_ensure(get_conn, logger_arg or logger)
        with get_conn() as c:
            if "priority_quadrant" not in _cols(c, "weekly_plan_items"):
                c.execute("ALTER TABLE weekly_plan_items ADD COLUMN priority_quadrant INTEGER NOT NULL DEFAULT 4")
            # Existing important-category Customer Work records that were still
            # on automatic urgency become the newly-defined Q2 default.
            try:
                c.execute("UPDATE customer_work_cases SET urgent_override=0 WHERE important_category_id IS NOT NULL AND urgent_override IS NULL")
            except Exception:
                pass
        if logger_arg or logger:
            (logger_arg or logger).info("PLANNING_PRIORITY_SCHEMA_READY version=%s", VERSION)

    def _max_item_id(get_conn):
        with get_conn() as c:
            return int(c.execute("SELECT COALESCE(MAX(id),0) FROM weekly_plan_items").fetchone()[0])

    def save_items(get_conn, uid, ws, items, logger_arg=None):
        ensure_schema(get_conn, logger_arg)
        before = _max_item_id(get_conn)
        good = [x for x in items if x and not x.get("error")]
        n, errors = original_save(get_conn, uid, ws, items, logger_arg or logger)
        if n:
            with get_conn() as c:
                rows = c.execute("SELECT id FROM weekly_plan_items WHERE user_id=? AND id>? ORDER BY id", (int(uid), before)).fetchall()
                for row, item in zip(rows, good):
                    c.execute("UPDATE weekly_plan_items SET priority_quadrant=? WHERE id=?", (_q(item.get("priority_quadrant")), int(row[0])))
        return n, errors

    def copy_prev(get_conn, uid, ws, logger_arg=None):
        ensure_schema(get_conn, logger_arg)
        before = _max_item_id(get_conn)
        n = original_copy(get_conn, uid, ws, logger_arg or logger)
        if n:
            with get_conn() as c:
                c.execute("""UPDATE weekly_plan_items
                    SET priority_quadrant=COALESCE((SELECT p.priority_quadrant FROM weekly_plan_items p WHERE p.id=weekly_plan_items.copied_from_item_id),4)
                    WHERE user_id=? AND id>?""", (int(uid), before))
        return n

    def add_task(get_conn, uid, ws, task, target_date, logger_arg=None):
        ensure_schema(get_conn, logger_arg)
        before = _max_item_id(get_conn)
        ok = original_add_task(get_conn, uid, ws, task, target_date, logger_arg or logger)
        if ok:
            priority = 4
            try:
                import streamlit as st
                priority = _q(st.session_state.get("_wp_next_add_task_priority", 4))
            except Exception:
                priority = 4
            with get_conn() as c:
                c.execute("UPDATE weekly_plan_items SET priority_quadrant=? WHERE user_id=? AND id>?", (priority, int(uid), before))
        return ok

    def preview(st, items):
        rows = []
        valid = []
        for idx, x in enumerate(items):
            if x.get("error"):
                rows.append(["⚠️", x.get("source_text", ""), x["error"], "", "", ""])
                continue
            d = __import__("datetime").date.fromisoformat(x["work_date"])
            when = weekly_core.day_label(d) + (f" · {x['start_time']}" if x.get("start_time") else (f" · {x['daypart']}" if x.get("daypart") else ""))
            q = _q(x.get("priority_quadrant"))
            rows.append([when, x["title"], x.get("customer_text") or "—", x["category"], ", ".join(x.get("purposes", [])) or "—", priority_label(q)])
            valid.append((idx, x))
        weekly_core.table(st, ["Ngày", "Công việc", "Khách hàng", "Nhóm", "Mục đích", "Ưu tiên"], rows)
        if valid:
            st.caption("Có thể chỉnh riêng mức ưu tiên cho từng công việc trước khi lưu.")
            for idx, x in valid:
                q = _q(x.get("priority_quadrant"))
                chosen = st.selectbox(
                    f"Ưu tiên · {str(x.get('title') or 'Công việc')[:70]}",
                    [1, 2, 3, 4], index=q-1, format_func=priority_label,
                    key=f"wp_preview_priority_{idx}_{str(x.get('work_date'))[:10]}",
                )
                x["priority_quadrant"] = int(chosen)

    def card(st, x, ws, get_conn, uid, logger_arg=None):
        _priority_badge(st, x.get("priority_quadrant"))
        return original_card(st, x, ws, get_conn, uid, logger_arg or logger)

    weekly_core.ensure_schema = ensure_schema
    weekly_core.save_items = save_items
    weekly_core.copy_prev = copy_prev
    weekly_core.add_task = add_task
    weekly_core.preview = preview
    weekly_core.card = card
    weekly_core.priority_label = priority_label

    # ---------- Leader/Admin dashboard with a real heat scale ----------
    def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None):
        customer_core.ensure_schema(get_conn, logger)
        weekly_core.ensure_schema(get_conn, logger)
        if page_title:
            page_title("Điều hành công việc phòng", "Tình hình thực hiện kế hoạch, tồn đọng, cảnh báo và ưu tiên")
        else:
            st.title("📊 Điều hành công việc phòng")
        with get_conn() as c:
            data = customer_core.list_cases(c, manager=True, include_completed=False)
            plans, reschedules = customer_core.pending_case_approvals(c)
            try:
                wp_plan = int(c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE approval_status='PENDING'").fetchone()[0])
                wp_move = int(c.execute("SELECT COUNT(*) FROM weekly_plan_reschedule_requests WHERE status='PENDING'").fetchone()[0])
            except Exception:
                wp_plan = wp_move = 0
            today = __import__("datetime").date.today().isoformat()
            try:
                wp_today = [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE work_date=? AND status<>'CANCELLED' AND COALESCE(approval_status,'APPROVED')='APPROVED'", (today,)).fetchall()]
                wp_open = [dict(r) for r in c.execute("""SELECT * FROM weekly_plan_items
                    WHERE status NOT IN ('DONE','CANCELLED') AND COALESCE(approval_status,'APPROVED')='APPROVED'""").fetchall()]
            except Exception:
                wp_today = []; wp_open = []
        delayed = [x for x in data if x.get("is_stage_delayed")]
        overdue = [x for x in data if x.get("is_overdue")]
        blocked = [x for x in data if int(x.get("open_issue_count") or 0) > 0]
        a,b,c,d,e = st.columns(5)
        a.metric("Đang xử lý", len(data)); b.metric("Kế hoạch hôm nay", len(wp_today)); c.metric("Quá hạn", len(overdue)); d.metric("Mục bị chậm", len(delayed)); e.metric("Chờ phê duyệt", len(plans)+len(reschedules)+wp_plan+wp_move)

        st.subheader("Theo mục công việc")
        stage_rows = []
        for name in sorted({x.get("stage_name") for x in data if x.get("stage_name")}):
            arr=[x for x in data if x.get("stage_name")==name]
            stage_rows.append([name,len(arr),sum(bool(z.get("is_stage_delayed")) for z in arr),sum(int(z.get("open_issue_count") or 0)>0 for z in arr),sum(bool(z.get("is_overdue")) for z in arr)])
        customer_ui._html_table(st,["Mục công việc","Số việc","Bị chậm","Có vướng mắc","Quá hạn"],stage_rows)

        st.subheader("Theo cán bộ")
        staff={}
        for x in data:
            k=x.get("owner_name") or "—"; r=staff.setdefault(k,[0,0,0,0]); r[0]+=1; r[1]+=int(bool(x.get("is_stage_delayed"))); r[2]+=int(bool(x.get("is_overdue"))); r[3]+=int(int(x.get("open_issue_count") or 0)>0)
        customer_ui._html_table(st,["Cán bộ","Đang xử lý","Bị chậm","Quá hạn","Có vướng mắc"],[[k]+v for k,v in sorted(staff.items())])

        st.subheader("🔥 Góc phần tư ưu tiên")
        st.caption("Màu nhiệt từ Q1 → Q4. Số liệu gồm cả Công việc khách hàng và Kế hoạch tuần đã được duyệt, chưa hoàn thành.")
        case_counts={q:sum(_q(x.get("quadrant"))==q for x in data) for q in range(1,5)}
        weekly_counts={q:sum(_q(x.get("priority_quadrant"))==q for x in wp_open) for q in range(1,5)}
        _heat_cards(st, case_counts, weekly_counts)

        if overdue or delayed or blocked:
            st.subheader("⚠ Danh sách cần chú ý")
            seen=set()
            for x in overdue+delayed+blocked:
                if x["id"] in seen: continue
                seen.add(x["id"]); customer_ui._case_card(st,x,get_conn,int(u["id"]),True,logger,compact=True)
        customer_ui._glossary(st)

    customer_ui.render_leader_dashboard = render_leader_dashboard

    # ---------- Approval page: leader can revise weekly priority in-line ----------
    original_approvals = customer_ui.render_approvals_page

    def render_approvals_page(st, u, get_conn, page_title=None, logger=None):
        customer_core.ensure_schema(get_conn, logger); weekly_core.ensure_schema(get_conn, logger)
        uid=int(u["id"])
        if not customer_ui._manager(u):
            st.error("Chỉ Lãnh đạo/Admin được phê duyệt."); return
        if page_title: page_title("Phê duyệt", "Kế hoạch mới và các đề nghị dời thời gian")
        else: st.title("✅ Phê duyệt")
        with get_conn() as c:
            plans,reschedules=customer_core.pending_case_approvals(c)
            try:
                weekly=[dict(r) for r in c.execute("""SELECT w.*,u.full_name,c.customer_name FROM weekly_plan_items w
                    JOIN users u ON u.id=w.user_id LEFT JOIN customers c ON c.id=w.customer_id
                    WHERE w.approval_status='PENDING' ORDER BY w.work_date,w.id""").fetchall()]
                weekly_moves=[dict(r) for r in c.execute("""SELECT r.*,w.title,w.customer_text,u.full_name AS requester_name
                    FROM weekly_plan_reschedule_requests r JOIN weekly_plan_items w ON w.id=r.item_id
                    JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
            except Exception:
                weekly=[]; weekly_moves=[]
        total=len(plans)+len(reschedules)+len(weekly)+len(weekly_moves)
        st.caption(f"Có {total} đề nghị đang chờ xử lý.")

        st.subheader("Công việc khách hàng mới")
        if not plans: st.caption("Không có kế hoạch mới chờ phê duyệt.")
        for x in plans:
            with st.container(border=True):
                st.markdown(f"**{x.get('customer_name')} · {x.get('title')}**"); st.caption(f"{x.get('owner_name')} · {x.get('stage_name')} · Dự kiến {customer_ui._dt_text(x.get('expected_complete_at'))}")
                note=st.text_input("Ý kiến",key=f"ap_case_note_{x['id']}"); a,b=st.columns(2)
                if a.button("✓ Phê duyệt",key=f"ap_case_yes_{x['id']}",type="primary",use_container_width=True): customer_core.approve_case_plan(get_conn,x["id"],uid,True,note,logger);st.rerun()
                if b.button("✕ Từ chối",key=f"ap_case_no_{x['id']}",use_container_width=True): customer_core.approve_case_plan(get_conn,x["id"],uid,False,note,logger);st.rerun()

        st.subheader("Đề nghị dời thời gian công việc khách hàng")
        if not reschedules: st.caption("Không có đề nghị dời thời gian.")
        for r in reschedules:
            with st.container(border=True):
                st.markdown(f"**{r.get('customer_name')} · {r.get('title')}**"); st.caption(f"{r.get('requester_name')} · {customer_ui._dt_text(r.get('old_due_at'))} → {customer_ui._dt_text(r.get('proposed_due_at'))}"); st.write(f"Lý do: {r.get('reason')}")
                note=st.text_input("Ý kiến",key=f"ap_rs_note_{r['id']}"); a,b=st.columns(2)
                if a.button("✓ Phê duyệt",key=f"ap_rs_yes_{r['id']}",type="primary",use_container_width=True): customer_core.decide_reschedule(get_conn,r["id"],uid,True,note,logger);st.rerun()
                if b.button("✕ Từ chối",key=f"ap_rs_no_{r['id']}",use_container_width=True): customer_core.decide_reschedule(get_conn,r["id"],uid,False,note,logger);st.rerun()

        st.subheader("Kế hoạch tuần/ngày")
        st.caption("Lãnh đạo/Admin có thể điều chỉnh mức ưu tiên trước khi phê duyệt. Mức được duyệt là mức chính thức.")
        if not weekly: st.caption("Không có kế hoạch tuần/ngày chờ phê duyệt.")
        for w in weekly:
            with st.container(border=True):
                st.markdown(f"**{w.get('full_name')} · {w.get('title')}**"); st.caption(f"Ngày {customer_ui._date_text(w.get('work_date'))} · {w.get('customer_name') or w.get('customer_text') or 'Nội bộ'}")
                current=_q(w.get("priority_quadrant")); priority=st.selectbox("Mức ưu tiên khi duyệt",[1,2,3,4],index=current-1,format_func=priority_label,key=f"ap_wp_priority_{w['id']}")
                note=st.text_input("Ý kiến",key=f"ap_wp_note_{w['id']}"); a,b=st.columns(2)
                if a.button("✓ Phê duyệt",key=f"ap_wp_yes_{w['id']}",type="primary",use_container_width=True):
                    ts=customer_core.now_str(); detail=json.dumps({"note":note,"priority_quadrant":int(priority)},ensure_ascii=False)
                    with get_conn() as c:
                        c.execute("UPDATE weekly_plan_items SET priority_quadrant=?,approval_status='APPROVED',approved_by_user_id=?,approved_at=?,approval_note=? WHERE id=?",(int(priority),uid,ts,note,w["id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_APPROVE',?,?)",(w["id"],uid,detail,ts))
                    st.rerun()
                if b.button("✕ Từ chối",key=f"ap_wp_no_{w['id']}",use_container_width=True):
                    ts=customer_core.now_str()
                    with get_conn() as c:
                        c.execute("UPDATE weekly_plan_items SET approval_status='REJECTED',rejected_by_user_id=?,rejected_at=?,approval_note=? WHERE id=?",(uid,ts,note,w["id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_REJECT',?,?)",(w["id"],uid,note,ts))
                    st.rerun()

        st.subheader("Đề nghị dời kế hoạch tuần/ngày")
        if not weekly_moves: st.caption("Không có đề nghị dời kế hoạch.")
        for r in weekly_moves:
            with st.container(border=True):
                st.markdown(f"**{r.get('requester_name')} · {r.get('title')}**"); st.caption(f"{customer_ui._date_text(r.get('old_work_date'))} → {customer_ui._date_text(r.get('proposed_work_date'))} · {r.get('customer_text') or 'Nội bộ'}")
                note=st.text_input("Ý kiến",key=f"ap_wpr_note_{r['id']}"); a,b=st.columns(2)
                if a.button("✓ Phê duyệt",key=f"ap_wpr_yes_{r['id']}",type="primary",use_container_width=True):
                    ts=customer_core.now_str()
                    with get_conn() as c:
                        c.execute("UPDATE weekly_plan_reschedule_requests SET status='APPROVED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",(uid,ts,note,r["id"]))
                        c.execute("UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?",(r["proposed_work_date"],ts,r["item_id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_APPROVE',?,?)",(r["item_id"],uid,note,ts))
                    st.rerun()
                if b.button("✕ Từ chối",key=f"ap_wpr_no_{r['id']}",use_container_width=True):
                    ts=customer_core.now_str()
                    with get_conn() as c:
                        c.execute("UPDATE weekly_plan_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",(uid,ts,note,r["id"]))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_REJECT',?,?)",(r["item_id"],uid,note,ts))
                    st.rerun()
        customer_ui._glossary(st)

    customer_ui.render_approvals_page = render_approvals_page

    weekly_core._PLANNING_PRIORITY_V2_INSTALLED = True
    if logger:
        logger.info("PLANNING_PRIORITY_V2_INSTALLED version=%s", VERSION)
