"""Append-only storage for standalone Fisher Top-Down macro snapshots."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _payload_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class TopDownMacroSnapshotStore:
    """Small standalone repository with no company/review foreign key or mutation API."""

    def __init__(self, database: str | Path):
        raw = str(database)
        self.is_postgres = raw.startswith(("postgresql://", "postgres://"))
        self.database = raw
        if not self.is_postgres:
            if raw.startswith("sqlite:///"):
                raw = raw.removeprefix("sqlite:///")
            self.sqlite_path = Path(raw)
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            conn = psycopg.connect(
                self.database,
                row_factory=dict_row,
                autocommit=False,
                prepare_threshold=None,
                connect_timeout=10,
            )
        else:
            conn = sqlite3.connect(self.sqlite_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connection() as conn:
            if self.is_postgres:
                with conn.cursor() as cur:
                    cur.execute(
                        """CREATE TABLE IF NOT EXISTS topdown_macro_snapshots (
                            id BIGSERIAL PRIMARY KEY,
                            version_no INTEGER NOT NULL UNIQUE CHECK(version_no > 0),
                            as_of_date DATE NOT NULL,
                            snapshot_label TEXT NOT NULL CHECK(length(trim(snapshot_label)) > 0),
                            methodology_version TEXT NOT NULL,
                            source_registry_hash TEXT,
                            payload_json JSONB NOT NULL,
                            payload_hash TEXT NOT NULL UNIQUE,
                            save_reason TEXT NOT NULL CHECK(length(trim(save_reason)) > 0),
                            created_by TEXT NOT NULL CHECK(length(trim(created_by)) > 0),
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )"""
                    )
                    cur.execute(
                        """CREATE INDEX IF NOT EXISTS ix_topdown_macro_snapshots_asof
                        ON topdown_macro_snapshots(as_of_date DESC, version_no DESC)"""
                    )
                    cur.execute(
                        """CREATE OR REPLACE FUNCTION prevent_topdown_macro_snapshot_mutation()
                        RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                            RAISE EXCEPTION 'topdown_macro_snapshots is append-only';
                        END;
                        $$"""
                    )
                    cur.execute(
                        """DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_trigger
                                WHERE tgname='no_mutation_topdown_macro_snapshots'
                                  AND tgrelid='topdown_macro_snapshots'::regclass
                            ) THEN
                                CREATE TRIGGER no_mutation_topdown_macro_snapshots
                                BEFORE UPDATE OR DELETE ON topdown_macro_snapshots
                                FOR EACH ROW EXECUTE FUNCTION prevent_topdown_macro_snapshot_mutation();
                            END IF;
                        END $$"""
                    )
                    cur.execute("ALTER TABLE topdown_macro_snapshots ENABLE ROW LEVEL SECURITY")
                    for role in ("anon", "authenticated"):
                        cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                        if cur.fetchone():
                            cur.execute(f"REVOKE ALL ON TABLE topdown_macro_snapshots FROM {role}")
                            cur.execute(
                                f"REVOKE ALL ON SEQUENCE topdown_macro_snapshots_id_seq FROM {role}"
                            )
            else:
                conn.executescript(
                    """CREATE TABLE IF NOT EXISTS topdown_macro_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_no INTEGER NOT NULL UNIQUE CHECK(version_no > 0),
                        as_of_date TEXT NOT NULL,
                        snapshot_label TEXT NOT NULL CHECK(length(trim(snapshot_label)) > 0),
                        methodology_version TEXT NOT NULL,
                        source_registry_hash TEXT,
                        payload_json TEXT NOT NULL,
                        payload_hash TEXT NOT NULL UNIQUE,
                        save_reason TEXT NOT NULL CHECK(length(trim(save_reason)) > 0),
                        created_by TEXT NOT NULL CHECK(length(trim(created_by)) > 0),
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS ix_topdown_macro_snapshots_asof
                    ON topdown_macro_snapshots(as_of_date DESC, version_no DESC);
                    CREATE TRIGGER IF NOT EXISTS no_update_topdown_macro_snapshots
                    BEFORE UPDATE ON topdown_macro_snapshots
                    BEGIN SELECT RAISE(ABORT, 'topdown_macro_snapshots is append-only'); END;
                    CREATE TRIGGER IF NOT EXISTS no_delete_topdown_macro_snapshots
                    BEFORE DELETE ON topdown_macro_snapshots
                    BEGIN SELECT RAISE(ABORT, 'topdown_macro_snapshots is append-only'); END;
                    """
                )

    def save(
        self,
        payload: dict[str, Any],
        *,
        as_of_date: date | str,
        snapshot_label: str,
        save_reason: str,
        created_by: str,
        methodology_version: str,
        source_registry_hash: str | None = None,
    ) -> dict[str, Any]:
        label = str(snapshot_label or "").strip()
        reason = str(save_reason or "").strip()
        actor = str(created_by or "").strip()
        if not label or not reason or not actor:
            raise ValueError("Tên snapshot, lý do lưu và người thực hiện đều là bắt buộc.")
        payload_text = _canonical_json(payload)
        digest = _payload_hash(payload)
        asof = as_of_date.isoformat() if isinstance(as_of_date, date) else str(as_of_date)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connection() as conn:
            if self.is_postgres:
                with conn.cursor() as cur:
                    cur.execute("LOCK TABLE topdown_macro_snapshots IN SHARE ROW EXCLUSIVE MODE")
                    cur.execute("SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version FROM topdown_macro_snapshots")
                    version = int(cur.fetchone()["next_version"])
                    cur.execute(
                        """INSERT INTO topdown_macro_snapshots(
                            version_no,as_of_date,snapshot_label,methodology_version,
                            source_registry_hash,payload_json,payload_hash,save_reason,created_by
                        ) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) RETURNING *""",
                        (
                            version, asof, label, methodology_version, source_registry_hash,
                            payload_text, digest, reason, actor,
                        ),
                    )
                    row = dict(cur.fetchone())
            else:
                conn.execute("BEGIN IMMEDIATE")
                version = int(
                    conn.execute("SELECT COALESCE(MAX(version_no), 0) + 1 FROM topdown_macro_snapshots").fetchone()[0]
                )
                cur = conn.execute(
                    """INSERT INTO topdown_macro_snapshots(
                        version_no,as_of_date,snapshot_label,methodology_version,
                        source_registry_hash,payload_json,payload_hash,save_reason,created_by,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        version, asof, label, methodology_version, source_registry_hash,
                        payload_text, digest, reason, actor, created_at,
                    ),
                )
                row = dict(conn.execute("SELECT * FROM topdown_macro_snapshots WHERE id=?", (cur.lastrowid,)).fetchone())
        return self._decode(row)

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        payload = out.pop("payload_json")
        out["payload"] = json.loads(payload) if isinstance(payload, str) else payload
        for key in ("as_of_date", "created_at"):
            if key in out and not isinstance(out[key], str):
                out[key] = out[key].isoformat()
        return out

    def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with self._connection() as conn:
            if self.is_postgres:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT * FROM topdown_macro_snapshots
                        ORDER BY version_no DESC LIMIT %s""",
                        (safe_limit,),
                    )
                    rows = [dict(row) for row in cur.fetchall()]
            else:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        """SELECT * FROM topdown_macro_snapshots
                        ORDER BY version_no DESC LIMIT ?""",
                        (safe_limit,),
                    )
                ]
        return [self._decode(row) for row in rows]


def compare_snapshots(newer: dict[str, Any], older: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return driver and sector deltas between two decoded snapshot rows/payloads."""
    new_payload = newer.get("payload", newer)
    old_payload = older.get("payload", older)
    new_drivers = dict(new_payload.get("parameters", {}).get("driver_outlook", {}))
    old_drivers = dict(old_payload.get("parameters", {}).get("driver_outlook", {}))
    driver_rows = []
    for driver_id in sorted(set(new_drivers) | set(old_drivers)):
        old_value = old_drivers.get(driver_id)
        new_value = new_drivers.get(driver_id)
        if old_value != new_value:
            driver_rows.append(
                {
                    "Driver ID": driver_id,
                    "Điểm cũ": old_value,
                    "Điểm mới": new_value,
                    "Thay đổi": None if old_value is None or new_value is None else float(new_value) - float(old_value),
                }
            )

    def ranking_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(row.get("sector_code")): row for row in payload.get("ranking", [])}

    new_ranking = ranking_map(new_payload)
    old_ranking = ranking_map(old_payload)
    sector_rows = []
    for code in sorted(set(new_ranking) | set(old_ranking)):
        old_row, new_row = old_ranking.get(code, {}), new_ranking.get(code, {})
        old_rank, new_rank = old_row.get("rank"), new_row.get("rank")
        old_score, new_score = old_row.get("score"), new_row.get("score")
        if old_rank != new_rank or old_score != new_score:
            sector_rows.append(
                {
                    "Mã ngành": code,
                    "Ngành": new_row.get("sector_name") or old_row.get("sector_name") or "",
                    "Hạng cũ": old_rank,
                    "Hạng mới": new_rank,
                    "Điểm cũ": old_score,
                    "Điểm mới": new_score,
                    "Δ điểm": None if old_score is None or new_score is None else float(new_score) - float(old_score),
                }
            )
    return {"drivers": driver_rows, "sectors": sector_rows}


__all__ = ["TopDownMacroSnapshotStore", "compare_snapshots"]
