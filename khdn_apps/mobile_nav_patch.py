"""Build-time source patch for compact CBHT/QLKH mobile navigation.

The production loader keeps the large Streamlit engine compressed.  This helper
patches only the navigation fragments before that engine is executed, so the
business workflow remains unchanged while the mobile UI stays compact.
"""


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"KHDN mobile-nav patch cannot find: {label}")
    return source.replace(old, new, 1)


def patch_source(source: str) -> str:
    # Allow action cards without a numeric counter.  Status cards keep their
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

    # CBHT: put the only standalone action in the status-card row and remove
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

    # QLKH: same compact pattern — create/assign becomes a card beside workflow
    # statuses; review/assigned/history are reached from their status cards.
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
    return source
