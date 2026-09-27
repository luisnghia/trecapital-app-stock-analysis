from __future__ import annotations

import ast
from pathlib import Path


def run():
    here = Path(__file__).resolve().parent
    src = (here / "planning_usability_v3_patch.py").read_text(encoding="utf-8")
    entry = (here / "online_entry.py").read_text(encoding="utf-8")
    ast.parse(src)

    checks = {
        "red_required_fields": "#FF4B4B" in src and "cwuv3_invalid_" in src and "ô viền đỏ" in src,
        "staff_owner_default": 'disabled=True' in src and '"Cán bộ phụ trách *"' in src and '[current_owner]' in src,
        "leader_controller": '"Lãnh đạo kiểm soát *"' in src and "controller_user_id" in src,
        "controller_schema": "idx_cw_controller" in src and "controller_name" in src,
        "created_at_card": "<b>Tạo lúc:</b>" in src and 'x.get("created_at")' in src,
        "customer_click_resets": 'str(label).strip() == "Công việc khách hàng"' in src and '["cw_view"] = "processing"' in src,
        "detail_reset": 'pop("cw_case_id", None)' in src,
        "catalog_exact_command_tabs": "ui_hotfix._local_command_tabs" in src and "render_catalog_page" in src,
        "customer_exact_command_tabs": "render_cases_page" in src and "_exact_child_nav" in src,
        "installed_online": "_install_planning_usability_v3(" in entry,
        "installed_after_hotfix": entry.find("_install_planning_usability_v3(") > entry.find("_install_planning_ui_post("),
    }
    assert all(checks.values()), checks
    print("PLANNING_USABILITY_V3_QA_PASS", checks)


if __name__ == "__main__":
    run()
