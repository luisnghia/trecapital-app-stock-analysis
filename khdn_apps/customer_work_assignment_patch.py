"""Controlled Customer Work reassignment (owner + supervising leader).

Admin and phòng leaders can reassign any ACTIVE customer case in their
room-wide management scope. Staff and Vấn tin never receive edit permissions. All changes are atomic, optimistic
concurrency-protected and audited to case_actions. No case history, stages,
tasks, customers or deadlines are reassigned/deleted by this operation.

The added input uses legacy_fast_form's submit-only client-side mechanism so
typing a reason does not rerun Streamlit for every keystroke.
"""
from __future__ import annotations

import json

from khdn_apps.authorization import active_user

VERSION = "1.1.0"
FLAG = "_KHDN_WORK_ASSIGNMENT_PATCH_V1"


def _is_manager(user):
    return str(user.get("role") or "") == "Lãnh đạo phòng" or bool(int(user.get("is_admin") or 0))


def _active_users(c, allowed_roles):
    marks = ",".join("?" for _ in allowed_roles)
    sql = (
        "SELECT id,username,full_name,role,is_admin FROM users "
        f"WHERE active=1 AND role IN ({marks}) "
        "AND (deleted_at IS NULL OR TRIM(deleted_at)='') "
        "ORDER BY CASE WHEN role='Lãnh đạo phòng' THEN 0 ELSE 1 END,full_name,id"
    )
    return [dict(r) for r in c.execute(sql, tuple(allowed_roles)).fetchall()]


def _can_manage(actor, case):
    if not _is_manager(actor):
        return False
    if str(case.get("status") or "") != "ACTIVE":
        return False
    if int(actor.get("is_admin") or 0):
        return True
    # Room leadership already has full-room Customer Work visibility in phase 9.
    # Changing the currently assigned controller must not be blocked merely
    # because that controller is another leader or the legacy case is unassigned.
    return str(actor.get("role") or "") == "Lãnh đạo phòng"


def reassign_case(
    get_conn, case_id, actor_uid, new_owner_uid, new_controller_uid,
    reason, *, expected_owner_uid, expected_controller_uid, logger=None,
):
    """Return True on a real change, False on a no-op; never silently clobber.

    Validate the ACTUAL current role/leader ownership in the DB inside an
    immediate transaction, not the potentially stale page/session role.
    """
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Phải nhập lý do điều chỉnh phân công.")
    case_id = int(case_id)
    new_owner_uid, new_controller_uid = int(new_owner_uid), int(new_controller_uid)
    with get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        actor = active_user(c, int(actor_uid))
        if not _is_manager(actor):
            raise PermissionError("Chỉ Admin hoặc Lãnh đạo phòng được điều chỉnh phân công.")
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            raise ValueError("Công việc không còn tồn tại.")
        case = dict(row)
        if not _can_manage(actor, case):
            raise PermissionError("Chỉ Admin/Lãnh đạo phòng được điều chỉnh công việc đang thực hiện.")
        old_owner = int(case.get("owner_user_id") or 0)
        old_controller = int(case.get("controller_user_id") or 0)
        if (old_owner != int(expected_owner_uid or 0)
                or old_controller != int(expected_controller_uid or 0)):
            raise ValueError("Phân công đã thay đổi trên thiết bị khác. Hãy tải lại trước khi cập nhật.")

        owners = {int(x["id"]): x for x in _active_users(c, ("Cán bộ QLKH", "Lãnh đạo phòng"))}
        leaders = {int(x["id"]): x for x in _active_users(c, ("Lãnh đạo phòng",))}
        if new_owner_uid not in owners:
            raise ValueError("Cán bộ phụ trách không còn hoạt động hoặc không thuộc nhóm được phân công.")
        if new_controller_uid not in leaders:
            raise ValueError("Lãnh đạo kiểm soát không còn hoạt động hoặc không đúng vai trò.")
        if old_owner == new_owner_uid and old_controller == new_controller_uid:
            return False

        def old_user(uid):
            row = c.execute("SELECT full_name FROM users WHERE id=?", (uid,)).fetchone()
            return str(row[0]) if row and row[0] else f"Tài khoản #{uid}"

        change = {
            "old_owner_user_id": old_owner,
            "new_owner_user_id": new_owner_uid,
            "old_owner_name": old_user(old_owner),
            "new_owner_name": owners[new_owner_uid]["full_name"],
            "old_controller_user_id": old_controller or None,
            "new_controller_user_id": new_controller_uid,
            "old_controller_name": old_user(old_controller) if old_controller else "Chưa gán",
            "new_controller_name": leaders[new_controller_uid]["full_name"],
            "reason": reason,
        }
        from khdn_apps import customer_work as core
        ts = core.now_str()
        c.execute(
            """UPDATE customer_work_cases
               SET owner_user_id=?,controller_user_id=?,updated_at=?
               WHERE id=? AND status='ACTIVE'
               AND owner_user_id=? AND COALESCE(controller_user_id,0)=?""",
            (new_owner_uid, new_controller_uid, ts, case_id, old_owner, old_controller),
        )
        if c.execute("SELECT changes()").fetchone()[0] != 1:
            raise ValueError("Công việc đã thay đổi đồng thời. Hãy tải lại màn hình.")
        c.execute(
            """INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at)
               VALUES(?,?,'CASE_ASSIGNMENT_UPDATE',?,?)""",
            (case_id, int(actor_uid), json.dumps(change, ensure_ascii=False), ts),
        )
    if logger:
        logger.info(
            "CW_ASSIGNMENT_CHANGED case=%s actor=%s old_owner=%s new_owner=%s old_controller=%s new_controller=%s history_preserved=1",
            case_id, int(actor_uid), old_owner, new_owner_uid, old_controller, new_controller_uid,
        )
    return True


def _form(st, u, get_conn, case_id, logger=None):
    from khdn_apps.legacy_fast_form import legacy_fast_form

    actor_uid = int(u.get("id") or 0)
    if not _is_manager(u):
        return
    with get_conn() as c:
        actor = active_user(c, actor_uid)
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
        if not row:
            return
        case = dict(row)
        if str(case.get("status") or "") != "ACTIVE":
            return
        allowed = _can_manage(actor, case)
        if not allowed:
            st.warning("Chỉ Admin/Lãnh đạo phòng được chỉnh sửa phân công công việc đang thực hiện.")
            return
        owners = _active_users(c, ("Cán bộ QLKH", "Lãnh đạo phòng"))
        leaders = _active_users(c, ("Lãnh đạo phòng",))
    if not owners or not leaders:
        st.warning("Chưa có đủ cán bộ QLKH hoặc lãnh đạo đang hoạt động để phân công.")
        return

    owner_id = int(case.get("owner_user_id") or 0)
    controller_id = int(case.get("controller_user_id") or 0)
    owner_options = [
        {"value": str(x["id"]), "label": f"{x['full_name']} · {x['role']}"}
        for x in owners
    ]
    leader_options = [
        {"value": str(x["id"]), "label": f"{x['full_name']} · Lãnh đạo phòng"}
        for x in leaders
    ]

    st.subheader("✏️ Chỉnh sửa công việc · Phân công phụ trách")
    st.caption(
        "Admin/Lãnh đạo phòng có thể điều chỉnh người phụ trách và lãnh đạo kiểm soát "
        "trong toàn phòng. Nhập lý do để lưu; lịch sử và thời hạn công việc được giữ nguyên. "
        "Không tự thay đổi cán bộ quản lý khách hàng CIF."
    )
    # Open by default: the previous collapsed expander made the feature
    # effectively undiscoverable, even for the administrator account.
    with st.expander("👥 Đổi cán bộ phụ trách / Lãnh đạo kiểm soát", expanded=True):
        payload = legacy_fast_form(
            [
                {"name": "owner", "label": "Cán bộ phụ trách *",
                 "type": "select", "required": True, "default": str(owner_id),
                 "options": owner_options},
                {"name": "controller", "label": "Lãnh đạo phụ trách / kiểm soát *",
                 "type": "select", "required": True, "default": str(controller_id),
                 "options": leader_options},
                {"name": "reason", "label": "Lý do điều chỉnh phân công *",
                 "type": "textarea", "required": True, "full": True,
                 "placeholder": "Nêu lý do chuyển cán bộ hoặc lãnh đạo phụ trách"},
            ],
            "Lưu thay đổi phân công",
            key=f"cw_reassign_fast_{int(case_id)}_{actor_uid}",
            reset_token=f"{owner_id}:{controller_id}",
            columns=2,
        )
        if payload is None:
            return
        try:
            changed = reassign_case(
                get_conn, int(case_id), actor_uid,
                int(payload.get("owner") or 0), int(payload.get("controller") or 0),
                payload.get("reason"), expected_owner_uid=owner_id,
                expected_controller_uid=controller_id, logger=logger,
            )
        except (PermissionError, ValueError) as exc:
            st.error(str(exc))
            if logger:
                logger.warning("CW_ASSIGNMENT_REJECTED case=%s actor=%s", int(case_id), actor_uid)
            return
        except Exception:
            st.error("Không lưu được thay đổi phân công. Vui lòng thử lại.")
            if logger:
                logger.exception("CW_ASSIGNMENT_FAILED case=%s actor=%s", int(case_id), actor_uid)
            return
        if changed:
            st.toast("Đã thay đổi phân công và lưu nhật ký công việc.", icon="✅")
            st.rerun()
        else:
            st.info("Phân công không thay đổi.")


def install(customer_ui, logger=None):
    """Run as the final Customer Work UI binding, after manager note overlays."""
    if getattr(customer_ui, FLAG, False):
        return
    original = customer_ui._case_detail

    def _case_detail(st, u, get_conn, case_id, logger=None):
        _form(st, u, get_conn, case_id, logger)
        return original(st, u, get_conn, case_id, logger)

    customer_ui._case_detail = _case_detail
    setattr(customer_ui, FLAG, True)
    if logger:
        logger.info(
            "CW_CASE_ASSIGNMENT_INSTALLED version=%s admin_scope=all leader_scope=all "
            "owner_and_leader_edit=1 audit=1 optimistic_lock=1 no_data_migration=1",
            VERSION,
        )
