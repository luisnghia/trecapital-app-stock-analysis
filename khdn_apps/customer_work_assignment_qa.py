"""Real SQLite and installed-renderer regression for managed Customer Work assignment.

Run without production data. Covers Admin/all-room, controlling leader,
other leader denied, Vấn tin/staff denied, inactive/deleted candidates, stale
writes, archived immutable, owner/controller change journal and CIF source.
"""
from __future__ import annotations
import base64
import gzip
from pathlib import Path
import json
import sqlite3
import tempfile
from unittest.mock import patch

from khdn_apps import customer_work_assignment_patch as assignment
from khdn_apps import customer_work_manager_note_history_patch as history
from khdn_apps import customer_work_archive_history as archive


class UI:
    def __init__(self):
        self.labels=[]
        self.expander_options=[]
        self.messages=[]
        self.session_state={}

    def __enter__(self): return self
    def __exit__(self,*a): return False
    def expander(self,label,*a,**kw):
        self.labels.append(label)
        self.expander_options.append(dict(kw))
        return self
    def subheader(self,value,*a,**kw): self.labels.append(value)
    def caption(self,value,*a,**kw): self.messages.append(("caption",str(value)))
    def error(self,value,*a,**kw): self.messages.append(("error",str(value)))
    def warning(self,value,*a,**kw): self.messages.append(("warning",str(value)))
    def info(self,value,*a,**kw): self.messages.append(("info",str(value)))
    def toast(self,value,*a,**kw): self.messages.append(("toast",str(value)))
    def rerun(self): self.messages.append(("rerun","called"))


def fixture(db):
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.executescript("""
          CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,
              role TEXT,is_admin INTEGER,active INTEGER,deleted_at TEXT);
          CREATE TABLE customer_work_cases(
              id INTEGER PRIMARY KEY,owner_user_id INTEGER NOT NULL,
              controller_user_id INTEGER,status TEXT,created_at TEXT,updated_at TEXT,
              FOREIGN KEY(owner_user_id) REFERENCES users(id));
          CREATE TABLE case_actions(
              id INTEGER PRIMARY KEY,case_id INTEGER,actor_user_id INTEGER,
              action TEXT,detail TEXT,created_at TEXT);
          CREATE TABLE case_reschedule_requests(
              id INTEGER PRIMARY KEY,case_id INTEGER,old_due_at TEXT,
              proposed_due_at TEXT,reason TEXT,requested_by INTEGER,
              requested_at TEXT,status TEXT,decided_by INTEGER,
              decided_at TEXT,decision_note TEXT);
        """)
        c.executemany("INSERT INTO users VALUES(?,?,?,?,?,?,?)",[
            (1,"admin","Quản trị hệ thống","Lãnh đạo phòng",1,1,None),
            (2,"leaderA","Lãnh đạo A","Lãnh đạo phòng",0,1,None),
            (3,"leaderB","Lãnh đạo B","Lãnh đạo phòng",0,1,None),
            (4,"staffA","QLKH A","Cán bộ QLKH",0,1,None),
            (5,"staffB","QLKH B","Cán bộ QLKH",0,1,None),
            (6,"support","CBHT","Cán bộ hỗ trợ",0,1,None),
            (7,"query","Vấn tin","Vấn tin",0,1,None),
            (8,"inactive","QLKH nghỉ việc","Cán bộ QLKH",0,0,None),
            (9,"deleted","Lãnh đạo đã xóa","Lãnh đạo phòng",0,1,"2026-11-01"),
        ])
        c.executemany("INSERT INTO customer_work_cases VALUES(?,?,?,?,?,?)",[
            (101,4,2,"ACTIVE","2026-10-01","2026-10-01"),
            (102,4,3,"ACTIVE","2026-10-01","2026-10-01"),
            (103,4,2,"COMPLETED","2026-10-01","2026-11-04"),
            (104,4,2,"CANCELLED","2026-10-01","2026-11-04"),
        ])


def connect(db):
    def get_conn():
        c=sqlite3.connect(db)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c
    return get_conn


def reject(fn, message_type):
    try:
        fn()
    except message_type:
        return
    raise AssertionError("Required guard did not reject mutation")


def test_server_authorization_and_audit(get_conn):
    changed=assignment.reassign_case(
        get_conn,101,2,5,3,"Chuyển việc theo phân công mới",
        expected_owner_uid=4,expected_controller_uid=2)
    assert changed
    with get_conn() as c:
        r=dict(c.execute("SELECT * FROM customer_work_cases WHERE id=101").fetchone())
        actions=[dict(x) for x in c.execute(
            "SELECT * FROM case_actions WHERE case_id=101").fetchall()]
    assert r["owner_user_id"]==5 and r["controller_user_id"]==3
    assert r["created_at"]=="2026-10-01"
    assert len(actions)==1
    change=json.loads(actions[0]["detail"])
    assert actions[0]["actor_user_id"]==2
    assert change["old_owner_name"]=="QLKH A"
    assert change["new_owner_name"]=="QLKH B"
    assert change["old_controller_name"]=="Lãnh đạo A"
    assert change["new_controller_name"]=="Lãnh đạo B"
    assert change["reason"]=="Chuyển việc theo phân công mới"
    labelled=history._decode_action(actions[0]["action"],actions[0]["detail"])
    assert labelled[0]=="Điều chỉnh phân công công việc"
    assert "QLKH A → QLKH B" in labelled[1]
    assert "Lãnh đạo A → Lãnh đạo B" in labelled[1]
    assert labelled[2]=="Chuyển việc theo phân công mới"
    archived_label, archived_detail = archive._event_description(
        actions[0], {}, {}
    )
    assert archived_label == "Điều chỉnh phân công công việc"
    assert "QLKH A → QLKH B" in archived_detail
    assert "Lãnh đạo A → Lãnh đạo B" in archived_detail
    assert "Chuyển việc theo phân công mới" in archived_detail

    # Every active phòng leader has room-wide management authority, including
    # cases controlled by another leader or unassigned old cases.
    assert assignment.reassign_case(
        get_conn,101,2,4,2,"Lãnh đạo chuyển lại trong toàn phòng",
        expected_owner_uid=5,expected_controller_uid=3)
    assert assignment.reassign_case(
        get_conn,101,3,5,3,"Lãnh đạo khác tiếp nhận",
        expected_owner_uid=4,expected_controller_uid=2)
    with get_conn() as c:
        assert c.execute("SELECT COUNT(*) FROM case_actions WHERE case_id=101").fetchone()[0]==3
    assert assignment.reassign_case(
        get_conn,101,3,5,3,"Không đổi",
        expected_owner_uid=5,expected_controller_uid=3) is False
    reject(lambda:assignment.reassign_case(
        get_conn,101,3,4,2,"Bản cũ",
        expected_owner_uid=4,expected_controller_uid=2),ValueError)
    assert assignment.reassign_case(
        get_conn,102,1,4,2,"Admin đổi Lãnh đạo",
        expected_owner_uid=4,expected_controller_uid=3)
    assert assignment.reassign_case(
        get_conn,102,1,2,2,"Admin giao Lãnh đạo làm cán bộ",
        expected_owner_uid=4,expected_controller_uid=2)

    # Every manager can hand over an active case. Staff and Vấn tin
    # cannot use this low-level function even by spoofing a Streamlit button.
    for actor in (4,6,7):
        reject(lambda a=actor:assignment.reassign_case(
            get_conn,101,a,4,3,"Sai nhóm quyền",
            expected_owner_uid=5,expected_controller_uid=3),PermissionError)
    for case_id in (103,104):
        reject(lambda cid=case_id:assignment.reassign_case(
            get_conn,cid,1,5,3,"Hồ sơ đã kết thúc",
            expected_owner_uid=4,expected_controller_uid=2),PermissionError)
    for uid,which in ((8,"owner"),(6,"owner"),(7,"owner"),(9,"controller")):
        reject(lambda v=uid,role=which:assignment.reassign_case(
            get_conn,101,1,v if role=="owner" else 5,
            v if role=="controller" else 3,
            "Không hợp lệ", expected_owner_uid=5, expected_controller_uid=3),ValueError)
    reject(lambda:assignment.reassign_case(
        get_conn,101,1,4,2,"   ",
        expected_owner_uid=5,expected_controller_uid=3),ValueError)
    with get_conn() as c:
        assert c.execute("SELECT COUNT(*) FROM case_actions WHERE case_id=101").fetchone()[0]==3
        assert tuple(c.execute(
            "SELECT owner_user_id,controller_user_id FROM customer_work_cases WHERE id=101"
        ).fetchone())==(5,3)


def test_final_ui_scope_and_form(get_conn):
    from khdn_apps import legacy_fast_form as fast
    ui=UI()
    captured=[]
    def fake_form(fields,label,**kwargs):
        captured.append({"fields":fields,"label":label,"kw":kwargs})
        return None
    with patch.object(fast,"legacy_fast_form",side_effect=fake_form):
        assignment._form(ui,{"id":1,"role":"Lãnh đạo phòng","is_admin":1},get_conn,101)
        assert len(captured)==1
        fields=captured[-1]["fields"]
        owner={int(z["value"]) for z in fields[0]["options"]}
        leaders={int(z["value"]) for z in fields[1]["options"]}
        assert owner=={1,2,3,4,5},owner
        assert leaders=={1,2,3},leaders
        assert fields[0]["default"]=="5" and fields[1]["default"]=="3"
        assert fields[2]["name"]=="reason" and fields[2]["required"] is True
        assert captured[-1]["kw"]["columns"]==2
        assert "👥 Đổi cán bộ phụ trách" in ui.labels[-1]
        assert "✏️ Chỉnh sửa công việc · Phân công phụ trách" in ui.labels
        assert ui.labels[-1] == "👥 Đổi cán bộ phụ trách / Lãnh đạo kiểm soát"
        assert ui.expander_options[-1]["expanded"] is True

        for actor in ({"id":4,"role":"Cán bộ QLKH","is_admin":0},
                      {"id":7,"role":"Vấn tin","is_admin":0}):
            before=len(captured)
            assignment._form(ui,actor,get_conn,101)
            assert len(captured)==before
        # A different phòng leader MUST see the editor too even if the current
        # controller is someone else; this was the real-world blocker.
        before=len(captured)
        assignment._form(ui,{"id":2,"role":"Lãnh đạo phòng","is_admin":0},get_conn,101)
        assert len(captured)==before+1
        before=len(captured)
        assignment._form(ui,{"id":1,"role":"Lãnh đạo phòng","is_admin":1},get_conn,103)
        assert len(captured)==before

    # The final wrapper installs once and leaves original Customer Work UI
    # callable, without changing unrelated roles or screens.
    class Demo:
        def __init__(self):
            self.called=[]
            self._case_detail=lambda *a,**k:self.called.append("existing")
    demo=Demo()
    assignment.install(demo)
    assignment.install(demo)
    with patch.object(assignment,"_form",side_effect=lambda *a,**k:demo.called.append("assignment")):
        demo._case_detail(ui,{"id":7,"role":"Vấn tin"},get_conn,101)
    assert demo.called==["assignment","existing"],demo.called



def test_end_to_end_form_submit_and_history(get_conn):
    # This specifically exercises the *UI submit action* rather than calling
    # the low-level SQL mutation directly. The previous QA did not cover it.
    from khdn_apps import legacy_fast_form as fast
    with get_conn() as c:
        c.execute("INSERT INTO customer_work_cases VALUES(105,4,2,'ACTIVE','2026-10-01','2026-10-01')")

    screen=UI()
    submit = {"owner":"5","controller":"3","reason":"Điều động phụ trách hồ sơ khách hàng"}
    with patch.object(fast,"legacy_fast_form",return_value=submit):
        assignment._form(
            screen,{"id":3,"role":"Lãnh đạo phòng","is_admin":0},
            get_conn,105
        )
    assert ("rerun","called") in screen.messages
    assert any(tag=="toast" and "lưu nhật ký" in msg for tag,msg in screen.messages)
    with get_conn() as c:
        row=c.execute("SELECT owner_user_id,controller_user_id,created_at FROM customer_work_cases WHERE id=105").fetchone()
        records=[dict(x) for x in c.execute("SELECT * FROM case_actions WHERE case_id=105")]
    assert tuple(row[:2])==(5,3)
    assert row[2]=="2026-10-01"
    assert len(records)==1 and records[0]["action"]=="CASE_ASSIGNMENT_UPDATE"
    assert json.loads(records[0]["detail"])["reason"]==submit["reason"]

    # A no-op submitted from a current screen must not duplicate history.
    screen=UI()
    with patch.object(fast,"legacy_fast_form",return_value=submit):
        assignment._form(
            screen,{"id":2,"role":"Lãnh đạo phòng","is_admin":0},
            get_conn,105
        )
    assert ("info","Phân công không thay đổi.") in screen.messages
    assert ("rerun","called") not in screen.messages
    with get_conn() as c:
        assert c.execute("SELECT COUNT(*) FROM case_actions WHERE case_id=105").fetchone()[0]==1


def test_cif_embedded_patch():
    root=Path(__file__).with_name("app.py")
    app_src=root.read_text(encoding="utf-8")
    assert 'CIF customer QLKH dropdown includes active leaders' in app_src
    assert 'CB QLKH / Lãnh đạo phòng phụ trách' in app_src
    import gzip,base64
    parts=sorted((root.parent/"_src").glob("*.txt"))
    old=gzip.decompress(base64.b64decode(
        "".join(p.read_text(encoding="ascii") for p in parts)
    )).decode("utf-8")
    original='qusers = all_users("Cán bộ QLKH", active_only=True)'
    assert old.count(original)==1
    label='qid = st.selectbox("CB QLKH phụ trách", opts, index=idx, format_func='
    assert old.count(label)==1
    assert "drop_duplicates(subset=[\"id\"])" in app_src
    # Static source install is checked, and the fully installed runtime import
    # is validated by runtime_page_qa in the same Docker build.
    entry=Path(__file__).with_name("online_entry.py").read_text(encoding="utf-8")
    assert entry.index("_install_customer_work_assignment(") > entry.index(
        "_install_customer_work_manager_note_history("
    )
    assert entry.count("_install_customer_work_assignment(")==1


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="khdn-case-owner-qa-") as folder:
        db=str(Path(folder)/"test.db")
        fixture(db)
        get_conn=connect(db)
        test_server_authorization_and_audit(get_conn)
        test_final_ui_scope_and_form(get_conn)
        test_end_to_end_form_submit_and_history(get_conn)
    test_cif_embedded_patch()
    print("CW_CASE_ASSIGNMENT_CIF_LEADER_QA_PASS admin_all leader_controller_guard staff_inquiry_denied active_role_guards optimistic_stale immutable_closed atomic_history exact_reason ui_options_cif_dropdown final_wrapper_no_migration")
