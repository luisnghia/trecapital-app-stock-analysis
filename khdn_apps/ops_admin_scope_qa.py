from __future__ import annotations
from pathlib import Path

from khdn_apps.admin_scope_patch import patch_source
import khdn_apps.operations_admin_nav_patch as ops_nav


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
    assert 'page_title("Quản trị tác nghiệp"' in out
    assert 'page_title("Quản trị hệ thống", "Quản lý người dùng và khách hàng CIF.")' in out
    assert '_admin_scope=="ops"' in out
    assert '[("types","🧩","Loại công việc"),("reasons","🧩","Nhóm nguyên nhân")] if _leader_scope' in out
    assert '("audit","🧾","Audit")' in out and '("backup","💾","Sao lưu")' in out
    assert '_admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF")]' in out
    assert 'Tác nghiệp → Quản trị → Nhóm nguyên nhân' in out

    nav_src=Path(ops_nav.__file__).read_text(encoding="utf-8")
    assert '("ops_admin","Quản trị")' in nav_src
    assert 'CUSTOM_PAGES.add("ops_admin")' in nav_src
    assert 'st.session_state["admin_scope"]="ops"' in nav_src
    assert 'st.session_state["admin_scope"]="system"' in nav_src
    assert 'role!="Lãnh đạo phòng" and not admin' in nav_src
    print("OPS_ADMIN_SCOPE_QA_PASS")


if __name__=="__main__":
    main()
