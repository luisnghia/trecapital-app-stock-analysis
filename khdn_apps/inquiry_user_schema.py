"""Lossless SQLite users-table CHECK migration to admit the read-only Vấn tin role.

The UI can offer a role while the existing users table still enforces the
original three-role CHECK. SQLite cannot ALTER a CHECK constraint in-place,
so rebuild only users in one IMMEDIATE transaction, keeping IDs, every column,
secondary indexes, triggers, AUTOINCREMENT high-water mark and foreign keys.

No other table is recreated; nothing is changed if the constraint is already
upgraded. On any error, the entire change is rolled back.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3

ROLE = "Vấn tin"
_OLD_CHECK = re.compile(
    r"CHECK\s*\(\s*role\s+IN\s*\(\s*'Cán bộ hỗ trợ'\s*,\s*'Cán bộ QLKH'\s*,\s*'Lãnh đạo phòng'\s*\)\s*\)",
    re.IGNORECASE,
)
_USERS_NAME = re.compile(
    r'^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:"users"|\x60users\x60|\[users\]|users)(?=\s|\()',
    re.IGNORECASE,
)
_TEMP = "__users_inquiry_role_upgrade_v1"


def _quoted(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _foreign_key_snapshot(conn):
    return set(tuple(row) for row in conn.execute("PRAGMA foreign_key_check"))


def ensure_inquiry_user_schema(db_path, logger=None) -> bool:
    """Idempotent, transactionally widen users.role CHECK; return True if upgraded."""
    path = Path(db_path).resolve()
    if not path.is_file():
        # init_db() always executes before this migration.
        raise RuntimeError("INQUIRY_USER_SCHEMA: Cơ sở dữ liệu chưa được khởi tạo.")

    con = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    try:
        con.execute("PRAGMA busy_timeout=30000")
        # FOREIGN_KEYS must be disabled BEFORE BEGIN, otherwise DROP of the
        # referenced table can cascade/change unrelated business records.
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
            if row is None or not row[0]:
                raise RuntimeError("INQUIRY_USER_SCHEMA: Không tìm thấy bảng users.")
            table_sql = str(row[0])

            if "'Vấn tin'" in table_sql:
                con.execute("COMMIT")
                return False

            if len(_OLD_CHECK.findall(table_sql)) != 1:
                raise RuntimeError("INQUIRY_USER_SCHEMA: CHECK(role) không khớp cấu trúc dự kiến.")
            if len(_USERS_NAME.findall(table_sql)) != 1:
                raise RuntimeError("INQUIRY_USER_SCHEMA: CREATE TABLE users không khớp cấu trúc dự kiến.")
            if con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (_TEMP,)).fetchone():
                raise RuntimeError("INQUIRY_USER_SCHEMA: Bảng trung gian đã tồn tại; ngừng để bảo vệ dữ liệu.")

            original_fks = _foreign_key_snapshot(con)
            original_rows = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            schema_objects = [
                (r[0], r[1], r[2])
                for r in con.execute(
                    """SELECT type,name,sql FROM sqlite_master
                       WHERE tbl_name='users' AND type IN ('index','trigger')
                         AND sql IS NOT NULL ORDER BY type,name"""
                )
            ]
            # Column additions from earlier migrations are retained because the
            # actual sqlite_master schema, not a hardcoded copy, is rebuilt.
            columns = [
                r[1] for r in con.execute("PRAGMA table_xinfo('users')") if r[6] == 0
            ]
            if not columns or "id" not in columns or "role" not in columns:
                raise RuntimeError("INQUIRY_USER_SCHEMA: Cột users không hợp lệ.")

            was_seq_table = con.execute(
                "SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence' AND type='table'"
            ).fetchone()
            seq = None
            if was_seq_table:
                previous = con.execute(
                    "SELECT seq FROM sqlite_sequence WHERE name='users'"
                ).fetchone()
                if previous:
                    seq = int(previous[0])

            widened_sql = _OLD_CHECK.sub(
                "CHECK(role IN ('Cán bộ hỗ trợ','Cán bộ QLKH','Lãnh đạo phòng','Vấn tin'))",
                table_sql,
                count=1,
            )
            replacement, n = _USERS_NAME.subn(
                'CREATE TABLE ' + _quoted(_TEMP), widened_sql, count=1
            )
            if n != 1:
                raise RuntimeError("INQUIRY_USER_SCHEMA: Không đổi được tên bảng trung gian.")

            con.execute(replacement)
            column_list = ",".join(_quoted(c) for c in columns)
            con.execute(
                f"INSERT INTO {_quoted(_TEMP)} ({column_list}) "
                f"SELECT {column_list} FROM users"
            )
            if con.execute(
                f"SELECT COUNT(*) FROM {_quoted(_TEMP)}"
            ).fetchone()[0] != original_rows:
                raise RuntimeError("INQUIRY_USER_SCHEMA: Số user đã thay đổi trong quá trình sao chép.")

            # Never rename the existing users table: doing so can rewrite
            # references on other tables. Replace it with FK checking disabled
            # inside the SAME transaction, then validate all references.
            con.execute("DROP TABLE users")
            con.execute(f"ALTER TABLE {_quoted(_TEMP)} RENAME TO users")
            for kind, name, sql in schema_objects:
                con.execute(sql)
            if seq is not None:
                current = con.execute(
                    "SELECT seq FROM sqlite_sequence WHERE name='users'"
                ).fetchone()
                highest = max(seq, int(current[0]) if current else 0)
                con.execute("DELETE FROM sqlite_sequence WHERE name='users'")
                con.execute(
                    "INSERT INTO sqlite_sequence(name,seq) VALUES('users',?)",
                    (highest,),
                )

            if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] != original_rows:
                raise RuntimeError("INQUIRY_USER_SCHEMA: Không khớp số lượng tài khoản sau nâng cấp.")
            new_fks = _foreign_key_snapshot(con)
            if new_fks != original_fks:
                raise RuntimeError("INQUIRY_USER_SCHEMA: Kiểm tra khóa ngoại không đạt.")
            new_schema = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()[0]
            if "'Vấn tin'" not in str(new_schema):
                raise RuntimeError("INQUIRY_USER_SCHEMA: Nhóm quyền Vấn tin chưa được ghi nhận.")

            con.execute("COMMIT")
            if logger:
                logger.info(
                    "INQUIRY_USER_SCHEMA_UPGRADED rows_preserved=%s secondary_objects=%s foreign_keys_preserved=1",
                    original_rows, len(schema_objects)
                )
            return True
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
    finally:
        con.close()
