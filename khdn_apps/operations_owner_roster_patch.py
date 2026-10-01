"""Allow active room leaders to be selected as the owner of legacy Operations tasks.

The legacy schema stores the responsible person in tasks.qlkh_user_id, which is a
foreign key to users.id and is not role-restricted.  This overlay expands only the
roster used by the leader-side "Tạo / giao hồ sơ" workflow and its scope filter:
active Cán bộ QLKH + active Lãnh đạo phòng can own a newly assigned Operations
case.  Existing task rows and ownership are not migrated or rewritten.
"""
from __future__ import annotations

import pandas as pd

from khdn_apps import planning_operational_phase14_patch as phase14

VERSION = "1.0.0"
_FLAG = "_OPERATIONS_OWNER_ROSTER_PATCH_VERSION"


def _users(app_ns, role: str, active_only: bool):
    try:
        return app_ns["all_users"](role, active_only=active_only)
    except TypeError:
        # Older helper signatures support only the active roster.  For create
        # flows this is exact; for scope/history it is a safe fallback and old
        # task owners are still appended by Phase 14 from the task dataframe.
        return app_ns["all_users"](role, active_only=True)


def _combined_owner_roster(app_ns, active_only: bool):
    frames = []
    for role in ("Cán bộ QLKH", "Lãnh đạo phòng"):
        df = _users(app_ns, role, active_only)
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
    # Keep QLKH first, then leaders; alphabetical within each group.  This makes
    # the expanded dropdown predictable without changing the existing UI widget.
    role_rank = {"Cán bộ QLKH": 0, "Lãnh đạo phòng": 1}
    roster["_owner_role_rank"] = roster.get("role", "").map(role_rank).fillna(9)
    sort_cols = ["_owner_role_rank"]
    if "full_name" in roster.columns:
        sort_cols.append("full_name")
    roster = roster.sort_values(sort_cols, kind="stable").drop(columns=["_owner_role_rank"])
    return roster.reset_index(drop=True)


def install(app_ns, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return

    def active_owners(ns):
        return _combined_owner_roster(ns, active_only=True)

    def all_owners(ns):
        return _combined_owner_roster(ns, active_only=False)

    # Phase 14's _create_task and _scope_selector resolve these module globals at
    # call time, so patching them here changes the final renderer without touching
    # task data or duplicating the large leader workflow implementation.
    phase14._active_qlkh = active_owners
    phase14._all_qlkh = all_owners

    app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "OPERATIONS_OWNER_ROSTER_PATCH_INSTALLED version=%s qlkh=1 leader=1 data_migration=0",
            VERSION,
        )
