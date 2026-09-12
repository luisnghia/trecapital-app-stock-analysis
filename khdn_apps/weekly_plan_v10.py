"""Weekly Plan V10 persistent draft autosave.

Implements the v1.2 30-second draft-save requirement without creating a second
application/database. New-task form state is persisted in a small buffer table;
existing draft-task edits are written back only when values actually change.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v3 as v3
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v9 as v9


_ORIGINAL_V6_INSTALL = v6._install_due_driven_overrides
_ORIGINAL_ADD = v6._add_task_form_due_driven
_ORIGINAL_EDITOR = v6._draft_editor_due_driven


def _init_autosave_schema(get_conn: Callable):
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_draft_buffers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            buffer_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id,plan_id,buffer_key),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(plan_id) REFERENCES weekly_plans(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_weekly_draft_buffer_plan
            ON weekly_draft_buffers(user_id,plan_id,updated_at);
        """)
        c.execute("DELETE FROM weekly_draft_buffers WHERE datetime(updated_at)<datetime('now','-14 days')")
        c.commit()


def _buffer_row(get_conn: Callable, user_id: int, plan_id: int, buffer_key: str):
    df = wp._qdf(get_conn, "SELECT * FROM weekly_draft_buffers WHERE user_id=? AND plan_id=? AND buffer_key=?",
                 (int(user_id), int(plan_id), str(buffer_key)))
    return None if df.empty else df.iloc[0].to_dict()


def _delete_buffer(get_conn: Callable, user_id: int, plan_id: int, buffer_key: str):
    wp._execute(get_conn, "DELETE FROM weekly_draft_buffers WHERE user_id=? AND plan_id=? AND buffer_key=?",
                (int(user_id), int(plan_id), str(buffer_key)))


def _load_buffer_payload(get_conn: Callable, user_id: int, plan_id: int, buffer_key: str):
    row = _buffer_row(get_conn, user_id, plan_id, buffer_key)
    if not row:
        return None
    try:
        payload = json.loads(str(row.get("payload_json") or "{}"))
    except Exception:
        _delete_buffer(get_conn, user_id, plan_id, buffer_key)
        return None

    # If a buffered item was already turned into a real task before a browser
    # session ended, do not resurrect it on the next login.
    title = str(payload.get("title") or "").strip()
    expected = str(payload.get("expected") or "").strip()
    due = str(payload.get("due") or "").strip()
    if title and expected and due:
        matched = wp._qdf(get_conn, """SELECT COUNT(*) n FROM weekly_tasks
            WHERE plan_id=? AND title=? AND expected_result=? AND due_date=?
              AND datetime(created_at)>=datetime(?)""",
            (int(plan_id), title, expected, due, str(row.get("updated_at") or "1970-01-01")))
        if not matched.empty and int(matched.iloc[0]["n"]) > 0:
            _delete_buffer(get_conn, user_id, plan_id, buffer_key)
            return None
    return payload


def _json_value(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@st.fragment(run_every=30)
def _autosave_new_task_fragment(get_conn: Callable, user_id: int, plan_id: int,
                                buffer_key: str, state_keys: dict):
    payload = {name: _json_value(st.session_state.get(key)) for name, key in state_keys.items()}
    meaningful = bool(str(payload.get("title") or "").strip() or str(payload.get("expected") or "").strip())
    if not meaningful:
        return
    with get_conn() as c:
        c.execute("""INSERT INTO weekly_draft_buffers(user_id,plan_id,buffer_key,payload_json,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(user_id,plan_id,buffer_key) DO UPDATE SET
            payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
            (int(user_id), int(plan_id), str(buffer_key), json.dumps(payload, ensure_ascii=False), wp._now()))
        c.commit()
    st.caption("💾 Nháp được lưu tự động mỗi 30 giây.")


@st.fragment(run_every=30)
def _autosave_existing_task_fragment(get_conn: Callable, user_id: int, plan_id: int, task_id: int):
    pdf = wp._qdf(get_conn, "SELECT status FROM weekly_plans WHERE id=? AND user_id=?", (int(plan_id), int(user_id)))
    if pdf.empty or str(pdf.iloc[0]["status"]) not in {"DRAFT", "RETURNED"}:
        return
    rowdf = wp._qdf(get_conn, "SELECT * FROM weekly_tasks WHERE id=? AND plan_id=?", (int(task_id), int(plan_id)))
    if rowdf.empty:
        return
    row = rowdf.iloc[0].to_dict()
    suffix = int(task_id)
    title = st.session_state.get(f"weekly_v6_edit_title_{suffix}")
    focus_id = st.session_state.get(f"weekly_v6_edit_focus_{suffix}")
    due = st.session_state.get(f"weekly_v6_edit_due_{suffix}")
    hours = st.session_state.get(f"weekly_v6_edit_hours_{suffix}")
    expected = st.session_state.get(f"weekly_v6_edit_expected_{suffix}")
    if title is None or due is None or hours is None or expected is None:
        return
    if not str(title).strip() or not str(expected).strip():
        return
    focus_id = int(focus_id or 0)
    urgent = False if focus_id else v6._urgent_from_due(due)
    has_kpi = False
    if urgent and not focus_id:
        has_kpi = bool(st.session_state.get(f"weekly_v6_edit_kpi_{suffix}", row.get("has_kpi_or_risk") or 0))
    q = wp._classification(focus_id if focus_id else None, urgent, has_kpi)
    due_iso = due.isoformat() if hasattr(due, "isoformat") else str(due)

    changed = any([
        str(row.get("title") or "") != str(title).strip(),
        str(row.get("expected_result") or "") != str(expected).strip(),
        (int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else 0) != focus_id,
        int(row.get("is_urgent") or 0) != int(urgent),
        int(row.get("has_kpi_or_risk") or 0) != int(has_kpi),
        str(row.get("quadrant") or "") != q,
        str(row.get("due_date") or "") != due_iso,
        abs(float(row.get("planned_hours") or 0) - float(hours)) > 1e-9,
    ])
    if not changed:
        st.caption("💾 Lưu nháp tự động mỗi 30 giây đang bật.")
        return

    siblings = wp._qdf(get_conn, "SELECT COALESCE(SUM(planned_hours),0) h FROM weekly_tasks WHERE plan_id=? AND id<>?",
                       (int(plan_id), int(task_id)))
    other_hours = float(siblings.iloc[0]["h"] or 0) if not siblings.empty else 0.0
    if other_hours + float(hours) > 45:
        st.caption("⚠️ Chưa tự lưu vì tổng giờ dự kiến sẽ vượt 45 giờ.")
        return

    old_q = str(row.get("quadrant") or "")
    wp._execute(get_conn, """UPDATE weekly_tasks SET title=?,expected_result=?,focus_category_id=?,is_urgent=?,
        has_kpi_or_risk=?,quadrant=?,due_date=?,planned_hours=?,updated_at=? WHERE id=?""",
        (str(title).strip(), str(expected).strip(), focus_id if focus_id else None, int(urgent), int(has_kpi), q,
         due_iso, float(hours), wp._now(), int(task_id)))
    wp._task_log(get_conn, int(task_id), int(user_id), "autosave_draft", old_q, q, "Tự lưu nháp 30 giây")
    st.caption("💾 Đã tự lưu thay đổi nháp.")


def _add_task_form_with_autosave(get_conn, u, plan, *, emergent=False):
    year = int(plan["iso_year"])
    focus = wp._focus_df(get_conn, year, active_only=True)
    prefix = f"weekly_v6_{'emergent' if emergent else 'planned'}_{int(plan['id'])}"
    nonce_key = f"{prefix}_nonce"
    nonce = int(st.session_state.get(nonce_key, 0))
    key = lambda name: f"{prefix}_{nonce}_{name}"
    buffer_key = f"{'emergent' if emergent else 'planned'}:{nonce}"

    payload = _load_buffer_payload(get_conn, int(u["id"]), int(plan["id"]), buffer_key)
    if payload:
        preload = {
            key("title"): payload.get("title"),
            key("focus"): int(payload.get("focus") or 0),
            key("hours"): float(payload.get("hours") or 2.0),
            key("expected"): payload.get("expected"),
            key("kpi"): bool(payload.get("kpi")),
        }
        try:
            preload[key("due")] = pd.to_datetime(payload.get("due")).date() if payload.get("due") else None
        except Exception:
            preload[key("due")] = None
        valid_focus = {0} | (set(focus["id"].astype(int).tolist()) if not focus.empty else set())
        if preload[key("focus")] not in valid_focus:
            preload[key("focus")] = 0
        for sk, sv in preload.items():
            if sv is not None and sk not in st.session_state:
                st.session_state[sk] = sv
        st.caption("↩ Đã khôi phục bản nháp tự động.")

    _ORIGINAL_ADD(get_conn, u, plan, emergent=emergent)
    state_keys = {
        "title": key("title"), "focus": key("focus"), "due": key("due"),
        "hours": key("hours"), "kpi": key("kpi"), "expected": key("expected"),
    }
    _autosave_new_task_fragment(get_conn, int(u["id"]), int(plan["id"]), buffer_key, state_keys)


def _draft_editor_with_autosave(get_conn: Callable, u, plan):
    _ORIGINAL_EDITOR(get_conn, u, plan)
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    if tasks.empty:
        return
    selected = st.session_state.get("weekly_v6_edit_task")
    valid_ids = set(tasks["id"].astype(int).tolist())
    if selected is None:
        selected = int(tasks.iloc[0]["id"])
    try:
        selected = int(selected)
    except Exception:
        return
    if selected in valid_ids:
        _autosave_existing_task_fragment(get_conn, int(u["id"]), int(plan["id"]), selected)


def _install_autosave_overrides():
    _ORIGINAL_V6_INSTALL()
    wp._add_task_form = _add_task_form_with_autosave
    v3._draft_editor = _draft_editor_with_autosave


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    if not (wp._is_officer(u) or wp._is_leader(u)):
        st.error("Bạn không có quyền truy cập Kế hoạch tuần.")
        return
    # V9 delegates into V8, which invokes V6's install hook. Replacing the hook
    # here keeps the stable page routing while adding persistent autosave.
    v6._install_due_driven_overrides = _install_autosave_overrides
    v6._init_v6_schema(get_conn)
    _init_autosave_schema(get_conn)
    return v9.weekly_plan_page(u, get_conn, page_title, pill_nav)
