"""Authenticated encryption for portable and automatic backups (no stored passwords)."""
from __future__ import annotations

import base64
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import struct
import tempfile
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"KHDNENC1\n"


def validate_password(password):
    if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
        raise ValueError("Mật khẩu bảo vệ file phải có từ 12 đến 1024 ký tự.")
    return password


def _password_key(password, salt):
    return hashlib.scrypt(validate_password(password).encode("utf-8"), salt=salt,
                          n=131072, r=8, p=1, maxmem=256 * 1024 * 1024, dklen=32)


def encrypt(data: bytes, *, password=None, key=None, kind="backup") -> bytes:
    if (password is None) == (key is None):
        raise ValueError("Exactly one encryption credential is required")
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    mode = "scrypt-131072-8-1" if password is not None else "server-key"
    encryption_key = _password_key(password, salt) if password is not None else key
    if len(encryption_key) != 32:
        raise ValueError("Encryption key must contain 32 bytes")
    header = json.dumps({"version": 1, "mode": mode, "kind": kind,
                         "salt": salt.hex(), "nonce": nonce.hex()}, separators=(",", ":")).encode()
    aad = MAGIC + struct.pack(">I", len(header)) + header
    return aad + AESGCM(encryption_key).encrypt(nonce, data, aad)


def decrypt(data: bytes, *, password=None, key=None, kind=None) -> bytes:
    if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 4:
        raise ValueError("Đây không phải file mã hóa KHDN được hỗ trợ.")
    offset = len(MAGIC)
    length = struct.unpack(">I", data[offset:offset + 4])[0]
    if not 0 < length <= 1024 or len(data) < offset + 4 + length + 16:
        raise ValueError("File mã hóa không hợp lệ.")
    boundary = offset + 4 + length
    header = json.loads(data[offset + 4:boundary])
    if header.get("version") != 1 or (kind is not None and header.get("kind") != kind):
        raise ValueError("Loại file mã hóa không hợp lệ.")
    salt, nonce = bytes.fromhex(header["salt"]), bytes.fromhex(header["nonce"])
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError("File mã hóa không hợp lệ.")
    if header.get("mode") == "scrypt-131072-8-1" and password is not None and key is None:
        encryption_key = _password_key(password, salt)
    elif header.get("mode") == "server-key" and key is not None and password is None and len(key) == 32:
        encryption_key = key
    else:
        raise ValueError("Cần đúng mật khẩu hoặc khóa khôi phục của file này.")
    return AESGCM(encryption_key).decrypt(nonce, data[boundary:], data[:boundary])


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".encrypted-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def server_key(data_dir):
    encoded = os.getenv("KHDN_BACKUP_ENCRYPTION_KEY", "")
    if encoded:
        try:
            key = base64.b64decode(encoded, validate=True)
            if len(key) == 32:
                return key
        except ValueError:
            pass
        raise RuntimeError("KHDN_BACKUP_ENCRYPTION_KEY must be base64 of 32 random bytes")
    if os.getenv("KHDN_CLOUD_MODE", "0").lower() in {"1", "true", "yes"}:
        raise RuntimeError("Configure KHDN_BACKUP_ENCRYPTION_KEY before starting cloud backups")
    path = Path(data_dir) / ".backup-encryption.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        key = path.read_bytes()
    else:
        key = secrets.token_bytes(32)
        with os.fdopen(fd, "wb") as stream:
            stream.write(key); stream.flush(); os.fsync(stream.fileno())
    if len(key) != 32:
        raise RuntimeError("Local backup recovery key is invalid")
    return key


def migrate_legacy_backups(data_dir, db_path=None):
    """Retain old snapshots, encrypt and verify before removing their plaintext."""
    key = server_key(data_dir)
    count = 0
    files = list((Path(data_dir) / "backups").rglob("*"))
    files += list((Path(data_dir) / "annual_archive").rglob("*.db"))
    for path in sorted(files):
        if not path.is_file() or path.suffix not in {".gz", ".zip", ".db"}:
            continue
        if path.suffix == ".zip" and encrypted_package(path):
            continue
        target = path.with_name(path.name + ".khdn")
        data = path.read_bytes()
        if target.exists():
            sealed = target.read_bytes()
        else:
            sealed = encrypt(data, key=key, kind="legacy-backup")
            atomic_bytes(target, sealed)
        if decrypt(sealed, key=key, kind="legacy-backup") != data:
            raise RuntimeError("Legacy backup verification failed; plaintext retained")
        if db_path and path.parent == Path(data_dir) / "annual_archive":
            with sqlite3.connect(db_path) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "annual_archives" in tables:
                    conn.execute("UPDATE annual_archives SET db_backup_file=? WHERE db_backup_file=?",
                                 (target.name, path.name))
        path.unlink()
        count += 1
    if count:
        from khdn_apps.storage import read_status, atomic_json
        status_path = Path(data_dir) / "backup_status.json"
        status = read_status(status_path)
        if status:
            status["encryption"] = "AES-256-GCM"
            status["file"] = str(status.get("file") or "").removesuffix(".khdn") + ".khdn"
            status["retained"] = [p.name for p in sorted((Path(data_dir) / "backups").glob("khdn_ops_????-??-??.db.gz.khdn"), reverse=True)]
            status["stored_bytes"] = sum((Path(data_dir) / "backups" / name).stat().st_size for name in status["retained"])
            if (Path(data_dir) / "backups" / status["file"]).exists():
                status["sha256"] = hashlib.sha256((Path(data_dir) / "backups" / status["file"]).read_bytes()).hexdigest()
            atomic_json(status_path, status)
    return count


def encrypted_snapshot(source, target, data_dir):
    from khdn_apps.storage import snapshot_database
    target = Path(target).with_suffix(".db.khdn")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".yearly-", dir=target.parent) as work:
        snapshot = snapshot_database(source, Path(work) / "database.db")
        atomic_bytes(target, encrypt(snapshot.read_bytes(), key=server_key(data_dir), kind="yearly-backup"))
    return target


def encrypted_package(path, member="backup.khdn"):
    try:
        with zipfile.ZipFile(path) as archive:
            if member not in archive.namelist():
                # Offline archive has a different encrypted member.
                member = "data/khdn_ops.db.khdn"
            with archive.open(member) as stream:
                return stream.read(len(MAGIC)) == MAGIC
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def password_form(st, key, label):
    from khdn_apps.legacy_fast_form import legacy_fast_form
    epoch = str(st.session_state.get("_backup_password_epoch_" + key, 0))
    payload = legacy_fast_form([
        {"name": "password", "label": "Mật khẩu bảo vệ file", "type": "password", "required": True},
        {"name": "confirm", "label": "Nhập lại mật khẩu bảo vệ file", "type": "password", "required": True},
    ], label, key="encrypted_" + key + "_" + epoch, reset_token=epoch,
       help_text="Đặt mật khẩu riêng từ 12 ký tự. Bạn cần mật khẩu này để khôi phục backup hoặc mở dữ liệu offline; app không lưu mật khẩu.")
    if payload is None:
        return None
    try:
        password = validate_password(payload.get("password"))
        if password != payload.get("confirm"):
            raise ValueError("Hai lần nhập mật khẩu bảo vệ không khớp.")
        return password
    except ValueError as exc:
        st.error(str(exc))
        return None


def reset_password_form(st, key):
    name = "_backup_password_epoch_" + key
    old = str(st.session_state.get(name, 0))
    st.session_state[name] = int(old) + 1
    # Release the previous component's submitted password from the server session.
    st.session_state.pop("encrypted_" + key + "_" + old, None)


def unlock_offline(root, password=None):
    root = Path(root).resolve()
    database = root / "data" / "khdn_ops.db"
    if database.exists():
        return database
    sealed = root / "data" / "khdn_ops.db.khdn"
    if not sealed.exists():
        raise FileNotFoundError("Không tìm thấy dữ liệu offline đã mã hóa.")
    password = password if password is not None else getpass.getpass("Mat khau bao ve goi offline: ")
    data = decrypt(sealed.read_bytes(), password=password, kind="offline-database")
    # Check the entire decrypted database before installing it for first use.
    with tempfile.TemporaryDirectory(prefix=".unlock-", dir=root / "data") as work:
        temporary = Path(work) / "database.db"
        temporary.write_bytes(data)
        with sqlite3.connect(temporary.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Dữ liệu offline không hợp lệ.")
        os.link(temporary, database)  # Never overwrite an existing working database.
    return database


def restore_portable(path, destination, password=None):
    path, destination = Path(path), Path(destination).resolve()
    password = password if password is not None else getpass.getpass("Mat khau bao ve backup: ")
    if path.suffix == ".khdn":
        sealed = path.read_bytes()
    else:
        with zipfile.ZipFile(path) as outer:
            sealed = outer.read("backup.khdn")
    payload = decrypt(sealed, password=password, kind="portable-backup")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination) or member.file_size > 512 * 1024 * 1024:
                raise ValueError("Backup chứa đường dẫn hoặc kích thước không hợp lệ.")
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Chọn một thư mục khôi phục trống để giữ dữ liệu hiện tại.")
        destination.mkdir(parents=True, exist_ok=True)
        archive.extractall(destination)
    return destination


def main():
    import sys
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "unlock-offline":
            unlock_offline(sys.argv[2])
        elif len(sys.argv) == 4 and sys.argv[1] == "restore":
            restore_portable(sys.argv[2], sys.argv[3])
        else:
            raise ValueError("Usage: backup_crypto.py restore backup.zip empty-folder")
    except Exception:
        print("Khong mo duoc du lieu. Kiem tra mat khau, file va thu muc dich.")
        raise SystemExit(1)
    print("KHDN_DECRYPT_OK")


if __name__ == "__main__":
    main()
