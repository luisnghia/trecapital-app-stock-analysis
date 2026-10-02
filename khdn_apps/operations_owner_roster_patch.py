"""Expand Operations task-owner selection to active QLKH + active room leaders.

The responsible person for a legacy Operations task is stored in ``tasks.qlkh_user_id``.
That column references ``users.id`` and is not role-restricted, so an active
``Lãnh đạo phòng`` can safely be the responsible owner without schema changes.

This overlay applies the same owner rule to every create/assign path:
- Cán bộ hỗ trợ self-create
- Cán bộ QLKH create/assign
- Lãnh đạo/Admin leader mode create/assign

Existing task rows are never migrated or rewritten. The actor performing an action
remains the real logged-in user; selecting another owner never impersonates that user.
"""
from __future__ import annotations

import pandas as pd

from khdn_apps import planning_operational_phase14_patch as phase14
from khdn_apps import planning_operational_phase15_patch as phase15

VERSION = "1.2.0"
_FLAG = "_OPERATIONS_OWNER_ROSTER_PATCH_VERSION"


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _call_all_users(fn, role: str, active_only: bool):
    try:
        return fn(role, active_only=active_only)
    except TypeError:
        return fn(role, active_only=True)


def _combined_owner_roster(app_ns, active_only: bool, all_users_fn=None):
    fn = all_users_fn or app_ns["all_users"]
    frames = []
    for role in ("Cán bộ QLKH", "Lãnh đạo phòng"):
        df = _call_all_users(fn, role, active_only)
        if df is None or getattr(df, "empty", True):
            continue
        copy = df.copy()
        if "role" not in copy.columns:
            copy["role"] = role
        frames.append(copy)
    if not frames:
        return pd.DataFrame()
    roster = pd.concat(frames, ignore_index=True, sort=False)
    if "id" in roster.columns:
        roster = roster.drop_duplicates(subset=["id"], keep="first")
    role_rank = {"Cán bộ QLKH": 0, "Lãnh đạo phòng": 1}
    roster["_owner_role_rank"] = roster.get("role", "").map(role_rank).fillna(9)
    sort_cols = ["_owner_role_rank"]
    if "full_name" in roster.columns:
        sort_cols.append("full_name")
    roster = roster.sort_values(sort_cols, kind="stable").drop(columns=["_owner_role_rank"])
    return roster.reset_index(drop=True)


def _owner_label(roster, uid):
    try:
        row = roster[roster.id.astype(int) == int(uid)].iloc[0]
    except Exception:
        return f"Người phụ trách #{uid}"
    name = str(getattr(row, "full_name", "") or f"User #{uid}")
    role = str(getattr(row, "role", "") or "")
    username = str(getattr(row, "username", "") or "")
    suffix = f" · {role}" if role else ""
    if username:
        suffix += f" ({username})"
    return name + suffix


def _render_owner_select(st, roster, key: str, default_id=None):
    if roster is None or getattr(roster, "empty", True):
        st.error("Chưa có Cán bộ QLKH hoặc Lãnh đạo phòng đang hoạt động.")
        return None
    ids = roster.id.astype(int).tolist()
    idx = ids.index(int(default_id)) if default_id is not None and int(default_id) in ids else None
    return st.selectbox(
        "Cán bộ QLKH phụ trách *",
        ids,
        index=idx,
        key=key,
        placeholder="Chọn Cán bộ QLKH / Lãnh đạo phòng",
        format_func=lambda x: _owner_label(roster, x),
        help="Có thể chọn Cán bộ QLKH hoặc Lãnh đạo phòng đang hoạt động làm người phụ trách hồ sơ.",
    )


def _is_qlkh_task_insert(sql):
    compact = " ".join(str(sql or "").upper().split())
    return "INSERT INTO TASKS" in compact and "'QLKH'" in compact


def install(app_ns, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return

    base_all_users = app_ns.get("all_users")
    if base_all_users is None:
        return

    # Leader/Admin mode: Phase 14 resolves these module globals at call time.
    def active_owners(ns):
        return _combined_owner_roster(ns, active_only=True, all_users_fn=base_all_users)

    def all_owners(ns):
        return _combined_owner_roster(ns, active_only=False, all_users_fn=base_all_users)

    phase14._active_qlkh = active_owners
    phase14._all_qlkh = all_owners

    # QLKH create/assign: put the responsible-owner field immediately before the
    # Phase 15 customer selector, so the form has the same rule as leader mode.
    original_phase15_selector = phase15._customer_selector
    original_prospect_owner = phase15._prospect_owner_id

    def prospect_owner_id(u, key, state):
        if str(key).startswith("ql_new_cust"):
            owner = state.get("ql_new_owner")
            if owner not in (None, ""):
                try:
                    return int(owner)
                except Exception:
                    pass
        return original_prospect_owner(u, key, state)

    def customer_selector(st, u, ns, potential, key="cust", required_message=None, logger=None):
        if str(key) == "ql_new_cust":
            if st.session_state.get("reset_ql_create_fields"):
                st.session_state.pop("ql_new_owner", None)
            roster = _combined_owner_roster(ns, active_only=True, all_users_fn=base_all_users)
            # Streamlit automatically persists the selectbox value into the key.
            # Never assign st.session_state["ql_new_owner"] after instantiation:
            # Streamlit 1.63 raises StreamlitWidgetAlreadyInstantiatedError.
            _render_owner_select(st, roster, "ql_new_owner", default_id=_uget(u, "id"))
        return original_phase15_selector(st, u, ns, potential, key, required_message, logger)

    phase15._prospect_owner_id = prospect_owner_id
    phase15._customer_selector = customer_selector

    original_qlkh_page = app_ns.get("qlkh_page")
    if original_qlkh_page:
        def qlkh_page(u, *args, **kwargs):
            st = app_ns["st"]
            if st.session_state.get("reset_ql_create_fields"):
                st.session_state.pop("ql_new_owner", None)

            previous_execute = app_ns.get("execute")
            previous_log_action = app_ns.get("log_action")
            created = {"task_id": None, "owner_id": None, "owner_name": None}

            def execute(sql, params=()):
                if previous_execute is None:
                    raise RuntimeError("execute helper is unavailable")
                use_params = params
                if _is_qlkh_task_insert(sql) and str(st.session_state.get("qlkh_view", "create")) == "create":
                    owner = st.session_state.get("ql_new_owner")
                    try:
                        owner_id = int(owner)
                    except Exception:
                        owner_id = int(_uget(u, "id"))
                    seq = list(params or ())
                    if len(seq) >= 3:
                        seq[2] = owner_id
                        use_params = tuple(seq)
                        roster = _combined_owner_roster(app_ns, active_only=True, all_users_fn=base_all_users)
                        created["owner_id"] = owner_id
                        created["owner_name"] = _owner_label(roster, owner_id)
                result = previous_execute(sql, use_params)
                if _is_qlkh_task_insert(sql):
                    created["task_id"] = result
                return result

            def log_action(task_id, actor_user_id, action, detail=None):
                if previous_log_action is None:
                    return None
                if (
                    created.get("task_id") is not None
                    and int(task_id) == int(created["task_id"])
                    and str(action) in {"CREATE", "ASSIGN"}
                    and created.get("owner_name")
                ):
                    detail = (str(detail or "").rstrip("; ") + f"; QLKH phụ trách={created['owner_name']}").strip()
                # Never replace actor_user_id: audit always remains the real creator.
                return previous_log_action(task_id, actor_user_id, action, detail)

            if previous_execute is not None:
                app_ns["execute"] = execute
            if previous_log_action is not None:
                app_ns["log_action"] = log_action
            try:
                return original_qlkh_page(u, *args, **kwargs)
            finally:
                if previous_execute is not None:
                    app_ns["execute"] = previous_execute
                if previous_log_action is not None:
                    app_ns["log_action"] = previous_log_action

        app_ns["qlkh_page"] = qlkh_page

    # CBHT self-create: the legacy form already has a QLKH dropdown. Broaden only
    # that create-screen roster; all other CBHT filters/lists stay unchanged.
    original_support_page = app_ns.get("support_page")
    if original_support_page:
        def support_page(u, *args, **kwargs):
            st = app_ns["st"]
            previous_all_users = app_ns.get("all_users")
            previous_selectbox = st.selectbox

            def all_users(role, active_only=True):
                if str(role) == "Cán bộ QLKH" and str(st.session_state.get("support_view", "inbox")) == "create":
                    return _combined_owner_roster(app_ns, active_only=bool(active_only), all_users_fn=previous_all_users)
                return _call_all_users(previous_all_users, role, bool(active_only))

            def selectbox(label, *sargs, **skwargs):
                if str(label) == "Cán bộ QLKH" and str(st.session_state.get("support_view", "inbox")) == "create":
                    label = "Cán bộ QLKH phụ trách *"
                    skwargs["placeholder"] = "Chọn Cán bộ QLKH / Lãnh đạo phòng"
                return previous_selectbox(label, *sargs, **skwargs)

            app_ns["all_users"] = all_users
            st.selectbox = selectbox
            try:
                return original_support_page(u, *args, **kwargs)
            finally:
                app_ns["all_users"] = previous_all_users
                st.selectbox = previous_selectbox

        app_ns["support_page"] = support_page

    app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "OPERATIONS_OWNER_ROSTER_PATCH_INSTALLED version=%s cbht=1 qlkh=1 leader=1 admin=1 active_qlkh=1 active_leader=1 actor_preserved=1 data_migration=0",
            VERSION,
        )
