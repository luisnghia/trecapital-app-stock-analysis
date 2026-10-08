from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from khdn_apps import backup_crypto
from khdn_apps import offline_export_patch as patch
from khdn_apps import backup_management_patch as backup


def main():
    with tempfile.TemporaryDirectory(prefix="khdn-offline-export-qa-") as td:
        root = Path(td)
        db = root / "live.db"
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT)")
            c.execute("CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT)")
            c.execute("INSERT INTO users VALUES(1,'admin')")
            c.execute("INSERT INTO tasks VALUES(1,'Hồ sơ kiểm thử')")

        source = root / "src" / "khdn_apps"
        (source / ".streamlit").mkdir(parents=True)
        (source / "logs").mkdir(parents=True)
        (source / "__pycache__").mkdir(parents=True)
        (source / "requirements.txt").write_text("streamlit==1.63.0\n", encoding="utf-8")
        (source / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")
        (source / ".streamlit" / "config.toml").write_text("[theme]\n", encoding="utf-8")
        (source / "logs" / "should-not-ship.log").write_text("no", encoding="utf-8")
        (source / "__pycache__" / "runtime.pyc").write_bytes(b"no")

        target = patch.create_offline_package(
            root,
            db,
            root / "offline.zip",
            actor="qa",
            source_dir=source,
            backup_module=backup,
            password="QA-offline-strong-password",
        )
        assert target.exists() and target.stat().st_size > 0
        with zipfile.ZipFile(target) as zf:
            names = set(zf.namelist())
            required = {
                "khdn_apps/requirements.txt",
                "khdn_apps/runtime.py",
                "khdn_apps/.streamlit/config.toml",
                "data/khdn_ops.db.khdn",
                "offline_manifest.khdn",
                "README_OFFLINE.txt",
                "INSTALL_KHDN_OFFLINE.bat",
                "RUN_KHDN_OFFLINE.bat",
                "BACKUP_DATA_OFFLINE.bat",
                "offline_backup.py",
            }
            assert required.issubset(names), sorted(required - names)
            assert "khdn_apps/logs/should-not-ship.log" not in names
            assert "khdn_apps/__pycache__/runtime.pyc" not in names

            manifest = json.loads(backup_crypto.decrypt(zf.read("offline_manifest.khdn"), password="QA-offline-strong-password", kind="offline-manifest").decode("utf-8"))
            assert manifest["database_integrity"] == "ok"
            assert manifest["table_counts"]["users"] == 1
            assert manifest["source_file_count"] == 3

            run_bat = zf.read("RUN_KHDN_OFFLINE.bat").decode("utf-8")
            install_bat = zf.read("INSTALL_KHDN_OFFLINE.bat").decode("utf-8")
            backup_bat = zf.read("BACKUP_DATA_OFFLINE.bat").decode("utf-8")
            assert "KHDN_REQUIRE_VOLUME=0" in run_bat
            assert "KHDN_CLOUD_MODE=0" in run_bat
            assert "-m khdn_apps.runtime" in run_bat
            assert 'pip install -r "khdn_apps\\requirements.txt"' in install_bat
            assert "offline_backup.py" in backup_bat

            restored = root / "restored.db"
            assert "data/khdn_ops.db" not in names
            assert "unlock-offline" in run_bat and "install_security.py" in install_bat
            restored.write_bytes(backup_crypto.decrypt(zf.read("data/khdn_ops.db.khdn"), password="QA-offline-strong-password", kind="offline-database"))
        with sqlite3.connect(restored) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert c.execute("SELECT username FROM users WHERE id=1").fetchone()[0] == "admin"

    print(
        "KHDN_OFFLINE_EXPORT_QA_PASS source=1 data_snapshot=1 integrity=1 "
        "windows_install=1 windows_run=1 offline_backup=1 excludes_runtime_junk=1"
    )


if __name__ == "__main__":
    main()
