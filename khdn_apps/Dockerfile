# Release: Customer Work notes visible on every functional work card.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY khdn_apps/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Dark is the deterministic default; users can switch the custom BIDV Light/Dark
# variants from Streamlit Settings without changing application data.
COPY khdn_apps/.streamlit /app/.streamlit
COPY khdn_apps /app/khdn_apps
# Fail the image build if the dashboard CBHT detail section is not present in
# the source patch. This prevents a stale/cached image from reaching users.
RUN grep -Fq 'st.subheader("Chi tiết theo từng CBHT")' /app/khdn_apps/mobile_nav_patch.py
RUN python /app/khdn_apps/install_branding.py \
    && python /app/khdn_apps/install_push_pwa.py \
    && python /app/khdn_apps/admin_color_fix.py \
    && python /app/khdn_apps/lunch_break_preflight.py \
    && python /app/khdn_apps/reason_categories_preflight.py \
    && python /app/khdn_apps/reason_categories_semantic_qa.py \
    && python /app/khdn_apps/reason_categories_streamlit_smoke.py \
    && python /app/khdn_apps/install_reason_categories.py \
    && python /app/khdn_apps/task_note_visibility_qa.py \
    && python /app/khdn_apps/performance_preflight.py \
    && python /app/khdn_apps/performance_benchmark.py \
    && python /app/khdn_apps/install_performance.py \
    && python /app/khdn_apps/install_admin_scope.py \
    && python /app/khdn_apps/install_theme.py \
    && python /app/khdn_apps/theme_bridge_fix.py \
    && python /app/khdn_apps/mobile_client_focus_install.py \
    && python /app/khdn_apps/install_security.py \
    && python /app/khdn_apps/performance_install_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/amount_decimal_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/full_task_edit_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/direct_task_edit_button_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/direct_task_edit_runtime_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/catalog_sync_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/notification_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/customer_work_notification_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_work_notification_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_push_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_priority_policy_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_important_categories_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_compliance_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/room_workload_partition_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_schedule_export_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_entry_edit_qa.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/fast_client_form.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/legacy_fast_form.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/global_zero_keystroke_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/customer_work_note_card_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/mobile_input_performance_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/mobile_admin_restore_perf_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/mobile_legacy_ui_perf_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/mobile_client_focus_install.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/task_type_scope_source_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/task_type_scope_runtime_fix.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/weekly_plan_form_refinement_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_final_defaults_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_final_ux_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_week_board_focus_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_followup_ux_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_dashboard_consolidation_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_navigation_approval_parity_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_room_dashboard_detail_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/weekly_performance_phase2_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/weekly_phase2_notifications.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase3_core.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase3_weekly.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase3_dashboard.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase3_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase4_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase5_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase6_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase7_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase8_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase9_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase10_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase10_fix.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase11_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase12_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase13_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase14_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/planning_operational_phase15_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/customer_cif_admin_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/backup_management_patch.py \
    && PYTHONPATH=/app python -m py_compile /app/khdn_apps/offline_export_patch.py \
    && PYTHONPATH=/app python /app/khdn_apps/mobile_input_performance_v2_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/mobile_admin_restore_perf_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/mobile_legacy_ui_perf_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/global_zero_keystroke_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/customer_work_note_card_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_plan_form_refinement_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_plan_unified_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_final_defaults_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_final_ux_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_week_board_focus_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_followup_ux_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_dashboard_consolidation_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_navigation_approval_parity_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_room_dashboard_detail_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_performance_phase2_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase3_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase4_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase5_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase6_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase7_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase8_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase9_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase10_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase11_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase12_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase13_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/planning_operational_phase14_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/customer_cif_admin_patch_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/backup_management_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/offline_export_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/weekly_manager_edit_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/security_hardening_qa.py

RUN PYTHONUNBUFFERED=1 PYTHONPATH=/app python /app/khdn_apps/runtime_page_qa.py

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=Asia/Ho_Chi_Minh \
    KHDN_CLOUD_MODE=1 \
    KHDN_REQUIRE_VOLUME=1 \
    KHDN_DATA_DIR=/data \
    KHDN_DB_PATH=/data/khdn_ops.db

RUN mkdir -p /data /app/khdn_apps/logs /app/khdn_apps/annual_archive

EXPOSE 8080

CMD ["python", "-m", "khdn_apps.runtime"]
