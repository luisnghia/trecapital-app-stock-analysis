"""Build-time source patch for compact CBHT/QLKH mobile navigation.

The production loader keeps the large Streamlit engine compressed. This helper
patches only navigation/UI fragments before that engine is executed, so the
business workflow remains unchanged while the phone UI stays compact.
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

    # Admin: remove the five-button strip. A single compact selector keeps all
    # five admin sections reachable without producing a long row/stack on phones.
    source = _replace_once(
        source,
        '    admin_view = pill_nav("admin_view", [("users","👥 Người dùng"),("customers","🏢 Khách hàng CIF"),("types","🧩 Loại công việc"),("audit","🧾 Audit"),("backup","💾 Sao lưu")], default="users", prefix="subnav_admin")\n',
        '    _admin_options=[("users","👥 Người dùng"),("customers","🏢 Khách hàng CIF"),("types","🧩 Loại công việc"),("audit","🧾 Audit"),("backup","💾 Sao lưu")]\n    _admin_values=[v for v,_ in _admin_options]; _admin_labels=dict(_admin_options)\n    _admin_current=st.session_state.get("admin_view","users")\n    if _admin_current not in _admin_values: _admin_current="users"\n    admin_view=st.selectbox("Chức năng quản trị",_admin_values,index=_admin_values.index(_admin_current),format_func=lambda v:_admin_labels[v],key="admin_view_compact")\n    st.session_state["admin_view"]=admin_view\n',
        "Admin compact selector",
    )

    # Inject this at the END of inject_css(). Earlier CSS rules were overriding
    # the yellow CTA and Streamlit's mobile column rules were collapsing every
    # workflow card to one full-width row. These final rules deliberately win.
    final_mobile_css = r'''

    /* V2.31 final mobile workflow override */
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
      div[class*="st-key-ops_cards_support_view"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-ops_cards_qlkh_view"] [data-testid="stHorizontalBlock"],
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
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_create_support_view_"])>div[data-testid="column"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_create_qlkh_view_"])>div[data-testid="column"]{
        width:100%!important;min-width:0!important;max-width:none!important;
        flex:none!important;grid-column:auto!important;padding:0!important;
      }
      div[class*="st-key-ops_cards_support_view"] button,
      div[class*="st-key-ops_cards_qlkh_view"] button{
        min-height:70px!important;height:100%!important;padding:7px 6px!important;
        border-radius:13px!important;margin:0!important;
      }
      div[class*="st-key-ops_cards_support_view"] button p,
      div[class*="st-key-ops_cards_qlkh_view"] button p,
      div[class*="st-key-ops_cards_support_view"] button [data-testid="stMarkdownContainer"],
      div[class*="st-key-ops_cards_qlkh_view"] button [data-testid="stMarkdownContainer"]{
        font-size:.69rem!important;line-height:1.12!important;margin:0!important;
      }
      /* Five/six cards become 2 columns x 3 compact rows instead of 5/6 full-width rows. */
      div[class*="st-key-ops_cards_support_view"],div[class*="st-key-ops_cards_qlkh_view"]{margin-bottom:.35rem!important}
    }
    @media(max-width:390px){
      div[class*="st-key-ops_cards_support_view"] button,
      div[class*="st-key-ops_cards_qlkh_view"] button{min-height:66px!important;padding:6px 4px!important}
      div[class*="st-key-ops_cards_support_view"] button p,
      div[class*="st-key-ops_cards_qlkh_view"] button p{font-size:.64rem!important}
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
