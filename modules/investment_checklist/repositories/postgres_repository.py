from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re

import psycopg
from psycopg.rows import dict_row

from ..catalog.catalog import SCREENING_CRITERIA, load_questions
from ..db.postgres_schema import POSTGRES_SCHEMA_SQL
from .sqlite_repository import SQLiteChecklistRepository


_INSERT_ID_TABLES = {
    'research_reviews',
    'analyst_assessments',
    'screening_assessments',
    'opportunity_inventory_snapshots',
    'data_snapshots',
    'audit_logs',
    'integration_sync_log',
}


def _translate_sql(sql: str) -> str:
    out = sql.replace("datetime('now')", "CURRENT_TIMESTAMP::text")
    out = out.replace('?', '%s')
    return out


class _PgCursorProxy:
    def __init__(self, cursor, *, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class _PgConnectionProxy:
    """Small DB-API compatibility layer so Phase 1B repository logic can run on psycopg3.

    The production repository deliberately reuses the already-tested append-only/versioning
    business logic. This proxy only translates SQLite parameter markers and INSERT id handling;
    it does not alter domain rules.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=()):
        translated = _translate_sql(sql)
        table = None
        m = re.match(r"\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", translated, flags=re.I)
        if m:
            table = m.group(1).lower()
        wants_id = table in _INSERT_ID_TABLES and ' returning ' not in translated.lower()
        if wants_id:
            translated = translated.rstrip().rstrip(';') + ' RETURNING id'
        cur = self._conn.cursor()
        cur.execute(translated, params)
        lastrowid = None
        if wants_id:
            row = cur.fetchone()
            lastrowid = row['id'] if row else None
        return _PgCursorProxy(cur, lastrowid=lastrowid)


class PostgresChecklistRepository(SQLiteChecklistRepository):
    """PostgreSQL/Supabase-compatible durable persistence for Investment Checklist.

    All analyst assessment, screening, versioning, inventory and immutable snapshot domain
    behavior is inherited from the Phase 1B repository. Only connection/schema mechanics differ.
    """

    def __init__(self, database_url: str, question_catalog_path: str | Path):
        if not str(database_url or '').strip():
            raise ValueError('database_url is required for PostgresChecklistRepository')
        self.database_url = str(database_url).strip()
        self.question_catalog_path = Path(question_catalog_path)

    @contextmanager
    def _conn(self):
        conn = psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            autocommit=False,
            prepare_threshold=None,  # compatible with Supabase/PgBouncer transaction pooling
        )
        proxy = _PgConnectionProxy(conn)
        try:
            yield proxy
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        conn = psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            autocommit=False,
            prepare_threshold=None,
        )
        try:
            with conn.cursor() as cur:
                for statement in [x.strip() for x in POSTGRES_SCHEMA_SQL.split(';') if x.strip()]:
                    cur.execute(statement)
                for q in load_questions(self.question_catalog_path):
                    cur.execute(
                        """INSERT INTO checklist_questions(question_id,question_no,group_name,question_vi,guidance,research_mode,supporting_tool)
                        VALUES(%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(question_id) DO UPDATE SET question_no=excluded.question_no,group_name=excluded.group_name,
                        question_vi=excluded.question_vi,guidance=excluded.guidance,research_mode=excluded.research_mode,supporting_tool=excluded.supporting_tool""",
                        (q['question_id'], q['question_no'], q['group_name'], q['question_vi'], q['guidance'], q['research_mode'], q['supporting_tool']),
                    )
                for i, (code, en, vi) in enumerate(SCREENING_CRITERIA, 1):
                    cur.execute(
                        """INSERT INTO screening_criteria(criterion_code,criterion_name_en,criterion_name_vi,display_order)
                        VALUES(%s,%s,%s,%s)
                        ON CONFLICT(criterion_code) DO UPDATE SET criterion_name_en=excluded.criterion_name_en,
                        criterion_name_vi=excluded.criterion_name_vi,display_order=excluded.display_order""",
                        (code, en, vi, i),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
