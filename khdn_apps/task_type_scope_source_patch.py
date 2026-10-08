"""Patch the legacy KHDN engine so task-type uniqueness is per module scope.

The historical schema used UNIQUE(name) and init_db() used ON CONFLICT(name).
That makes it impossible to have the same visible task name in Operations and
Planning.  This transformer changes only the task_types DDL/bootstrap path:
- name is no longer globally unique;
- module_scope exists from initial schema creation;
- (module_scope, name) is unique;
- default task types bootstrap into OPS and conflicts on that composite key.

Existing databases are migrated separately at runtime before app() calls init_db().
"""
from __future__ import annotations


def patch_source(source: str) -> str:
    old_table = '''        CREATE TABLE IF NOT EXISTS task_types (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            name TEXT UNIQUE NOT NULL,\n            sla_hours REAL NOT NULL DEFAULT 8,\n            active INTEGER NOT NULL DEFAULT 1,\n            created_at TEXT NOT NULL,\n            updated_at TEXT NOT NULL\n        );'''
    new_table = '''        CREATE TABLE IF NOT EXISTS task_types (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            name TEXT NOT NULL,\n            sla_hours REAL NOT NULL DEFAULT 8,\n            active INTEGER NOT NULL DEFAULT 1,\n            created_at TEXT NOT NULL,\n            updated_at TEXT NOT NULL,\n            module_scope TEXT NOT NULL DEFAULT 'OPS',\n            UNIQUE(module_scope,name)\n        );'''
    if old_table not in source:
        if new_table not in source:
            raise RuntimeError("Task-type scope patch cannot find task_types CREATE TABLE block")
    else:
        source = source.replace(old_table, new_table, 1)

    old_bootstrap = '''            c.execute(\'\'\'INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES(?,8,1,?,?)\n                         ON CONFLICT(name) DO NOTHING\'\'\', (name, ts, ts))'''
    new_bootstrap = '''            c.execute(\'\'\'INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) VALUES(?,8,1,'OPS',?,?)\n                         ON CONFLICT(module_scope,name) DO NOTHING\'\'\', (name, ts, ts))'''
    if old_bootstrap not in source:
        if new_bootstrap not in source:
            raise RuntimeError("Task-type scope patch cannot find default task-type bootstrap block")
    else:
        source = source.replace(old_bootstrap, new_bootstrap, 1)

    required = [
        "UNIQUE(module_scope,name)",
        "INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at)",
        "ON CONFLICT(module_scope,name) DO NOTHING",
    ]
    missing = [x for x in required if x not in source]
    if missing:
        raise RuntimeError("Task-type scope source markers missing: " + ", ".join(missing))
    return source
