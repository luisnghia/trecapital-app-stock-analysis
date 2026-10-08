"""Admin-only export of the current KHDN application + live data for offline use."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

from khdn_apps.storage import snapshot_database
from khdn_apps import backup_crypto
from khdn_apps.authorization import require_admin

VERSION = "2.0.0"
_FLAG = "_KHDN_OFFLINE_EXPORT_PATCH_VERSION"

_EXCLUDED_PARTS = {"__pycache__", ".git", ".github", "logs", "annual_archive", "backups", "data", ".venv"}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".zip", ".log"}


def _source_files(source_dir: Path):
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir)
        if any(part in _EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.name.lower() in {"secrets.toml", ".backup-encryption.key"} or path.name.startswith(".env") or path.suffix.lower() in {".pem", ".key", ".khdn"}:
            continue
        if path.suffix.lower() in _EXCLUDED_SUFFIXES:
            continue
        yield path, rel


def _install_bat() -> str:
    return r"""@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo KHDN Ops - Cai dat lan dau
echo ==========================================
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYCMD=py -3"
) else (
  set "PYCMD=python"
)
%PYCMD% --version >nul 2>nul
if errorlevel 1 (
  echo KHONG TIM THAY PYTHON 3.
  echo Hay cai Python 3.11 hoac 3.12, sau do chay lai file nay.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  %PYCMD% -m venv .venv
  if errorlevel 1 goto :error
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r "khdn_apps\requirements.txt"
if errorlevel 1 goto :error

echo.
echo Dang ap dung giao dien va cac ban va hieu nang...
for %%S in (
  install_branding.py
  install_push_pwa.py
  admin_color_fix.py
  install_reason_categories.py
  install_performance.py
  install_admin_scope.py
  install_theme.py
  theme_bridge_fix.py
  mobile_client_focus_install.py
  install_security.py
) do (
  if exist "khdn_apps\%%S" (
    python "khdn_apps\%%S"
    if errorlevel 1 goto :error
  )
)

echo.
echo CAI DAT HOAN TAT.
echo Tu lan sau chi can bam RUN_KHDN_OFFLINE.bat
pause
exit /b 0

:error
echo.
echo CAI DAT THAT BAI. Vui long chup man hinh loi va gui de kiem tra.
pause
exit /b 1
"""


def _run_bat() -> str:
    return r"""@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai moi truong offline.
  echo Hay chay INSTALL_KHDN_OFFLINE.bat truoc.
  pause
  exit /b 1
)
set "KHDN_DATA_DIR=%~dp0data"
set "KHDN_DB_PATH=%~dp0data\khdn_ops.db"
set "KHDN_REQUIRE_VOLUME=0"
set "KHDN_CLOUD_MODE=0"
set "PORT=8501"
".venv\Scripts\python.exe" -m khdn_apps.backup_crypto unlock-offline "%~dp0."
if errorlevel 1 (
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8501"
".venv\Scripts\python.exe" -m khdn_apps.runtime
pause
"""


def _backup_py() -> str:
    return '''from datetime import datetime
from pathlib import Path
from getpass import getpass
from khdn_apps.backup_management_patch import create_full_backup_package, database_inventory

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "khdn_ops.db"
OUT = ROOT / "backups"
OUT.mkdir(parents=True, exist_ok=True)
if not DB.exists():
    raise SystemExit(f"Khong tim thay CSDL: {DB}")
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
target = OUT / f"KHDN-Ops-Offline-Backup-{stamp}.zip"
password = getpass("Mat khau bao ve backup (tu 12 ky tu): ")
if password != getpass("Nhap lai mat khau: "):
    raise SystemExit("Mat khau khong khop")
create_full_backup_package(DB, target, reason="offline-manual", actor="offline-user", password=password)
info = database_inventory(DB)
print(f"BACKUP_OK: {target}")
print(f"integrity={info['integrity']} tables={len(info['tables'])}")
'''


def _backup_bat() -> str:
    return r"""@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai moi truong offline. Hay chay INSTALL_KHDN_OFFLINE.bat truoc.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" offline_backup.py
echo.
echo File backup nam trong thu muc backups.
pause
"""


def _readme() -> str:
    return """KHDN Ops - Gói chạy Offline
============================

Gói gồm mã nguồn KHDN đang chạy tại thời điểm xuất, một ảnh chụp SQLite nhất quán
của dữ liệu hiện tại và các file cài/chạy/backup trên máy local.

CHẠY LẦN ĐẦU
- Giải nén ZIP vào một thư mục riêng.
- Cần Python 3.11 hoặc 3.12.
- Khi còn Internet, chạy INSTALL_KHDN_OFFLINE.bat một lần để cài thư viện.
- Sau đó chạy RUN_KHDN_OFFLINE.bat. App dùng http://127.0.0.1:8501 và đọc/ghi
  trực tiếp data\\khdn_ops.db, không phụ thuộc Railway. Lần chạy đầu tiên nhập mật khẩu bảo vệ đã đặt khi xuất để mở CSDL.

SAO LƯU OFFLINE
- Có thể dùng chức năng Sao lưu trong app.
- Hoặc đóng app rồi chạy BACKUP_DATA_OFFLINE.bat; file ZIP nằm trong thư mục backups.

KHÔI PHỤC
- Đóng app.
- Giữ lại một bản data\\khdn_ops.db hiện tại.
- Giải nén gói backup vào thư mục riêng, chạy DECRYPT_BACKUP.bat và nhập mật khẩu.\n- Lấy restored\\khdn_ops.db chép vào data\\khdn_ops.db sau khi đã giữ bản hiện tại.
- Chạy lại RUN_KHDN_OFFLINE.bat.

BẢO MẬT
- Dữ liệu trong gói ZIP được mã hóa AES-256-GCM; mật khẩu không nằm trong gói. Không thể khôi phục nếu mất mật khẩu.\n- Sau khi mở khóa, data\\khdn_ops.db là bản sao đầy đủ, có thể chứa tài khoản, hồ sơ khách hàng,
  lịch sử, audit và dữ liệu nội bộ. Lưu file ở nơi an toàn, không gửi công khai.

LƯU Ý
- INSTALL_KHDN_OFFLINE.bat cần Internet ở lần cài thư viện đầu tiên nếu máy chưa có
  các gói Python cần thiết. Sau khi .venv được cài, app có thể vận hành local.
"""


def create_offline_package(
    data_dir: Path | str,
    db_path: Path | str,
    target: Path | str,
    *,
    actor: str | None = None,
    source_dir: Path | str | None = None,
    backup_module=None,
    password: str,
) -> Path:
    """Create source + transaction-consistent DB + local launchers in one ZIP."""
    backup_crypto.validate_password(password)
    data_dir = Path(data_dir).resolve()
    db_path = Path(db_path).resolve()
    target = Path(target).resolve()
    source_dir = Path(source_dir or Path(__file__).resolve().parent).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if not source_dir.exists():
        raise FileNotFoundError(f"App source not found: {source_dir}")
    if not (source_dir / "requirements.txt").exists():
        raise FileNotFoundError(f"requirements.txt not found under: {source_dir}")
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    if backup_module is None:
        from khdn_apps import backup_management_patch as backup_module

    fd, tmp_name = tempfile.mkstemp(prefix=".khdn-offline-", suffix=".zip", dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with tempfile.TemporaryDirectory(prefix="khdn-offline-snapshot-", dir=target.parent) as work:
            snap = snapshot_database(db_path, Path(work) / "khdn_ops.db")
            inventory = backup_module.database_inventory(snap)
            with snap.open("rb") as stream:
                db_sha = hashlib.file_digest(stream, "sha256").hexdigest()
            files = list(_source_files(source_dir))
            manifest = {
                "product": "KHDN Ops",
                "offline_export_version": VERSION,
                "created_at": datetime.now().astimezone().isoformat(),
                "actor": str(actor or "") or None,
                "git_commit": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA") or None,
                "git_branch": os.getenv("RAILWAY_GIT_BRANCH") or os.getenv("GIT_BRANCH") or None,
                "database_sha256": db_sha,
                "database_integrity": inventory["integrity"],
                "table_counts": inventory["tables"],
                "source_file_count": len(files),
                "runtime": {
                    "data_dir": "data",
                    "db_path": "data/khdn_ops.db",
                    "require_volume": False,
                    "cloud_mode": False,
                    "port": 8501,
                },
            }
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for path, rel in files:
                    zf.write(path, Path("khdn_apps") / rel)
                zf.writestr("data/khdn_ops.db.khdn", backup_crypto.encrypt(snap.read_bytes(), password=password, kind="offline-database"))
                zf.writestr("offline_manifest.khdn", backup_crypto.encrypt(json.dumps(manifest, ensure_ascii=False, indent=2).encode(), password=password, kind="offline-manifest"))
                zf.writestr("README_OFFLINE.txt", _readme())
                zf.writestr("INSTALL_KHDN_OFFLINE.bat", _install_bat())
                zf.writestr("RUN_KHDN_OFFLINE.bat", _run_bat())
                zf.writestr("BACKUP_DATA_OFFLINE.bat", _backup_bat())
                zf.writestr("offline_backup.py", _backup_py())
                zf.writestr("backups/.keep", "")
        os.replace(tmp, target)
        return target
    finally:
        tmp.unlink(missing_ok=True)


def create_offline_export(data_dir, db_path, actor=None, backup_module=None, *, password: str) -> Path:
    folder = Path(data_dir).resolve() / "backups" / "offline"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = folder / f"KHDN-Ops-Offline-App-{stamp}-{__import__('secrets').token_hex(4)}.zip"
    result = create_offline_package(
        data_dir,
        db_path,
        target,
        actor=actor,
        backup_module=backup_module,
        password=password,
    )
    files = sorted(folder.glob("KHDN-Ops-Offline-App-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[5:]:
        old.unlink(missing_ok=True)
    return result


def _audit_export(app_ns, u, path: Path, logger=None):
    try:
        with app_ns["get_conn"]() as c:
            tables = {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "system_audit" not in tables:
                return
            c.execute(
                "INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
                (
                    int(u.get("id") or 0),
                    "OFFLINE_EXPORT_CREATE",
                    "application",
                    path.name,
                    json.dumps({"file": path.name, "size": path.stat().st_size}, ensure_ascii=False),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
    except Exception:
        if logger:
            logger.exception("OFFLINE_EXPORT_AUDIT_FAILED")


def install(backup_module, logger=None):
    if getattr(backup_module, _FLAG, None) == VERSION:
        return
    original = backup_module.render_backup_admin

    def render_backup_admin(st, u, app_ns, logger=logger):
        result = original(st, u, app_ns, logger)
        if not bool(u.get("is_admin")):
            return result
        if str(st.session_state.get("admin_scope") or "system") != "system":
            return result

        data_dir = Path(os.getenv("KHDN_DATA_DIR", str(app_ns.get("RUNTIME_DATA_DIR") or Path.cwd()))).resolve()
        db_path = Path(os.getenv("KHDN_DB_PATH", str(app_ns.get("DB_PATH") or data_dir / "khdn_ops.db"))).resolve()
        u = require_admin(db_path, u.get("id"))
        actor = str(u.get("full_name") or u.get("username") or f"UID {u.get('id')}")

        st.divider()
        st.markdown("## 💻 App Offline + dữ liệu hiện tại")
        st.caption(
            "Xuất một file ZIP gồm toàn bộ mã nguồn KHDN đang chạy, ảnh chụp CSDL hiện tại "
            "và bộ cài/chạy/backup local. Chỉ Admin có thể tạo gói này."
        )
        st.info(
            "Sau khi cài thư viện Python lần đầu, app offline đọc/ghi trực tiếp vào "
            "`data\\khdn_ops.db` và không phụ thuộc Railway."
        )

        password = backup_crypto.password_form(st, "offline_export", "📦 Tạo gói Offline có mật khẩu")
        if password is not None:
            try:
                require_admin(db_path, u["id"])
                path = create_offline_export(data_dir, db_path, actor, backup_module, password=password)
                st.session_state["khdn_offline_export_owner"] = int(u["id"])
                backup_crypto.reset_password_form(st, "offline_export")
                st.session_state["khdn_offline_export_path"] = str(path)
                _audit_export(app_ns, u, path, logger)
                if logger:
                    logger.info("OFFLINE_EXPORT_OK file=%s size=%s", path.name, path.stat().st_size)
                st.toast("Đã tạo gói App Offline + dữ liệu.", icon="✅")
                st.rerun()
            except Exception as exc:
                if logger:
                    logger.exception("OFFLINE_EXPORT_FAILED")
                st.error(f"Không tạo được gói offline: {exc}")

        candidate = st.session_state.get("khdn_offline_export_path")
        path = Path(candidate) if candidate else None
        if (path and path.exists() and path.resolve().is_relative_to(data_dir / "backups" / "offline")
                and st.session_state.get("khdn_offline_export_owner") == int(u["id"])
                and backup_crypto.encrypted_package(path)):
            require_admin(db_path, u["id"])
            st.download_button(
                "⬇️ Tải App Offline + dữ liệu về máy",
                data=path.read_bytes(),
                file_name=path.name,
                mime="application/zip",
                key="khdn_offline_export_download",
                use_container_width=True,
            )
            st.caption(
                f"Gói hiện tại: {path.name} · {backup_module._fmt_size(path.stat().st_size)} · "
                "có INSTALL_KHDN_OFFLINE.bat, RUN_KHDN_OFFLINE.bat và BACKUP_DATA_OFFLINE.bat."
            )
            st.warning("Gói chứa CSDL đầy đủ. Hãy lưu ở thiết bị/ổ đĩa an toàn và không gửi công khai.")
        return result

    backup_module.render_backup_admin = render_backup_admin
    setattr(backup_module, _FLAG, VERSION)
    if logger:
        logger.info("KHDN_OFFLINE_EXPORT_INSTALLED version=%s source=container data_snapshot=1 admin_only=1", VERSION)
