# Release: Light contrast, per-task lunch exclusion, legacy cancellation migration.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
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
    && python /app/khdn_apps/performance_install_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/amount_decimal_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/full_task_edit_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/direct_task_edit_button_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/direct_task_edit_runtime_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/catalog_sync_qa.py \
    && PYTHONPATH=/app python /app/khdn_apps/notification_qa.py

RUN PYTHONPATH=/app python /app/khdn_apps/runtime_page_qa.py

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
