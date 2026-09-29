from __future__ import annotations

from pathlib import Path

from khdn_apps import planning_operational_phase6_patch as p6

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase6_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "admin_six_tabs": all(
        marker in src
        for marker in [
            '("users", "👥 Người dùng")',
            '("customers", "🏢 Khách hàng CIF")',
            '("types", "🧩 Loại công việc")',
            '("reasons", "🧩 Nhóm nguyên nhân tác nghiệp")',
            '("audit", "🧾 Audit")',
            '("backup", "💾 Sao lưu")',
        ]
    ),
    "admin_only": 'Chỉ Admin mới có quyền truy cập Quản trị hệ thống.' in src,
    "controller_exact": 'controller_user_id' in src and '_controller_allows' in src,
    "admin_all": 'if _is_admin_row(actor):' in src and 'return True' in src,
    "permission_guard": 'Bạn chỉ được phê duyệt công việc do mình là Lãnh đạo kiểm soát' in src,
    "compact_room_detail": 'p6_room_case_detail_' in src and 'h1, h2, h3 = st.columns' in src,
    "compact_week_update": 'p6_update_btn_' in src and 'h1, h2 = st.columns' in src,
    "yellow_actions": '#F4B41A' in src and '#FFD45A' in src and '#FFE589' in src,
    "readable_classification": 'CLASSIFICATION_CHANGE' in src and 'Q4 · Giá trị thấp' in src and 'Lý do:' in src,
    "unique_quick_add": 'p3_quick_add_{uid}_{ws.isoformat()}_{idx}_{status}' in src,
    "phase3_alias_rebind": 'p3dash.weekly_card = _compact_weekly_card' in src,
    "phase6_installed_last": '_operational_phase6.install' in hotfix and 'VERSION = "2.2.0"' in hotfix,
}

bad = [name for name, ok in checks.items() if not ok]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE6_QA_FAIL {bad} {checks}")

label, detail = p6._fmt_action(
    "CLASSIFICATION_CHANGE",
    '{"old_q":4,"new_q":2,"old_focus":null,"new_focus":4,"reason":"Phân loại khi tạo kế hoạch"}',
)
assert label == "Điều chỉnh phân loại", (label, detail)
assert "Q4 · Giá trị thấp → Q2 · Trọng tâm" in detail, detail
assert "Phân loại khi tạo kế hoạch" in detail, detail
assert "{" not in detail and '"old_q"' not in detail, detail

print("PLANNING_OPERATIONAL_PHASE6_QA_PASS", checks, detail)
