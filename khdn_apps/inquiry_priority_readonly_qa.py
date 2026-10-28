"""Security and real-data QA for read-only Q1–Q4 drilldown in Vấn tin."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from khdn_apps import inquiry_priority_readonly as priority
from khdn_apps import inquiry_readonly_role as inquiry
from khdn_apps.inquiry_readonly_role_qa import FakeUI, sample_cases


SCHEMA = """
CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT);
CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT);
CREATE TABLE work_stage_catalog(
    id INTEGER PRIMARY KEY,name TEXT,sla_hours REAL,
    sort_order INTEGER,is_completion INTEGER);
CREATE TABLE important_categories(id INTEGER PRIMARY KEY,name TEXT);
CREATE TABLE customer_work_cases(
    id INTEGER PRIMARY KEY, case_code TEXT, customer_id INTEGER,
    owner_user_id INTEGER, title TEXT, case_type TEXT,current_stage_id INTEGER,
    stage_started_at TEXT,expected_complete_at TEXT,status TEXT,
    plan_approval_status TEXT,important_category_id INTEGER,is_important INTEGER,
    urgent_override INTEGER,note TEXT,created_at TEXT,completed_at TEXT);
CREATE TABLE case_issues(id INTEGER PRIMARY KEY,case_id INTEGER,stage_id INTEGER,
    issue_text TEXT,severity TEXT,opened_by INTEGER,opened_at TEXT,
    resolved_by INTEGER,resolved_at TEXT,resolution_text TEXT);
CREATE TABLE case_stage_history(id INTEGER PRIMARY KEY,case_id INTEGER,
    stage_id INTEGER,started_at TEXT,ended_at TEXT,actor_user_id INTEGER,
    note TEXT);
CREATE TABLE case_reschedule_requests(id INTEGER PRIMARY KEY,case_id INTEGER,
    old_due_at TEXT,proposed_due_at TEXT,reason TEXT,requested_by INTEGER,
    requested_at TEXT,status TEXT,decided_at TEXT,decision_note TEXT);
CREATE TABLE customer_contact_master(customer_id INTEGER,slot INTEGER,
    contact_name TEXT,contact_phone TEXT,contact_role TEXT,
    PRIMARY KEY(customer_id,slot));
"""


def _make_db(path):
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        c.execute("INSERT INTO customers VALUES(7,'003659','Công ty <script>alert(1)</script>')")
        c.execute("INSERT INTO users VALUES(9,'TRẦN VĂN A')")
        c.execute("INSERT INTO work_stage_catalog VALUES(3,'Thẩm định',48,1,0)")
        c.execute("INSERT INTO important_categories VALUES(2,'Trọng tâm')")
        c.executemany(
            """INSERT INTO customer_work_cases
              (id,case_code,customer_id,owner_user_id,title,case_type,
               current_stage_id,stage_started_at,expected_complete_at,status,
               plan_approval_status,important_category_id,is_important,
               urgent_override,note,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(101,"CVKH-101",7,9,"Hồ sơ <img src=x onerror=alert(1)>","Tín dụng",
              3,"2026-10-20 08:00:00","2026-11-10 17:00:00","ACTIVE",
              "APPROVED",2,1,0,"Ghi chú </td><script>BAD</script>","2026-10-20"),
             (102,"CVKH-102",7,9,"Đã hoàn thành","Huy động",
              3,"2026-10-20 08:00:00","2026-10-21 17:00:00","COMPLETED",
              "APPROVED",2,1,0,"Hoàn thành","2026-10-20")],
        )
        c.execute("INSERT INTO case_stage_history VALUES(1,101,3,'2026-10-20 08:00:00',NULL,9,'Ghi chú chuyển bước')")
        c.execute("INSERT INTO case_issues VALUES(1,101,3,'Thiếu hồ sơ', 'HIGH',9,'2026-10-23 10:00:00',NULL,NULL,NULL)")
        c.execute("INSERT INTO case_reschedule_requests VALUES(1,101,'2026-10-30','2026-11-10','Chờ khách hàng',9,'2026-10-23','PENDING',NULL,NULL)")
        c.execute("INSERT INTO customer_contact_master VALUES(7,1,'Nguyễn A','0900000000','Giám đốc')")


def _no_write(conn):
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    try:
        conn.execute("INSERT INTO users(id,full_name) VALUES(11,'mutation')")
    except sqlite3.OperationalError:
        return
    raise AssertionError("Query-only connection was able to mutate users")


def qa_read_only_exact_scope_history_and_html():
    with tempfile.TemporaryDirectory() as folder:
        p = Path(folder) / "test.db"
        _make_db(p)
        before = sha256(p.read_bytes()).hexdigest()
        original = priority.core.get_case
        observed = []
        def get_case_checked(conn, case_id):
            _no_write(conn)
            observed.append(case_id)
            return original(conn, case_id)
        with patch.object(priority.core, "get_case", side_effect=get_case_checked):
            item, history, issues, contacts, moves = priority._load_detail(
                p, 101, [{"id": 101}]
            )
        assert observed == [101]
        assert item["case_code"] == "CVKH-101"
        assert item["status"] == "ACTIVE"
        assert len(history) == len(issues) == len(contacts) == len(moves) == 1
        assert history[0]["note"] == "Ghi chú chuyển bước"
        assert issues[0]["issue_text"] == "Thiếu hồ sơ"
        assert moves[0]["reason"] == "Chờ khách hàng"
        assert contacts[0]["contact_name"] == "Nguyễn A"
        card = priority._readable_card(item)
        assert "<script>" not in card and "<img" not in card
        assert "&lt;script&gt;" in card and "&lt;img" in card
        fake = FakeUI()
        priority.render_detail(fake, p, 101, [{"id": 101}])
        detail_html = "".join(x for tag, x in fake.messages if tag == "html")
        assert "Ghi chú chuyển bước" in detail_html
        assert "Thiếu hồ sơ" in detail_html
        assert "Nguyễn A" in detail_html
        assert "Chờ khách hàng" in detail_html
        assert "<script>" not in detail_html
        assert not fake.buttons  # no save/edit/approve widgets in details
        for forged in ("101 OR 1=1", "bad", 102, -1, 999):
            try:
                priority._load_detail(p, forged, [{"id": 101}])
            except PermissionError: pass
            else: raise AssertionError(f"Forged/non-room case accepted: {forged!r}")
        try:
            priority._load_detail(p, 102, [{"id": 102}])
        except PermissionError: pass
        else: raise AssertionError("Completed case accepted with crafted room scope")
        assert sha256(p.read_bytes()).hexdigest() == before
        with sqlite3.connect(p) as c:
            assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def qa_case_open_back_and_stale_selection():
    records = sample_cases()
    user = {"id": 21, "role": "Vấn tin", "is_admin": 0}
    open_ui = FakeUI(open_case=2)
    with patch.object(inquiry, "_room_cases", return_value=records):
        inquiry.render_inquiry(open_ui, user, "/not-accessed.db")
    assert open_ui.session_state[priority.SELECTED_KEY] == 2
    assert open_ui.messages[-1] == ("rerun", "triggered")
    assert "cw_case_id" not in open_ui.session_state
    assert "main_page" not in open_ui.session_state

    details = FakeUI()
    details.session_state[priority.SELECTED_KEY] = 2
    with patch.object(inquiry, "_room_cases", return_value=records), patch.object(
        priority, "_load_detail", return_value=(records[1], [], [], [], [])
    ) as read:
        inquiry.render_inquiry(details, user, "/readonly.db")
    read.assert_called_once()
    assert [label for tag, label in details.messages if tag == "subheader"] == [
        "🔎 Chi tiết công việc · chỉ xem",
        "📋 Lịch sử mục công việc",
        "⚠ Lịch sử vướng mắc",
    ]
    assert "🔎 Chi tiết" not in details.buttons
    assert not any("Cập nhật" in b or "Phê duyệt" in b or "Gửi" in b
                   or "Lưu" in b for b in details.buttons)

    go_back = FakeUI(back=True)
    go_back.session_state[priority.SELECTED_KEY] = 2
    with patch.object(inquiry, "_room_cases", return_value=records), patch.object(
        priority, "_load_detail"
    ) as read:
        inquiry.render_inquiry(go_back, user, "/readonly.db")
    read.assert_not_called()
    assert priority.SELECTED_KEY not in go_back.session_state
    assert go_back.messages[-1] == ("rerun", "triggered")

    stale = FakeUI()
    stale.session_state[priority.SELECTED_KEY] = 99999
    with patch.object(inquiry, "_room_cases", return_value=records), patch.object(
        priority, "_load_detail"
    ) as read:
        inquiry.render_inquiry(stale, user, "/readonly.db")
    read.assert_not_called()
    assert priority.SELECTED_KEY not in stale.session_state
    assert any(tag == "warning" for tag, _ in stale.messages)
    assert "🔥 Góc phần tư ưu tiên · toàn phòng" in [
        label for tag, label in stale.messages if tag == "subheader"
    ]


def qa_quadrant_counts_order_and_security():
    records = [
        dict(id=101, customer_name="A", title="A", owner_name="A", quadrant=1,
             open_issue_count=0),
        dict(id=102, customer_name="B", title="B", owner_name="B", quadrant=2,
             open_issue_count=1),
        dict(id=103, customer_name="C", title="C", owner_name="C", quadrant=3,
             open_issue_count=0),
        dict(id=104, customer_name="D", title="D", owner_name="D", quadrant=4,
             open_issue_count=0),
    ]
    fake = FakeUI()
    priority.render_quadrants(fake, records)
    text = "".join(v for tag, v in fake.messages if tag == "html")
    assert "A" in text and "B" in text and "C" in text and "D" in text
    assert len([v for tag, v in fake.messages if tag == "expander"]) == 4
    assert fake.buttons == ["🔎 Chi tiết"] * 4
    assert "open_case_id" not in fake.session_state
    # Both managers and readonly role use the same quadrant selector and sort.
    assert [priority.priority._quadrant(x) for x in sorted(
        records, key=lambda x: priority.priority._priority_sort_key(priority.core, x)
    )] == [1, 2, 3, 4]


def qa_source_does_not_expose_editing():
    source = (Path(__file__).with_name("inquiry_priority_readonly.py")
              .read_text(encoding="utf-8"))
    assert "mode=ro" in source and "PRAGMA query_only=ON" in source
    assert "return render_inquiry(st, u, DB_PATH, LOGGER)" in (
        Path(__file__).with_name("inquiry_readonly_role.py").read_text(encoding="utf-8")
    )
    for banned in ("customer_ui._case_detail(", "core.change_stage(",
                   "core.add_issue(", "core.resolve_issue(",
                   "core.request_reschedule(", "core.set_importance("):
        assert banned not in source, banned
    assert "SELECTED_KEY" in source and "if selected is None:" in source


if __name__ == "__main__":
    qa_read_only_exact_scope_history_and_html()
    qa_case_open_back_and_stale_selection()
    qa_quadrant_counts_order_and_security()
    qa_source_does_not_expose_editing()
    print("INQUIRY_PRIORITY_READONLY_QA_PASS real_sqlite_ro query_only no_mutation current_scope completed_denied xss_escape four_quadrants details_history_issues_contacts_reschedule open_back_logout_safe")
