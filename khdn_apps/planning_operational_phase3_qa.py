from pathlib import Path
ROOT=Path(__file__).resolve().parent
core=(ROOT/'planning_operational_phase3_core.py').read_text(encoding='utf-8')
weekly=(ROOT/'planning_operational_phase3_weekly.py').read_text(encoding='utf-8')
dash=(ROOT/'planning_operational_phase3_dashboard.py').read_text(encoding='utf-8')
patch=(ROOT/'planning_operational_phase3_patch.py').read_text(encoding='utf-8')
hotfix=(ROOT/'weekly_priority_policy_hotfix.py').read_text(encoding='utf-8')
checks={
 'realtime': all(x in core for x in ['_visible_task_change_token','customer_work_cases','weekly_plan_items','planning_attention_events']),
 'mandatory_stage_note': 'Bắt buộc nhập **Ghi chú chuyển bước**' in core and 'cw_stage_note_invalid_' in core,
 'events': 'planning_attention_events' in core and 'STAGE_CHANGE' in core and 'ISSUE_OPEN' in core,
 'detail_color': 'Chuyển đổi / vướng mắc nổi bật' in core and 'p3-stage' in core and 'p3-issue' in core,
 'duplicate_fix': 'planning_week_board_focus_patch.py' in core and 'finalux._render_context = render_context' in core,
 'weekday_board': 'st.columns(5' in weekly and 'Kế hoạch Thứ 2 → Thứ 6' in weekly,
 'card_progress': '🔄 Cập nhật tiến độ' in weekly and 'p3_update_week_item' in weekly,
 'old_progress_replaced': 'Cập nhật tiến độ trực tiếp trên từng card công việc' in weekly,
 'manager_edit_all': all(x in weekly for x in ['Khách hàng','Công việc *','Ngày thực hiện *','Ngày dự kiến hoàn thành *','Lãnh đạo kiểm soát *','Nhóm công việc','Nguồn / nội dung gốc','Kết quả đầu ra','Ghi chú']),
 'today_rich': 'Công việc theo kế hoạch hôm nay' in dash and 'weekly_card(' in dash,
 'ack': '✓ Đã xem' in dash and '✓ Đã xử lý' in dash,
 'approval_weekday': 'manager_edit=True' in dash and 'Kế hoạch tuần đã nộp' in dash,
 'room_lists': 'Theo mục công việc · danh sách khách hàng' in dash and 'Theo cán bộ · danh sách khách hàng' in dash,
 'attention_color': 'p3-watch-flags' in dash and '#F04438' in dash and '#F79009' in dash,
 'html_table': '.p3-table table' in dash and 'white-space:normal' in dash and 'overflow-wrap:anywhere' in dash,
 'installed': '_operational_phase3.install' in hotfix and 'operational_phase3=1' in hotfix and 'dashboard.install_room_dashboard' in patch,
}
assert all(checks.values()),checks
print('PLANNING_OPERATIONAL_PHASE3_QA_PASS',checks)
