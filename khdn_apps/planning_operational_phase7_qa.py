from __future__ import annotations

from pathlib import Path

from khdn_apps import planning_operational_phase7_patch as p7

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase7_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "large_admin_cards": "min-height:7.25rem" in src and "p7_system_admin_cards" in src,
    "six_admin_routes": all(x in src for x in [
        '("users", "👥 Người dùng")', '("customers", "🏢 Khách hàng CIF")',
        '("types", "🧩 Loại công việc")', '("reasons", "🧩 Nhóm nguyên nhân tác nghiệp")',
        '("audit", "🧾 Audit")', '("backup", "💾 Sao lưu")',
    ]),
    "reason_route": '_render_reason_category_manager' in src,
    "audit_route": 'Audit hệ thống' in src and 'FROM system_audit' in src,
    "backup_route": 'backup.render_backup_admin' in src,
    "cancel_request_schema": 'weekly_plan_cancel_requests' in src and 'idx_week_cancel_one_pending' in src,
    "cancel_not_immediate": 'Gửi đề nghị hủy' in src and 'công việc chưa bị hủy' in src,
    "controller_approval": '_weekly_controller_allows' in src and 'Lãnh đạo kiểm soát' in src,
    "admin_approval": 'is_admin' in src and 'return True' in src,
    "cancel_approval_effect": "SET status='CANCELLED'" in src and 'CANCEL_APPROVE' in src,
    "cancel_reject": 'CANCEL_REJECT' in src and 'Từ chối hủy' in src,
    "vietnamese_status": all(x in src for x in ['"PLANNED": "Chưa làm"', '"IN_PROGRESS": "Đang làm"', '"DONE": "Hoàn thành"']),
    "phase7_last": '_operational_phase7.install' in hotfix,
}

bad = [name for name, ok in checks.items() if not ok]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE7_QA_FAIL {bad} {checks}")

label, detail = p7._fmt_action_vi(
    "EXEC_UPDATE_PHASE3",
    '{"old_status":"IN_PROGRESS","new_status":"DONE","actual_result":"Đã hoàn tất hồ sơ"}',
)
assert label == "Cập nhật tiến độ", (label, detail)
assert detail == "Đang làm → Hoàn thành · Đã hoàn tất hồ sơ", detail

label2, detail2 = p7._fmt_action_vi(
    "CANCEL_REQUEST",
    '{"status_before":"PLANNED","reason":"Khách hàng dừng nhu cầu"}',
)
assert label2 == "Đề nghị hủy công việc", (label2, detail2)
assert "Chưa làm" in detail2 and "Khách hàng dừng nhu cầu" in detail2, detail2

print("PLANNING_OPERATIONAL_PHASE7_QA_PASS", checks, detail, detail2)
