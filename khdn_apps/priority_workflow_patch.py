"""Priority workflow V2.

- Leader/Admin dashboard uses a true heat-colored Q1->Q4 matrix.
- Important-category catalog is only a category master; assigning a category starts at Q2.
- QLKH chooses priority for new Weekly Plan work; leaders can revise before approval.
"""
from __future__ import annotations

import json
from datetime import date

VERSION="1.0.0"
HEAT={
  1:("🔴","#D92D20","rgba(217,45,32,.16)","I · Quan trọng & Khẩn cấp"),
  2:("🟠","#F79009","rgba(247,144,9,.15)","II · Quan trọng & Chưa khẩn cấp"),
  3:("🟡","#FEC84B","rgba(254,200,75,.13)","III · Khẩn cấp & Không quan trọng"),
  4:("🟢","#12B76A","rgba(18,183,106,.11)","IV · Không quan trọng & Chưa khẩn cấp"),
}


def _q(v):
    try:v=int(v or 4)
    except Exception:v=4
    return v if v in (1,2,3,4) else 4


def _label(q): return HEAT[_q(q)][3]


def _ensure_weekly_priority(core,get_conn,logger=None):
    core.ensure_schema(get_conn,logger)
    with get_conn() as c:
        cols={str(r[1]) for r in c.execute("PRAGMA table_info(weekly_plan_items)").fetchall()}
        if "priority_quadrant" not in cols:
            c.execute("ALTER TABLE weekly_plan_items ADD COLUMN priority_quadrant INTEGER NOT NULL DEFAULT 4")
        if "priority_changed_by" not in cols:
            c.execute("ALTER TABLE weekly_plan_items ADD COLUMN priority_changed_by INTEGER")
        if "priority_changed_at" not in cols:
            c.execute("ALTER TABLE weekly_plan_items ADD COLUMN priority_changed_at TEXT")
        c.execute("UPDATE weekly_plan_items SET priority_quadrant=4 WHERE priority_quadrant IS NULL OR priority_quadrant NOT IN (1,2,3,4)")


def install(cw_core,cw_ui,weekly_core,weekly_ui,logger=None):
    if getattr(cw_ui,"_PRIORITY_WORKFLOW_V2",False): return

    # Important categories mean important + not urgent by default => Q2.
    original_set_importance=cw_core.set_importance
    def set_importance(get_conn,case_id,actor_uid,category_id=None,urgent_override=None,logger_arg=None):
        if category_id and urgent_override is None:
            urgent_override=0
        return original_set_importance(get_conn,case_id,actor_uid,category_id,urgent_override,logger_arg or logger)
    cw_core.set_importance=set_importance

    # Weekly schema + save wrapper. Each parsed row may carry its own Q; otherwise
    # use the visible default selected by QLKH before saving.
    original_ensure=weekly_core.ensure_schema
    def ensure_schema(get_conn,logger_arg=None):
        original_ensure(get_conn,logger_arg or logger)
        with get_conn() as c:
            cols={str(r[1]) for r in c.execute("PRAGMA table_info(weekly_plan_items)").fetchall()}
            for name,ddl in [
                ("priority_quadrant","INTEGER NOT NULL DEFAULT 4"),
                ("priority_changed_by","INTEGER"),
                ("priority_changed_at","TEXT"),
            ]:
                if name not in cols:c.execute(f"ALTER TABLE weekly_plan_items ADD COLUMN {name} {ddl}")
    weekly_core.ensure_schema=ensure_schema

    original_parse_line=weekly_core.parse_line
    def parse_line(line,ws,cs,forced=None):
        x=original_parse_line(line,ws,cs,forced)
        if not x or x.get("error"): return x
        import re
        m=re.search(r"(?:^|\s)Q\s*([1-4])(?:\s|$)",str(line or ""),flags=re.I)
        x["priority_quadrant"]=int(m.group(1)) if m else _q(getattr(weekly_core,"_DEFAULT_PRIORITY_QUADRANT",4))
        return x
    weekly_core.parse_line=parse_line

    original_save=weekly_core.save_items
    def save_items(get_conn,uid,ws,items,logger_arg=None):
        ensure_schema(get_conn,logger_arg)
        with get_conn() as c: before=int(c.execute("SELECT COALESCE(MAX(id),0) FROM weekly_plan_items").fetchone()[0])
        n,e=original_save(get_conn,uid,ws,items,logger_arg or logger)
        if n:
            good=[x for x in items if not x.get("error")]
            with get_conn() as c:
                ids=[int(r[0]) for r in c.execute("SELECT id FROM weekly_plan_items WHERE user_id=? AND id>? ORDER BY id",(uid,before)).fetchall()]
                for iid,x in zip(ids,good):
                    c.execute("UPDATE weekly_plan_items SET priority_quadrant=? WHERE id=?",(_q(x.get("priority_quadrant",getattr(weekly_core,"_DEFAULT_PRIORITY_QUADRANT",4))),iid))
        return n,e
    weekly_core.save_items=save_items

    # QLKH gets a visible default selector. Per-line Q1/Q2/Q3/Q4 can override it.
    original_weekly_render=weekly_ui.render_page
    def render_weekly(st,u,get_conn,page_title=None,logger=None):
        ensure_schema(get_conn,logger)
        role=str(u.get("role") or "")
        if role=="Cán bộ QLKH":
            opts=[1,2,3,4]
            cur=_q(st.session_state.get("wp_priority_default",4))
            chosen=st.selectbox("Mức ưu tiên cho kế hoạch mới",opts,index=opts.index(cur),format_func=_label,key="wp_priority_default")
            weekly_core._DEFAULT_PRIORITY_QUADRANT=int(chosen)
            st.caption("Có thể ghi Q1/Q2/Q3/Q4 ngay trong từng dòng nhập nhanh để đặt mức ưu tiên riêng cho từng việc.")
        else:
            weekly_core._DEFAULT_PRIORITY_QUADRANT=4
        return original_weekly_render(st,u,get_conn,page_title,logger)
    weekly_ui.render_page=render_weekly

    def heat_cards(st,data):
        counts={q:sum(_q(x.get("quadrant"))==q for x in data) for q in (1,2,3,4)}
        cards=[]
        for q in (1,2,3,4):
            icon,accent,bg,label=HEAT[q]
            cards.append(f'''<div style="border:1px solid {accent};border-left:7px solid {accent};background:{bg};border-radius:14px;padding:13px 14px;min-height:92px"><div style="font-weight:850">{icon} {label}</div><div style="font-size:1.7rem;font-weight:900;color:{accent};margin-top:8px">{counts[q]}</div></div>''')
        st.html('<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px">'+''.join(cards)+'</div><style>@media(max-width:760px){div[style*="grid-template-columns:repeat(4"]{grid-template-columns:repeat(2,minmax(0,1fr))!important}}</style>')

    # Dashboard: retain existing content, replace the plain quadrant metrics with
    # an additional authoritative heat matrix at the top so leader/admin see risk immediately.
    original_dashboard=cw_ui.render_leader_dashboard
    def render_dashboard(st,u,get_conn,page_title=None,logger=None):
        cw_core.ensure_schema(get_conn,logger)
        with get_conn() as c:data=cw_core.list_cases(c,manager=True,include_completed=False)
        if page_title: page_title("Điều hành công việc phòng","Tình hình thực hiện kế hoạch, tồn đọng, cảnh báo và ưu tiên")
        else: st.title("📊 Điều hành công việc phòng")
        st.subheader("🔥 Góc phần tư ưu tiên")
        st.caption("Màu nhiệt và thứ tự ưu tiên: Q1 → Q2 → Q3 → Q4.")
        heat_cards(st,data)
        # Render the rest using the current dashboard, but suppress duplicate page title by passing None.
        return original_dashboard(st,u,get_conn,None,logger)
    cw_ui.render_leader_dashboard=render_dashboard

    # Catalog: category master only; there is no quadrant control here. A category
    # becomes Q2 when assigned to a case. Urgency can later be deliberately changed.
    original_catalog=cw_ui.render_catalog_page
    def render_catalog(st,u,get_conn,page_title=None,logger=None):
        st.info("Danh mục công việc quan trọng chỉ dùng để tạo/sửa/xóa nhóm công việc. Khi gán danh mục cho một công việc, hệ thống mặc định xếp **Q2 – Quan trọng & Chưa khẩn cấp**.")
        return original_catalog(st,u,get_conn,page_title,logger)
    cw_ui.render_catalog_page=render_catalog

    # Approval page copied from existing behavior, adding leader-editable priority
    # for each Weekly Plan item before the decision is committed.
    original_approvals=cw_ui.render_approvals_page
    def render_approvals(st,u,get_conn,page_title=None,logger=None):
        ensure_schema(get_conn,logger)
        # Reuse legacy page for customer-work approvals/reschedules, but weekly-plan
        # priority editing needs its own compact panel. Put it first and mark handled
        # rows as approved/rejected here; legacy page will then naturally omit them.
        uid=int(u["id"])
        manager=str(u.get("role") or "")=="Lãnh đạo phòng" or bool(u.get("is_admin"))
        if not manager: return original_approvals(st,u,get_conn,page_title,logger)
        with get_conn() as c:
            weekly=[dict(r) for r in c.execute("""SELECT w.*,u.full_name,c.customer_name FROM weekly_plan_items w JOIN users u ON u.id=w.user_id LEFT JOIN customers c ON c.id=w.customer_id WHERE w.approval_status='PENDING' ORDER BY w.work_date,w.id""").fetchall()]
        if weekly:
            st.subheader("🎯 Duyệt ưu tiên kế hoạch tuần")
            st.caption("Lãnh đạo/Admin có thể điều chỉnh mức ưu tiên trước khi phê duyệt.")
            for w in weekly:
                with st.container(border=True):
                    st.markdown(f"**{w.get('full_name')} · {w.get('title')}**")
                    st.caption(f"Ngày {str(w.get('work_date') or '')[:10]} · {w.get('customer_name') or w.get('customer_text') or 'Nội bộ'}")
                    opts=[1,2,3,4];cur=_q(w.get("priority_quadrant"))
                    pq=st.selectbox("Mức ưu tiên",opts,index=opts.index(cur),format_func=_label,key=f"ap_wp_priority_{w['id']}")
                    note=st.text_input("Ý kiến",key=f"ap_wp2_note_{w['id']}")
                    a,b=st.columns(2)
                    if a.button("✓ Phê duyệt",key=f"ap_wp2_yes_{w['id']}",type="primary",use_container_width=True):
                        ts=cw_core.now_str()
                        with get_conn() as c:
                            c.execute("UPDATE weekly_plan_items SET priority_quadrant=?,priority_changed_by=?,priority_changed_at=?,approval_status='APPROVED',approved_by_user_id=?,approved_at=?,approval_note=? WHERE id=?",(int(pq),uid,ts,uid,ts,note,w['id']))
                            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_APPROVE',?,?)",(w['id'],uid,json.dumps({'note':note,'priority_quadrant':int(pq)},ensure_ascii=False),ts))
                        st.rerun()
                    if b.button("✕ Từ chối",key=f"ap_wp2_no_{w['id']}",use_container_width=True):
                        ts=cw_core.now_str()
                        with get_conn() as c:
                            c.execute("UPDATE weekly_plan_items SET priority_quadrant=?,priority_changed_by=?,priority_changed_at=?,approval_status='REJECTED',rejected_by_user_id=?,rejected_at=?,approval_note=? WHERE id=?",(int(pq),uid,ts,uid,ts,note,w['id']))
                            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_REJECT',?,?)",(w['id'],uid,json.dumps({'note':note,'priority_quadrant':int(pq)},ensure_ascii=False),ts))
                        st.rerun()
            st.divider()
        return original_approvals(st,u,get_conn,page_title,logger)
    cw_ui.render_approvals_page=render_approvals

    cw_ui._PRIORITY_WORKFLOW_V2=True
    if logger: logger.info("PRIORITY_WORKFLOW_V2_INSTALLED version=%s",VERSION)
