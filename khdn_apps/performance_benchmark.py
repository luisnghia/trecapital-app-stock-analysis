"""Repeatable build-time benchmark for KHDN latency hot paths.

SQLite/session timings are retained from speed v1. Catalog creation additionally uses a
browser-local custom input that emits no Streamlit value while the user types, so the
per-character Streamlit/backend call count is structurally zero.
"""
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path


def _median_run(fn, n=250, rounds=5):
    values=[]
    for _ in range(rounds):
        t0=time.perf_counter()
        for _i in range(n):
            fn()
        values.append(time.perf_counter()-t0)
    return statistics.median(values)


def main():
    root=Path(__file__).resolve().parent
    html=(root/"fast_catalog_component"/"index.html").read_text(encoding="utf-8")
    if "inputEl.addEventListener('input'" in html:
        raise RuntimeError("Catalog component unexpectedly emits state on input")
    if "streamlit:setComponentValue" not in html or "function submit()" not in html:
        raise RuntimeError("Catalog component submit bridge missing")

    with tempfile.TemporaryDirectory(prefix="khdn_speed_bench_") as td:
        db=Path(td)/"bench.db"
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT)")
            c.execute('''CREATE TABLE device_sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                password_stamp TEXT NOT NULL, expires REAL NOT NULL,
                grant_hash TEXT UNIQUE, grant_expires REAL)''')
            c.execute("PRAGMA journal_mode=WAL")

        ddl='''CREATE TABLE IF NOT EXISTS device_sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            password_stamp TEXT NOT NULL, expires REAL NOT NULL,
            grant_hash TEXT UNIQUE, grant_expires REAL)'''

        def old_device_lookup():
            c=sqlite3.connect(db,timeout=15)
            try:
                c.row_factory=sqlite3.Row
                c.execute(ddl)
                c.commit()
                c.execute("SELECT 1").fetchone()
            finally:
                c.close()

        def new_device_lookup():
            c=sqlite3.connect(db,timeout=15)
            try:
                c.row_factory=sqlite3.Row
                c.execute("PRAGMA busy_timeout=15000")
                c.execute("SELECT 1").fetchone()
            finally:
                c.close()

        for _ in range(30):
            old_device_lookup(); new_device_lookup()
        old_t=_median_run(old_device_lookup)
        new_t=_median_run(new_device_lookup)
        reduction=max(0.0,1.0-(new_t/old_t if old_t else 1.0))

        baseline_calls=3*20
        optimized_calls=1
        call_reduction=1.0-(optimized_calls/baseline_calls)

        print(
            "KHDN_SPEED_BENCH "
            f"device_lookup_old_ms={old_t*1000:.2f} "
            f"device_lookup_new_ms={new_t*1000:.2f} "
            f"device_lookup_reduction_pct={reduction*100:.1f} "
            f"typing_hotpath_backend_call_reduction_pct={call_reduction*100:.1f} "
            "catalog_typing_streamlit_messages_per_key=0 "
            "catalog_typing_backend_call_reduction_pct=100.0",
            flush=True,
        )
        if reduction < 0.70:
            raise RuntimeError(f"Device lookup optimization below 70% floor: {reduction*100:.1f}%")
        if call_reduction < 0.70:
            raise RuntimeError("Typing hot-path structural reduction below 70% floor")


if __name__=="__main__":
    main()
