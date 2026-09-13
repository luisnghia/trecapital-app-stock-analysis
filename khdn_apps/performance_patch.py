"""Performance transformer for KHDN Apps.

Targets the exact V2.38+reason source used by production. The goal is to cut
avoidable per-rerun work without changing business behaviour.
"""


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"Performance patch cannot find source fragment: {label}")
    return source.replace(old, new, 1)


def patch_source(source: str) -> str:
    # 1) SQLite: WAL mode is a database setting, not something to renegotiate on
    # every read connection. Mounted persistent volumes amplify that overhead.
    old = '''    conn.row_factory = sqlite3.Row\n    conn.execute("PRAGMA foreign_keys=ON")\n    conn.execute("PRAGMA journal_mode=WAL")\n    conn.execute("PRAGMA busy_timeout=30000")\n    return conn\n'''
    new = '''    conn.row_factory = sqlite3.Row\n    conn.execute("PRAGMA foreign_keys=ON")\n    conn.execute("PRAGMA busy_timeout=30000")\n    conn.execute("PRAGMA synchronous=NORMAL")\n    conn.execute("PRAGMA temp_store=MEMORY")\n    return conn\n'''
    source = _replace_once(source, old, new, "get_conn WAL renegotiation")

    old = '''def init_db():\n    with get_conn() as c:\n        c.executescript(\'\'\'\n'''
    new = '''def init_db():\n    with get_conn() as c:\n        # Configure persistent SQLite mode once per Streamlit session instead of\n        # on every query connection.\n        c.execute("PRAGMA journal_mode=WAL")\n        c.execute("PRAGMA synchronous=NORMAL")\n        c.executescript(\'\'\'\n'''
    source = _replace_once(source, old, new, "init_db WAL setup")

    # 2) Session identity: do not hit SQLite on every widget rerun. Revalidate
    # regularly so account disable/password/role changes still take effect quickly.
    old = '''    device_login.sync(DB_PATH)\n    if "user" not in st.session_state:\n        login_ui(); return\n    fresh = user_by_username(st.session_state.user["username"])\n    if not fresh:\n        st.session_state.pop("user", None); st.rerun()\n    st.session_state.user = dict(fresh)\n    u = st.session_state.user\n'''
    new = '''    device_login.sync(DB_PATH)\n    if "user" not in st.session_state:\n        login_ui(); return\n    _now_mono = __import__("time").monotonic()\n    _last_user_check = float(st.session_state.get("_user_last_validated_mono", 0.0) or 0.0)\n    if (_now_mono - _last_user_check) >= 10.0:\n        fresh = user_by_username(st.session_state.user["username"])\n        if not fresh:\n            st.session_state.pop("user", None); st.rerun()\n        st.session_state.user = dict(fresh)\n        st.session_state["_user_last_validated_mono"] = _now_mono\n    u = st.session_state.user\n'''
    source = _replace_once(source, old, new, "session user revalidation")

    # 3) Realtime polling is useful on operational pages, but it is pure overhead
    # while typing in Admin/Profile/Guide. Route first, then poll only pages that
    # actually need live workflow updates.
    old = '''    sidebar_user(u)\n    realtime_refresh_watch(u)\n    notice = st.session_state.pop("_auto_refresh_notice", None)\n    if notice:\n        st.toast(notice, icon="🔄")\n    page = sidebar_navigation(u)\n    if page == "support": support_page(u)\n'''
    new = '''    sidebar_user(u)\n    page = sidebar_navigation(u)\n    if page in {"support", "qlkh", "leader", "dashboard"}:\n        realtime_refresh_watch(u)\n    notice = st.session_state.pop("_auto_refresh_notice", None)\n    if notice:\n        st.toast(notice, icon="🔄")\n    if page == "support": support_page(u)\n'''
    source = _replace_once(source, old, new, "page-scoped realtime polling")

    # 4) Revision probes are often called several times during one rerun. A
    # one-second session memo keeps cross-user data fresh while collapsing duplicate
    # mounted-volume reads inside bursts of widget interactions.
    old = '''def _users_revision():\n    with get_conn() as c:\n        r=c.execute("SELECT COALESCE(MAX(updated_at),\'\'),COUNT(*) FROM users").fetchone()\n    return f"{r[0]}|{r[1]}"\n'''
    new = '''def _users_revision():\n    _now=__import__("time").monotonic(); _key="_perf_users_revision"\n    _cached=st.session_state.get(_key)\n    if _cached and (_now-float(_cached[0])) < 1.0:\n        return _cached[1]\n    with get_conn() as c:\n        r=c.execute("SELECT COALESCE(MAX(updated_at),\'\'),COUNT(*) FROM users").fetchone()\n    _value=f"{r[0]}|{r[1]}"; st.session_state[_key]=(_now,_value); return _value\n'''
    if old in source:
        source = source.replace(old, new, 1)

    old = '''def _task_types_revision():\n    with get_conn() as c:\n        r=c.execute("SELECT COALESCE(MAX(updated_at),\'\'),COUNT(*) FROM task_types").fetchone()\n    return f"{r[0]}|{r[1]}"\n'''
    new = '''def _task_types_revision():\n    _now=__import__("time").monotonic(); _key="_perf_task_types_revision"\n    _cached=st.session_state.get(_key)\n    if _cached and (_now-float(_cached[0])) < 1.0:\n        return _cached[1]\n    with get_conn() as c:\n        r=c.execute("SELECT COALESCE(MAX(updated_at),\'\'),COUNT(*) FROM task_types").fetchone()\n    _value=f"{r[0]}|{r[1]}"; st.session_state[_key]=(_now,_value); return _value\n'''
    if old in source:
        source = source.replace(old, new, 1)

    # 5) Streamlit 1.63 text widgets outside a form normally rerun the app when
    # their value is committed (blur / Enter). For action-draft fields that are
    # consumed only by the next button click, keep the draft browser-local with
    # on_change="ignore". The next button rerun delivers the latest draft to Python,
    # so workflow validation/audit remains unchanged while field-to-field entry no
    # longer causes a full app rerun. Search fields intentionally remain rerunning.
    draft_widgets = [
        (
            'st.text_area("Ghi chú / nội dung hồ sơ (không bắt buộc)",key="new_note")',
            'st.text_area("Ghi chú / nội dung hồ sơ (không bắt buộc)",key="new_note",on_change="ignore")',
            "support create note",
        ),
        (
            'st.text_input("Lý do trả lại chi tiết *", key=f"return_pending_reason_{tid}")',
            'st.text_input("Lý do trả lại chi tiết *", key=f"return_pending_reason_{tid}",on_change="ignore")',
            "support pending return reason",
        ),
        (
            'st.text_area("Ghi chú khi hoàn thành",value=default_note,key=f"finish_note_{tid}_{int(row.current_round)}")',
            'st.text_area("Ghi chú khi hoàn thành",value=default_note,key=f"finish_note_{tid}_{int(row.current_round)}",on_change="ignore")',
            "support finish note",
        ),
        (
            'st.text_input("Lý do trả lại chi tiết *", key=f"return_work_reason_{tid}_{int(row.current_round)}")',
            'st.text_input("Lý do trả lại chi tiết *", key=f"return_work_reason_{tid}_{int(row.current_round)}",on_change="ignore")',
            "support work return reason",
        ),
        (
            'st.text_area("Ghi chú",value=str(er.note or ""),key=f"post_note_{eid}_{int(er.current_round)}")',
            'st.text_area("Ghi chú",value=str(er.note or ""),key=f"post_note_{eid}_{int(er.current_round)}",on_change="ignore")',
            "support post-review note",
        ),
        (
            'st.text_area("Ghi chú / yêu cầu xử lý (không bắt buộc)",key="ql_new_note")',
            'st.text_area("Ghi chú / yêu cầu xử lý (không bắt buộc)",key="ql_new_note",on_change="ignore")',
            "qlkh create note",
        ),
        (
            'st.text_input("Lý do đổi/giao lại (khuyến nghị ghi để audit)",key=f"{key_prefix}_reason_{tid}")',
            'st.text_input("Lý do đổi/giao lại (khuyến nghị ghi để audit)",key=f"{key_prefix}_reason_{tid}",on_change="ignore")',
            "qlkh reassign reason",
        ),
        (
            'st.text_input("Lý do hủy chi tiết *",key=f"{key_prefix}_cancel_reason_{tid}")',
            'st.text_input("Lý do hủy chi tiết *",key=f"{key_prefix}_cancel_reason_{tid}",on_change="ignore")',
            "qlkh pending cancel reason",
        ),
        (
            'st.text_input("Lý do hủy chi tiết *",key=f"{key_prefix}_cancel_returned_reason_{tid}")',
            'st.text_input("Lý do hủy chi tiết *",key=f"{key_prefix}_cancel_returned_reason_{tid}",on_change="ignore")',
            "qlkh returned cancel reason",
        ),
        (
            'st.text_area("Ý kiến lãnh đạo / yêu cầu thực hiện lại",key=f"leader_reason_{tid}")',
            'st.text_area("Ý kiến lãnh đạo / yêu cầu thực hiện lại",key=f"leader_reason_{tid}",on_change="ignore")',
            "leader rework reason",
        ),
        (
            'new_name=st.text_input("Tên nhóm nguyên nhân",value=str(row["name"]),key=f"{edit_key}_name_{int(xid)}")',
            'new_name=st.text_input("Tên nhóm nguyên nhân",value=str(row["name"]),key=f"{edit_key}_name_{int(xid)}",on_change="ignore")',
            "reason category edit name",
        ),
        (
            'new_username = c0.text_input("Username", value=str(cur.username), key=f"admin_username_{int(uid)}", help="Admin có thể đổi username. Username cũ được giải phóng ngay sau khi đổi.")',
            'new_username = c0.text_input("Username", value=str(cur.username), key=f"admin_username_{int(uid)}", help="Admin có thể đổi username. Username cũ được giải phóng ngay sau khi đổi.", on_change="ignore")',
            "admin username draft",
        ),
        (
            'np = st.text_input("Reset mật khẩu (để trống nếu không đổi)", type="password", key=f"new_pw_{int(uid)}")',
            'np = st.text_input("Reset mật khẩu (để trống nếu không đổi)", type="password", key=f"new_pw_{int(uid)}", on_change="ignore")',
            "admin reset password draft",
        ),
    ]
    for old_widget, new_widget, label in draft_widgets:
        source = _replace_once(source, old_widget, new_widget, label)

    compile(source, "<khdn-performance-patch>", "exec")
    return source
