FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY khdn_apps/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Streamlit's explicit theme config makes Dark the deterministic default in Railway.
COPY khdn_apps/.streamlit /app/.streamlit
COPY khdn_apps /app/khdn_apps
RUN python /app/khdn_apps/install_branding.py \
    && python /app/khdn_apps/admin_color_fix.py \
    && python /app/khdn_apps/reason_categories_preflight.py \
    && python /app/khdn_apps/reason_categories_semantic_qa.py \
    && python /app/khdn_apps/reason_categories_streamlit_smoke.py \
    && python /app/khdn_apps/install_reason_categories.py

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
