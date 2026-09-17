"""Semantic QA for KHDN V2.31.6 catalog propagation."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pandas as pd

from khdn_apps import catalog_sync_patch as patch


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "catalog.db"

        def get_conn():
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            return c

        with get_conn() as c:
            c.executescript(
                """
                CREATE TABLE task_types(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    sla_hours REAL NOT NULL DEFAULT 8,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE reason_categories(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reason_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO task_types(name,sla_hours,active,updated_at)
                VALUES('Giải Ngân',8,1,'2026-09-17 16:00:00');
                INSERT INTO reason_categories(reason_type,name,active,updated_at)
                VALUES('RETURN','Thiếu hồ sơ',1,'2026-09-17 16:00:00');
                """
            )
            c.commit()

        def qdf(sql, params=()):
            with get_conn() as c:
                return pd.read_sql_query(sql, c, params=params)

        # Simulate the old cache returning stale data forever. V2.31.6 must not use it.
        stale = pd.DataFrame([{"name": "Giải Ngân", "sla_hours": 8.0}])
        ns = {
            "get_conn": get_conn,
            "qdf": qdf,
            "active_task_types": lambda: stale.copy(),
            "active_reason_categories": lambda _kind: pd.DataFrame(columns=["id", "name"]),
            "_visible_task_change_token": lambda _user: "task-token-static",
            "APP_VERSION": "old",
        }

        patch.install(ns)
        user = {"id": 10, "role": "Cán bộ QLKH", "is_admin": False}
        rev0 = patch.catalog_revision(ns)
        token0 = ns["_visible_task_change_token"](user)

        with get_conn() as c:
            # Same timestamp as existing row on purpose: digest must still detect add.
            c.execute(
                "INSERT INTO task_types(name,sla_hours,active,updated_at) VALUES(?,?,1,?)",
                ("Tài trợ thương mại", 8.0, "2026-09-17 16:00:00"),
            )
            c.execute(
                "INSERT INTO reason_categories(reason_type,name,active,updated_at) VALUES('RETURN',?,1,?)",
                ("Sai thông tin", "2026-09-17 16:00:00"),
            )
            c.execute(
                "INSERT INTO reason_categories(reason_type,name,active,updated_at) VALUES('CANCEL',?,1,?)",
                ("Khách hàng rút nhu cầu", "2026-09-17 16:00:00"),
            )
            c.commit()

        types = ns["active_task_types"]()
        returns = ns["active_reason_categories"]("RETURN")
        cancels = ns["active_reason_categories"]("CANCEL")
        rev1 = patch.catalog_revision(ns)
        token1 = ns["_visible_task_change_token"](user)

        assert "Tài trợ thương mại" in types["name"].tolist(), types
        assert "Sai thông tin" in returns["name"].tolist(), returns
        assert "Khách hàng rút nhu cầu" in cancels["name"].tolist(), cancels
        assert rev1 != rev0, (rev0, rev1)
        assert token1 != token0 and token1.endswith(rev1), (token0, token1)

        # Same-second rename/activation updates must also invalidate the token.
        with get_conn() as c:
            c.execute(
                "UPDATE reason_categories SET name=?,active=0,updated_at=? WHERE reason_type='RETURN' AND name='Sai thông tin'",
                ("Sai thông tin hồ sơ", "2026-09-17 16:00:00"),
            )
            c.execute(
                "UPDATE task_types SET active=0,updated_at=? WHERE name='Tài trợ thương mại'",
                ("2026-09-17 16:00:00",),
            )
            c.commit()

        rev2 = patch.catalog_revision(ns)
        token2 = ns["_visible_task_change_token"](user)
        types2 = ns["active_task_types"]()
        returns2 = ns["active_reason_categories"]("RETURN")
        assert rev2 != rev1, (rev1, rev2)
        assert token2 != token1 and token2.endswith(rev2), (token1, token2)
        assert "Tài trợ thương mại" not in types2["name"].tolist(), types2
        assert "Sai thông tin hồ sơ" not in returns2["name"].tolist(), returns2
        assert ns["APP_VERSION"] == "2.31.6"

        print(
            "KHDN_CATALOG_SYNC_QA PASS",
            {
                "new_task_type_immediate": True,
                "new_return_reason_immediate": True,
                "new_cancel_reason_immediate": True,
                "same_second_digest": True,
                "realtime_token_changes": True,
                "deactivation_immediate": True,
            },
        )


if __name__ == "__main__":
    main()
