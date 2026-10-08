from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase4_patch.py").read_text(encoding="utf-8")
backup = (ROOT / "backup_management_patch.py").read_text(encoding="utf-8")
checks = {
    "quick_add_all_roles": "wp_add_open_" in src and "p3_quick_add_" in src and "roles=all-plan-owners" in src,
    "combined_queue": "Trung tâm việc chờ lãnh đạo xử lý" in src and "Phê duyệt kế hoạch / dời hạn" in src and "Cập nhật tiến độ / vướng mắc" in src,
    "old_bottom_removed": "room_dashboard._render_approval_center = no_bottom_approval" in src,
    "room_card_today_info": all(x in src for x in ["Tạo lúc:", "Phụ trách:", "Kiểm soát:", "Dự kiến:", "Vướng mắc:", "🔎 Chi tiết"]),
    "room_detail_route": all(x in src for x in ['st.session_state["cw_case_id"]', 'st.session_state["main_page"] = "customer_work"']),
    "approval_week_board": "manager_edit=True" in src and "p3week.manager_edit_item" in src,
    "backup_installed": "backup.install(app_ns, logger)" in src,
    "backup_full_sqlite": "FULL_SQLITE_ALL_APPLICATION_TABLES" in backup and "khdn_ops.db" in backup,
    "backup_csv": "tables/{table}.csv" in backup,
    "backup_phone_copy": "số điện thoại/người liên hệ" in backup,
    "backup_admin": "Sao lưu dữ liệu" in backup and "Tạo bản backup có mật khẩu" in backup and "require_admin(db_path" in backup,
    "backup_integrity": "PRAGMA integrity_check" in backup,
    "html_table_wrap": "table-layout:fixed" in backup and "white-space:normal" in backup and "overflow-wrap:anywhere" in backup,
}
assert all(checks.values()), checks
print("PLANNING_OPERATIONAL_PHASE4_QA_PASS", checks)
