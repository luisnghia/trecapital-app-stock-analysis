from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

from modules.investment_checklist.db.postgres_schema import POSTGRES_SCHEMA_SQL


def database_url() -> str:
    value = (
        os.getenv("TREC_CHECKLIST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
    )
    if not value:
        raise SystemExit(
            "Missing TREC_CHECKLIST_DATABASE_URL/DATABASE_URL/SUPABASE_DB_URL. "
            "Configure it as a deployment secret; never commit the credential."
        )
    return value


def connect(url: str):
    return psycopg.connect(
        url,
        row_factory=dict_row,
        autocommit=False,
        prepare_threshold=None,
    )


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        for statement in [x.strip() for x in POSTGRES_SCHEMA_SQL.split(';') if x.strip()]:
            cur.execute(statement)
    conn.commit()


def write_probe(conn, marker: str | None) -> str:
    key = "trec-" + secrets.token_urlsafe(18)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO persistence_probes(probe_key,deployment_marker) VALUES(%s,%s)",
            (key, marker),
        )
    conn.commit()
    return key


def verify_probe(conn, key: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT probe_key,deployment_marker,created_at,verified_at "
            "FROM persistence_probes WHERE probe_key=%s",
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            raise SystemExit(
                "PERSISTENCE_FAIL: probe not found. The deployment may be using a different "
                "database/secret, or data did not survive the restart/rebuild."
            )
        cur.execute(
            "UPDATE persistence_probes SET verified_at=CURRENT_TIMESTAMP::text WHERE probe_key=%s",
            (key,),
        )
    conn.commit()
    return dict(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Two-stage production persistence probe for Investment Checklist. "
            "Run 'write' before restart/rebuild, then 'verify --probe-key ...' after it."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write")
    p_write.add_argument("--marker", default=os.getenv("TREC_DEPLOYMENT_MARKER"))

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--probe-key", required=True)

    args = parser.parse_args()
    url = database_url()
    conn = connect(url)
    try:
        ensure_schema(conn)
        if args.command == "write":
            key = write_probe(conn, args.marker)
            print("PERSISTENCE_PROBE_WRITTEN")
            print(f"PROBE_KEY={key}")
            print("Restart/rebuild the deployment, then run verify with this probe key.")
        else:
            row = verify_probe(conn, args.probe_key)
            print("PERSISTENCE_OK")
            print(f"PROBE_KEY={row['probe_key']}")
            print(f"DEPLOYMENT_MARKER={row.get('deployment_marker') or ''}")
            print(f"CREATED_AT={row['created_at']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
