from __future__ import annotations
import sqlite3
import tempfile
from pathlib import Path
from khdn_apps import worktype_contact_card_patch as p


def main():
    db = Path(tempfile.mkstemp(prefix="khdn-worktype-", suffix=".db")[1])
    def conn():
        c=sqlite3.connect(db); c.row_factory=sqlite3.Row; return c
    try:
        with conn() as c:
            c.executescript("""
            CREATE TABLE task_types(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,sla_hours REAL NOT NULL DEFAULT 8,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES('Giải ngân',8,1,'x','x');
            CREATE TABLE customer_work_cases(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT);
            """)
        p.ensure_worktype_scope(conn)
        p.ensure_case_contacts(conn)
        with conn() as c:
            cols={r[1] for r in c.execute("PRAGMA table_info(task_types)")}
            assert "module_scope" in cols
            assert c.execute("SELECT module_scope FROM task_types WHERE name='Giải ngân'").fetchone()[0]=="OPS"
            c.execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at,module_scope) VALUES('Tiếp thị tiền gửi',8,1,'x','x','PLAN')")
            plans=p.planning_task_types(c)
            assert [x['name'] for x in plans]==['Tiếp thị tiền gửi']
            ccols={r[1] for r in c.execute("PRAGMA table_info(customer_work_cases)")}
            assert {'contact_name','contact_phone','contact_role'} <= ccols
        src=Path(__file__).with_name('worktype_contact_card_patch.py').read_text(encoding='utf-8')
        assert 'Người liên hệ *' in src and 'SĐT liên hệ *' in src and 'Chức vụ *' in src
        assert 'CONTACT_ROLES' in src and 'Kế toán trưởng/GĐ Tài chính' in src
        assert 'cw_create_epoch' in src
        assert 'st.button("Chi tiết"' in src
        assert 'use_container_width=True' not in src[src.index('def _card'):src.index('def install')]
        print('WORKTYPE_CONTACT_CARD_QA_PASS')
    finally:
        try: db.unlink()
        except OSError: pass


if __name__=='__main__':
    main()
