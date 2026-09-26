"""Final Customer Work UX/data-source refinements.

Installed last so it can safely compose all earlier planning patches:
- Customer Work group/type uses the same active ``task_types`` master as Tác nghiệp.
- Entering Customer Work from another top tab always lands on Đang xử lý.
- Customer Work cards are visually prominent and priority/status aware.
- System Admin and Operational Admin keep fully separate scope + child view state.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import html

from khdn_apps import potential_customer_patch as prospects

VERSION = "1.0.0"

_HEAT = {
    1: {"icon":"🔴","accent":"#D92D20","bg":"rgba(217,45,32,.12)","border":"rgba(240,68,56,.72)"},
    2: {"icon":"🟠","accent":"#F79009","bg":"rgba(247,144,9,.12)","border":"rgba(247,144,9,.72)"},
    3: {"icon":"🟡","accent":"#EAAA08","bg":"rgba(254,200,75,.12)","border":"rgba(234,170,8,.68)"},
    4: {"icon":"🟢","accent":"#12B76A","bg":"rgba(18,183,106,.10)","border":"rgba(18,183,106,.58)"},
}


def _q(v):
    try:
        q=int(v or 4)
    except Exception:
        q=4
    return q if q in (1,2,3,4) else 4


def _task_types(c):
    """Single source of truth: Tác nghiệp -> Quản trị -> Loại công việc."""
    try:
        rows=c.execute("SELECT id,name,sla_hours,active FROM task_types WHERE active=1 ORDER BY name COLLATE NOCASE,id").fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def _status_meta(x):
    if x.get("is_overdue"):
        return "🔴 Quá hạn", "#F04438", "rgba(240,68,56,.14)"
    if x.get("is_stage_delayed"):
        return "🔴 Mục bị chậm", "#F04438", "rgba(240,68,56,.14)"
    if x.get("is_stage_warning"):
        return "🟠 Sắp chậm", "#F79009", "rgba(247,144,9,.14)"
    return "🟢 Trong hạn", "#12B76A", "rgba(18,183,106,.12)"


def _card(st, ui, x, get_conn, uid, manager, logger=None, compact=False):
    q=_q(x.get("quadrant"))
    heat=_HEAT[q]
    status_text,status_color,status_bg=_status_meta(x)
    customer=html.escape(str(x.get("customer_name") or "—"))
    case_type=html.escape(str(x.get("case_type") or x.get("title") or "Công việc"))
    title=html.escape(str(x.get("title") or ""))
    code=html.escape(str(x.get("case_code") or ""))
    owner=html.escape(str(x.get("owner_name") or "—"))
    stage=html.escape(str(x.get("stage_name") or "—"))
    elapsed=html.escape(ui.core.duration_text(x.get("stage_elapsed_hours")))
    due=html.escape(ui._dt_text(x.get("expected_complete_at")))
    issues=int(x.get("open_issue_count") or 0)
    priority=html.escape(ui.core.quadrant_label(q))
    approval=str(x.get("plan_approval_status") or "PENDING")
    work_line="" if not title or title.casefold()==case_type.casefold() else f'<div class="cw-focus-work">📌 {title}</div>'

    st.markdown(
        f'''<div class="cw-focus-card" style="--cw-accent:{heat['accent']};--cw-border:{heat['border']};--cw-bg:{heat['bg']};">
          <div class="cw-focus-head">
            <div><div class="cw-focus-title">{customer} <span>·</span> {case_type}</div>{work_line}</div>
            <div class="cw-focus-code">{code}</div>
          </div>
          <div class="cw-focus-row">
            <span>👤 <b>{owner}</b></span>
            <span class="cw-stage">📍 {stage}</span>
            <span>⏱ {elapsed}</span>
            <span class="cw-status" style="color:{status_color};background:{status_bg};">{status_text}</span>
          </div>
          <div class="cw-focus-row cw-focus-row2">
            <span>🎯 <b>Dự kiến hoàn thành:</b> {due}</span>
            <span class="cw-issue">⚠ <b>Vướng mắc mở:</b> {issues}</span>
            <span class="cw-priority" style="border-color:{heat['border']};background:{heat['bg']};color:{heat['accent']};">{heat['icon']} {priority}</span>
          </div>
        </div>
        <style>
        .cw-focus-card{{border:1px solid var(--cw-border);border-left:7px solid var(--cw-accent);border-radius:14px;padding:13px 15px;margin:.34rem 0 .55rem 0;background:linear-gradient(120deg,var(--cw-bg),rgba(6,78,72,.08));box-shadow:0 7px 18px rgba(0,0,0,.10)}}
        .cw-focus-head{{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}}
        .cw-focus-title{{font-size:1.05rem;font-weight:950;line-height:1.28;color:#63DCCB}}
        .cw-focus-title span{{opacity:.72}}
        .cw-focus-code{{font-size:.78rem;font-weight:900;color:#F4B41A;white-space:nowrap;padding-top:2px}}
        .cw-focus-work{{font-size:.82rem;font-weight:750;opacity:.92;margin-top:4px}}
        .cw-focus-row{{display:flex;flex-wrap:wrap;gap:8px 15px;margin-top:10px;align-items:center;font-size:.84rem;line-height:1.35}}
        .cw-stage{{font-weight:800}}
        .cw-status,.cw-priority{{display:inline-block;padding:3px 8px;border-radius:999px;font-weight:900}}
        .cw-priority{{border:1px solid}}
        .cw-issue{{font-weight:760}}
        @media(max-width:760px){{.cw-focus-card{{padding:11px 12px}}.cw-focus-head{{display:block}}.cw-focus-code{{margin-top:5px}}.cw-focus-title{{font-size:.98rem}}.cw-focus-row{{font-size:.78rem;gap:7px 10px}}}}
        </style>''',
        unsafe_allow_html=True,
    )
    if approval=="PENDING":
        st.warning("Kế hoạch công việc đang chờ phê duyệt.")
    elif approval=="REJECTED":
        st.error("Kế hoạch đã bị từ chối." + (f" {x.get('approval_note')}" if x.get("approval_note") else ""))
    if not compact and st.button("Mở chi tiết",key=f"cw_open_{x['id']}",use_container_width=True):
        st.session_state["cw_case_id"]=int(x["id"])
        st.rerun()


def _create_form(st,u,get_conn,customer_core,ui,logger=None):
    prospects.ensure_customer_master(get_conn,logger)
    prospects.render_quick_add(st,u,get_conn,"cw_new_customer",logger,select_state_key="cw_customer_pick")
    uid=int(u["id"]); manager=ui._manager(u)
    with get_conn() as c:
        cs=prospects.planning_customers(c,uid)
        stages=customer_core.active_stages(c)
        users=customer_core.staff_users(c) if manager else []
        types=_task_types(c)
    if not cs:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error("Chưa có Loại công việc đang sử dụng. Lãnh đạo/Admin hãy tạo tại Tác nghiệp → Quản trị → Loại công việc.")
        return
    st.caption(f"Nhóm công việc dùng chung danh mục **Tác nghiệp → Quản trị → Loại công việc** · {len(types)} loại đang sử dụng.")
    preferred=st.session_state.get("cw_customer_pick")
    idx=next((i for i,x in enumerate(cs) if int(x["id"])==int(preferred or -1)),0)
    with st.form("cw_create_case",clear_on_submit=True):
        customer=st.selectbox("Khách hàng",cs,index=idx,format_func=prospects._label)
        case_type=st.selectbox("Nhóm công việc / Loại công việc",types,format_func=lambda x:x["name"])
        title=st.text_input("Công việc",placeholder="Ví dụ: Hạn mức tín dụng 2026 / Tiếp thị tiền gửi / Dự án A")
        c1,c2=st.columns(2)
        due_date=c1.date_input("Dự kiến hoàn thành",value=date.today()+timedelta(days=7))
        due_time=c2.time_input("Giờ dự kiến",value=time(17,0))
        stage=st.selectbox("Mục công việc bắt đầu",stages,format_func=lambda x:x["name"])
        owner=st.selectbox("Cán bộ phụ trách",users,format_func=lambda x:f"{x['full_name']} · {x['role']}") if manager else None
        note=st.text_area("Ghi chú",height=80)
        ok=st.form_submit_button("Tạo công việc",type="primary",use_container_width=True)
    if ok:
        try:
            due=datetime.combine(due_date,due_time).strftime("%Y-%m-%d %H:%M:%S")
            cid,state=customer_core.create_case(
                get_conn,uid,customer["id"],title,due,
                owner_uid=owner["id"] if owner else uid,
                case_type=case_type["name"],note=note,stage_id=stage["id"],logger=logger,
            )
            st.session_state["cw_case_id"]=cid
            st.session_state.pop("cw_customer_pick",None)
            st.toast("Đã tạo công việc." if state=="APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.",icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_cases_page(st,u,get_conn,customer_core,ui,page_title=None,logger=None):
    customer_core.ensure_schema(get_conn,logger)
    uid=int(u["id"]); manager=ui._manager(u)
    if page_title:
        page_title("Công việc khách hàng","Theo dõi xuyên suốt từ tiếp cận đến hoàn thành")
    else:
        st.title("👥 Công việc khách hàng")
    if st.session_state.get("cw_case_id"):
        ui._case_detail(st,u,get_conn,int(st.session_state["cw_case_id"]),logger)
        ui._glossary(st)
        return

    # Deliberately only two tabs; Processing is always the first/default view.
    tab_processing,tab_new=st.tabs(["Đang xử lý","Tạo công việc mới"])
    with tab_processing:
        with get_conn() as c:
            data=customer_core.list_cases(c,uid=uid,manager=manager,include_completed=False)
        f1,f2=st.columns(2)
        stages=sorted({x.get("stage_name") for x in data if x.get("stage_name")})
        sf=f1.selectbox("Lọc mục công việc",["Tất cả"]+stages,key="cw_filter_stage")
        search=f2.text_input("Tìm khách hàng/công việc",key="cw_filter_text")
        ss=str(search or "").lower().strip()
        shown=[x for x in data if (sf=="Tất cả" or x.get("stage_name")==sf) and (
            not ss or ss in str(x.get("customer_name") or "").lower() or ss in str(x.get("cif") or "").lower()
            or ss in str(x.get("title") or "").lower() or ss in str(x.get("case_type") or "").lower()
        )]
        # Most urgent quadrant first, then operational risks and nearest due time.
        def due_key(x):
            return customer_core.parse_dt(x.get("expected_complete_at")) or datetime.max
        shown.sort(key=lambda x:(
            _q(x.get("quadrant")),0 if x.get("is_overdue") else 1,0 if x.get("is_stage_delayed") else 1,
            -int(x.get("open_issue_count") or 0),due_key(x),int(x.get("id") or 0)
        ))
        if not shown:
            st.info("Không có công việc phù hợp.")
        for x in shown:
            ui._case_card(st,x,get_conn,uid,manager,logger)
    with tab_new:
        _create_form(st,u,get_conn,customer_core,ui,logger)
    ui._glossary(st)


def install(ns,nav_module,customer_core,customer_ui,logger=None):
    if getattr(customer_ui,"_CUSTOMER_WORK_REFINEMENT_INSTALLED",False):
        return
    st=ns["st"]

    # Card renderer is referenced dynamically by Today, Leader Dashboard and Case lists.
    def case_card(st_arg,x,get_conn,uid,manager,logger_arg=None,compact=False):
        return _card(st_arg,customer_ui,x,get_conn,uid,manager,logger_arg or logger,compact)
    customer_ui._case_card=case_card

    def create_case_form(st_arg,u,get_conn,logger_arg=None):
        return _create_form(st_arg,u,get_conn,customer_core,customer_ui,logger_arg or logger)
    customer_ui._create_case_form=create_case_form

    def render_cases_page(st_arg,u,get_conn,page_title=None,logger_arg=None):
        return _render_cases_page(st_arg,u,get_conn,customer_core,customer_ui,page_title,logger_arg or logger)
    customer_ui.render_cases_page=render_cases_page

    # Strong route isolation. Both route AND child destination are normalized.
    original_sidebar=ns["sidebar_navigation"]
    def sidebar_navigation(u):
        before=st.session_state.get("main_page")
        try:
            return original_sidebar(u)
        finally:
            page=st.session_state.get("main_page")
            if page=="admin":
                st.session_state["admin_scope"]="system"
                if st.session_state.get("admin_view") not in {"users","customers"}:
                    st.session_state["admin_view"]="users"
            elif page=="ops_admin":
                st.session_state["admin_scope"]="ops"
                allowed={"types","reasons","audit","backup"} if bool(u.get("is_admin")) else {"types","reasons"}
                if st.session_state.get("admin_view") not in allowed:
                    st.session_state["admin_view"]="types"
            if page=="customer_work" and before!="customer_work":
                # Clicking the top Customer Work tab from another page always opens Processing.
                st.session_state.pop("cw_case_id",None)
    ns["sidebar_navigation"]=sidebar_navigation

    original_admin=ns["admin_page"]
    def admin_page(u):
        page=st.session_state.get("main_page")
        if page=="admin":
            st.session_state["admin_scope"]="system"
            if st.session_state.get("admin_view") not in {"users","customers"}:
                st.session_state["admin_view"]="users"
        elif page=="ops_admin":
            st.session_state["admin_scope"]="ops"
            allowed={"types","reasons","audit","backup"} if bool(u.get("is_admin")) else {"types","reasons"}
            if st.session_state.get("admin_view") not in allowed:
                st.session_state["admin_view"]="types"
        return original_admin(u)
    ns["admin_page"]=admin_page

    customer_ui._CUSTOMER_WORK_REFINEMENT_INSTALLED=True
    if logger or ns.get("LOGGER"):
        (logger or ns.get("LOGGER")).info("CUSTOMER_WORK_REFINEMENT_INSTALLED version=%s",VERSION)
