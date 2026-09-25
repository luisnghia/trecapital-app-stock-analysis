from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from khdn_apps import customer_work as cw
import khdn_apps.customer_work_ui  # noqa: F401 - import is part of syntax smoke test
import khdn_apps.customer_work_patch  # noqa: F401


def main():
    db=Path(tempfile.mkstemp(prefix="khdn-cw-",suffix=".db")[1])
    def conn():
        c=sqlite3.connect(db);c.row_factory=sqlite3.Row;c.execute("PRAGMA foreign_keys=ON");return c
    try:
        with conn() as c:
            c.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER,last_login_at TEXT);
            CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT,qlkh_user_id INTEGER,active INTEGER);
            CREATE TABLE tasks(id INTEGER PRIMARY KEY,task_code TEXT,task_type TEXT,due_time TEXT,status TEXT,customer_id INTEGER,qlkh_user_id INTEGER,support_user_id INTEGER);
            INSERT INTO users VALUES(1,'CB A','Cán bộ QLKH',0,1,'2026-09-25 08:00:00');
            INSERT INTO users VALUES(2,'LDP','Lãnh đạo phòng',0,1,'2026-09-25 08:00:00');
            INSERT INTO users VALUES(3,'Admin','Cán bộ QLKH',1,1,'2026-09-25 08:00:00');
            INSERT INTO customers VALUES(1,'123','Công ty ABC',1,1);
            ''')
        cw.ensure_schema(conn)
        with conn() as c:
            stages=cw.active_stages(c)
            assert len(stages)==8
            assert stages[0]['name']=='Đang tiếp cận khách hàng'
            assert stages[-1]['is_completion']==1
        due=(datetime.now()+timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
        cid,state=cw.create_case(conn,1,1,'Hạn mức 2026',due)
        assert state=='PENDING'
        with conn() as c:
            x=cw.get_case(c,cid);assert x['plan_approval_status']=='PENDING';assert not x['stage_started_at'];assert len(cw.case_history(c,cid))==0
        assert cw.approve_case_plan(conn,cid,2,True,'Đồng ý')
        with conn() as c:
            x=cw.get_case(c,cid);assert x['plan_approval_status']=='APPROVED';assert x['stage_started_at'];assert len(cw.case_history(c,cid))==1
            stages=cw.active_stages(c)
        assert cw.change_stage(conn,cid,1,stages[1]['id'],'Đã đề nghị hồ sơ')
        with conn() as c:
            assert cw.get_case(c,cid)['stage_name']==stages[1]['name'];assert len(cw.case_history(c,cid))==2
        issue=cw.add_issue(conn,cid,1,'KH thiếu BCTC','HIGH');assert issue
        with conn() as c: assert len(cw.case_issues(c,cid,False))==1
        assert cw.resolve_issue(conn,issue,1,'Đã bổ sung')
        with conn() as c: assert len(cw.case_issues(c,cid,False))==0
        new_due=(datetime.now()+timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
        req,rs=cw.request_reschedule(conn,cid,1,new_due,'Chờ hồ sơ');assert rs=='PENDING'
        assert cw.decide_reschedule(conn,req,2,True,'Đồng ý')
        with conn() as c: assert cw.get_case(c,cid)['expected_complete_at']==new_due
        cw.save_important_category(conn,2,None,'Trọng tâm quý','Khách hàng trọng tâm',1,True)
        with conn() as c: cat=cw.active_important_categories(c)[0]
        assert cw.set_importance(conn,cid,2,cat['id'],1)
        with conn() as c:
            x=cw.get_case(c,cid);assert x['is_important']==1 and x['quadrant']==1
        # Leader-created work is approved immediately.
        cid2,state2=cw.create_case(conn,2,1,'Dự án A',due,owner_uid=1)
        assert state2=='APPROVED'
        # Completing the final stage closes the work.
        assert cw.change_stage(conn,cid2,2,stages[-1]['id'],'Hoàn thành')
        with conn() as c: assert cw.get_case(c,cid2)['status']=='COMPLETED'
        print('CUSTOMER_WORK_QA_PASS')
    finally:
        try: db.unlink()
        except OSError: pass


if __name__=='__main__':
    main()
