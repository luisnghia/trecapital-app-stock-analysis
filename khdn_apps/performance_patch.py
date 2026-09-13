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

    compile(source, "<khdn-performance-patch>", "exec")
    return source
