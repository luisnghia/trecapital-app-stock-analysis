from __future__ import annotations

import ast
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    src = (here / "planning_ui_admin_hotfix.py").read_text(encoding="utf-8")
    admin_src = (here / "admin_scope_patch.py").read_text(encoding="utf-8")
    entry = (here / "online_entry.py").read_text(encoding="utf-8")
    ast.parse(src)
    ast.parse(admin_src)
    ast.parse(entry)

    checks = {
        "system_admin_has_types": '("types","🧩","Loại công việc")' in admin_src,
        "ops_admin_has_no_types": '_admin_options=[("reasons","🧩","Nhóm nguyên nhân")] if _leader_scope' in admin_src,
        "system_type_renderer": 'def _render_system_task_types' in src,
        "module_scope_create": 'module_scope,created_at,updated_at' in src and 'Thuộc phân hệ *' in src,
        "module_scope_edit": 'UPDATE task_types SET name=?,module_scope=?,active=?,updated_at=?' in src,
        "exact_command_css": 'background:#F3F1E3!important' in src and 'border:2px solid #F4B41A!important' in src,
        "customer_child_tabs": 'state_key in {"cw_view", "cw_catalog_view_v2"}' in src,
        "approval_signature": 'def render_approvals_page(st=None, u=None, get_conn=None' in src,
        "approval_positional_bridge": 'previous_approval(st_arg, u, conn_fn' in src,
        "pre_before_v2": entry.index('_install_planning_ui_pre(') < entry.index('_install_planning_usability_v2('),
        "post_after_v2": entry.index('_install_planning_ui_post(') > entry.index('_install_planning_usability_v2('),
    }
    assert all(checks.values()), checks
    print("PLANNING_UI_ADMIN_HOTFIX_QA_PASS", checks)


if __name__ == "__main__":
    main()
