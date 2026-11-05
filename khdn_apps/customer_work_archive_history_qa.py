"""Real-SQLite and installed-renderer regression: customer work search + archive.

No production DB is used; every test creates an isolated temporary SQLite file.
Checks both current/closed ordering and immutable/authorized history details.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from khdn_apps import customer_work as core
from khdn_apps import customer_work_archive_history as archive
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import customer_work_refinement_patch as refinement
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps.inquiry_priority_readonly_qa import _make_db


class UI:
    def __init__(self, search="Công ty", selected_id=None):
        self.session_state = {}
        if selected_id is not None:
            self.session_state["cw_case_id"] = selected_id
        self.search = search
        self.cards = []
        self.buttons = []
        self.messages = []

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def columns(self, *a, **kw):
        arg = a[0] if a else 2
        return [self] * (arg if isinstance(arg, int) else len(arg))
    def container(self, *a, **kw): return self
    def title(self, x, *a, **kw): self.messages.append(("title", str(x)))
    def subheader(self, x, *a, **kw): self.messages.append(("subheader", str(x)))
    def caption(self, x, *a, **kw): self.messages.append(("caption", str(x)))
    def markdown(self, x, *a, **kw): self.messages.append(("markdown", str(x)))
    def html(self, x, *a, **kw): self.messages.append(("html", str(x)))
    def error(self, x, *a, **kw): self.messages.append(("error", str(x)))
    def warning(self, x, *a, **kw): self.messages.append(("warning", str(x)))
    def info(self, x, *a, **kw): self.messages.append(("info", str(x)))
    def selectbox(self, label, options, **kw): return options[0]
    def text_input(self, label, **kw): return self.search
    def button(self, label, *a, **kw):
        self.buttons.append((label, kw.get("key")))
        return False
    def rerun(self): raise AssertionError("No clicks or reruns expected in view-only QA")


def _db(path):
    _make_db(path)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE customer_work_cases SET customer_id=7,owner_user_id=9")
        # Keep the shared isolated fixture compatible with future production
        # schema additions; add only columns not already present.
        existing = {str(row[1]) for row in c.execute("PRAGMA table_info(customer_work_cases)")}
        for field in ("updated_at", "completed_at", "contact_name",
                      "contact_phone", "contact_role", "plan_approved_by",
                      "plan_approved_at", "plan_rejected_by", "plan_rejected_at",
                      "approval_note"):
            if field not in existing:
                coltype = "INTEGER" if field.endswith("_by") else "TEXT"
                c.execute(f"ALTER TABLE customer_work_cases ADD COLUMN {field} {coltype}")
        c.execute("""UPDATE customer_work_cases SET updated_at='2026-11-05 08:00:00',
                     contact_name='Nguyễn A',contact_role='Giám đốc',
                     contact_phone='0900012345' WHERE id=101""")
        c.execute("""UPDATE customer_work_cases SET
                     title='Hồ sơ đã hoàn thành',updated_at='2026-11-04 09:00:00',
                     completed_at='2026-11-04 09:00:00',
                     note='<script>not executable</script>'
                     WHERE id=102""")
        c.execute("""INSERT INTO customer_work_cases(
                    id,case_code,customer_id,owner_user_id,title,case_type,
                    current_stage_id,stage_started_at,expected_complete_at,status,
                    plan_approval_status,important_category_id,is_important,
                    urgent_override,note,created_at,updated_at)
                 VALUES(103,'CVKH-103',7,9,'Hồ sơ đã hủy','Tín dụng',
                    3,'2026-10-20','2026-11-01','CANCELLED','APPROVED',
                    2,1,0,'Lý do hủy <b>đã ghi</b>','2026-10-20','2026-11-03 10:00:00')""")
        c.execute("""INSERT INTO customer_work_cases(
                    id,case_code,customer_id,owner_user_id,title,case_type,
                    current_stage_id,stage_started_at,expected_complete_at,status,
                    plan_approval_status,important_category_id,is_important,
                    urgent_override,note,created_at,updated_at)
                 VALUES(104,'CVKH-104',7,8,'Công việc cán bộ khác','Tín dụng',
                    3,'2026-10-20','2026-11-01','COMPLETED','APPROVED',
                    2,1,0,'Nội bộ','2026-10-20','2026-11-02 10:00:00')""")
        c.execute("INSERT INTO users VALUES(8,'NGƯỜI KHÁC')")
        c.execute("INSERT INTO case_stage_history VALUES(2,102,3,'2026-10-21','2026-11-04',9,'Hoàn thành thực tế')")
        c.execute("INSERT INTO case_issues VALUES(2,102,3,'Đã xử lý thiếu tài liệu','MEDIUM',9,'2026-10-22',9,'2026-10-23','Đã bổ sung')")
        c.execute("""INSERT INTO case_reschedule_requests(
                  id,case_id,old_due_at,proposed_due_at,reason,requested_by,
                  requested_at,status,decided_at,decision_note)
                  VALUES(2,102,'2026-10-30','2026-11-04','Khách cần bổ sung',9,
                  '2026-10-23','APPROVED','2026-10-24','Đồng ý dời hạn')""")
        c.execute("""CREATE TABLE case_actions(
                    id INTEGER PRIMARY KEY,case_id INTEGER,actor_user_id INTEGER,
                    action TEXT,detail TEXT,created_at TEXT)""")
        c.execute("""INSERT INTO case_actions VALUES
                   (1,102,9,'PLAN_APPROVE','{"note":"Đồng ý thẩm định"}','2026-10-21')""")


def _connect(path):
    def open_db():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c
    return open_db


def test_archived_scope_sort_and_search(dbpath):
    get_conn = _connect(dbpath)
    with get_conn() as c:
        own = core.list_cases(c, uid=9, manager=False, include_completed=True)
        manager = core.list_cases(c, uid=9, manager=True, include_completed=True)
        live_only = core.list_cases(c, uid=9, manager=False, include_completed=False)

    assert {x["id"] for x in own} == {101,102,103}, own
    assert {x["id"] for x in manager} == {101,102,103,104}, manager
    assert {x["id"] for x in live_only} == {101,103}, live_only
    sorted_own = archive.sort_cases(own, core)
    assert [x["id"] for x in sorted_own] == [101,102,103]
    assert archive.status_label(sorted_own[0]) == "🟢 Đang thực hiện"
    assert archive.status_label(sorted_own[1]) == "✅ Đã hoàn thành"
    assert archive.status_label(sorted_own[2]) == "⚫ Đã hủy"

    fake = UI(search="Công ty")
    customer_ui = SimpleNamespace(
        _manager=lambda u: False,
        _case_detail=lambda *args: (_ for _ in ()).throw(AssertionError("Unexpected editable detail")),
        _case_card=lambda st,x,*args: fake.cards.append(dict(x)),
        _glossary=lambda st: None,
    )
    with patch.object(v2, "_ensure_case_priority", return_value=None):
        v2._render_cases_page(fake, {"id": 9, "role":"Cán bộ QLKH"},
                              get_conn, core, customer_ui, refinement, None,
                              lambda *args, **kwargs: "processing")
    assert [x["id"] for x in fake.cards] == [101,102,103], fake.cards
    assert any("Đang thực hiện: 1" in text and "Đã hoàn thành: 1" in text
               and "Đã hủy: 1" in text for tag,text in fake.messages if tag=="caption")
    fake2 = UI(search="CVKH-103")
    # The search matches name/CIF/title/case_type, not the generated work code.
    fake2.search = "đã hủy"
    customer_ui._case_card = lambda st,x,*args: fake2.cards.append(dict(x))
    with patch.object(v2, "_ensure_case_priority", return_value=None):
        v2._render_cases_page(fake2, {"id": 9, "role":"Cán bộ QLKH"},
                              get_conn, core, customer_ui, refinement, None,
                              lambda *args, **kwargs: "processing")
    assert [x["id"] for x in fake2.cards] == [103]


def test_history_readonly_full_and_guard(dbpath):
    get_conn = _connect(dbpath)
    before = sha256(Path(dbpath).read_bytes()).hexdigest()
    user={"id":9,"role":"Cán bộ QLKH"}
    x,h,iss,a,r=archive.load_archive(get_conn,core,102,user,False)
    assert x["status"]=="COMPLETED"
    assert len(h) == len(iss) == len(r) == 1
    assert a and any("Phê duyệt" in z["action"] for z in a)
    assert archive._dt(x["completed_at"]) == "04/11/2026 09:00"
    for cid, viewer, manager in ((101,user,False), (102,{"id":8},False),
                                 (103,{"id":8},False),(999,user,True)):
        try: archive.load_archive(get_conn,core,cid,viewer,manager)
        except PermissionError: pass
        else: raise AssertionError(f"Unauthorized archive accessed: {cid}")
    # A leader can inspect historical tasks from the whole room.
    assert archive.load_archive(get_conn,core,104,{"id":9},True)[0]["id"] == 104
    st=UI()
    st.session_state["cw_case_id"] = 102
    archive.render_archive(st,user,get_conn,core,102,False)
    combined = "\n".join(v for tag,v in st.messages if tag=="html")
    assert "Hoàn thành thực tế" in combined
    assert "Đã bổ sung" in combined
    assert "Đồng ý dời hạn" in combined
    assert "Đồng ý thẩm định" in combined
    assert "&lt;script&gt;" in combined and "<script>not executable</script>" not in combined
    assert not any("Phê duyệt" in k or "Lưu" in k or "Cập nhật" in k
                   for k,_ in st.buttons), st.buttons
    assert st.buttons == [("← Danh sách công việc","cw_back_list")]
    assert sha256(Path(dbpath).read_bytes()).hexdigest() == before

    # Route closed cases to view-only archive rather than legacy edit forms.
    archived_page = UI(selected_id=102)
    called = []
    ui = SimpleNamespace(
        _manager=lambda u: False,
        _case_detail=lambda *args: called.append("editable"),
        _glossary=lambda st: None,
    )
    with patch.object(v2,"_ensure_case_priority",return_value=None):
        v2._render_cases_page(archived_page,user,get_conn,core,ui,refinement,
                              None,lambda *a,**kw: "processing")
    assert not called
    assert "📚 Lịch sử công việc" in "".join(
        v for tag,v in archived_page.messages if tag=="subheader")
    active_page = UI(selected_id=101)
    with patch.object(v2,"_ensure_case_priority",return_value=None):
        v2._render_cases_page(active_page,user,get_conn,core,ui,refinement,
                              None,lambda *a,**kw: "processing")
    assert called == ["editable"]


def test_card_archive_status_no_mutating_manager_actions(dbpath):
    with _connect(dbpath)() as c:
        archived = core.get_case(c, 102)
        cancelled = core.get_case(c, 103)
        active = core.get_case(c, 101)
    archived["plan_approval_status"] = "PENDING"
    cancelled["plan_approval_status"] = "PENDING"
    active["plan_approval_status"] = "PENDING"
    fake=UI()
    ui=SimpleNamespace(core=core,_dt_text=lambda x:str(x or ""),_date_text=lambda x:str(x or ""))
    for row in (archived, cancelled):
        fake.buttons.clear()
        fake.messages.clear()
        finalux._customer_card(fake,ui,refinement,row,None,9,True)
        alltext="".join(v for tag,v in fake.messages if tag=="markdown")
        assert archive.status_label(row) in alltext
        assert "Đã kết thúc" in alltext
        assert not any(k in ("✅ Phê duyệt","↩ Từ chối") for k,_ in fake.buttons),fake.buttons
    fake.buttons.clear()
    finalux._customer_card(fake,ui,refinement,active,None,9,True)
    assert any(k=="✅ Phê duyệt" for k,_ in fake.buttons)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="khdn-archive-qa-") as folder:
        dbpath=str(Path(folder)/"archive.db")
        _db(dbpath)
        test_archived_scope_sort_and_search(dbpath)
        test_history_readonly_full_and_guard(dbpath)
        test_card_archive_status_no_mutating_manager_actions(dbpath)
    print("CUSTOMER_WORK_ARCHIVE_HISTORY_QA_PASS current_closed_query staff_scope manager_scope active_first newest_archive readonly_history stage issues approvals moves escaped_html no_mutation cards_and_details")
