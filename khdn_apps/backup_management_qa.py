from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from khdn_apps.backup_management_patch import create_full_backup_package, database_inventory


def main():
    with tempfile.TemporaryDirectory(prefix="khdn-backup-qa-") as td:
        root = Path(td)
        db = root / "live.db"
        with sqlite3.connect(db) as c:
            c.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,password_hash TEXT,full_name TEXT);
            CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT,phone TEXT);
            CREATE TABLE tasks(id INTEGER PRIMARY KEY,customer_id INTEGER,note TEXT);
            CREATE TABLE case_contacts(id INTEGER PRIMARY KEY,case_id INTEGER,contact_name TEXT,contact_phone TEXT);
            CREATE TABLE customer_work_cases(id INTEGER PRIMARY KEY,customer_id INTEGER,title TEXT);
            CREATE TABLE weekly_plan_items(id INTEGER PRIMARY KEY,user_id INTEGER,title TEXT,note TEXT);
            """)
            c.execute("INSERT INTO users VALUES(1,'admin','SECRET_HASH','Admin')")
            c.execute("INSERT INTO customers VALUES(1,'001','Công ty Kiểm thử','0905123456')")
            c.execute("INSERT INTO tasks VALUES(1,1,'Hồ sơ tín dụng')")
            c.execute("INSERT INTO case_contacts VALUES(1,1,'Chị Lan','0987654321')")
            c.execute("INSERT INTO customer_work_cases VALUES(1,1,'Cấp hạn mức')")
            c.execute("INSERT INTO weekly_plan_items VALUES(1,1,'Theo dõi hồ sơ','Gọi khách hàng')")

        inv = database_inventory(db)
        assert inv["integrity"] == "ok"
        assert inv["tables"]["case_contacts"] == 1
        assert inv["tables"]["weekly_plan_items"] == 1

        package = create_full_backup_package(db, root / "backup.zip", reason="qa", actor="tester")
        assert package.exists() and package.stat().st_size > 0
        with zipfile.ZipFile(package) as zf:
            names = set(zf.namelist())
            assert {"khdn_ops.db", "manifest.json", "tables/customers.csv", "tables/case_contacts.csv", "tables/weekly_plan_items.csv"}.issubset(names)
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            assert manifest["integrity"] == "ok"
            assert manifest["table_counts"]["customers"] == 1
            assert manifest["table_counts"]["case_contacts"] == 1
            contacts = zf.read("tables/case_contacts.csv").decode("utf-8-sig")
            customers = zf.read("tables/customers.csv").decode("utf-8-sig")
            users = zf.read("tables/users.csv").decode("utf-8-sig")
            assert "0987654321" in contacts
            assert "0905123456" in customers
            assert "SECRET_HASH" not in users and "password_hash" not in users
            extracted = root / "restored.db"
            extracted.write_bytes(zf.read("khdn_ops.db"))
        with sqlite3.connect(extracted) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert c.execute("SELECT contact_phone FROM case_contacts WHERE id=1").fetchone()[0] == "0987654321"
            assert c.execute("SELECT password_hash FROM users WHERE id=1").fetchone()[0] == "SECRET_HASH"

    print("BACKUP_MANAGEMENT_QA_PASS full_db=1 all_tables=1 phone=1 csv=1 secrets_db_only=1 integrity=1")


if __name__ == "__main__":
    main()
