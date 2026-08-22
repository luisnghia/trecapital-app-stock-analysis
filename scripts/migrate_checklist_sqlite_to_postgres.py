from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Allow direct execution via `python scripts/migrate_checklist_sqlite_to_postgres.py`
# by adding the repository root to sys.path before importing the app package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.services.portfolio_extensions import ensure_extension_schema
from modules.investment_checklist.services.watchlist_v2 import ensure_watchlist_financial_schema

CATALOG = ROOT / "modules" / "investment_checklist" / "catalog" / "question_catalog_prd.csv"

TABLES = [
    "checklist_company_refs",
    "checklist_watchlist",
    "analyst_table_overrides",
    "checklist_watchlist_financials",
    "research_reviews",
    "analyst_assessments",
    "research_sources",
    "research_source_contents",
    "research_evidence",
    "evidence_question_links",
    "ai_research_runs",
    "ai_research_suggestions",
    "ai_suggestion_decisions",
    "management_people_versions",
    "management_timeline_events",
    "management_track_records",
    "management_question_signals",
    "monitoring_rules",
    "monitoring_observations",
    "delta_review_items",
    "delta_review_decisions",
    "screening_assessments",
    "opportunity_inventory_snapshots",
    "peer_comparison_snapshots",
    "data_snapshots",
    "audit_logs",
    "integration_sync_log",
]
NON_SERIAL_TABLES = {
    "checklist_watchlist", "analyst_table_overrides", "checklist_watchlist_financials",
    "peer_comparison_snapshots",
}
SERIAL_TABLES = [table for table in TABLES if table not in NON_SERIAL_TABLES]


def sqlite_rows(conn: sqlite3.Connection, table: str):
    conn.row_factory = sqlite3.Row
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return []
    columns = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})")}
    ordering = [
        name for name in (
            "id", "company_ref_id", "review_id", "table_key", "period_key", "metric_key", "version_no"
        ) if name in columns
    ]
    order_by = ",".join(ordering) if ordering else "rowid"
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]


def ensure_target_empty(pg) -> None:
    nonempty = []
    with pg.cursor() as cur:
        for table in TABLES:
            cur.execute(sql.SQL("SELECT COUNT(*) AS n FROM {}").format(sql.Identifier(table)))
            if cur.fetchone()["n"]:
                nonempty.append(table)
    if nonempty:
        raise RuntimeError(
            "Target PostgreSQL contains checklist history. Migration aborted to prevent ID/FK collision: "
            + ", ".join(nonempty)
        )


def insert_rows(pg, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(",").join(sql.Placeholder() for _ in columns),
    )
    with pg.cursor() as cur:
        for row in rows:
            cur.execute(statement, [row[c] for c in columns])
    return len(rows)


def reset_sequences(pg) -> None:
    with pg.cursor() as cur:
        for table in SERIAL_TABLES:
            cur.execute("SELECT pg_get_serial_sequence(%s, 'id') AS seq", (table,))
            seq = cur.fetchone()["seq"]
            if not seq:
                continue
            cur.execute(sql.SQL("SELECT COALESCE(MAX(id),0) AS m FROM {}").format(sql.Identifier(table)))
            max_id = cur.fetchone()["m"]
            if max_id:
                cur.execute("SELECT setval(%s, %s, true)", (seq, max_id))
            else:
                cur.execute("SELECT setval(%s, 1, false)", (seq,))


def main():
    parser = argparse.ArgumentParser(description="Safely migrate Phase 1B SQLite checklist history to PostgreSQL/Supabase.")
    parser.add_argument("--sqlite", default=str(ROOT / "data_cache" / "investment_checklist.db"), help="Source SQLite file")
    parser.add_argument("--database-url", default=os.getenv("TREC_CHECKLIST_DATABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Missing --database-url or TREC_CHECKLIST_DATABASE_URL/DATABASE_URL/SUPABASE_DB_URL")
    source = Path(args.sqlite)
    if not source.exists():
        raise SystemExit(f"SQLite source not found: {source}")

    target_repo = PostgresChecklistRepository(args.database_url, CATALOG)
    target_repo.initialize()
    ensure_extension_schema(target_repo)
    ensure_watchlist_financial_schema(target_repo)

    sqlite_conn = sqlite3.connect(source)
    pg = psycopg.connect(args.database_url, row_factory=dict_row, autocommit=False, prepare_threshold=None)
    try:
        ensure_target_empty(pg)
        counts = {}
        for table in TABLES:
            rows = sqlite_rows(sqlite_conn, table)
            counts[table] = insert_rows(pg, table, rows)
        reset_sequences(pg)
        pg.commit()
    except Exception:
        pg.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg.close()

    print("Migration completed successfully.")
    for table, count in counts.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
