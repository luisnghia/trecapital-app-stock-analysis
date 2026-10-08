"""Fresh database authorization at mutation and confidential-export boundaries."""
from pathlib import Path
import sqlite3


def active_user(conn, uid):
    cursor = conn.execute("SELECT * FROM users WHERE id=?", (int(uid),))
    row = cursor.fetchone()
    user = dict(zip((x[0] for x in cursor.description), row)) if row else {}
    if not user or not int(user.get("active", 1) or 0) or user.get("deleted_at"):
        raise PermissionError("Tài khoản không còn hoạt động. Vui lòng đăng nhập lại.")
    return user


def manager(user):
    return bool(int(user.get("is_admin") or 0) or user.get("role") == "Lãnh đạo phòng")


def require_admin(db_path, uid):
    with sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        user = active_user(conn, uid)
    if not int(user.get("is_admin") or 0) or int(user.get("must_change_password") or 0):
        raise PermissionError("Chỉ Admin đang hoạt động được xuất toàn bộ dữ liệu.")
    return user


def require_weekly_item(conn, iid, uid):
    actor = active_user(conn, uid)
    row = conn.execute("SELECT user_id FROM weekly_plan_items WHERE id=?", (int(iid),)).fetchone()
    if not row:
        raise PermissionError("Công việc không còn tồn tại.")
    if int(row[0]) != int(uid) and not manager(actor):
        raise PermissionError("Bạn không có quyền cập nhật kế hoạch của người khác.")
    return actor


def require_case(conn, case_id, uid):
    actor = active_user(conn, uid)
    row = conn.execute("SELECT owner_user_id FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
    if not row or (int(row[0]) != int(uid) and not manager(actor)):
        raise PermissionError("Bạn không có quyền cập nhật công việc khách hàng này.")
    return actor
