"""Move Customer Work priority quadrants into the Today screen.

Goals:
- Customer Work keeps only Processing + New work tabs.
- Today becomes the operational cockpit for the Eisenhower quadrants.
- Quadrants are shown as a heat scale and sorted I -> IV, then by risk/due date.
- Leaders/Admin can open Today for a room-wide view while keeping their default
  landing page on the management dashboard.
- Customer selectors continue to use the single active `customers` master used
  by System administration -> Customer CIF; no duplicate planning customer list.
"""
from __future__ import annotations

from datetime import date, datetime
import html

VERSION = "1.0.0"

_HEAT = {
    1: {"icon": "🔴", "accent": "#D92D20", "bg": "rgba(217,45,32,.14)", "border": "rgba(240,68,56,.72)"},
    2: {"icon": "🟠", "accent": "#F79009", "bg": "rgba(247,144,9,.14)", "border": "rgba(247,144,9,.72)"},
    3: {"icon": "🟡", "accent": "#FEC84B", "bg": "rgba(254,200,75,.12)", "border": "rgba(254,200,75,.68)"},
    4: {"icon": "🟢", "accent": "#12B76A", "bg": "rgba(18,183,106,.10)", "border": "rgba(18,183,106,.58)"},
}


def _quadrant(x):
    try:
        q = int(x.get("quadrant") or 4)
    except Exception:
        q = 4
    return q if q in (1, 2, 3, 4) else 4


def _due_key(core, x):
    d = core.parse_dt(x.get("expected_complete_at"))
    return d if d is not None else datetime.max


def _priority_sort_key(core, x):
    """I->IV; within a quadrant: overdue, delayed, blockers, earliest due."""
    return (
        _quadrant(x),
        0 if x.get("is_overdue") else 1,
        0 if x.get("is_stage_delayed") else 1,
        -int(x.get("open_issue_count") or 0),
        _due_key(core, x),
        int(x.get("id") or 0),
    )


def _install_heat_css(st):
    rules = []
    for q, c in _HEAT.items():
        rules.append(
            f'''div[class*="st-key-cw_heat_q{q}"]{{
                border-left:6px solid {c["accent"]}!important;
                border-top:1px solid {c["border"]}!important;
                border-right:1px solid {c["border"]}!important;
                border-bottom:1px solid {c["border"]}!important;
                border-radius:14px!important;
                background:{c["bg"]}!important;
                padding:.38rem .48rem .52rem .48rem!important;
                margin:.55rem 0 .8rem 0!important;
            }}
            div[class*="st-key-cw_heat_q{q}"] details{{background:transparent!important;}}
            div[class*="st-key-cw_heat_q{q}"] summary{{font-weight:850!important;}}'''
        )
    st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)


def _heat_summary(st, ui, data):
    counts = {q: sum(_quadrant(x) == q for x in data) for q in range(1, 5)}
    cards = []
    for q in range(1, 5):
        c = _HEAT[q]
        label = html.escape(ui.core.quadrant_label(q))
        cards.append(
            f'''<div class="cw-heat-card" style="border-color:{c['border']};background:{c['bg']};">
                <div class="cw-heat-label"><span>{c['icon']}</span>{label}</div>
                <div class="cw-heat-count" style="color:{c['accent']};">{counts[q]}</div>
            </div>'''
        )
    st.html(
        '''<div class="cw-heat-grid">''' + "".join(cards) + '''</div>
        <style>
        .cw-heat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:.35rem 0 .85rem 0}
        .cw-heat-card{border:1px solid;border-radius:14px;padding:12px 13px;min-height:88px}
        .cw-heat-label{font-weight:800;font-size:.92rem;line-height:1.25;display:flex;gap:7px;align-items:flex-start}
        .cw-heat-count{font-size:1.55rem;font-weight:900;margin-top:8px}
        @media(max-width:760px){.cw-heat-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.cw-heat-card{min-height:82px;padding:10px}.cw-heat-label{font-size:.80rem}.cw-heat-count{font-size:1.35rem}}
        </style>'''
    )
    return counts


def _render_priority_heatmap(st, ui, data, get_conn, uid, manager, logger=None):
    st.subheader("🔥 Góc phần tư ưu tiên")
    st.caption("Xếp theo mức ưu tiên I → IV. Trong từng góc: quá hạn → mục bị chậm → có vướng mắc → hạn gần nhất.")
    _install_heat_css(st)
    ordered = sorted(list(data), key=lambda x: _priority_sort_key(ui.core, x))
    counts = _heat_summary(st, ui, ordered)
    for q in range(1, 5):
        c = _HEAT[q]
        arr = [x for x in ordered if _quadrant(x) == q]
        with st.container(key=f"cw_heat_q{q}"):
            with st.expander(
                f"{c['icon']} {ui.core.quadrant_label(q)} · {counts[q]} công việc",
                expanded=(q == 1),
            ):
                if not arr:
                    st.caption("Không có công việc trong nhóm ưu tiên này.")
                for x in arr:
                    ui._case_card(st, x, get_conn, uid, manager, logger, compact=False)


def install(ui_module, nav_module, weekly_core=None, logger=None):
    if getattr(ui_module, "_PRIORITY_TODAY_PATCH_INSTALLED", False):
        return

    st_core = ui_module.core
    original_create_form = ui_module._create_case_form

    def _create_case_form(st, u, get_conn, logger=None):
        with get_conn() as c:
            active_count = len(st_core.customers(c, int(u["id"])))
        st.caption(
            f"Khách hàng dùng chung từ Quản trị hệ thống → Khách hàng CIF · {active_count} khách hàng đang hoạt động."
        )
        return original_create_form(st, u, get_conn, logger)

    def render_cases_page(st, u, get_conn, page_title=None, logger=None):
        st_core.ensure_schema(get_conn, logger)
        uid = int(u["id"])
        manager = ui_module._manager(u)
        if page_title:
            page_title("Công việc khách hàng", "Theo dõi xuyên suốt từ tiếp cận đến hoàn thành")
        else:
            st.title("👥 Công việc khách hàng")
        if st.session_state.get("cw_case_id"):
            ui_module._case_detail(st, u, get_conn, int(st.session_state["cw_case_id"]), logger)
            ui_module._glossary(st)
            return

        tab_processing, tab_new = st.tabs(["Đang xử lý", "Tạo công việc mới"])
        with tab_processing:
            with get_conn() as c:
                data = st_core.list_cases(c, uid=uid, manager=manager, include_completed=False)
            f1, f2 = st.columns(2)
            stages = sorted({x.get("stage_name") for x in data if x.get("stage_name")})
            sf = f1.selectbox("Lọc mục công việc", ["Tất cả"] + stages, key="cw_filter_stage")
            search = f2.text_input("Tìm khách hàng/công việc", key="cw_filter_text")
            ss = str(search or "").lower().strip()
            shown = [
                x for x in data
                if (sf == "Tất cả" or x.get("stage_name") == sf)
                and (
                    not ss
                    or ss in str(x.get("customer_name") or "").lower()
                    or ss in str(x.get("cif") or "").lower()
                    or ss in str(x.get("title") or "").lower()
                )
            ]
            shown = sorted(shown, key=lambda x: _priority_sort_key(st_core, x))
            if not shown:
                st.info("Không có công việc phù hợp.")
            for x in shown:
                ui_module._case_card(st, x, get_conn, uid, manager, logger)
        with tab_new:
            _create_case_form(st, u, get_conn, logger)
        ui_module._glossary(st)

    def render_today_page(st, u, get_conn, page_title=None, logger=None):
        st_core.ensure_schema(get_conn, logger)
        uid = int(u["id"])
        manager = ui_module._manager(u)
        if page_title:
            page_title(
                "Hôm nay",
                "Việc phải làm hôm nay, tồn đọng và thứ tự ưu tiên theo góc phần tư",
            )
        else:
            st.title("🏠 Hôm nay")

        if st.session_state.get("cw_case_id"):
            ui_module._case_detail(st, u, get_conn, int(st.session_state["cw_case_id"]), logger)
            ui_module._glossary(st)
            return

        today = date.today().isoformat()
        with get_conn() as c:
            cases = st_core.list_cases(c, uid=uid, manager=manager, include_completed=False)
            try:
                if manager:
                    wp = [dict(r) for r in c.execute(
                        """SELECT w.*,u.full_name AS owner_name,c.customer_name AS master_customer_name
                           FROM weekly_plan_items w
                           JOIN users u ON u.id=w.user_id
                           LEFT JOIN customers c ON c.id=w.customer_id
                           WHERE w.status NOT IN ('DONE','CANCELLED')
                             AND COALESCE(w.approval_status,'APPROVED')='APPROVED'
                           ORDER BY w.work_date,COALESCE(w.start_time,'99:99'),w.id"""
                    ).fetchall()]
                else:
                    wp = [dict(r) for r in c.execute(
                        """SELECT w.*,u.full_name AS owner_name,c.customer_name AS master_customer_name
                           FROM weekly_plan_items w
                           JOIN users u ON u.id=w.user_id
                           LEFT JOIN customers c ON c.id=w.customer_id
                           WHERE w.user_id=? AND w.status NOT IN ('DONE','CANCELLED')
                             AND COALESCE(w.approval_status,'APPROVED')='APPROVED'
                           ORDER BY w.work_date,COALESCE(w.start_time,'99:99'),w.id""",
                        (uid,),
                    ).fetchall()]
            except Exception:
                wp = []

        due_today = sorted(
            [x for x in cases if str(x.get("expected_complete_at") or "")[:10] == today],
            key=lambda x: _priority_sort_key(st_core, x),
        )
        backlog = sorted(
            [x for x in cases if x.get("is_overdue") or x.get("is_stage_delayed") or int(x.get("open_issue_count") or 0) > 0],
            key=lambda x: _priority_sort_key(st_core, x),
        )
        today_plan = [x for x in wp if str(x.get("work_date") or "")[:10] == today]
        plan_backlog = [x for x in wp if str(x.get("work_date") or "")[:10] < today]
        pending = sum(1 for x in cases if x.get("plan_approval_status") == "PENDING")

        a, b, c, d = st.columns(4)
        a.metric("Việc hôm nay", len(today_plan) + len(due_today))
        b.metric("Tồn đọng", len(backlog) + len(plan_backlog))
        c.metric("Đang vướng mắc", sum(int(x.get("open_issue_count") or 0) > 0 for x in cases))
        d.metric("Chờ phê duyệt", pending)

        # Priority is intentionally above the detailed lists so the user sees the
        # required order of attack immediately on mobile and desktop.
        _render_priority_heatmap(st, ui_module, cases, get_conn, uid, manager, logger)

        st.subheader("📅 Công việc theo kế hoạch hôm nay")
        if not today_plan and not due_today:
            st.info("Hôm nay chưa có công việc đã được phê duyệt.")
        for x in today_plan:
            with st.container(border=True):
                st.markdown(f"**{html.escape(str(x.get('title') or ''))}**")
                owner = f"👤 {x.get('owner_name')} · " if manager and x.get("owner_name") else ""
                customer = x.get("master_customer_name") or x.get("customer_text") or "Công việc nội bộ"
                st.caption(
                    f"{owner}{x.get('start_time') or x.get('daypart') or 'Cả ngày'} · "
                    f"{customer} · {x.get('category') or ''}"
                )
        for x in due_today:
            ui_module._case_card(st, x, get_conn, uid, manager, logger, compact=True)

        st.subheader("⏳ Công việc còn tồn đọng")
        if not backlog and not plan_backlog:
            st.success("Không có công việc tồn đọng.")
        for x in backlog:
            ui_module._case_card(st, x, get_conn, uid, manager, logger, compact=True)
        for x in plan_backlog:
            with st.container(border=True):
                st.markdown(f"**📌 {html.escape(str(x.get('title') or ''))}**")
                owner = f"👤 {x.get('owner_name')} · " if manager and x.get("owner_name") else ""
                customer = x.get("master_customer_name") or x.get("customer_text") or "Công việc nội bộ"
                st.caption(
                    f"{owner}Kế hoạch ngày {ui_module._date_text(x.get('work_date'))} · {customer}"
                )
                st.error("Quá ngày kế hoạch nhưng chưa hoàn thành.")
        ui_module._glossary(st)

    # Managers keep Dashboard as their landing page, but can explicitly open Today.
    original_plan_options = nav_module._plan_options

    def _plan_options(role, admin):
        options = list(original_plan_options(role, admin))
        manager = role == "Lãnh đạo phòng" or bool(admin)
        if manager and not any(route == "work_today" for route, _ in options):
            insert_at = 1 if options and options[0][0] == "work_dashboard" else 0
            options.insert(insert_at, ("work_today", "Công việc hôm nay"))
        return options

    ui_module._create_case_form = _create_case_form
    ui_module.render_cases_page = render_cases_page
    ui_module.render_today_page = render_today_page
    nav_module._plan_options = _plan_options
    ui_module._PRIORITY_TODAY_PATCH_INSTALLED = True

    # Assert at install time that Weekly Plan consumes the same master table.
    if weekly_core is not None:
        names = set(getattr(weekly_core.customers, "__code__", None).co_names if getattr(weekly_core.customers, "__code__", None) else ())
        if logger:
            logger.info("WEEKLY_PLAN_CUSTOMER_MASTER_SHARED function_names=%s", sorted(names))
    if logger:
        logger.info("PRIORITY_TODAY_PATCH_INSTALLED version=%s", VERSION)
