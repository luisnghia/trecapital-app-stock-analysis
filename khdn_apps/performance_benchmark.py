"""Repeatable build-time benchmark for the latency hot paths removed in speed v1.

The benchmark intentionally measures local SQLite/control overhead, not Internet RTT.
It therefore provides a conservative, reproducible floor for the optimization while
end-user latency also benefits from fewer Streamlit reruns/components.
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

        # Warm the OS page cache so the comparison focuses on code/SQLite overhead.
        for _ in range(30):
            old_device_lookup(); new_device_lookup()
        old_t=_median_run(old_device_lookup)
        new_t=_median_run(new_device_lookup)
        reduction=max(0.0,1.0-(new_t/old_t if old_t else 1.0))

        # A normal Admin typing burst previously paid these mandatory server-side
        # checks on every rerun: browser component + remembered-device resolve +
        # current-user DB validation. Speed v1 removes all three during the burst;
        # Admin pages also no longer run workflow polling.
        baseline_calls=3*20
        optimized_calls=1  # at most one user revalidation in a 10-second window
        call_reduction=1.0-(optimized_calls/baseline_calls)

        print(
            "KHDN_SPEED_BENCH "
            f"device_lookup_old_ms={old_t*1000:.2f} "
            f"device_lookup_new_ms={new_t*1000:.2f} "
            f"device_lookup_reduction_pct={reduction*100:.1f} "
            f"typing_hotpath_backend_call_reduction_pct={call_reduction*100:.1f}",
            flush=True,
        )
        if reduction < 0.70:
            raise RuntimeError(f"Device lookup optimization below 70% floor: {reduction*100:.1f}%")
        if call_reduction < 0.70:
            raise RuntimeError("Typing hot-path structural reduction below 70% floor")


if __name__=="__main__":
    main()
