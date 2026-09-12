# KHDN Ops V2.25 — Persistent Railway deployment

The standalone Docker entry point is `python -m khdn_apps.runtime`. The embedded
Trecapital entry point remains `pages/KHDNApps.py`.

## Persistent storage

Attach one Railway volume to the KHDNApps service at `/data`. Keep one replica.
The current workspace allows a 500 MB volume. The runtime verifies that `/data`
is an actual mount before starting Streamlit; an absent volume causes startup
to fail instead of silently creating an ephemeral database.

| Content | Location |
|---|---|
| Accounts, avatars, customers, tasks, scores and audit | `/data/khdn_ops.db` |
| SQLite WAL and shared-memory sidecars | Alongside the database |
| Operational and storage logs | `/data/logs/` |
| Annual reports and year-end SQLite snapshots | `/data/annual_archive/` |
| Daily compressed database copies | `/data/backups/` |
| Stable volume identity and startup counts | `/data/storage_identity.json`, `/data/storage_status.json` |
| Last backup result | `/data/backup_status.json` |

Use `KHDN_DATA_DIR=/data`, `KHDN_DB_PATH=/data/khdn_ops.db`,
`PYTHONPATH=/app` and `KHDN_REQUIRE_VOLUME=1`. Configure the existing
`KHDN_ADMIN_PASSWORD` privately in Railway. The image defaults to port 8080;
Railway's `PORT` variable takes precedence. Healthcheck: `/_stcore/health`.

## Backups

The runtime checks once a minute and creates one compressed SQLite snapshot per
UTC date, including committed transactions still in the WAL. The newest 14 daily
copies are retained, subject to a combined 50 MiB budget. Older copies are removed
only after a new, verified copy has been installed. A copy exceeding the budget
or insufficient free space records a backup error and preserves previous copies.

The Admin → Sao lưu page provides consistent current database downloads and
downloads of the scheduled `.db.gz` copies. Gunzip a scheduled copy to obtain a
SQLite database. Year-end database snapshots use the same consistent backup API.

These copies are on the **same volume**. They help recover from application/data
entry mistakes but do not survive deletion of the entire volume. Download copies
to separate controlled storage. The effective workspace backup limit reported by
Railway is currently zero; native Railway snapshot schedules are not enabled.
Persistent primary data has no age-based deletion in this change. Rotation applies
only to the daily backup copies and existing rotating log files.

## Migrate the currently running ephemeral database

Do not deploy, restart, or apply the new mount before securing the old database.
Mounting an empty volume does not copy data out of the previous container.

1. Stop entering new work during the cutover and export the existing database
   through the authenticated Admin backup page. The legacy V2.24 export reads the
   database file directly: verify there are no outstanding WAL writes before and
   after that export, or obtain a proper SQLite online backup through an authorized
   container session. Validate the export with `PRAGMA integrity_check` and record
   counts for `users`, `customers`, and `tasks`.
2. Keep the export private. Never commit a database, migration payload, password,
   or user data to GitHub. Compute SHA-256 over the uncompressed SQLite file.
3. If using the one-time initializer, gzip and base64-encode that verified file and
   set private service variables `KHDN_MIGRATION_DB_GZIP_BASE64` and
   `KHDN_MIGRATION_DB_SHA256`. Payloads are limited to 20 MiB compressed and 250 MiB
   expanded. For larger data, perform a controlled offline file restore instead.
4. Apply the volume attachment, reviewed code revision, and migration variables in
   the same deployment. Avoid an automatic code deployment before the volume and
   migration payload are ready. The initializer checks the checksum, SQLite
   integrity, expected tables, and absence of a conflicting target database. It
   records `migration_receipt.json` and never replaces subsequent user work on a
   restart. The temporary payload is not passed to the Streamlit child process.
5. Verify the mounted volume, migration counts, login page, and first successful
   backup. Clear the two temporary migration variables from Railway after success.
6. Redeploy once more and compare the stable storage ID and database counts. Only
   then report persistent storage as live and verified.

Future code updates must keep the same volume attached. Do not delete the volume
when replacing or recreating a service. Restore operations require an offline
cutover; there is no unauthenticated restore endpoint.

## Verification

From the repository root:

```bash
python -m unittest discover -s tests -p test_khdn_storage.py -v
```

The tests cover committed WAL content and avatars, checked migration, refusing
overwrite, persistent identity across initialization, mount/path guards, backup
retention, gzip integrity, and preservation of existing copies after a failed
backup. The standard-library tests do not substitute for the live migration and
redeployment checks above.
