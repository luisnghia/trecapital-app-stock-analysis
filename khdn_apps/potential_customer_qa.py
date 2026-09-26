from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import khdn_apps.potential_customer_patch as pc


def main():
    db = Path(tempfile.mkstemp(prefix="khdn-prospect-", suffix=".db")[1])
    def conn():
        c=sqlite3.connect(db); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
    try:
        # Legacy shape: CIF is UNIQUE NOT NULL and an existing task references customer 1.
        with conn() as c:
            c.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER);
            CREATE TABLE customers(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              cif TEXT UNIQUE NOT NULL,
              customer_name TEXT NOT NULL,
              qlkh_user_id INTEGER,
              qlkh_source_text TEXT,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT
            );
            CREATE TABLE tasks(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL,FOREIGN KEY(customer_id) REFERENCES customers(id));
            CREATE TABLE system_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_user_id INTEGER,action TEXT,object_type TEXT,object_id TEXT,detail TEXT,created_at TEXT);
            INSERT INTO users VALUES(1,'CB QLKH A','Cán bộ QLKH',0,1);
            INSERT INTO users VALUES(2,'Admin','Cán bộ QLKH',1,1);
            INSERT INTO customers(cif,customer_name,qlkh_user_id,active,created_at) VALUES('001','Công ty ABC',1,1,'2026-09-26 08:00:00');
            INSERT INTO tasks VALUES(1,1);
            ''')
        pc.ensure_customer_master(conn)
        with conn() as c:
            info={r[1]:r for r in c.execute("PRAGMA table_info(customers)").fetchall()}
            assert int(info['cif'][3] or 0)==0, 'CIF must be nullable after migration'
            assert {'customer_status','tax_id','contact_name','contact_phone','prospect_created_by','prospect_created_at'} <= set(info)
            assert c.execute("SELECT customer_name FROM customers WHERE id=1").fetchone()[0]=='Công ty ABC'
            assert c.execute("SELECT customer_id FROM tasks WHERE id=1").fetchone()[0]==1

        # Multiple prospects use NULL CIF, not generated/fake values.
        p1,dup=pc.create_prospect(conn,1,'Công ty Mới Một',tax_id='0401111111',qlkh_user_id=1,force=True)
        p2,dup2=pc.create_prospect(conn,1,'Công ty Mới Hai',tax_id='0402222222',qlkh_user_id=1,force=True)
        assert p1 and p2 and p1!=p2 and not dup and not dup2
        with conn() as c:
            rows=c.execute("SELECT id,cif,active,customer_status FROM customers WHERE id IN (?,?) ORDER BY id",(p1,p2)).fetchall()
            assert all(r['cif'] is None for r in rows)
            assert all(int(r['active'])==0 and r['customer_status']=='PROSPECT' for r in rows)
            # Planning sees official customers + prospects.
            planning=pc.planning_customers(c,1)
            ids={int(x['id']) for x in planning}
            assert {1,p1,p2} <= ids
            # Legacy Tác nghiệp filter active=1 still excludes prospects.
            ops_ids={int(r[0]) for r in c.execute("SELECT id FROM customers WHERE active=1").fetchall()}
            assert 1 in ops_ids and p1 not in ops_ids and p2 not in ops_ids
            similar=pc.find_similar(c,'Cong ty Moi Mot',tax_id='0401111111')
            assert similar and int(similar[0]['id'])==p1

        # Normal create blocks possible duplicate until user explicitly forces it.
        blocked,similar=pc.create_prospect(conn,1,'Công ty Mới Một',tax_id='0401111111',qlkh_user_id=1,force=False)
        assert blocked is None and similar

        # Admin adds the real CIF to the SAME row/ID; history references stay valid.
        pc.activate_customer(conn,2,p1,'009999','Công ty Mới Một',tax_id='0401111111',qlkh_user_id=1)
        with conn() as c:
            r=c.execute("SELECT id,cif,active,customer_status FROM customers WHERE id=?",(p1,)).fetchone()
            assert int(r['id'])==p1 and r['cif']=='009999' and int(r['active'])==1 and r['customer_status']=='ACTIVE_CIF'
            actions=[r[0] for r in c.execute("SELECT action FROM system_audit ORDER BY id").fetchall()]
            assert 'PROSPECT_CUSTOMER_CREATE' in actions and 'PROSPECT_CUSTOMER_ACTIVATE' in actions
        print('POTENTIAL_CUSTOMER_QA_PASS')
    finally:
        try: db.unlink()
        except OSError: pass


if __name__=='__main__':
    main()
