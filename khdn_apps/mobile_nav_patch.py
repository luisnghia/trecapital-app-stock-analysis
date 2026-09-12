"""Build-time source patch for compact KHDN mobile navigation and dashboard analytics.

The production loader keeps the large Streamlit engine compressed. This helper
patches only navigation/UI/reporting fragments before that engine is executed,
so the business workflow and persistent data remain unchanged.
"""


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"KHDN mobile-nav patch cannot find: {label}")
    return source.replace(old, new, 1)


def patch_source(source: str) -> str:
    # Allow action cards without a numeric counter. Status cards keep their
    # existing counters/attention animation; create cards render as plain CTAs.
    source = _replace_once(
        source,
        '            container_key = f"ops_alert_hot_{state_key}_{idx}" if needs_attention else f"ops_alert_idle_{state_key}_{idx}"\n',
        '            container_key = (f"ops_create_{state_key}_{idx}" if count is None else (f"ops_alert_hot_{state_key}_{idx}" if needs_attention else f"ops_alert_idle_{state_key}_{idx}"))\n',
        "ops card container key",
    )
    source = _replace_once(
        source,
        '                        f"{icon}  {label}\\n\\n{int(count)}{status_text}",\n',
        '                        (f"{icon}  {label}" if count is None else f"{icon}  {label}\\n\\n{int(count)}{status_text}"),\n',
        "ops card label",
    )

    # CBHT: place Create in the same status-card group and remove the separate
    # operation-tab strip. The source ops_action_cards() remains the renderer.
    source = _replace_once(
        source,
        '    ops_action_cards("support_view",[\n        ("inbox","📥","Chờ tiếp nhận",wait_count,True,wait_count>0),\n',
        '    ops_action_cards("support_view",[\n        ("create","➕","Tạo công việc mới",None,False,False),\n        ("inbox","📥","Chờ tiếp nhận",wait_count,True,wait_count>0),\n',
        "CBHT create card",
    )
    source = _replace_once(
        source,
        '    view=pill_nav("support_view",[("inbox","📥 Hồ sơ chờ tiếp nhận"),("create","➕ Tạo công việc mới"),("work","🛠 Hồ sơ đang xử lý"),("history","🕘 Lịch sử hồ sơ")],default="inbox",prefix="subnav_support")\n',
        '    view=st.session_state.get("support_view","inbox")\n    if view not in ("inbox","create","work","history"):\n        view="inbox"; st.session_state["support_view"]=view\n',
        "CBHT operation tabs",
    )

    # QLKH: same structure as leader_view — one ops_action_cards() group only.
    source = _replace_once(
        source,
        '    ops_action_cards("qlkh_view",[("assigned","📤","Chờ CBHT tiếp nhận",wait,True,wait>0),("assigned","↩️","CBHT trả lại",returned,True,returned>0,{"qlkh_focus":"returned"}),("assigned","🛠️","CBHT đang xử lý",work,True,False),("review","⭐","Chờ tôi đánh giá",len(pending),True,len(pending)>0),("history","✅","Đã kết thúc",closed,False,False)])\n',
        '    ops_action_cards("qlkh_view",[("create","➕","Tạo/giao hồ sơ",None,False,False),("assigned","📤","Chờ CBHT tiếp nhận",wait,True,wait>0),("assigned","↩️","CBHT trả lại",returned,True,returned>0,{"qlkh_focus":"returned"}),("assigned","🛠️","CBHT đang xử lý",work,True,False),("review","⭐","Chờ tôi đánh giá",len(pending),True,len(pending)>0),("history","✅","Đã kết thúc",closed,False,False)])\n',
        "QLKH create card",
    )
    source = _replace_once(
        source,
        '    view=pill_nav("qlkh_view",[("create","➕ Tạo / giao hồ sơ"),("review","⭐ Công việc chờ đánh giá"),("assigned","📂 Hồ sơ tôi phụ trách"),("history","🕘 Lịch sử đánh giá")],default="create",prefix="subnav_qlkh")\n',
        '    view=st.session_state.get("qlkh_view","create")\n    if view not in ("create","review","assigned","history"):\n        view="create"; st.session_state["qlkh_view"]=view\n',
        "QLKH operation tabs",
    )

    # Lãnh đạo/Admin - Quản lý công việc: status cards are navigation; remove
    # the redundant two-button strip beneath them.
    source = _replace_once(
        source,
        '    view=pill_nav("leader_view",[("active","📋 Công việc đang theo dõi"),("history","🕘 Lịch sử & yêu cầu làm lại")],default="active",prefix="subnav_leader")\n',
        '    view=st.session_state.get("leader_view","active")\n    if view not in ("active","history"):\n        view="active"; st.session_state["leader_view"]=view\n',
        "Leader operation tabs",
    )

    # Admin keeps the original five choices and old active/idle color semantics,
    # but is rendered inside the same ops_cards_* container family as leader_view.
    admin_nav = (
        '    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n'
        '    _admin_values=[v for v,_,_ in _admin_options]\n'
        '    _admin_current=st.session_state.get("admin_view","users")\n'
        '    if _admin_current not in _admin_values: _admin_current="users"; st.session_state["admin_view"]="users"\n'
        '    with st.container(key="ops_cards_admin_view"):\n'
        '        _admin_cols=st.columns(len(_admin_options),gap="small")\n'
        '        for _idx,(_value,_icon,_label) in enumerate(_admin_options):\n'
        '            with _admin_cols[_idx]:\n'
        '                with st.container(key=f"admin_nav_card_{_idx}"):\n'
        '                    if st.button(f"{_icon}  {_label}",key=f"adminnav_{_value}",use_container_width=True,type="primary" if _admin_current==_value else "secondary"):\n'
        '                        st.session_state["admin_view"]=_value; st.rerun()\n'
        '    admin_view=st.session_state.get("admin_view","users")\n'
    )
    source = _replace_once(
        source,
        '    admin_view = pill_nav("admin_view", [("users","👥 Người dùng"),("customers","🏢 Khách hàng CIF"),("types","🧩 Loại công việc"),("audit","🧾 Audit"),("backup","💾 Sao lưu")], default="users", prefix="subnav_admin")\n',
        admin_nav,
        "Admin leader-structure navigation",
    )

    # Dashboard-only workflow analysis. Attribution comes from task_actions so
    # the staff member shown is the person who actually performed the action.
    # Counts are DISTINCT task counts, not event-frequency counts.
    workflow_helper = r'''

def _render_workflow_staff_analysis(task_df):
    # Dashboard: unique hồ sơ điều phối / trả lại / hủy theo cán bộ, tuần/tháng hiện tại.
    if task_df is None or task_df.empty or "id" not in task_df.columns:
        st.info("Chưa có dữ liệu điều phối / trả lại / hủy hồ sơ.")
        return
    ids = sorted({int(x) for x in pd.to_numeric(task_df["id"], errors="coerce").dropna().tolist()})
    if not ids:
        st.info("Chưa có dữ liệu điều phối / trả lại / hủy hồ sơ.")
        return
    marks = ",".join(["?"] * len(ids))
    acts = qdf(f"""SELECT a.task_id,a.action,a.actor_user_id,a.created_at,u.full_name actor,u.role
                   FROM task_actions a
                   JOIN users u ON u.id=a.actor_user_id
                   WHERE a.task_id IN ({marks})
                     AND a.action IN ('RETURN_TO_QLKH','QLKH_REASSIGN','REASSIGN','QLKH_CANCEL')
                   ORDER BY a.id""", ids)
    if acts.empty:
        st.info("Chưa phát sinh sự kiện điều phối / trả lại / hủy hồ sơ trong phạm vi dữ liệu này.")
        return

    acts["event_dt"] = pd.to_datetime(acts["created_at"], errors="coerce")
    acts = acts[acts["event_dt"].notna()].copy()
    if acts.empty:
        st.info("Chưa có mốc thời gian hợp lệ để phân tích điều phối / trả lại / hủy.")
        return
    category_map = {
        "RETURN_TO_QLKH": "Trả lại",
        "QLKH_REASSIGN": "Điều phối",
        "REASSIGN": "Điều phối",
        "QLKH_CANCEL": "Hủy",
    }
    acts["Nhóm"] = acts["action"].map(category_map)

    today = pd.Timestamp(now_dt()).normalize()
    week_start = today - pd.Timedelta(days=int(today.weekday()))
    month_start = today.replace(day=1)
    tomorrow = today + pd.Timedelta(days=1)
    periods = [("Tuần", week_start, tomorrow), ("Tháng", month_start, tomorrow)]
    cats = ["Điều phối", "Trả lại", "Hủy"]
    actors = acts[["actor","role"]].drop_duplicates().sort_values(["role","actor"], kind="stable")
    rows = []
    for _, person in actors.iterrows():
        actor = person["actor"]
        role = person["role"]
        g = acts[(acts["actor"] == actor) & (acts["role"] == role)].copy()
        row = {"Cán bộ": str(actor or "—"), "Vai trò": str(role or "—")}
        for period_label, start_dt, end_dt in periods:
            gp = g[(g["event_dt"] >= start_dt) & (g["event_dt"] < end_dt)]
            period_total = set()
            for cat in cats:
                z = gp[gp["Nhóm"].eq(cat)]
                task_ids = {int(v) for v in pd.to_numeric(z["task_id"], errors="coerce").dropna().tolist()}
                row[f"{cat} {period_label.lower()}"] = len(task_ids)
                period_total.update(task_ids)
            row[f"Tổng {period_label.lower()}"] = len(period_total)
        rows.append(row)

    show = pd.DataFrame(rows)
    if show.empty:
        st.info("Chưa có dữ liệu phân tích theo cán bộ.")
        return
    numeric_cols = [
        "Điều phối tuần", "Trả lại tuần", "Hủy tuần", "Tổng tuần",
        "Điều phối tháng", "Trả lại tháng", "Hủy tháng", "Tổng tháng",
    ]
    for c in numeric_cols:
        show[c] = pd.to_numeric(show[c], errors="coerce").fillna(0).astype(int)
    show = show.sort_values(["Tổng tháng","Tổng tuần","Cán bộ"], ascending=[False,False,True], kind="stable").reset_index(drop=True)

    week_dispatch = int(show["Điều phối tuần"].sum())
    week_return = int(show["Trả lại tuần"].sum())
    week_cancel = int(show["Hủy tuần"].sum())
    month_dispatch = int(show["Điều phối tháng"].sum())
    month_return = int(show["Trả lại tháng"].sum())
    month_cancel = int(show["Hủy tháng"].sum())
    render_kpi_cards([
        ("Hồ sơ điều phối", money(month_dispatch), f"Tuần hiện tại: {money(week_dispatch)}"),
        ("Hồ sơ trả lại", money(month_return), f"Tuần hiện tại: {money(week_return)}"),
        ("Hồ sơ hủy", money(month_cancel), f"Tuần hiện tại: {money(week_cancel)}"),
    ])
    st.markdown(
        '<div class="section-note"><b>Cách ghi nhận:</b> mỗi cán bộ/mỗi nhóm chỉ tiêu chỉ đếm <b>hồ sơ duy nhất</b> trong tuần hoặc tháng hiện tại; không đếm số lần lặp lại. “Điều phối” gồm QLKH đổi CBHT và Lãnh đạo/Admin điều chuyển; “Trả lại” ghi cho CBHT thực hiện trả; “Hủy” ghi cho cán bộ thực hiện hủy.</div>',
        unsafe_allow_html=True,
    )

    # Heatmap trực tiếp trên bảng; mỗi vai trò có một bảng riêng.
    global_heat_max = max(1, int(show[numeric_cols].to_numpy().max()))
    def _heat_style(v):
        try:
            n = int(v)
        except Exception:
            return ""
        if n <= 0:
            return "background-color:#17312F;color:#D9EEEA;font-weight:700;"
        ratio = min(1.0, max(0.0, n / global_heat_max))
        if ratio <= 0.25:
            return "background-color:#195F58;color:#FFFFFF;font-weight:850;"
        if ratio <= 0.50:
            return "background-color:#0B7F75;color:#FFFFFF;font-weight:900;"
        if ratio <= 0.75:
            return "background-color:#B88716;color:#16120A;font-weight:950;"
        return "background-color:#F4B41A;color:#181306;font-weight:950;"

    present_roles = [str(x) for x in show["Vai trò"].dropna().astype(str).unique().tolist()]
    preferred = ["Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng"]
    role_order = [r for r in preferred if r in present_roles] + sorted([r for r in present_roles if r not in preferred])
    for role in role_order:
        table = show[show["Vai trò"].astype(str).eq(role)][["Cán bộ"] + numeric_cols].copy()
        if table.empty:
            continue
        st.markdown(f"#### {role}")
        sty = table.style
        try:
            sty = sty.map(_heat_style, subset=numeric_cols)
        except AttributeError:
            sty = sty.applymap(_heat_style, subset=numeric_cols)
        sty = sty.set_properties(subset=["Tổng tuần","Tổng tháng"], **{"font-weight":"950","border-left":"2px solid #F4B41A"})
        st.dataframe(sty, use_container_width=True, hide_index=True, height=_task_list_height(len(table), 420))
'''
    source = _replace_once(
        source,
        '\ndef dashboard_page(u):\n',
        workflow_helper + '\n\ndef dashboard_page(u):\n',
        "workflow staff analysis helper",
    )

    # Workflow analysis sits immediately before Dữ liệu chi tiết. Therefore the
    # detailed data table + Excel export are the absolute bottom of Dashboard.
    detail_anchor = '    st.subheader("Dữ liệu chi tiết")\n'
    source = _replace_once(
        source,
        detail_anchor,
        '    if bool(u["is_admin"]) or u["role"] == "Lãnh đạo phòng":\n        st.markdown("## Phân tích điều phối / trả lại / hủy hồ sơ theo cán bộ")\n        _render_workflow_staff_analysis(room_f)\n\n' + detail_anchor,
        "Dashboard workflow analysis before detail",
    )

    # Final CSS: support/QLKH use exactly the same ops_cards_* structure as the
    # working leader_view. Admin uses the same container layout but restores the
    # old subnav teal/dark color semantics and compact pill height.
    final_mobile_css = r'''

    /* V2.35: one proven layout path for Leader/Admin/CBHT/CBQLKH */
    div[class*="st-key-ops_create_support_view_"] button,
    div[class*="st-key-ops_create_qlkh_view_"] button,
    div[class*="st-key-ops_alert_create_support_view_"] button,
    div[class*="st-key-ops_alert_create_qlkh_view_"] button{
      background:linear-gradient(135deg,#FFD45A 0%,#F4B41A 100%)!important;
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
      border:2px solid #FFE790!important;box-shadow:0 8px 20px rgba(244,180,26,.34)!important;
      font-weight:950!important;
    }
    div[class*="st-key-ops_create_support_view_"] button *,
    div[class*="st-key-ops_create_qlkh_view_"] button *,
    div[class*="st-key-ops_alert_create_support_view_"] button *,
    div[class*="st-key-ops_alert_create_qlkh_view_"] button *{
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important;
    }

    /* Admin: restore the original subnav palette. */
    div[class*="st-key-admin_nav_card_"] button{
      min-height:43px!important;border-radius:999px!important;
      border:1.6px solid rgba(164,232,219,.42)!important;
      background:linear-gradient(135deg,#173A37,#15302E)!important;
      color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;
      font-size:.88rem!important;font-weight:850!important;
      box-shadow:0 5px 14px rgba(0,0,0,.20)!important;padding:0 15px!important;
    }
    div[class*="st-key-admin_nav_card_"] button *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    div[class*="st-key-admin_nav_card_"] button:hover{
      background:linear-gradient(135deg,#20514B,#1A3D39)!important;
      border-color:#F4B41A!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
    }
    div[class*="st-key-admin_nav_card_"] button[kind="primary"],
    div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{
      background:linear-gradient(135deg,#006B68,#008F80)!important;
      color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
      border-color:#F4B41A!important;box-shadow:0 8px 19px rgba(11,127,117,.24)!important;
    }

    @media(max-width:768px){
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"]{
        display:flex!important;flex-wrap:wrap!important;gap:.44rem!important;
        align-items:stretch!important;overflow:visible!important;width:100%!important;
      }
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"] > [data-testid="column"],
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"] > div{
        flex:0 0 calc(50% - .22rem)!important;
        width:calc(50% - .22rem)!important;min-width:0!important;max-width:calc(50% - .22rem)!important;
        box-sizing:border-box!important;margin:0!important;padding:0!important;
      }
      div[class*="st-key-ops_cards_"] button{
        width:100%!important;min-height:70px!important;height:100%!important;
        padding:7px 6px!important;border-radius:13px!important;margin:0!important;
      }
      div[class*="st-key-ops_cards_"] button p{
        font-size:.69rem!important;line-height:1.12!important;margin:0!important;
        white-space:pre-line!important;overflow-wrap:anywhere!important;
      }

      /* Admin keeps compact old-style buttons inside the same two-column grid. */
      div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button{
        min-height:46px!important;height:100%!important;border-radius:999px!important;padding:5px 9px!important;
      }
      div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button p{
        font-size:.70rem!important;line-height:1.12!important;white-space:normal!important;
      }
      div[class*="st-key-ops_cards_"]{margin-bottom:.35rem!important}
    }

    @media(max-width:430px){
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"] > [data-testid="column"],
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"] > div{
        flex:0 0 calc(50% - .22rem)!important;
        width:calc(50% - .22rem)!important;min-width:0!important;max-width:calc(50% - .22rem)!important;
      }
      div[class*="st-key-ops_cards_"] button{min-height:66px!important;padding:6px 4px!important}
      div[class*="st-key-ops_cards_"] button p{font-size:.64rem!important}
      div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button{
        min-height:44px!important;padding:4px 6px!important;
      }
      div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button p{font-size:.66rem!important}
    }
'''
    css_anchor = '</style>""", unsafe_allow_html=True)\n\ndef page_title(title, caption=None):'
    source = _replace_once(
        source,
        css_anchor,
        final_mobile_css + '\n</style>""", unsafe_allow_html=True)\n\ndef page_title(title, caption=None):',
        "final mobile CSS",
    )
    return source
