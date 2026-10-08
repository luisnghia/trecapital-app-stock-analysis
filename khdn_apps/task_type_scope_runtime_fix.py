"""Safe runtime migration for task-type uniqueness per module scope.

Runs before app() calls the transformed init_db(). Existing production rows/IDs are
preserved. A SQLite backup is created once before rebuilding the legacy table.
"""
from __future__ import annotations

from pathlib import Path
import os
import sqlite3


def _table_exists(c, name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(str(name),)).fetchone())


def _index_columns(c, index_name):
    return [str(r[2]) for r in c.execute(f'PRAGMA index_info("{str(index_name).replace(chr(34), chr(34)*2)}")').fetchall() if r[2] is not None]


def _has_global_name_unique(c):
    if not _table_exists(c,"task_types"):
        return False
    for idx in c.execute("PRAGMA index_list(task_types)").fetchall():
        if int(idx[2] or 0) and _index_columns(c,str(idx[1]))==["name"]:
            return True
    return False


def _backup_db(db_path: Path, data_dir: Path, logger=None):
    if not db_path.exists() or not db_path.is_file():
        return None
    dest=data_dir/"backups"/"pre_task_type_scope_unique_v2.db"
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        return dest
    src=sqlite3.connect(str(db_path),timeout=30); dst=sqlite3.connect(str(dest),timeout=30)
    try: src.backup(dst)
    finally: dst.close(); src.close()
    if logger: logger.info("TASK_TYPE_SCOPE_PREMIGRATION_BACKUP file=%s",dest.name)
    return dest


def migrate_db_path(db_path, data_dir=None, logger=None):
    """Migrate a concrete SQLite DB before Streamlit starts serving requests."""
    db_path=Path(db_path).expanduser().resolve()
    data_dir=Path(data_dir or os.getenv("KHDN_DATA_DIR") or db_path.parent).expanduser().resolve()
    if not db_path.exists():
        if logger: logger.info("TASK_TYPE_SCOPE_MIGRATION deferred=fresh_database")
        return "fresh"
    c=sqlite3.connect(str(db_path),timeout=30)
    c.row_factory=sqlite3.Row
    try:
        if not _table_exists(c,"task_types"):
            if logger: logger.info("TASK_TYPE_SCOPE_MIGRATION deferred=no_task_types")
            return "fresh"
        cols={str(r[1]) for r in c.execute("PRAGMA table_info(task_types)").fetchall()}
        if "module_scope" not in cols:
            c.execute("ALTER TABLE task_types ADD COLUMN module_scope TEXT NOT NULL DEFAULT 'OPS'")
        c.execute("UPDATE task_types SET module_scope='OPS' WHERE module_scope IS NULL OR trim(module_scope)='' OR module_scope NOT IN ('OPS','PLAN')")
        c.commit()
        legacy=_has_global_name_unique(c)
    finally:
        c.close()

    if legacy:
        _backup_db(db_path,data_dir,logger)
        c=sqlite3.connect(str(db_path),timeout=30)
        try:
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("BEGIN IMMEDIATE")
            rows=c.execute("PRAGMA table_info(task_types)").fetchall()
            names=[str(r[1]) for r in rows]
            defs=[]
            for r in rows:
                name,typ,notnull,default,pk=str(r[1]),str(r[2] or "TEXT"),int(r[3] or 0),r[4],int(r[5] or 0)
                qn='"'+name.replace('"','""')+'"'
                if name=="id" and pk:
                    ddl=f"{qn} INTEGER PRIMARY KEY AUTOINCREMENT"
                else:
                    ddl=f"{qn} {typ}"
                    if notnull: ddl+=" NOT NULL"
                    if default is not None: ddl+=f" DEFAULT {default}"
                    if pk: ddl+=" PRIMARY KEY"
                defs.append(ddl)
            c.execute("DROP TABLE IF EXISTS task_types_scope_v2")
            c.execute("CREATE TABLE task_types_scope_v2("+",".join(defs)+", UNIQUE(module_scope,name))")
            quoted=",".join('"'+n.replace('"','""')+'"' for n in names)
            c.execute(f"INSERT INTO task_types_scope_v2({quoted}) SELECT {quoted} FROM task_types")
            c.execute("DROP TABLE task_types")
            c.execute("ALTER TABLE task_types_scope_v2 RENAME TO task_types")
            c.execute("COMMIT")
        except Exception:
            try: c.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            try: c.execute("PRAGMA foreign_keys=ON")
            except Exception: pass
            c.close()

    c=sqlite3.connect(str(db_path),timeout=30)
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_task_types_scope_name ON task_types(module_scope,name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_types_scope_active ON task_types(module_scope,active,id)")
        c.commit()
        bad=c.execute("SELECT module_scope,name,COUNT(*) n FROM task_types GROUP BY module_scope,name HAVING n>1 LIMIT 1").fetchone()
        if bad:
            raise RuntimeError("Duplicate task type remains inside one module scope")
    finally:
        c.close()
    if logger: logger.info("TASK_TYPE_SCOPE_MIGRATION_READY legacy_rebuilt=%s cross_scope_duplicate=1",int(bool(legacy)))
    return "migrated" if legacy else "ready"


def migrate(app_ns, logger=None):
    db_path=Path(str(app_ns.get("DB_PATH") or os.getenv("KHDN_DB_PATH") or "")).expanduser()
    if not db_path.exists() and app_ns.get("get_conn"):
        try:
            with app_ns["get_conn"]() as c:
                row=c.execute("PRAGMA database_list").fetchone()
                if row and row[2]: db_path=Path(str(row[2]))
        except Exception:
            pass
    return migrate_db_path(db_path,os.getenv("KHDN_DATA_DIR") or db_path.parent,logger)


def install(mobile_module, app_ns, logger=None):
    mobile_module._migrate_task_type_scope_uniqueness=lambda _app_ns,_logger=None:migrate(_app_ns,_logger or logger)
    if logger: logger.info("TASK_TYPE_SCOPE_RUNTIME_FIX_INSTALLED")
