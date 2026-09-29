"""Complete KHDN Ops backup management.

The runtime already creates one consistent SQLite snapshot per day on the
persistent volume.  This patch makes that protection visible to administrators
and adds an on-demand portable package containing:
- a transaction-consistent SQLite database with every application table;
- a manifest with table/row inventory and SHA-256 checksum;
- readable CSV exports for every application table (secret/authentication
  columns are omitted from CSV only; they remain intact in the SQLite file).

No business data is logged.
"""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from khdn_apps.storage import read_status, snapshot_database

VERSION = "1.0.0"
_FLAG = "_KHDN_BACKUP_MANAGEMENT_VERSION"

_SECRET_CSV_COLUMNS = {
    "password_hash", "avatar_blob", "remember_token", "device_token",
    "push_subscription", "secret", "token", "private_key",
}


def _qident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        str(r[0]) for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]


def database_inventory(path: Path | str) -> dict:
    """Integrity-check a database and inventory every application table."""
    db = Path(path).resolve()
    uri = db.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30) as c:
        check = [str(r[0]) for r in c.execute("PRAGMA integrity_check").fetchall()]
        if check != ["ok"]:
            raise ValueError("SQLite integrity_check failed: " + "; ".join(check[:3]))
        counts = {}
        columns = {}
        for table in _tables(c):
            counts[table] = int(c.execute(f"SELECT COUNT(*) FROM {_qident(table)}").fetchone()[0])
            columns[table] = [str(r[1]) for r in c.execute(f"PRAGMA table_info({_qident(table)})").fetchall()]
    return {"integrity": "ok", "tables": counts, "columns": columns}


def _safe_csv_value(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"[BLOB {len(bytes(value))} bytes — retained in khdn_ops.db]"
    return "" if value is None else value


def create_full_backup_package(
    db_path: Path | str,
    target: Path | str,
    *,
    reason: str = "manual",
    actor: str | None = None,
) -> Path:
    """Create a self-verifying ZIP package with a full DB and readable exports."""
    db_path, target = Path(db_path).resolve(), Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    fd, tmp_name = tempfile.mkstemp(prefix=".khdn-backup-", suffix=".zip", dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with tempfile.TemporaryDirectory(prefix="khdn-snapshot-", dir=target.parent) as work:
            snap = snapshot_database(db_path, Path(work) / "khdn_ops.db")
            inventory = database_inventory(snap)
            with snap.open("rb") as stream:
                db_sha = hashlib.file_digest(stream, "sha256").hexdigest()

            manifest = {
                "product": "KHDN Ops",
                "backup_version": VERSION,
                "created_at": datetime.now().astimezone().isoformat(),
                "reason": str(reason or "manual"),
                "actor": str(actor or "") or None,
                "database_sha256": db_sha,
                "integrity": inventory["integrity"],
                "table_counts": inventory["tables"],
                "scope": "FULL_SQLITE_ALL_APPLICATION_TABLES",
                "notes": [
                    "khdn_ops.db is the authoritative full-fidelity backup.",
                    "CSV files are convenience exports for inspection.",
                    "Authentication/secret columns are intentionally omitted from CSV exports but remain in khdn_ops.db.",
                ],
            }

            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                zf.write(snap, "khdn_ops.db")
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                zf.writestr(
                    "README.txt",
                    "KHDN Ops - Full Backup\n"
                    "======================\n"
                    "khdn_ops.db contains the complete database snapshot, including customers, "
                    "customer contacts/phone numbers, work items, weekly plans, approvals, issues, "
                    "history, audit and configuration tables present at backup time.\n\n"
                    "manifest.json records integrity, SHA-256 and row counts.\n"
                    "tables/*.csv are readable convenience exports; secret/authentication columns "
                    "are kept only inside khdn_ops.db.\n",
                )

                uri = snap.resolve().as_uri() + "?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=30) as c:
                    c.row_factory = sqlite3.Row
                    for table in _tables(c):
                        cols = [str(r[1]) for r in c.execute(f"PRAGMA table_info({_qident(table)})").fetchall()]
                        export_cols = [
                            col for col in cols
                            if col.lower() not in _SECRET_CSV_COLUMNS
                            and not col.lower().endswith("_secret")
                            and not col.lower().endswith("_token")
                            and "password" not in col.lower()
                        ]
                        if not export_cols:
                            continue
                        query_cols = ",".join(_qident(col) for col in export_cols)
                        with zf.open(f"tables/{table}.csv", "w") as raw:
                            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="", write_through=True)
                            writer = csv.writer(text)
                            writer.writerow(export_cols)
                            for row in c.execute(f"SELECT {query_cols} FROM {_qident(table)}"):
                                writer.writerow([_safe_csv_value(v) for v in row])
                            text.flush()

        os.replace(tmp, target)
        return target
    finally:
        tmp.unlink(missing_ok=True)


def create_manual_backup(data_dir: Path | str, db_path: Path | str, actor: str | None = None) -> Path:
    folder = Path(data_dir).resolve() / "backups" / "manual"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    target = folder / f"KHDN-Ops-Full-Backup-{stamp}.zip"
    result = create_full_backup_package(db_path, target, reason="manual", actor=actor)
    files = sorted(folder.glob("KHDN-Ops-Full-Backup-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[20:]:
        old.unlink(missing_ok=True)
    return result


def _fmt_size(value) -> str:
    try:
        n = float(value or 0)
    except Exception:
        return "—"
    units = ["B", "KB", "MB", "GB"]
    idx = 0
    while n >= 1024 and idx < len(units) - 1:
        n /= 1024.0; idx += 1
    return f"{n:.1f} {units[idx]}" if idx else f"{int(n)} {units[idx]}"


def _render_inventory_table(st, counts: dict):
    rows = "".join(
        f"<tr><td>{str(name)}</td><td>{int(count)}</td></tr>"
        for name, count in sorted((counts or {}).items())
    ) or "<tr><td colspan='2'>Chưa có dữ liệu</td></tr>"
    st.html(
        "<div class='bk-table'><table><thead><tr><th>Bảng dữ liệu</th><th>Số dòng</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        "<style>.bk-table{overflow-x:auto;width:100%}.bk-table table{width:100%;table-layout:fixed;border-collapse:collapse}"
        ".bk-table th,.bk-table td{padding:7px 9px;border:1px solid rgba(120,160,150,.28);white-space:normal;overflow-wrap:anywhere}"
        ".bk-table th{font-weight:900;color:#63DCCB}.bk-table td:nth-child(2),.bk-table th:nth-child(2){width:18%;text-align:right}</style>"
    )


def render_backup_admin(st, u, app_ns, logger=None):
    if not bool(u.get("is_admin")):
        return
    if str(st.session_state.get("admin_scope") or "system") != "system":
        return

    data_dir = Path(os.getenv("KHDN_DATA_DIR", str(app_ns.get("RUNTIME_DATA_DIR") or Path.cwd()))).resolve()
    db_path = Path(os.getenv("KHDN_DB_PATH", str(app_ns.get("DB_PATH") or data_dir / "khdn_ops.db"))).resolve()
    status = read_status(data_dir / "backup_status.json")

    st.divider()
    st.markdown("## 💾 Sao lưu dữ liệu")
    st.caption(
        "Backup toàn bộ CSDL: khách hàng, CIF, số điện thoại/người liên hệ, công việc khách hàng, "
        "kế hoạch tuần, phê duyệt, dời hạn, vướng mắc, lịch sử, audit và cấu hình."
    )

    last = str(status.get("last_success") or "—")
    retained = status.get("retained") or []
    stored = int(status.get("stored_bytes") or 0)
    a,b,c,d = st.columns(4)
    a.metric("Backup tự động", "Hằng ngày")
    b.metric("Bản gần nhất", last[:19].replace("T", " ") if last != "—" else "—")
    c.metric("Đang lưu", f"{len(retained)} bản")
    d.metric("Dung lượng", _fmt_size(stored))

    if status.get("last_error"):
        st.error(f"Backup tự động gần nhất có lỗi: {status.get('last_error')}")
    else:
        st.success("Backup tự động đang sử dụng SQLite online-backup nên bao gồm cả giao dịch WAL đã commit và không cần dừng ứng dụng.")
    st.warning("Backup tự động lưu trên Railway persistent volume. Nên định kỳ dùng **Tải bản backup về máy** để có thêm một bản off-site độc lập.")

    try:
        inv = database_inventory(db_path)
        st.caption(f"Kiểm tra CSDL hiện tại: integrity_check = {inv['integrity']} · {len(inv['tables'])} bảng ứng dụng.")
        with st.expander("📋 Danh mục dữ liệu được bảo vệ", expanded=False):
            _render_inventory_table(st, inv["tables"])
    except Exception as exc:
        inv = {"tables": {}}
        st.error(f"Không thể kiểm tra tính toàn vẹn CSDL: {exc}")

    actor = str(u.get("full_name") or u.get("username") or f"UID {u.get('id')}")
    left, right = st.columns(2)
    if left.button("🛡️ Tạo bản backup đầy đủ ngay", key="khdn_manual_backup_create", type="primary", use_container_width=True):
        try:
            path = create_manual_backup(data_dir, db_path, actor)
            st.session_state["khdn_manual_backup_path"] = str(path)
            try:
                with app_ns["get_conn"]() as c:
                    if "system_audit" in {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
                        c.execute(
                            "INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
                            (int(u.get("id") or 0), "BACKUP_CREATE", "database", path.name,
                             json.dumps({"file": path.name, "size": path.stat().st_size}, ensure_ascii=False),
                             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        )
            except Exception:
                if logger: logger.exception("MANUAL_BACKUP_AUDIT_FAILED")
            if logger: logger.info("MANUAL_FULL_BACKUP_OK file=%s size=%s", path.name, path.stat().st_size)
            st.toast("Đã tạo bản backup đầy đủ.", icon="✅")
            st.rerun()
        except Exception as exc:
            if logger: logger.exception("MANUAL_FULL_BACKUP_FAILED")
            st.error(f"Không tạo được backup: {exc}")

    if right.button("🔎 Kiểm tra tính toàn vẹn", key="khdn_backup_verify", use_container_width=True):
        try:
            check = database_inventory(db_path)
            st.success(f"CSDL hợp lệ: integrity_check = ok · {len(check['tables'])} bảng.")
        except Exception as exc:
            st.error(f"Kiểm tra thất bại: {exc}")

    candidate = st.session_state.get("khdn_manual_backup_path")
    path = Path(candidate) if candidate else None
    if not path or not path.exists():
        manual_dir = data_dir / "backups" / "manual"
        files = sorted(manual_dir.glob("KHDN-Ops-Full-Backup-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if manual_dir.exists() else []
        path = files[0] if files else None
    if path and path.exists():
        st.download_button(
            "⬇️ Tải bản backup đầy đủ về máy",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/zip",
            key="khdn_manual_backup_download",
            use_container_width=True,
        )
        st.caption(f"Gói hiện tại: {path.name} · {_fmt_size(path.stat().st_size)}")


def install(app_ns, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return
    original = app_ns.get("admin_page")
    if not callable(original):
        if logger: logger.warning("BACKUP_MANAGEMENT_ADMIN_PAGE_NOT_FOUND")
        return
    st = app_ns["st"]

    def admin_page(u):
        result = original(u)
        try:
            render_backup_admin(st, u, app_ns, logger)
        except Exception:
            if logger: logger.exception("BACKUP_MANAGEMENT_RENDER_FAILED")
            st.error("Không thể hiển thị khu vực sao lưu. Vui lòng xem log quản trị.")
        return result

    app_ns["admin_page"] = admin_page
    app_ns[_FLAG] = VERSION
    if logger:
        logger.info("BACKUP_MANAGEMENT_INSTALLED version=%s auto_daily=1 manual_full_zip=1 inventory=1 integrity=1", VERSION)
