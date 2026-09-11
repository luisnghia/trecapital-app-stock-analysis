FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY khdn_apps/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY khdn_apps /app/khdn_apps

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Ho_Chi_Minh \
    KHDN_CLOUD_MODE=1 \
    KHDN_DATA_DIR=/data \
    KHDN_DB_PATH=/data/khdn_ops.db

RUN mkdir -p /data /app/khdn_apps/logs /app/khdn_apps/annual_archive

EXPOSE 8501

CMD ["sh","-c","streamlit run khdn_apps/online_entry.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --browser.gatherUsageStats=false"]
