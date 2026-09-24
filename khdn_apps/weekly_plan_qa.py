from __future__ import annotations
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path
from khdn_apps import weekly_plan as w


def main():
    db = Path(tempfile.mkstemp(prefix="khdn-weekly-", suffix=".db")[1])
    def conn():
        c=sqlite3.connect(db); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
    try:
        with conn() as c:
            c.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,active INTEGER,role TEXT);
            CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT,qlkh_user_id INTEGER,active INTEGER);
            CREATE TABLE tasks(id INTEGER PRIMARY KEY,task_code TEXT,task_type TEXT,due_time TEXT,status TEXT,customer_id INTEGER,qlkh_user_id INTEGER,support_user_id INTEGER);
            INSERT INTO users VALUES(1,'Nguyen A',1,'Cán bộ QLKH');
            INSERT INTO customers VALUES(1,'123','CONG TY CP ABC',1,1);
            INSERT INTO customers VALUES(2,'456','CONG TY TNHH DEF',1,1);
            INSERT INTO tasks VALUES(1,'HS001','Giải Ngân','2026-09-22 10:00:00','OPEN',1,1,1);
            """)
        w.ensure_schema(conn)
        with conn() as c: cs=w.customers(c,1)
        ws=w.week_start(date(2026,9,21))
        items=w.parse_text("T2 gặp Công ty ABC - tiếp thị tiền gửi\nT3 làm hạn mức Công ty DEF\nT4 trình hồ sơ dự án Công ty ABC\nT5 9h họp phòng\nT6 sinh nhật Công ty DEF",ws,cs)
        assert len(items)==5
        assert items[0]["customer_id"]==1 and "Tiền gửi" in items[0]["purposes"]
        assert items[1]["category"]=="Tín dụng"
        assert items[2]["category"]=="Hồ sơ / Dự án"
        assert items[3]["start_time"]=="09:00" and items[3]["category"]=="Nội bộ"
        assert items[4]["category"]=="Chăm sóc khách hàng"
        n,e=w.save_items(conn,1,ws,items); assert n==5 and not e
        with conn() as c: got=w.load_items(c,1,ws); assert len(got)==5
        w.set_status(conn,got[0]["id"],1,"DONE")
        w.move_item(conn,got[1]["id"],1,ws+timedelta(days=4))
        nws=ws+timedelta(days=7); assert w.copy_prev(conn,1,nws)==5
        with conn() as c:
            assert len(w.load_items(c,1,nws))==5
            tasks=w.open_tasks(c,1); assert len(tasks)==1
        assert w.add_task(conn,1,nws,tasks[0],nws)
        with conn() as c: assert len(w.open_tasks(c,1))==0
        print("WEEKLY_PLAN_QA_PASS")
    finally:
        try: db.unlink()
        except OSError: pass


if __name__ == "__main__":
    main()
