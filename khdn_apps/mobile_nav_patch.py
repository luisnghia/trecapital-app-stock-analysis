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

    # Reusable event analysis for Admin/Lãnh đạo. This reads task_actions so the
    # attribution is to the staff member who actually performed each action.
    workflow_helper = r'''

def _render_workflow_staff_analysis(task_df, *, compact=False):
    """Phân tích điều phối / trả lại / hủy theo cán bộ thực hiện hành động."""
    if task_df is None or task_df.empty or "id" not in task_df.columns:
        st.info("Chưa có dữ liệu điều phối / trả lại / hủy hồ sơ.")
        return
    ids = sorted({int(x) for x in pd.to_numeric(task_df["id"], errors="coerce").dropna().tolist()})
    if not ids:
        st.info("Chưa có dữ liệu điều phối / trả lại / hủy hồ sơ.")
        return
    marks = ",".join(["?"] * len(ids))
    acts = qdf(f"""SELECT a.task_id,a.action,a.actor_user_id,u.full_name actor,u.role
                   FROM task_actions a
                   JOIN users u ON u.id=a.actor_user_id
                   WHERE a.task_id IN ({marks})
                     AND a.action IN ('RETURN_TO_QLKH','QLKH_REASSIGN','REASSIGN','QLKH_CANCEL')
                   ORDER BY a.id""", ids)
    if acts.empty:
        st.info("Chưa phát sinh sự kiện điều phối / trả lại / hủy hồ sơ trong phạm vi dữ liệu này.")
        return
    category_map = {
        "RETURN_TO_QLKH": "Trả lại",
        "QLKH_REASSIGN": "Điều phối",
        "REASSIGN": "Điều phối",
        "QLKH_CANCEL": "Hủy",
    }
    acts["Nhóm"] = acts["action"].map(category_map)
    rows = []
    for (actor, role), g in acts.groupby(["actor","role"], dropna=False):
        row = {"Cán bộ": str(actor or "—"), "Vai trò": str(role or "—")}
        total_tasks = set()
        total_events = 0
        for cat, prefix in [("Điều phối","Điều phối"),("Trả lại","Trả lại"),("Hủy","Hủy")]:
            z = g[g["Nhóm"].eq(cat)]
            task_set = {int(v) for v in pd.to_numeric(z.get("task_id"), errors="coerce").dropna().tolist()}
            row[f"HS {prefix}"] = len(task_set)
            row[f"Lần {prefix}"] = int(len(z))
            total_tasks.update(task_set)
            total_events += int(len(z))
        row["HS có sự kiện"] = len(total_tasks)
        row["Tổng sự kiện"] = total_events
        rows.append(row)
    show = pd.DataFrame(rows)
    if show.empty:
        st.info("Chưa có dữ liệu phân tích theo cán bộ.")
        return
    show = show.sort_values(["Tổng sự kiện","Cán bộ"], ascending=[False,True], kind="stable").reset_index(drop=True)
    total_dispatch = acts[acts["Nhóm"].eq("Điều phối")]
    total_return = acts[acts["Nhóm"].eq("Trả lại")]
    total_cancel = acts[acts["Nhóm"].eq("Hủy")]
    render_kpi_cards([
        ("Hồ sơ điều phối", money(total_dispatch["task_id"].nunique()), f"{money(len(total_dispatch))} lần điều phối/đổi CBHT"),
        ("Hồ sơ trả lại", money(total_return["task_id"].nunique()), f"{money(len(total_return))} lần CBHT trả QLKH"),
        ("Hồ sơ hủy", money(total_cancel["task_id"].nunique()), f"{money(len(total_cancel))} lần hủy; vẫn giữ audit"),
    ])
    st.markdown('<div class="section-note"><b>Cách ghi nhận:</b> “Điều phối” gồm QLKH đổi CBHT và Lãnh đạo/Admin điều chuyển; “Trả lại” ghi cho CBHT thực hiện trả; “Hủy” ghi cho cán bộ thực hiện hủy. Một hồ sơ có thể phát sinh nhiều lần nên bảng thể hiện đồng thời số hồ sơ và số lần.</div>', unsafe_allow_html=True)
    _html_table(show, max_height=360 if compact else 520)
'''
    source = _replace_once(
        source,
        '\ndef dashboard_page(u):\n',
        workflow_helper + '\n\ndef dashboard_page(u):\n',
        "workflow staff analysis helper",
    )

    # Show the analysis directly in the Leader/Admin work-management page, but
    # keep it collapsed by default so the phone screen stays compact.
    leader_cards = '    ops_action_cards("leader_view",[("active","↩️","CBHT trả lại QLKH",len(returned_active),True,len(returned_active)>0,{"leader_focus":"returned"}),("active","⚠️","Đang/chờ xử lý",len(normal_active),True,len(normal_active)>0),("history","✅","Đã kết thúc",len(closed),False,False)])\n'
    source = _replace_once(
        source,
        leader_cards,
        leader_cards + '    with st.expander("📊 Phân tích điều phối / trả lại / hủy theo cán bộ", expanded=False):\n        _render_workflow_staff_analysis(df, compact=True)\n',
        "Leader workflow analysis",
    )

    # Also expose the same analysis in Dashboard for every Admin or Lãnh đạo
    # account. Use room_f so an Admin keeps a room-wide view even if their base
    # role is CBHT/QLKH; the current Dashboard filters still apply.
    source = _replace_once(
        source,
        '    st.subheader("Mục tiêu thời gian xử lý")\n',
        '    if bool(u["is_admin"]) or u["role"] == "Lãnh đạo phòng":\n        st.markdown("### Phân tích điều phối / trả lại / hủy hồ sơ theo cán bộ")\n        _render_workflow_staff_analysis(room_f, compact=False)\n\n    st.subheader("Mục tiêu thời gian xử lý")\n',
        "Dashboard workflow staff analysis",
    )

    # IMPORTANT: Admin stays exactly as the old five-button navigation. We do
    # not replace admin_view with a selectbox. The final CSS below only changes
    # its phone layout to a two-column grid.

    # Inject this at the END of inject_css(). Earlier CSS rules collapse columns
    # to full width on phones, so these final specific selectors deliberately win.
    final_mobile_css = r'''

    /* V2.32 final compact workflow/admin override */
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
    div[class*="st-key-ops_create_support_view_"] button:hover,
    div[class*="st-key-ops_create_qlkh_view_"] button:hover,
    div[class*="st-key-ops_alert_create_support_view_"] button:hover,
    div[class*="st-key-ops_alert_create_qlkh_view_"] button:hover{
      background:linear-gradient(135deg,#FFE88A 0%,#FFC72C 100%)!important;
      border-color:#FFF4BE!important;color:#201B0A!important;-webkit-text-fill-color:#201B0A!important;
    }

    @media(max-width:700px){
      /* CBHT / QLKH / Lãnh đạo: status/action cards are always two columns. */
      div[class*="st-key-ops_cards_support_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_leader_view"] [data-testid="stHorizontalBlock"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_create_support_view_"]),
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_create_qlkh_view_"]){
        display:grid!important;
        grid-template-columns:repeat(2,minmax(0,1fr))!important;
        gap:.44rem!important;
        align-items:stretch!important;
        overflow:visible!important;
      }
      div[class*="st-key-ops_cards_support_view"] [data-testid="stHorizontalBlock"]>div[data-testid="column"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stHorizontalBlock"]>div[data-testid="column"],
      div[class*="st-key-ops_cards_leader_view"] [data-testid="stHorizontalBlock"]>div[data-testid="column"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_create_support_view_"])>div[data-testid="column"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_create_qlkh_view_"])>div[data-testid="column"]{
        width:100%!important;min-width:0!important;max-width:none!important;
        flex:none!important;grid-column:auto!important;padding:0!important;
      }
      div[class*="st-key-ops_cards_support_view"] button,
      div[class*="st-key-ops_cards_qlkh_view"] button,
      div[class*="st-key-ops_cards_leader_view"] button{
        min-height:70px!important;height:100%!important;padding:7px 6px!important;
        border-radius:13px!important;margin:0!important;
      }
      div[class*="st-key-ops_cards_support_view"] button p,
      div[class*="st-key-ops_cards_qlkh_view"] button p,
      div[class*="st-key-ops_cards_leader_view"] button p,
      div[class*="st-key-ops_cards_support_view"] button [data-testid="stMarkdownContainer"],
      div[class*="st-key-ops_cards_qlkh_view"] button [data-testid="stMarkdownContainer"],
      div[class*="st-key-ops_cards_leader_view"] button [data-testid="stMarkdownContainer"]{
        font-size:.69rem!important;line-height:1.12!important;margin:0!important;
      }

      /* Admin: keep the original five buttons, only arrange them 2 columns. */
      div[class*="st-key-subnav_admin_row"] [data-testid="stHorizontalBlock"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-subnav_admin_"]){
        display:grid!important;
        grid-template-columns:repeat(2,minmax(0,1fr))!important;
        gap:.44rem!important;
        overflow:visible!important;
        align-items:stretch!important;
      }
      div[class*="st-key-subnav_admin_row"] [data-testid="stHorizontalBlock"]>div[data-testid="column"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-subnav_admin_"])>div[data-testid="column"]{
        width:100%!important;min-width:0!important;max-width:none!important;
        flex:none!important;padding:0!important;
      }
      div[class*="st-key-subnav_admin_"] button{
        width:100%!important;min-height:48px!important;height:100%!important;
        padding:6px 7px!important;border-radius:12px!important;margin:0!important;
        white-space:normal!important;
      }
      div[class*="st-key-subnav_admin_"] button p,
      div[class*="st-key-subnav_admin_"] button [data-testid="stMarkdownContainer"]{
        font-size:.70rem!important;line-height:1.12!important;white-space:normal!important;margin:0!important;
      }

      div[class*="st-key-ops_cards_support_view"],
      div[class*="st-key-ops_cards_qlkh_view"],
      div[class*="st-key-ops_cards_leader_view"],
      div[class*="st-key-subnav_admin_row"]{margin-bottom:.35rem!important}
    }
    @media(max-width:390px){
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
