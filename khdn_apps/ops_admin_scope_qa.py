from __future__ import annotations
from khdn_apps.admin_scope_patch import patch_source


def main():
    sample='''def admin_page(u):
    _leader_scope = bool(u["role"] == "Lãnh đạo phòng" and not u["is_admin"])
    page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân, audit và sao lưu dữ liệu.")
    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("reasons","🧩","Nhóm nguyên nhân"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]
    _admin_values=[x[0] for x in _admin_options]
    _admin_default="types" if _leader_scope else "users"
    _admin_current=st.session_state.get("admin_view",_admin_default)
    if _admin_current not in _admin_values:
        _admin_current=_admin_default
    admin_view=_admin_current
    if admin_view == "users":
        pass
    if admin_view == "types":
        pass
    if admin_view == "reasons":
        pass
    if admin_view == "audit":
        pass
    if admin_view == "backup":
        pass

def reason_category_selectbox():
    st.warning("Chưa có nhóm nguyên nhân đang hoạt động. Admin/Lãnh đạo phòng cần tạo nhóm trong Quản trị hệ thống → Nhóm nguyên nhân trước khi thực hiện thao tác này.")

def profile_page(u):
    pass
'''
    out=patch_source(sample)
    assert 'if not bool(u["is_admin"])' in out
    assert 'Chỉ Admin mới có quyền truy cập Quản trị hệ thống.' in out
    assert 'st.session_state["admin_scope"]="system"' in out
    assert 'page_title("Quản trị hệ thống"' in out
    for marker in [
        '("users","👥","Người dùng")',
        '("customers","🏢","Khách hàng CIF")',
        '("types","🧩","Loại công việc")',
        '("reasons","🧩","Nhóm nguyên nhân tác nghiệp")',
        '("audit","🧾","Audit")',
        '("backup","💾","Sao lưu")',
    ]:
        assert marker in out, marker
    assert '_admin_default="users"' in out
    assert 'Quản trị hệ thống → Nhóm nguyên nhân tác nghiệp' in out
    assert 'Quản trị tác nghiệp' not in out
    print("OPS_ADMIN_SCOPE_QA_PASS unified_system_admin=1 admin_only=1 operational_admin_merged=1")


if __name__=="__main__":
    main()
