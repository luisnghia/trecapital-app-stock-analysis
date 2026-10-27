"""Regression tests: customer merge must never lose cases, tasks, histories or contacts."""
from __future__ import annotations

import json
import sqlite3

from khdn_apps import customer_cif_admin_patch as merge


DDL = """
CREATE TABLE customers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cif TEXT UNIQUE, customer_name TEXT NOT NULL,
    qlkh_user_id INTEGER, qlkh_source_text TEXT,
    active INTEGER DEFAULT 1, customer_status TEXT,
    tax_id TEXT, contact_name TEXT, contact_phone TEXT,
    updated_at TEXT
);
CREATE TABLE customer_work_cases(
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    title TEXT, status TEXT, owner_user_id INTEGER
);
CREATE TABLE case_stage_history(
    id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL
    REFERENCES customer_work_cases(id) ON DELETE CASCADE,
    stage_id INTEGER, note TEXT
);
CREATE TABLE case_issues(
    id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL
    REFERENCES customer_work_cases(id) ON DELETE CASCADE, issue_text TEXT
);
CREATE TABLE case_reschedule_requests(
    id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL
    REFERENCES customer_work_cases(id) ON DELETE CASCADE,
    proposed_due_at TEXT
);
CREATE TABLE case_actions(
    id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL
    REFERENCES customer_work_cases(id) ON DELETE CASCADE,
    action TEXT
);
CREATE TABLE tasks(
    id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
    status TEXT, task_type TEXT
);
CREATE TABLE task_actions(
    id INTEGER PRIMARY KEY, task_id INTEGER REFERENCES tasks(id), action TEXT
);
CREATE TABLE weekly_plan_items(
    id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), status TEXT
);
CREATE TABLE legacy_case_tags(
    id INTEGER PRIMARY KEY, customer_id INTEGER, tag TEXT
);
CREATE TABLE alternate_customer_ref(
    id INTEGER PRIMARY KEY,
    client_ref INTEGER REFERENCES customers(id), label TEXT
);
CREATE TABLE customer_contact_master(
    customer_id INTEGER NOT NULL,
    slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),
    contact_name TEXT NOT NULL, contact_phone TEXT NOT NULL, contact_role TEXT NOT NULL,
    updated_by INTEGER, updated_at TEXT NOT NULL,
    source_case_id INTEGER REFERENCES customer_work_cases(id),
    PRIMARY KEY(customer_id,slot),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);
CREATE TABLE system_audit(
    id INTEGER PRIMARY KEY, actor_user_id INTEGER,
    action TEXT, object_type TEXT, object_id TEXT, detail TEXT, created_at TEXT
);
"""


def _db(keep_cif="7654321", source_cif=None):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(DDL)
    c.execute(
        "INSERT INTO customers(id,cif,customer_name,active,customer_status) VALUES(10,?,'Công ty giữ lại',1,'ACTIVE_CIF')",
        (keep_cif,),
    )
    c.execute(
        "INSERT INTO customers(id,cif,customer_name,active,customer_status) VALUES(20,?,'Công ty bị gộp',0,'PROSPECT')",
        (source_cif,),
    )
    c.executemany(
        "INSERT INTO customer_work_cases(id,customer_id,title,status,owner_user_id) VALUES(?,?,?,?,?)",
        [(101,10,"Hồ sơ hiện có","ACTIVE",7),
         (201,20,"Hồ sơ tín dụng","ACTIVE",8),
         (202,20,"Tái thẩm định","COMPLETED",8)],
    )
    c.executemany("INSERT INTO case_stage_history VALUES(?,?,?,?)",
                  [(301,201,2,"Đã nhận hồ sơ"),(302,202,5,"Đã hoàn thành")])
    c.execute("INSERT INTO case_issues VALUES(401,201,'Chờ hồ sơ')")
    c.execute("INSERT INTO case_reschedule_requests VALUES(501,202,'2026-11-10')")
    c.execute("INSERT INTO case_actions VALUES(601,201,'CREATE')")
    c.executemany("INSERT INTO tasks VALUES(?,?,?,?)",
                  [(701,10,"OPEN","Giải ngân"),(702,20,"OPEN","Bảo lãnh"),
                   (703,20,"CLOSED","Giải ngân")])
    c.execute("INSERT INTO task_actions VALUES(711,702,'ASSIGNED')")
    c.execute("INSERT INTO weekly_plan_items VALUES(801,20,'APPROVED')")
    c.execute("INSERT INTO legacy_case_tags VALUES(901,20,'important')")
    c.execute("INSERT INTO alternate_customer_ref VALUES(911,20,'external')")
    c.executemany(
        "INSERT INTO customer_contact_master(customer_id,slot,contact_name,contact_phone,contact_role,updated_by,updated_at,source_case_id) VALUES(?,?,?,?,?,?,?,?)",
        [(10,1,"Người giữ lại","090001","Kế toán",7,"2026-10-20",101),
         (20,1,"Người thứ nhất","090002","Giám đốc",8,"2026-10-22",201),
         (20,2,"Người thứ hai","090003","Kế toán",8,"2026-10-23",202)],
    )
    return c


def _rows(c, table):
    return [tuple(row) for row in c.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]


def qa_merge_moves_all_work_and_preserves_history():
    c = _db()
    tracked = [
        "case_stage_history","case_issues","case_reschedule_requests",
        "case_actions","task_actions",
    ]
    before = {table:_rows(c,table) for table in tracked}
    source_contacts = [tuple(row)[2:] for row in c.execute(
        "SELECT * FROM customer_contact_master WHERE customer_id=20 ORDER BY slot")]
    c.execute("BEGIN IMMEDIATE") if not c.in_transaction else None
    assert merge.merge_customers(c,1,10,20)==10
    assert c.execute("SELECT COUNT(*) FROM customers WHERE id=20").fetchone()[0]==0
    assert [tuple(row) for row in c.execute(
        "SELECT id,customer_id,status,owner_user_id FROM customer_work_cases ORDER BY id"
    )]==[(101,10,"ACTIVE",7),(201,10,"ACTIVE",8),(202,10,"COMPLETED",8)]
    assert [tuple(row) for row in c.execute(
        "SELECT id,customer_id,status FROM tasks ORDER BY id"
    )]==[(701,10,"OPEN"),(702,10,"OPEN"),(703,10,"CLOSED")]
    assert c.execute("SELECT customer_id FROM weekly_plan_items WHERE id=801").fetchone()[0]==10
    assert c.execute("SELECT customer_id FROM legacy_case_tags WHERE id=901").fetchone()[0]==10
    assert c.execute("SELECT client_ref FROM alternate_customer_ref WHERE id=911").fetchone()[0]==10
    assert {t:_rows(c,t) for t in tracked} == before
    assert [tuple(row)[2:] for row in c.execute(
        "SELECT * FROM customer_contact_master WHERE customer_id=10 AND contact_name!='Người giữ lại' ORDER BY slot")] == source_contacts
    assert [tuple(row)[:2] for row in c.execute(
        "SELECT * FROM customer_contact_master WHERE customer_id=10 ORDER BY slot")] == [(10,1),(10,2),(10,3)]
    assert c.execute("SELECT COUNT(*) FROM customer_contact_master WHERE customer_id=20").fetchone()[0]==0
    assert c.execute("PRAGMA foreign_key_check").fetchall()==[]
    audit=c.execute("SELECT action,detail FROM system_audit").fetchone()
    assert audit[0]=="CUSTOMER_MERGE"
    detail=json.loads(audit[1])
    assert detail["reassigned"]["customer_work_cases.customer_id"]==2
    assert detail["reassigned"]["tasks.customer_id"]==2
    assert detail["moved_contacts"]==2 and detail["integrity_checked"] is True
    c.commit()
    c.close()


def qa_official_cif_moves_to_preserved_prospect_id():
    c=_db(keep_cif=None,source_cif="12345678")
    # The source owns the UNIQUE CIF until it is removed.
    assert merge.merge_customers(c,1,10,20)==10
    assert c.execute("SELECT cif FROM customers WHERE id=10").fetchone()[0]=="12345678"
    assert c.execute("SELECT COUNT(*) FROM customers").fetchone()[0]==1
    assert c.execute("PRAGMA foreign_key_check").fetchall()==[]
    c.close()


def qa_capacity_overflow_rolls_back_contacts_and_work():
    c=_db()
    c.execute("INSERT INTO customer_contact_master VALUES(10,2,'Thêm liên hệ','090099','Kế toán',7,'2026-10-21',101)")
    before={x:_rows(c,x) for x in ["customers","customer_work_cases","tasks","customer_contact_master","case_actions"]}
    try:
        merge.merge_customers(c,1,10,20)
    except ValueError as exc:
        assert "vượt giới hạn 3" in str(exc),str(exc)
    else: raise AssertionError("Must reject more than 3 contacts")
    assert {x:_rows(c,x) for x in before}==before
    assert c.execute("SELECT COUNT(*) FROM system_audit").fetchone()[0]==0
    c.close()


def qa_midway_failure_reverts_everything_with_fk_off():
    c=_db()
    c.commit()
    c.execute("PRAGMA foreign_keys=OFF")
    assert c.execute("PRAGMA foreign_keys").fetchone()[0]==0
    c.execute("""CREATE TRIGGER block_task_reassignment BEFORE UPDATE OF customer_id ON tasks
                 WHEN OLD.customer_id=20
                 BEGIN SELECT RAISE(ABORT,'synthetic task failure'); END""")
    before={x:_rows(c,x) for x in ["customers","customer_work_cases","tasks","customer_contact_master","weekly_plan_items"]}
    try:
        merge.merge_customers(c,1,10,20)
    except ValueError as exc:
        assert "Không thể chuyển lịch sử" in str(exc)
    else: raise AssertionError("Failure must rollback transfer of contacts/cases")
    assert {x:_rows(c,x) for x in before}==before
    assert c.execute("SELECT COUNT(*) FROM system_audit").fetchone()[0]==0
    c.close()


def qa_fk_disabled_succeeds_but_still_checks_references():
    c=_db()
    c.commit()
    c.execute("PRAGMA foreign_keys=OFF")
    assert merge.merge_customers(c,1,10,20)==10
    assert c.execute("SELECT COUNT(*) FROM customer_work_cases WHERE customer_id=20").fetchone()[0]==0
    assert c.execute("SELECT COUNT(*) FROM customer_contact_master WHERE customer_id=20").fetchone()[0]==0
    assert c.execute("PRAGMA foreign_key_check").fetchall()==[]
    c.close()


def qa_two_official_cifs_never_combined():
    c=_db(keep_cif="111",source_cif="222")
    before=_rows(c,"customers")
    try: merge.merge_customers(c,1,10,20)
    except ValueError as exc: assert "CIF khác nhau" in str(exc)
    else: raise AssertionError("Unrelated customers were merged")
    assert _rows(c,"customers")==before
    c.close()


def qa_source_absent_does_not_touch_keeper():
    c=_db()
    try: merge.merge_customers(c,1,10,999)
    except ValueError as e: assert "Không tìm thấy" in str(e)
    else: raise AssertionError("Unknown source accepted")
    assert c.execute("SELECT COUNT(*) FROM customers").fetchone()[0]==2
    c.close()


def qa_contact_free_slots_and_legacy_no_contacts_table():
    c=_db()
    c.execute("DELETE FROM customer_contact_master WHERE customer_id=10")
    assert merge.merge_customers(c,1,10,20)==10
    assert [row[0] for row in c.execute(
        "SELECT slot FROM customer_contact_master WHERE customer_id=10 ORDER BY slot")] == [1,2]
    c.close()
    c=_db()
    c.execute("DROP TABLE customer_contact_master")
    assert merge.merge_customers(c,1,10,20)==10
    assert c.execute("SELECT COUNT(*) FROM customer_work_cases WHERE customer_id=10").fetchone()[0]==3
    c.close()


def qa_source_ui_disallows_overflow_and_docker_gate():
    from pathlib import Path
    source=Path(merge.__file__).read_text(encoding="utf-8")
    assert "blocked_contacts = contacts_count > 3" in source
    assert "disabled=not confirm or blocked_contacts" in source
    assert "ROLLBACK TO SAVEPOINT khdn_safe_customer_merge" in source
    assert "PRAGMA foreign_key_check" in source
    assert "customer_contact_master SET customer_id=?,slot=?" in source
    docker=(Path(merge.__file__).parent/"Dockerfile").read_text(encoding="utf-8")
    assert "customer_merge_lossless_qa.py" in docker


if __name__=="__main__":
    qa_merge_moves_all_work_and_preserves_history()
    qa_official_cif_moves_to_preserved_prospect_id()
    qa_capacity_overflow_rolls_back_contacts_and_work()
    qa_midway_failure_reverts_everything_with_fk_off()
    qa_fk_disabled_succeeds_but_still_checks_references()
    qa_two_official_cifs_never_combined()
    qa_source_absent_does_not_touch_keeper()
    qa_contact_free_slots_and_legacy_no_contacts_table()
    qa_source_ui_disallows_overflow_and_docker_gate()
    print("CUSTOMER_MERGE_LOSSLESS_QA_PASS cases_history_issues_reschedule_actions tasks_weekly legacy_fk contacts_slot_clash contact_overflow_rollback foreign_keys_on_off cif_unique transaction_audit")
