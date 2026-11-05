"""Validate cancellation-reason and complete case-action timeline on real isolated SQLite.

Includes approved/rejected cancellation attempts, precise stored reason/actor,
older schemas, closed-case permission gates, escaped HTML and no writes.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile

from khdn_apps import customer_work as core
from khdn_apps import customer_work_archive_history as archive
from khdn_apps.customer_work_archive_history_qa import _db, _connect, UI


def fixture(path):
    _db(path)
    with sqlite3.connect(path) as c:
        for name,typ in (("cancelled_at","TEXT"),("cancelled_by","INTEGER"),
                         ("cancel_reason","TEXT")):
            c.execute(f"ALTER TABLE customer_work_cases ADD COLUMN {name} {typ}")
        c.execute("""CREATE TABLE customer_work_cancel_requests(
            id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL,
            requested_by INTEGER NOT NULL,reason TEXT NOT NULL,
            status TEXT NOT NULL,requested_at TEXT NOT NULL,
            decided_by INTEGER,decided_at TEXT,decision_note TEXT)""")
        c.execute("""UPDATE customer_work_cases SET
           cancelled_at='2026-11-05 08:18:00',cancelled_by=8,
           cancel_reason='Khách hàng dừng triển khai dự án logistics',
           updated_at='2026-11-05 08:18:00'
           WHERE id=103""")
        c.executemany("""INSERT INTO customer_work_cancel_requests
            (id,case_id,requested_by,reason,status,requested_at,
             decided_by,decided_at,decision_note)
            VALUES(?,?,?,?,?,?,?,?,?)""", [
            (44,103,9,"Thiếu nguồn vốn đối ứng","REJECTED","2026-11-01 12:00:00",
             8,"2026-11-02 13:00:00","Tiếp tục làm việc với khách hàng"),
            (45,103,9,"Khách hàng dừng triển khai dự án logistics","APPROVED",
             "2026-11-05 08:05:00",8,"2026-11-05 08:18:00",
             "Đã kiểm tra hồ sơ và đồng ý hủy"),
        ])
        c.executemany("""INSERT INTO case_actions
            (id,case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?,?)""",[
            (2,103,9,"CREATE",'{"approval":"PENDING"}',"2026-10-20 08:00:00"),
            (3,103,9,"STAGE_CHANGE",'{"stage_id":3,"note":"Đã làm việc khách hàng"}',"2026-10-25 08:00:00"),
            (4,103,9,"CANCEL_REQUEST_P12","request_id=44","2026-11-01 12:00:00"),
            (5,103,8,"CANCEL_REJECT_P12","request_id=44","2026-11-02 13:00:00"),
            (6,103,9,"CANCEL_REQUEST_P12","request_id=45","2026-11-05 08:05:00"),
            (7,103,8,"CANCEL_APPROVE_P12","request_id=45","2026-11-05 08:18:00"),
            (8,103,9,"NOTE_EDIT",
             '{"old_note":"<script>H</script>","new_note":"<b>New</b>","manager_comment":"Đã rà soát"}',
             "2026-11-05 08:17:00"),
        ])


def assert_denied(fn):
    try:
        fn()
    except PermissionError:
        return
    raise AssertionError("Closed-case permission check not enforced")


def qa_cancel_history_and_full_events(dbpath):
    conn = _connect(dbpath)
    before = sha256(Path(dbpath).read_bytes()).hexdigest()
    user={"id":9,"role":"Cán bộ QLKH"}
    item, requests, cancelled_by, events=archive.load_archived_audit(conn,core,103,user,False)
    assert item["cancel_reason"] == "Khách hàng dừng triển khai dự án logistics"
    assert [x["id"] for x in requests]==[44,45]
    assert cancelled_by=="NGƯỜI KHÁC",cancelled_by
    summary=dict(archive._closure_summary(item,requests,cancelled_by))
    assert summary["Lý do hủy"] == "Khách hàng dừng triển khai dự án logistics"
    assert summary["Người đề nghị hủy"] == "TRẦN VĂN A"
    assert summary["Ngày đề nghị hủy"] == "05/11/2026 08:05"
    assert summary["Người phê duyệt hủy"] == "NGƯỜI KHÁC"
    assert summary["Ngày phê duyệt hủy"] == "05/11/2026 08:18"
    assert summary["Ý kiến khi phê duyệt"] == "Đã kiểm tra hồ sơ và đồng ý hủy"
    assert [x["label"] for x in events if "hủy" in x["label"].lower()] == [
        "Gửi đề nghị hủy","Từ chối đề nghị hủy",
        "Gửi đề nghị hủy","Phê duyệt hủy công việc"
    ]
    assert len(events)==7
    assert any("Thiếu nguồn vốn đối ứng" in x["detail"] for x in events)
    assert any("Tiếp tục làm việc với khách hàng" in x["detail"] for x in events)
    assert any("Khách hàng dừng triển khai dự án logistics" in x["detail"] for x in events)
    assert any("Đã kiểm tra hồ sơ và đồng ý hủy" in x["detail"] for x in events)
    assert any("Đã làm việc khách hàng" in x["detail"] and "Thẩm định" in x["detail"] for x in events)
    assert not any("request_id=" in x["detail"] for x in events)

    screen=UI(selected_id=103)
    archive.render_archive(screen,user,conn,core,103,False)
    html="\n".join(x for tag,x in screen.messages if tag=="html")
    headers=[x for tag,x in screen.messages if tag=="subheader"]
    assert "🗑 Nguyên nhân và quyết định hủy công việc" in headers
    assert "📑 Toàn bộ đề nghị hủy và kết quả xử lý" in headers
    assert "🧾 Nhật ký toàn bộ thao tác" in headers
    assert "📋 Lịch sử mục công việc" in headers
    assert "⚠ Lịch sử vướng mắc" in headers
    assert "💬 Phê duyệt / thay đổi của Lãnh đạo/Admin" in headers
    assert "Khách hàng dừng triển khai dự án logistics" in html
    assert "Thiếu nguồn vốn đối ứng" in html
    assert "Tiếp tục làm việc với khách hàng" in html
    assert "Đã kiểm tra hồ sơ và đồng ý hủy" in html
    assert "NGƯỜI KHÁC" in html
    assert "&lt;script&gt;" in html and "<script>H</script>" not in html
    assert not any("Lưu" in label or "Phê duyệt" in label or "Hủy" in label
                   for label,_ in screen.buttons)
    assert screen.buttons==[("← Danh sách công việc","cw_back_list")]
    assert sha256(Path(dbpath).read_bytes()).hexdigest()==before

    assert_denied(lambda:archive.load_archived_audit(conn,core,101,user,False))
    assert_denied(lambda:archive.load_archived_audit(conn,core,103,{"id":8},False))
    assert_denied(lambda:archive.load_archived_audit(conn,core,999,user,True))
    assert archive.load_archived_audit(conn,core,103,{"id":8},True)[0]["id"]==103


def qa_legacy_reason_fallback_and_missing_data(dbpath):
    conn=_connect(dbpath)
    with conn() as c:
        c.execute("UPDATE customer_work_cases SET cancel_reason=NULL,cancelled_at=NULL,cancelled_by=NULL WHERE id=103")
    user={"id":9,"role":"Cán bộ QLKH"}
    case, requests, actor, actions=archive.load_archived_audit(conn,core,103,user,False)
    summary=dict(archive._closure_summary(case,requests,actor))
    assert summary["Lý do hủy"]=="Khách hàng dừng triển khai dự án logistics"
    assert summary["Ngày phê duyệt hủy"]=="05/11/2026 08:18"
    assert summary["Người phê duyệt hủy"]=="NGƯỜI KHÁC"

    # A pre-schema record may lack both the canonical reason and an approved
    # request. It must not present a fabricated cause based on the freeform note.
    with conn() as c:
        c.execute("DELETE FROM customer_work_cancel_requests WHERE case_id=103")
    case, requests, actor, actions=archive.load_archived_audit(conn,core,103,user,False)
    summary=dict(archive._closure_summary(case,requests,actor))
    assert summary["Lý do hủy"]=="Chưa có dữ liệu lý do hủy trong hồ sơ"
    screen=UI(selected_id=103)
    archive.render_archive(screen,user,conn,core,103,False)
    assert any("không tự suy đoán" in txt for tag,txt in screen.messages if tag=="warning")
    with conn() as c:
        c.execute("DROP TABLE customer_work_cancel_requests")
    case, requests, actor, actions=archive.load_archived_audit(conn,core,103,user,False)
    assert not requests and len(actions)==7
    summary=dict(archive._closure_summary(case,requests,actor))
    assert summary["Lý do hủy"]=="Chưa có dữ liệu lý do hủy trong hồ sơ"

    # Completed cases still offer the action timeline without cancellation UI.
    screen=UI(selected_id=102)
    archive.render_archive(screen,user,conn,core,102,False)
    h=[v for tag,v in screen.messages if tag=="subheader"]
    assert "✅ Kết quả kết thúc công việc" in h
    assert "🧾 Nhật ký toàn bộ thao tác" in h
    assert "🗑 Nguyên nhân và quyết định hủy công việc" not in h


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="khdn-cancel-audit-qa-") as directory:
        dbpath = str(Path(directory)/"audit.db")
        fixture(dbpath)
        qa_cancel_history_and_full_events(dbpath)
        qa_legacy_reason_fallback_and_missing_data(dbpath)
    print("CUSTOMER_CANCEL_FULL_AUDIT_QA_PASS actual_reason requester decider timestamps both_rejected_approved full_case_actions stage_notes old_reason_fallback no_reason_no_guess legacy_table absent sqlite_ro role_scope escaped_html no_write")
