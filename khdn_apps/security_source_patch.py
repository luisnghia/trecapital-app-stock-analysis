"""Final source guard after performance transforms, before engine execution."""
import re


def patch_source(source):
    source, count = re.subn(
        r"def hash_password\(.*?(?=\ndef password_ok\()",
        "from khdn_apps.password_security import hash_password, verify_password, needs_upgrade as _password_needs_upgrade\n\n",
        source, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Security patch: password functions missing")
    start = source.index('    _now_mono = __import__("time").monotonic()', source.index("def app():"))
    end = source.index("    u = st.session_state.user\n", start)
    source = source[:start] + source[end:]
    old = '                st.session_state.user = dict(user_by_username(username.strip()))\n'
    new = '''                if _password_needs_upgrade(u["password_hash"]):
                    execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), u["id"]))
                    device_login.sessions.revoke_user(DB_PATH, u["id"])
                st.session_state.user = dict(user_by_username(username.strip()))
                device_login.begin_session(st.session_state.user)
'''
    if old not in source:
        raise RuntimeError("Security patch: login binding missing")
    source = source.replace(old, new, 1)
    old = '            st.session_state.user = dict(user_by_username(u["username"]))\n            st.success("Đã đổi mật khẩu.")'
    new = '            st.session_state.user = dict(user_by_username(u["username"]))\n            device_login.password_changed(DB_PATH, st.session_state.user)\n            st.success("Đã đổi mật khẩu.")'
    if old not in source:
        raise RuntimeError("Security patch: forced password change missing")
    source = source.replace(old, new, 1)
    old = '            audit(u["id"], "CHANGE_PASSWORD", "user", u["id"], "Đổi mật khẩu cá nhân")\n            st.success("Đã đổi mật khẩu.")'
    new = '''            audit(u["id"], "CHANGE_PASSWORD", "user", u["id"], "Đổi mật khẩu cá nhân")
            st.session_state.user = dict(user_by_username(u["username"]))
            device_login.password_changed(DB_PATH, st.session_state.user)
            st.success("Đã đổi mật khẩu.")
            st.rerun()'''
    if old not in source:
        raise RuntimeError("Security patch: profile password change missing")
    source = source.replace(old, new, 1)
    # The legacy Backup tab must not expose a second, unencrypted DB download.
    source, count = re.subn(
        r'    if (?:_admin_view|admin_view)\s*==\s*"backup"[^\n]*:\n.*?(?=\ndef profile_page\()',
        '    if admin_view == "backup":\n        st.caption("Tạo và tải bản sao lưu có mật khẩu bảo vệ ở bên dưới.")\n\n',
        source, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Security patch: legacy backup route missing")
    # Yearly full database snapshots receive the same encryption protection.
    source = source.replace('if Path(DB_PATH).exists(): snapshot_database(DB_PATH, db_path)',
        'if Path(DB_PATH).exists():\n        from khdn_apps.backup_crypto import encrypted_snapshot\n        db_path = encrypted_snapshot(DB_PATH, db_path, RUNTIME_DATA_DIR)', 1)
    source = source.replace('    if not bool(u["is_admin"]):\n        st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")',
        '    from khdn_apps.authorization import require_admin\n    u = require_admin(DB_PATH, u["id"])\n    if not bool(u["is_admin"]):\n        st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")', 1)
    compile(source, "<khdn-security-source>", "exec")
    return source
