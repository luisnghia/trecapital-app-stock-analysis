"""Build-time semantic QA for reason return/cancel workflow.

Runs against the exact transformed V2.38 source, but executes only the atomic
transition helper in an isolated temporary SQLite database. No production data is
read or modified.
"""
from pathlib import Path
import ast
import base64
import gzip
import logging
import sqlite3
import sys
import tempfile

_app_root=str(Path(__file__).resolve().parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0,_app_root)

from khdn_apps.mobile_nav_patch import patch_source as mobile_patch
from khdn_apps.reason_categories_patch import patch_source as reason_patch


def transformed_source():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    source=gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    return reason_patch(mobile_patch(source))


def extract_transition(source):
    tree=ast.parse(source)
    target=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_reasoned_task_transition"),None)
    if target is None:
        raise RuntimeError("Atomic reason transition helper missing")
    return compile(ast.Module(body=[target],type_ignores=[]),"<reason-transition-qa>","exec")


def run():
    helper_code=extract_transition(transformed_source())
    with tempfile.TemporaryDirectory(prefix="khdn_reason_qa_") as td:
        db=str(Path(td)/"qa.db")
        def get_conn():
            c=sqlite3.connect(db)
            c.row_factory=sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            return c
        def now_str():
            return "2026-09-12 23:20:00"
        logger=logging.getLogger("khdn_reason_semantic_qa")
        ns={"get_conn":get_conn,"now_str":now_str,"LOGGER":logger,"ValueError":ValueError,"str":str,"int":int}
        exec(helper_code,ns,ns)
        transition=ns["_reasoned_task_transition"]
        with get_conn() as c:
            c.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY);
            CREATE TABLE tasks(id INTEGER PRIMARY KEY, support_user_id INTEGER, qlkh_user_id INTEGER, status TEXT, returned_to_qlkh_at TEXT, accepted_at TEXT, first_accepted_at TEXT, cancelled_at TEXT, updated_at TEXT);
            CREATE TABLE reason_categories(id INTEGER PRIMARY KEY AUTOINCREMENT, reason_type TEXT NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_by INTEGER, created_at TEXT, updated_at TEXT, UNIQUE(reason_type,name));
            CREATE TABLE task_reason_events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, actor_user_id INTEGER NOT NULL, event_type TEXT NOT NULL, reason_category_id INTEGER NOT NULL, reason_category_name TEXT NOT NULL, reason_detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE task_actions(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, actor_user_id INTEGER, action TEXT, detail TEXT, created_at TEXT);
            CREATE TABLE system_audit(id INTEGER PRIMARY KEY AUTOINCREMENT, actor_user_id INTEGER, action TEXT, object_type TEXT, object_id TEXT, detail TEXT, created_at TEXT);
            INSERT INTO users VALUES(1); INSERT INTO users VALUES(2);
            INSERT INTO tasks(id,support_user_id,qlkh_user_id,status) VALUES(10,1,2,'PENDING_ACCEPTANCE');
            INSERT INTO tasks(id,support_user_id,qlkh_user_id,status) VALUES(11,1,2,'OPEN');
            INSERT INTO tasks(id,support_user_id,qlkh_user_id,status,first_accepted_at) VALUES(12,1,2,'RETURNED_TO_QLKH','2026-09-12 10:00:00');
            INSERT INTO reason_categories(reason_type,name,active) VALUES('RETURN','Thiếu hồ sơ',1);
            INSERT INTO reason_categories(reason_type,name,active) VALUES('CANCEL','Khách hàng dừng nhu cầu',1);
            INSERT INTO reason_categories(reason_type,name,active) VALUES('RETURN','Nhóm khóa',0);
            ''')
            c.commit()

        # A. CBHT return is atomic and auditable.
        transition(10,1,'RETURN',1,'Thiếu BCTC',
            "UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,updated_at=? WHERE id=? AND support_user_id=? AND status='PENDING_ACCEPTANCE'",
            ('2026-09-12 23:20:00','2026-09-12 23:20:00',10,1),'RETURN_TO_QLKH','Trả lại trước khi tiếp nhận')
        with get_conn() as c:
            assert c.execute("SELECT status FROM tasks WHERE id=10").fetchone()[0]=='RETURNED_TO_QLKH'
            assert tuple(c.execute("SELECT event_type,reason_category_name,reason_detail FROM task_reason_events WHERE task_id=10").fetchone())==('RETURN','Thiếu hồ sơ','Thiếu BCTC')
            assert c.execute("SELECT COUNT(*) FROM task_actions WHERE task_id=10").fetchone()[0]==1
            assert c.execute("SELECT COUNT(*) FROM system_audit WHERE object_id='10'").fetchone()[0]==1

        # B. Blank detail is rejected with no mutation.
        try:
            transition(11,1,'RETURN',1,'   ',"UPDATE tasks SET status='RETURNED_TO_QLKH' WHERE id=?",(11,),'RETURN_TO_QLKH','x')
            raise AssertionError("blank detail accepted")
        except ValueError:
            pass
        with get_conn() as c:
            assert c.execute("SELECT status FROM tasks WHERE id=11").fetchone()[0]=='OPEN'
            assert c.execute("SELECT COUNT(*) FROM task_reason_events WHERE task_id=11").fetchone()[0]==0

        # C. Inactive category is rejected.
        try:
            transition(11,1,'RETURN',3,'reason',"UPDATE tasks SET status='RETURNED_TO_QLKH' WHERE id=?",(11,),'RETURN_TO_QLKH','x')
            raise AssertionError("inactive category accepted")
        except ValueError:
            pass

        # D. Stale status must roll back event/action/audit writes.
        with get_conn() as c:
            before=tuple(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ('task_reason_events','task_actions','system_audit'))
        try:
            transition(11,1,'RETURN',1,'reason',"UPDATE tasks SET status='RETURNED_TO_QLKH' WHERE id=? AND status='NOPE'",(11,),'RETURN_TO_QLKH','x')
            raise AssertionError("stale status accepted")
        except ValueError:
            pass
        with get_conn() as c:
            after=tuple(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ('task_reason_events','task_actions','system_audit'))
        assert before==after

        # E. QLKH cancellation is atomic.
        transition(12,2,'CANCEL',2,'KH rút nhu cầu',
            "UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='RETURNED_TO_QLKH'",
            ('2026-09-12 23:20:00','2026-09-12 23:20:00',12,2),'QLKH_CANCEL','QLKH hủy sau trả lại')
        with get_conn() as c:
            assert c.execute("SELECT status FROM tasks WHERE id=12").fetchone()[0]=='CANCELLED'
            assert tuple(c.execute("SELECT reason_category_name,reason_detail FROM task_reason_events WHERE task_id=12").fetchone())==('Khách hàng dừng nhu cầu','KH rút nhu cầu')

        # F. Historical reason name remains a snapshot after master-data rename.
        with get_conn() as c:
            c.execute("UPDATE reason_categories SET name='Tên mới' WHERE id=1")
            c.commit()
            assert c.execute("SELECT reason_category_name FROM task_reason_events WHERE task_id=10").fetchone()[0]=='Thiếu hồ sơ'

    print("KHDN_REASON_SEMANTIC_QA PASS return_atomic blank_block inactive_block rollback cancel_atomic history_snapshot",flush=True)


if __name__=="__main__":
    run()
