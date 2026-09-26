"""Split legacy Admin into System administration and Tác nghiệp administration.

This transformer runs after the reason/catalog source patches. It does not change
business logic or permissions; it only scopes which existing admin destinations
are visible from each navigation entry:
- Quản trị hệ thống: Người dùng + Khách hàng CIF + Loại công việc (Admin only).
- Tác nghiệp > Quản trị: Nhóm nguyên nhân; Admin additionally sees Audit + Sao lưu.
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

    # Leaders can reach operational administration only; System Admin remains
    # Admin-only and now owns the shared Loại công việc catalog.
    page = _sub_once(
        page,
        r'^    page_title\("Quản trị hệ thống".*\)\n',
        '''    _admin_scope=str(st.session_state.get("admin_scope","system") or "system")\n    if _admin_scope not in {"system","ops"}:\n        _admin_scope="system"; st.session_state["admin_scope"]="system"\n    if _leader_scope and _admin_scope!="ops":\n        _admin_scope="ops"; st.session_state["admin_scope"]="ops"\n    if _admin_scope=="ops":\n        page_title("Quản trị tác nghiệp", "Cấu hình nhóm nguyên nhân, audit và sao lưu dữ liệu." if u["is_admin"] else "Cấu hình nhóm nguyên nhân tác nghiệp.")\n    else:\n        page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF và loại công việc.")\n''',
        "admin page title",
    )

    page = _sub_once(
        page,
        r'^    _admin_options=.*\n',
        '''    if _admin_scope=="ops":\n        _admin_options=[("reasons","🧩","Nhóm nguyên nhân")] if _leader_scope else [("reasons","🧩","Nhóm nguyên nhân"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n    else:\n        _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc")]\n''',
        "admin options",
    )
    page = _sub_once(
        page,
        r'^    _admin_default=.*\n',
        '    _admin_default="reasons" if _admin_scope=="ops" else "users"\n',
        "admin default",
    )

    # User-facing guidance for reason categories stays under operational admin.
    source = source[:start] + page + source[end:]
    source = source.replace(
        "Admin/Lãnh đạo phòng cần tạo nhóm trong Quản trị hệ thống → Nhóm nguyên nhân trước khi thực hiện thao tác này.",
        "Admin/Lãnh đạo phòng cần tạo nhóm trong Tác nghiệp → Quản trị → Nhóm nguyên nhân trước khi thực hiện thao tác này.",
    )

    required = [
        'page_title("Quản trị tác nghiệp"',
        '_admin_scope=="ops"',
        '("reasons","🧩","Nhóm nguyên nhân")',
        '("audit","🧾","Audit")',
        '("backup","💾","Sao lưu")',
        'page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF và loại công việc.")',
        '("users","👥","Người dùng")',
        '("customers","🏢","Khách hàng CIF")',
        '("types","🧩","Loại công việc")',
        '_admin_default="reasons" if _admin_scope=="ops" else "users"',
    ]
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"Admin-scope patch marker missing: {marker}")
    return source
