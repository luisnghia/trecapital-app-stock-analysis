"""Start KHDN Ops only after the persistent volume passes its checks."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from .storage import atomic_json, daily_backup, prepare_storage, read_status


def main() -> int:
    data_dir = Path(os.getenv("KHDN_DATA_DIR", "/data")).resolve()
    db_path = Path(os.getenv("KHDN_DB_PATH", str(data_dir / "khdn_ops.db"))).resolve()
    require_volume = os.getenv("KHDN_REQUIRE_VOLUME", "1").lower() not in {"0", "false", "no"}
    status = prepare_storage(data_dir, db_path, require_volume)
    os.environ.pop("KHDN_MIGRATION_DB_GZIP_BASE64", None)
    os.environ.pop("KHDN_MIGRATION_DB_SHA256", None)
    logger = logging.getLogger("khdn_storage")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(data_dir / "logs" / "storage.log", maxBytes=1_000_000,
                                 backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    logger.info("STORAGE_READY id=%s mounted=%s", status["storage_id"], status["volume_mounted"])
    stop = threading.Event()

    def backup_loop():
        while not stop.is_set():
            try:
                previous = read_status(data_dir / "backup_status.json").get("last_success")
                target = daily_backup(data_dir, db_path)
                current = read_status(data_dir / "backup_status.json").get("last_success")
                if target and current != previous:
                    logger.info("BACKUP_OK file=%s", target.name)
            except Exception as exc:
                logger.exception("BACKUP_FAILED")
                info = read_status(data_dir / "backup_status.json")
                info.update(last_error=type(exc).__name__,
                            failed_at=datetime.now(timezone.utc).isoformat())
                try:
                    atomic_json(data_dir / "backup_status.json", info)
                except OSError:
                    logger.exception("BACKUP_STATUS_WRITE_FAILED")
            stop.wait(60)

    worker = threading.Thread(target=backup_loop, name="khdn-daily-backup", daemon=True)
    worker.start()
    child = None
    pending_signal = None

    def forward(signum, frame):
        nonlocal pending_signal
        pending_signal = signum
        stop.set()
        if child is not None and child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    try:
        child = subprocess.Popen([
            sys.executable, "-m", "khdn_apps.web_server", "run", str(Path(__file__).with_name("online_entry.py")),
            "--server.address=0.0.0.0", f"--server.port={os.getenv('PORT', '8080')}",
            "--server.headless=true", "--browser.gatherUsageStats=false",
        ])
        if pending_signal is not None:
            child.send_signal(pending_signal)
        return child.wait()
    finally:
        stop.set()
        worker.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
