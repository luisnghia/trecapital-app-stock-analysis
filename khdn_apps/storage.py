"""Persistent paths, consistent SQLite snapshots, and one-time migration.

This module uses only the standard library and never logs database row values.
"""
from __future__ import annotations

import base64
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import uuid


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_status(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_volume_mount(path: Path) -> bool:
    path = path.resolve()
    if os.path.ismount(path):
        return True
    try:
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            mount = line.split()[4]
            for encoded, decoded in [("\\040", " "), ("\\011", "\t"), ("\\134", "\\")]:
                mount = mount.replace(encoded, decoded)
            if Path(mount) == path:
                return True
    except (OSError, IndexError):
        pass
    return False


def _open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)


def validate_database(path: Path) -> dict:
    with closing(_open_readonly(path)) as conn:
        check = conn.execute("PRAGMA integrity_check").fetchall()
        if check != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                for name in ("users", "customers", "tasks") if name in tables}


def snapshot_database(source: Path | str, target: Path | str) -> Path:
    """Include committed WAL transactions using SQLite's online backup API."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError("Snapshot destination must differ from the live database")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".sqlite-", suffix=".db", dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    started = time.monotonic()

    def progress(status, remaining, total):
        if time.monotonic() - started > 60:
            raise TimeoutError("SQLite snapshot exceeded 60 seconds")

    try:
        with closing(_open_readonly(source)) as original, closing(sqlite3.connect(temporary)) as copy:
            original.backup(copy, pages=256, progress=progress, sleep=0.05)
            copy.execute("PRAGMA journal_mode=DELETE")
            copy.commit()
        validate_database(temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + "-wal").unlink(missing_ok=True)
        Path(str(temporary) + "-shm").unlink(missing_ok=True)


def sqlite_backup_bytes(source: Path | str) -> bytes:
    if not Path(source).exists():
        return b""
    with tempfile.TemporaryDirectory(prefix="khdn-download-") as directory:
        target = snapshot_database(source, Path(directory) / "khdn_ops.db")
        return target.read_bytes()


def restore_once(data_dir: Path, db_path: Path, payload: str, expected_sha256: str) -> bool:
    """Restore a verified, private migration payload before starting the app.

    Never replace a database already in use. A receipt makes restart safe after
    a successful restore even before the temporary migration variable is cleared.
    """
    if not payload:
        return False
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("A SHA-256 digest is required for migration")
    receipt_path = data_dir / "migration_receipt.json"
    receipt = read_status(receipt_path)
    if db_path.exists():
        if receipt.get("sha256") == expected_sha256:
            return False
        # Recover a crash between installing the DB and writing its receipt.
        with db_path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest == expected_sha256:
            counts = validate_database(db_path)
            atomic_json(receipt_path, {"sha256": digest, "counts": counts})
            return False
        raise RuntimeError("Refusing to replace an existing database during migration")
    compressed = base64.b64decode(payload, validate=True)
    if len(compressed) > 20 * 1024 * 1024:
        raise ValueError("Migration payload exceeds 20 MiB")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".migration-", suffix=".db", dir=db_path.parent)
    temporary = Path(name)
    try:
        from io import BytesIO
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "wb") as destination, gzip.GzipFile(fileobj=BytesIO(compressed)) as source:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > 250 * 1024 * 1024:
                    raise ValueError("Expanded migration database exceeds 250 MiB")
                destination.write(chunk)
                digest.update(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if digest.hexdigest() != expected_sha256:
            raise ValueError("Migration checksum mismatch")
        counts = validate_database(temporary)
        if not {"users", "customers", "tasks"}.issubset(counts):
            raise ValueError("The backup is not a KHDN Ops database")
        # Atomic create that fails if another process has installed a database.
        os.link(temporary, db_path)
        atomic_json(receipt_path, {"sha256": expected_sha256, "counts": counts,
                                  "restored_at": datetime.now(timezone.utc).isoformat()})
        return True
    finally:
        temporary.unlink(missing_ok=True)


def prepare_storage(data_dir: Path, db_path: Path, require_volume: bool = True) -> dict:
    data_dir, db_path = data_dir.resolve(), db_path.resolve()
    if require_volume and not is_volume_mount(data_dir):
        raise RuntimeError(f"Persistent volume is not mounted at {data_dir}; refusing ephemeral storage")
    if not db_path.is_relative_to(data_dir):
        raise RuntimeError("KHDN_DB_PATH must be inside KHDN_DATA_DIR")
    for path in (data_dir, db_path.parent, data_dir / "logs", data_dir / "annual_archive", data_dir / "backups"):
        path.mkdir(parents=True, exist_ok=True)
    identity_path = data_dir / "storage_identity.json"
    identity = read_status(identity_path)
    if not identity.get("id"):
        identity = {"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()}
        atomic_json(identity_path, identity)
    restore_once(data_dir, db_path, os.getenv("KHDN_MIGRATION_DB_GZIP_BASE64", ""),
                 os.getenv("KHDN_MIGRATION_DB_SHA256", ""))
    # Create and fsync a small disposable file to verify write permission.
    fd, probe = tempfile.mkstemp(prefix=".write-check-", dir=data_dir)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(b"ok")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        Path(probe).unlink(missing_ok=True)
    status = {"storage_id": identity["id"], "data_dir": str(data_dir), "db_path": str(db_path),
              "volume_mounted": is_volume_mount(data_dir),
              "started_at": datetime.now(timezone.utc).isoformat(),
              "counts_at_start": validate_database(db_path) if db_path.exists() else {}}
    atomic_json(data_dir / "storage_status.json", status)
    return status


def daily_backup(data_dir: Path, db_path: Path, *, now: datetime | None = None,
                 keep: int = 14, budget_bytes: int = 50 * 1024 * 1024) -> Path | None:
    """Keep daily compressed DB snapshots on the volume (not off-site backups)."""
    if not db_path.exists():
        return None
    now = now or datetime.now(timezone.utc)
    folder = data_dir / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"khdn_ops_{now:%Y-%m-%d}.db.gz"
    if target.exists():
        return target
    wal = Path(str(db_path) + "-wal")
    estimated = db_path.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
    if shutil.disk_usage(folder).free < estimated * 2 + 8 * 1024 * 1024:
        raise OSError("Insufficient free space to safely create a database backup")
    fd, compressed_name = tempfile.mkstemp(prefix=".backup-", suffix=".gz", dir=folder)
    os.close(fd)
    compressed = Path(compressed_name)
    try:
        with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=folder) as directory:
            snapshot = snapshot_database(db_path, Path(directory) / "snapshot.db")
            counts = validate_database(snapshot)
            with snapshot.open("rb") as source, gzip.open(compressed, "wb", compresslevel=6) as destination:
                shutil.copyfileobj(source, destination)
        with compressed.open("rb") as stream:
            os.fsync(stream.fileno())
        if compressed.stat().st_size > budget_bytes:
            raise OSError("Compressed backup exceeds its storage budget; existing backups are retained")
        os.replace(compressed, target)
        backups = sorted(folder.glob("khdn_ops_????-??-??.db.gz"), reverse=True)
        total = 0
        retained = []
        for index, file in enumerate(backups):
            size = file.stat().st_size
            if index > 0 and (index >= max(1, keep) or total + size > budget_bytes):
                file.unlink()
            else:
                retained.append(file.name)
                total += size
        with target.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        atomic_json(data_dir / "backup_status.json", {
            "last_success": now.isoformat(), "file": target.name, "sha256": digest,
            "counts": counts, "retained": retained, "stored_bytes": total,
            "location": "same_volume", "last_error": None,
        })
        return target
    finally:
        compressed.unlink(missing_ok=True)
