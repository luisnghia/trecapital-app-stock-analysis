from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..catalog.catalog import SCREENING_CRITERIA, load_questions
from ..db.postgres_schema import POSTGRES_SCHEMA_SQL
from .sqlite_repository import SQLiteChecklistRepository


_INSERT_ID_TABLES = {
    'research_reviews',
    'analyst_assessments',
    'research_sources',
    'research_source_contents',
    'research_evidence',
    'evidence_question_links',
    'ai_research_runs',
    'ai_research_suggestions',
    'ai_suggestion_decisions',
    'management_people_versions',
    'management_timeline_events',
    'management_track_records',
    'management_question_signals',
    'monitoring_rules',
    'monitoring_observations',
    'delta_review_items',
    'delta_review_decisions',
    'investment_memo_versions',
    'investment_thesis_pillars',
    'investment_risk_register',
    'investment_decisions',
    'decision_outcome_reviews',
    'topdown_sector_snapshots',
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
    """DB-API compatibility layer so the tested Phase 1B domain logic runs on psycopg3."""

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
    """PostgreSQL/Supabase durable persistence with a small reusable connection pool.

    Phase 1B business rules remain inherited unchanged. Phase 1C only changes persistence
    mechanics. A pool is critical on Streamlit/Supabase: opening a new TLS/PgBouncer
    connection for every repository read made Q01–Q59 navigation unnecessarily slow.
    """

    def __init__(self, database_url: str, question_catalog_path: str | Path):
        if not str(database_url or '').strip():
            raise ValueError('database_url is required for PostgresChecklistRepository')
        self.database_url = str(database_url).strip()
        self.question_catalog_path = Path(question_catalog_path)
        self._pool = ConnectionPool(
            conninfo=self.database_url,
            min_size=1,
            max_size=4,
            timeout=10,
            kwargs={
                'row_factory': dict_row,
                'autocommit': False,
                # Required for Supabase/PgBouncer transaction pooling compatibility.
                'prepare_threshold': None,
            },
            open=True,
        )
        # Fail fast on the first app load instead of surfacing a connection error later.
        self._pool.wait(timeout=10)

    @contextmanager
    def _conn(self):
        # pool.connection() reuses an existing connection and safely returns it to the pool.
        # This removes repeated DNS/TLS/PgBouncer handshakes from every question change.
        with self._pool.connection() as conn:
            proxy = _PgConnectionProxy(conn)
            try:
                yield proxy
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _runtime_schema_ready(self) -> tuple[bool, bool]:
        """Check the migration checkpoint and its required seed catalogs.

        Production schema changes are applied by migrations. Replaying every CREATE/ALTER plus 69
        catalog UPSERTs on each Streamlit worker cold-start added hundreds of protocol round-trips.
        Presence of the latest append-only Phase 7 tables is the runtime compatibility checkpoint.
        The two lookup catalogs must also be populated: a fresh/migrated database can already have
        every table while still needing the 59 questions and 10 screening criteria.  A genuinely
        old, empty, or partially seeded database falls through to the full idempotent initializer.
        """
        core_tables = (
            'checklist_company_refs', 'checklist_questions', 'screening_criteria',
            'research_reviews', 'research_source_contents', 'monitoring_rules',
            'investment_decisions', 'decision_outcome_reviews',
            'topdown_sector_snapshots',
        )
        extension_tables = ('checklist_watchlist', 'analyst_table_overrides')
        names = core_tables + extension_tables
        placeholders = ','.join(['%s'] * len(names))
        seed_ready = False
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT table_name FROM information_schema.tables
                    WHERE table_schema=current_schema() AND table_name IN ({placeholders})""",
                    names,
                )
                present = {row['table_name'] for row in cur.fetchall()}
                if set(core_tables).issubset(present):
                    cur.execute(
                        """SELECT
                        (SELECT COUNT(*) FROM checklist_questions WHERE active=1) AS question_count,
                        (SELECT COUNT(*) FROM screening_criteria) AS screening_count"""
                    )
                    counts = cur.fetchone()
                    seed_ready = (
                        int(counts['question_count']) == len(load_questions(self.question_catalog_path))
                        and int(counts['screening_count']) == len(SCREENING_CRITERIA)
                    )
        core_ready = set(core_tables).issubset(present) and seed_ready
        return core_ready, set(extension_tables).issubset(present)

    def initialize(self):
        core_ready, extension_ready = self._runtime_schema_ready()
        if core_ready:
            # The extension wrapper can skip its own CREATE TABLE probes as well.
            if extension_ready:
                self._portfolio_extension_schema_ready = True
            return
        with self._pool.connection() as conn:
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
                    # Phase 4A/4B tables are internal research workflow state. The app uses a
                    # trusted direct Postgres connection; they are not part of the Data API.
                    for table in (
                        'research_sources', 'research_source_contents', 'research_evidence', 'evidence_question_links',
                        'ai_research_runs', 'ai_research_suggestions', 'ai_suggestion_decisions',
                        'management_people_versions', 'management_timeline_events',
                        'management_track_records', 'management_question_signals',
                        'monitoring_rules', 'monitoring_observations',
                        'delta_review_items', 'delta_review_decisions',
                        'investment_memo_versions', 'investment_thesis_pillars',
                        'investment_risk_register', 'investment_decisions',
                        'decision_outcome_reviews',
                        'topdown_sector_snapshots',
                    ):
                        cur.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
                        for role in ('anon', 'authenticated'):
                            cur.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                            if cur.fetchone():
                                cur.execute(f'REVOKE ALL ON TABLE {table} FROM {role}')
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close(self) -> None:
        """Explicit shutdown hook for tests/tools. Streamlit normally keeps the pool for process life."""
        self._pool.close()
