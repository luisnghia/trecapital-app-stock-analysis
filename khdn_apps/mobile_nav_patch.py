"""Build-time source patch for compact KHDN mobile navigation and leader analytics.

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

    # CBHT: put the only standalone action in the status-card group and remove
    # the separate operation-tab strip beneath it.
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

    # QLKH: create/assign becomes a card beside workflow statuses; review,
    # assigned and history are reached directly from the status cards.
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

    # Lãnh đạo/Admin - Quản lý công việc: the status cards themselves are the
    # navigation. Remove the redundant two-button strip underneath them.
    source = _replace_once(
        source,
        '    view=pill_nav("leader_view",[("active","📋 Công việc đang theo dõi"),("history","🕘 Lịch sử & yêu cầu làm lại")],default="active",prefix="subnav_leader")\n',
        '    view=st.session_state.get("leader_view","active")\n    if view not in ("active","history"):\n        view="active"; st.session_state["leader_view"]=view\n',
        "Leader operation tabs",
    )

    # Dashboard-only workflow analysis. Attribution comes from task_actions so
    # the staff member shown is the person who actually performed the action.
    # Counts are DISTINCT task counts, not event-frequency counts.
    workflow_helper = r'''

def _render_workflow_staff_analysis(task_df):
    """Dashboard: số hồ sơ điều phối / trả lại / hủy theo cán bộ, tuần và tháng hiện tại."""
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

    periods = [
        ("Tuần", week_start, tomorrow),
        ("Tháng", month_start, tomorrow),
    ]
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
    _html_table(show[["Cán bộ","Vai trò"] + numeric_cols], max_height=520)

    # Heatmap theo số lượng hồ sơ, không dùng cột tổng để tránh tổng làm lệch thang màu.
    try:
        import plotly.graph_objects as go
        heat_cols = ["Điều phối tuần", "Trả lại tuần", "Hủy tuần", "Điều phối tháng", "Trả lại tháng", "Hủy tháng"]
        z = show[heat_cols].astype(float).to_numpy()
        y = [f"{r['Cán bộ']} · {r['Vai trò']}" for _, r in show.iterrows()]
        fig = go.Figure(go.Heatmap(
            z=z,
            x=heat_cols,
            y=y,
            text=z.astype(int),
            texttemplate="%{text}",
            colorscale=[[0,"#17312F"],[0.45,"#0B7F75"],[0.75,"#F4B41A"],[1,"#D64545"]],
            colorbar=dict(title="Số hồ sơ", thickness=12),
            hovertemplate="Cán bộ: %{y}<br>Chỉ tiêu: %{x}<br>Số hồ sơ: %{z:.0f}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text="Heatmap số lượng hồ sơ điều phối / trả lại / hủy", x=0, xanchor="left", font=dict(size=14)),
            height=max(320, min(720, 48 * max(1, len(show)) + 180)),
            margin=dict(l=120, r=20, t=55, b=75),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#EAFBF7"),
        )
        fig.update_xaxes(tickangle=-20, automargin=True)
        fig.update_yaxes(automargin=True)
        st.plotly_chart(fig, use_container_width=True, config=_plotly_config())
    except Exception as exc:
        st.caption(f"Chưa thể hiển thị heatmap: {exc}")
'''
    source = _replace_once(
        source,
        '\ndef dashboard_page(u):\n',
        workflow_helper + '\n\ndef dashboard_page(u):\n',
        "workflow staff analysis helper",
    )

    # Place the workflow analysis at the absolute bottom of Dashboard, after the
    # detailed data table and Excel export. Do not render it in Quản lý công việc.
    dashboard_report_line = '    report=make_excel_report(detail_df, support_privacy=support_view); st.download_button("Xuất báo cáo Excel theo bộ lọc",report,file_name=f"KHDN_TacNghiep_{datetime.now():%Y%m%d_%H%M}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",type="primary")\n'
    source = _replace_once(
        source,
        dashboard_report_line,
        dashboard_report_line + '    if bool(u["is_admin"]) or u["role"] == "Lãnh đạo phòng":\n        st.markdown("## Phân tích điều phối / trả lại / hủy hồ sơ theo cán bộ")\n        _render_workflow_staff_analysis(room_f)\n',
        "Dashboard bottom workflow analysis",
    )

    # IMPORTANT: Admin stays exactly as the original five-button navigation.
    # The CSS below only changes mobile layout into two columns.

    # Inject this at the END of inject_css(). Streamlit's base responsive rules
    # force columns to 100% width at small breakpoints; these more-specific final
    # selectors support both old `column` and current `stColumn` test IDs.
    final_mobile_css = r'''

    /* V2.33 final compact workflow/admin override */
    div[class*="st-key-ops_create_support_view_"] button,
    div[class*="st-key-ops_create_qlkh_view_"] button,
    div[class*="st-key-ops_alert_create_support_view_"] button,
    div[class*="st-key-ops_alert_create_qlkh_view_"] button{
      background:linear-gradient(135deg,#FFD45A 0%,#F4B41A 100%)!important;
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
      border:2px solid #FFE790!important;
      box-shadow:0 8px 20px rgba(244,180,26,.34)!important;
      font-weight:950!important;
    }
    div[class*="st-key-ops_create_support_view_"] button *,
    div[class*="st-key-ops_create_qlkh_view_"] button *,
    div[class*="st-key-ops_alert_create_support_view_"] button *,
    div[class*="st-key-ops_alert_create_qlkh_view_"] button *{
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important;
    }

    @media(max-width:768px){
      /* Workflow cards: CBHT / QLKH / Lãnh đạo always two columns. */
      div[class*="st-key-ops_cards_support_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_leader_view"] [data-testid="stHorizontalBlock"]{
        display:grid!important;
        grid-template-columns:repeat(2,minmax(0,1fr))!important;
        gap:.44rem!important;
        align-items:stretch!important;
        overflow:visible!important;
        width:100%!important;
      }
      div[class*="st-key-ops_cards_support_view"] [data-testid="stHorizontalBlock"]>div,
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stHorizontalBlock"]>div,
      div[class*="st-key-ops_cards_leader_view"] [data-testid="stHorizontalBlock"]>div,
      div[class*="st-key-ops_cards_support_view"] [data-testid="stColumn"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stColumn"],
      div[class*="st-key-ops_cards_leader_view"] [data-testid="stColumn"],
      div[class*="st-key-ops_cards_support_view"] [data-testid="column"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="column"],
      div[class*="st-key-ops_cards_leader_view"] [data-testid="column"]{
        width:100%!important;min-width:0!important;max-width:none!important;
        flex:0 0 auto!important;grid-column:auto!important;padding:0!important;margin:0!important;
      }
      div[class*="st-key-ops_cards_support_view"] button,
      div[class*="st-key-ops_cards_qlkh_view"] button,
      div[class*="st-key-ops_cards_leader_view"] button{
        width:100%!important;min-height:70px!important;height:100%!important;
        padding:7px 6px!important;border-radius:13px!important;margin:0!important;
      }
      div[class*="st-key-ops_cards_support_view"] button p,
      div[class*="st-key-ops_cards_qlkh_view"] button p,
      div[class*="st-key-ops_cards_leader_view"] button p{
        font-size:.69rem!important;line-height:1.12!important;margin:0!important;
        white-space:pre-line!important;overflow-wrap:anywhere!important;
      }

      /* Admin: preserve all five original buttons, force 2-column mobile grid. */
      div[class*="st-key-subnav_admin_row"] [data-testid="stHorizontalBlock"]{
        display:grid!important;
        grid-template-columns:repeat(2,minmax(0,1fr))!important;
        gap:.44rem!important;
        align-items:stretch!important;
        overflow:visible!important;
        width:100%!important;
      }
      div[class*="st-key-subnav_admin_row"] [data-testid="stHorizontalBlock"]>div,
      div[class*="st-key-subnav_admin_row"] [data-testid="stColumn"],
      div[class*="st-key-subnav_admin_row"] [data-testid="column"]{
        width:100%!important;min-width:0!important;max-width:none!important;
        flex:0 0 auto!important;padding:0!important;margin:0!important;
      }
      div[class*="st-key-subnav_admin_"] button{
        width:100%!important;min-height:50px!important;height:100%!important;
        padding:6px 7px!important;border-radius:12px!important;margin:0!important;
        white-space:normal!important;
      }
      div[class*="st-key-subnav_admin_"] button p{
        font-size:.70rem!important;line-height:1.12!important;white-space:normal!important;margin:0!important;
      }

      div[class*="st-key-ops_cards_support_view"],
      div[class*="st-key-ops_cards_qlkh_view"],
      div[class*="st-key-ops_cards_leader_view"],
      div[class*="st-key-subnav_admin_row"]{margin-bottom:.35rem!important}
    }

    @media(max-width:430px){
      div[class*="st-key-ops_cards_support_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_leader_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-subnav_admin_row"] [data-testid="stHorizontalBlock"]{
        grid-template-columns:repeat(2,minmax(0,1fr))!important;
      }
      div[class*="st-key-ops_cards_support_view"] button,
      div[class*="st-key-ops_cards_qlkh_view"] button,
      div[class*="st-key-ops_cards_leader_view"] button{min-height:66px!important;padding:6px 4px!important}
      div[class*="st-key-ops_cards_support_view"] button p,
      div[class*="st-key-ops_cards_qlkh_view"] button p,
      div[class*="st-key-ops_cards_leader_view"] button p{font-size:.64rem!important}
      div[class*="st-key-subnav_admin_"] button{min-height:46px!important;padding:5px 4px!important}
      div[class*="st-key-subnav_admin_"] button p{font-size:.66rem!important}
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
