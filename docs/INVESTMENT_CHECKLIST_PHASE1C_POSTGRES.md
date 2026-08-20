# Investment Checklist Phase 1C — PostgreSQL / Supabase Persistence

## Goal

Phase 1C replaces ephemeral Streamlit runtime persistence with durable PostgreSQL-compatible storage while keeping all Phase 1B domain rules unchanged:

- append-only analyst assessment versions;
- explicit carry-forward only;
- Research Gap is not Neutral;
- completed reviews are read-only;
- immutable review snapshots;
- audit and integration sync logs;
- Table 1.1 and Table 1.2 history.

SQLite remains available only as a local/dev fallback.

## Production configuration

Preferred Streamlit secret:

```toml
TREC_CHECKLIST_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require"
```

The resolver also accepts `DATABASE_URL` or `SUPABASE_DB_URL`. A standard Streamlit connection block is supported as well:

```toml
[connections.postgresql]
url = "postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require"
```

Do **not** commit the real URL/password to GitHub.

For Supabase, use the PostgreSQL connection string supplied by the project. Transaction-pooler URLs are supported; psycopg prepared statements are disabled (`prepare_threshold=None`) for PgBouncer compatibility.

## Backend selection

1. If a durable database URL exists, `PostgresChecklistRepository` is used.
2. Otherwise the app falls back to `data_cache/investment_checklist.db` for local/dev only.
3. The Investment Checklist sidebar displays which persistence backend is active without exposing credentials.

## Initial schema

No manual SQL is required by the app. Repository initialization creates the Phase 1C schema and seeds:

- 59 checklist questions;
- 10 Table 1.1 screening criteria;
- a small `persistence_probes` operational table used only to prove data survives deployment restart/rebuild.

The schema is in `modules/investment_checklist/db/postgres_schema.py`.

## Migrate existing Phase 1B SQLite history

The migration is intentionally conservative: the PostgreSQL target must contain no checklist history before migration. This avoids silent ID/FK collisions.

```powershell
$env:TREC_CHECKLIST_DATABASE_URL = "postgresql://..."
python scripts\migrate_checklist_sqlite_to_postgres.py --sqlite data_cache\investment_checklist.db
```

The script preserves original IDs and versions, copies review/snapshot/audit history, resets PostgreSQL sequences, and performs the migration in one transaction. If any step fails, PostgreSQL is rolled back.

## Production restart/rebuild persistence verification

Use the dedicated two-stage probe. It never prints the database URL or password.

Before restarting/rebuilding the deployment:

```powershell
python scripts\checklist_persistence_probe.py write --marker before-restart
```

Save the returned `PROBE_KEY`. Restart/rebuild the Streamlit deployment, then run from a fresh process using the same production secret:

```powershell
python scripts\checklist_persistence_probe.py verify --probe-key <PROBE_KEY>
```

Expected result:

```text
PERSISTENCE_OK
```

If the probe is missing after restart, verification exits non-zero and reports `PERSISTENCE_FAIL`. This detects a changed secret/database as well as non-durable storage.

## CI

`.github/workflows/investment-checklist-phase1c.yml` starts PostgreSQL 16 and runs:

- the existing SQLite regression suite;
- real PostgreSQL persistence tests;
- SQLite → PostgreSQL migration tests;
- a two-process persistence probe test that writes in one Python process and verifies from another.

A green Phase 1C CI is required before merging any production persistence work.

## Production acceptance criteria

- PostgreSQL/Supabase survives Streamlit rebuild/restart.
- A finalized snapshot can be re-read after a fresh app process.
- Prior assessment versions remain unchanged.
- No implicit carry-forward occurs.
- SQLite fallback is visibly labeled local/dev.
- No database credential appears in UI, logs, audit rows or source control.
- Existing Module 1 / Module 2 bridge behavior is unchanged.

## Rollback

If PostgreSQL is unavailable, remove/disable the production database secret and the app will use SQLite local/dev fallback. This is a continuity fallback only; do not enter production analyst history while running on ephemeral SQLite.
