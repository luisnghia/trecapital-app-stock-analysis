"""Unified System Admin scope.

All operational administration now lives under the Admin-only System Admin page:
- Users
- Customer/CIF master
- Work types
- Operational reason groups
- Audit
- Backup

The old Tác nghiệp > Quản trị split is retired.
"""
from __future__ import annotations

import re


def _sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    out, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1:
        raise RuntimeError(f"Admin-scope patch cannot find transformed fragment: {label}")
    return out


def patch_source(source: str) -> str:
    start = source.find("def admin_page(u):")
    if start < 0:
        raise RuntimeError("Admin-scope patch cannot find admin_page")
    end_candidates = [
        source.find("\ndef profile_page(", start),
        source.find("\ndef guide_page(", start),
        source.find("\ndef app(", start),
    ]
    end_candidates = [x for x in end_candidates if x > start]
    end = min(end_candidates) if end_candidates else len(source)
    page = source[start:end]

    if '_leader_scope = bool(u["role"] == "Lãnh đạo phòng" and not u["is_admin"])' not in page:
        raise RuntimeError("Admin-scope patch expects leader-scope reason patch first")

    page = _sub_once(
        page,
        r'^    page_title\("Quản trị hệ thống".*\)\n',
        '''    if not bool(u["is_admin"]):\n        st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")\n        return\n    st.session_state["admin_scope"]="system"\n    page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân tác nghiệp, audit và sao lưu dữ liệu.")\n''',
        "admin page title and guard",
    )
    page = _sub_once(
        page,
        r'^    _admin_options=.*\n',
        '''    _admin_options=[\n        ("users","👥","Người dùng"),\n        ("customers","🏢","Khách hàng CIF"),\n        ("types","🧩","Loại công việc"),\n        ("reasons","🧩","Nhóm nguyên nhân tác nghiệp"),\n        ("audit","🧾","Audit"),\n        ("backup","💾","Sao lưu"),\n    ]\n''',
        "unified admin options",
    )
    page = _sub_once(
        page,
        r'^    _admin_default=.*\n',
        '    _admin_default="users"\n',
        "admin default",
    )

    source = source[:start] + page + source[end:]
    source = source.replace(
        "Admin/Lãnh đạo phòng cần tạo nhóm trong Quản trị hệ thống → Nhóm nguyên nhân trước khi thực hiện thao tác này.",
        "Admin cần tạo nhóm trong Quản trị hệ thống → Nhóm nguyên nhân tác nghiệp trước khi thực hiện thao tác này.",
    )

    required = [
        'if not bool(u["is_admin"])',
        'st.session_state["admin_scope"]="system"',
        'page_title("Quản trị hệ thống"',
        '("reasons","🧩","Nhóm nguyên nhân tác nghiệp")',
        '("audit","🧾","Audit")',
        '("backup","💾","Sao lưu")',
        '_admin_default="users"',
    ]
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"Admin-scope patch marker missing: {marker}")
    return source
