"""KHDN Ops V2.32 runtime UI patch for the durable notification center."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from khdn_apps import notifications as notify

PATCH_VERSION = "2.32.0"
_INSTALL_FLAG = "_KHDN_NOTIFICATION_UI_V2320"


def _task_detail(ns: dict[str, Any], user: dict[str, Any], task_id: int) -> None:
    st = ns["st"]
    df = ns["qdf"](
        """SELECT t.*,c.cif,c.customer_name,s.full_name support_name,q.full_name qlkh_name,
                  e.quality_score,e.progress_score,e.comment
           FROM tasks t JOIN customers c ON c.id=t.customer_id
           JOIN users s ON s.id=t.support_user_id JOIN users q ON q.id=t.qlkh_user_id
           LEFT JOIN evaluations e ON e.task_id=t.id AND e.round_no=t.current_round
           WHERE t.id=?""",
        (int(task_id),),
    )
    if df.empty:
        st.warning("Hồ sơ không còn tồn tại.")
        return
    row = df.iloc[0]
    uid = int(user["id"])
    role = str(user.get("role") or "")
    if not (user.get("is_admin") or role == "Lãnh đạo phòng" or
            (role == "Cán bộ hỗ trợ" and int(row.support_user_id) == uid) or
            (role == "Cán bộ QLKH" and int(row.qlkh_user_id) == uid)):
        st.error("Bạn không có quyền xem hồ sơ này.")
        return
    if callable(ns.get("render_task_chips")):
        ns["render_task_chips"](row, time_label="Cập nhật", time_field="updated_at")
    st.caption(f"Trạng thái: **{ns.get('STATUS_LABEL', {}).get(str(row.status), str(row.status))}**")
    note = str(row.get("note") or "").strip()
    if note:
        st.info(f"📝 {note}")
    if callable(ns.get("task_history")):
        ns["task_history"](int(task_id))


def _render_center(ns: dict[str, Any], user: dict[str, Any]) -> None:
    st = ns["st"]
    db = ns["DB_PATH"]
    uid = int(user["id"])
    selected = st.session_state.get("_khdn_notification_selected")

    if selected:
        item = notify.get_notification(db, int(selected), uid)
        if not item:
            st.warning("Thông báo không còn tồn tại hoặc không thuộc tài khoản này.")
            st.session_state.pop("_khdn_notification_selected", None)
            return
        notify.mark_read(db, int(selected), uid)
        if st.button("← Quay lại Trung tâm thông báo", key="notif_back_center"):
            st.session_state.pop("_khdn_notification_selected", None)
            st.rerun()
        st.markdown(f"### {item['title']}")
        st.write(item["body"])
        st.caption(ns["fmt_dt"](item["created_at"]))
        if item.get("task_id"):
            st.divider()
            _task_detail(ns, user, int(item["task_id"]))
        return

    unread = notify.unread_count(db, uid)
    devices = notify.subscription_count(db, uid)
    c1, c2 = st.columns(2)
    c1.metric("Chưa đọc", unread)
    c2.metric("Thiết bị nhận Push", devices)

    if unread and st.button("✓ Đánh dấu tất cả đã đọc", use_container_width=True, key="notif_mark_all"):
        notify.mark_all_read(db, uid)
        st.rerun()

    if ns.get("CLOUD_MODE") and notify.push_available():
        try:
            ticket = notify.issue_setup_ticket(uid)
            url = f"/_khdn/push-setup?ticket={quote(ticket)}"
            st.link_button("📲 Cài/Bật Push Notification trên điện thoại", url, use_container_width=True)
            st.caption("iPhone/iPad: thêm KHDN Apps vào Màn hình chính rồi mở từ icon KHDN để bật Push. Android/Chrome có thể bật trực tiếp.")
        except Exception as exc:
            st.warning(f"Push chưa sẵn sàng: {exc}")
    elif not ns.get("CLOUD_MODE"):
        st.caption("Bản offline vẫn có Trung tâm thông báo trong app; Push ra điện thoại chỉ hoạt động trên bản online HTTPS.")

    with st.expander("⚙️ Chọn loại thông báo muốn nhận", expanded=False):
        prefs = notify.get_preferences(db, uid)
        with st.form("notification_preferences_form", clear_on_submit=False):
            values: dict[str, bool] = {}
            for key, label in notify.EVENT_LABELS.items():
                values[key] = st.checkbox(label, value=bool(prefs.get(key, True)), key=f"notif_pref_{key}")
            save = st.form_submit_button("Lưu cài đặt thông báo", type="primary", use_container_width=True)
        if save:
            for key, value in values.items():
                notify.set_preference(db, uid, key, value)
            st.success("Đã lưu cài đặt thông báo.")
            st.rerun()

    st.markdown("#### Thông báo gần đây")
    items = notify.list_notifications(db, uid, limit=80)
    if not items:
        st.info("Chưa có thông báo công việc.")
        return
    for item in items:
        unread_item = not bool(item.get("read_at"))
        icon = "🔴" if unread_item else "✅"
        with st.container(border=True):
            st.markdown(f"**{icon} {item['title']}**")
            st.write(item["body"])
            st.caption(f"{ns['fmt_dt'](item['created_at'])} · Push: {item.get('push_status') or '—'}")
            c1, c2 = st.columns([2, 1])
            if c1.button("Mở đúng hồ sơ", key=f"notif_open_{item['id']}", use_container_width=True, disabled=not bool(item.get("task_id"))):
                notify.mark_read(db, int(item["id"]), uid)
                st.session_state["_khdn_notification_selected"] = int(item["id"])
                st.rerun()
            if unread_item and c2.button("Đã đọc", key=f"notif_read_{item['id']}", use_container_width=True):
                notify.mark_read(db, int(item["id"]), uid)
                st.rerun()


def install(ns: dict[str, Any]) -> None:
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True
    ns["APP_VERSION"] = PATCH_VERSION
    notify.ensure_schema(ns["DB_PATH"])
    st = ns["st"]

    original_sidebar_user = ns["sidebar_user"]

    def sidebar_user_with_notifications(user):
        original_sidebar_user(user)
        uid = int(user["id"])
        # Push/deep links are authorization-bound to this user's durable inbox.
        try:
            raw = st.query_params.get("khdn_notification")
            if isinstance(raw, list):
                raw = raw[0] if raw else None
            if raw:
                nid = int(raw)
                if notify.get_notification(ns["DB_PATH"], nid, uid):
                    st.session_state["_khdn_notification_selected"] = nid
                    st.session_state["_khdn_notification_dialog_open"] = True
                    role = str(user.get("role") or "")
                    if role == "Cán bộ hỗ trợ":
                        st.session_state["main_page"] = "support"
                    elif role == "Cán bộ QLKH":
                        st.session_state["main_page"] = "qlkh"
                    elif role == "Lãnh đạo phòng":
                        st.session_state["main_page"] = "leader"
                try:
                    del st.query_params["khdn_notification"]
                except Exception:
                    pass
        except Exception:
            pass

        try:
            unread = notify.unread_count(ns["DB_PATH"], uid)
        except Exception:
            unread = 0
        label = f"🔔 Thông báo ({unread})" if unread else "🔔 Thông báo"
        if st.sidebar.button(label, use_container_width=True, key="khdn_notification_center_btn", type="primary" if unread else "secondary"):
            st.session_state["_khdn_notification_selected"] = None
            st.session_state["_khdn_notification_dialog_open"] = True

        if ns.get("CLOUD_MODE") and notify.push_available():
            try:
                devices = notify.subscription_count(ns["DB_PATH"], uid)
                st.sidebar.caption(f"📲 Push Notification: {devices} thiết bị")
            except Exception:
                pass

        if st.session_state.get("_khdn_notification_dialog_open"):
            def body():
                _render_center(ns, user)
                st.divider()
                if st.button("Đóng", use_container_width=True, key="close_notification_dialog"):
                    st.session_state["_khdn_notification_dialog_open"] = False
                    st.session_state.pop("_khdn_notification_selected", None)
                    st.rerun()
            if hasattr(st, "dialog"):
                dialog_fn = st.dialog("🔔 Trung tâm thông báo")(body)
                dialog_fn()
            else:
                with st.expander("🔔 Trung tâm thông báo", expanded=True):
                    body()

    ns["sidebar_user"] = sidebar_user_with_notifications

    # Include inbox changes in the existing six-second realtime token. This makes
    # SLA-only alerts refresh the bell even when the task row itself did not change.
    original_token = ns.get("_visible_task_change_token")
    if callable(original_token):
        def visible_task_and_notification_token(user):
            base = original_token(user)
            try:
                uid = int(user["id"])
                with ns["get_conn"]() as c:
                    row = c.execute(
                        "SELECT COALESCE(MAX(id),0),SUM(CASE WHEN read_at IS NULL THEN 1 ELSE 0 END) FROM notifications WHERE user_id=?",
                        (uid,),
                    ).fetchone()
                return f"{base}|notif:{row[0] or 0}:{row[1] or 0}"
            except Exception:
                return base
        ns["_visible_task_change_token"] = visible_task_and_notification_token
