"""Regression QA for the isolated inquiry-only role and read-only dashboards."""
from __future__ import annotations

import base64
import gzip
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from khdn_apps import authorization
from khdn_apps import inquiry_readonly_role as inquiry


class FakeUI:
    def __init__(self, logout=False):
        self.session_state = {"main_page": "admin", "main_section": "ops", "cw_case_id": 12}
        self.sidebar = self
        self.messages = []
        self.logout = logout
        self.buttons = []

    def markdown(self, message, *args, **kwargs): self.messages.append(("markdown", str(message)))
    def caption(self, message, *args, **kwargs): self.messages.append(("caption", str(message)))
    def title(self, message, *args, **kwargs): self.messages.append(("title", str(message)))
    def subheader(self, message, *args, **kwargs): self.messages.append(("subheader", str(message)))
    def html(self, message, *args, **kwargs): self.messages.append(("html", str(message)))
    def button(self, message, *args, **kwargs):
        self.buttons.append(str(message))
        return self.logout
    def rerun(self): self.messages.append(("rerun", "triggered"))


def sample_cases():
    return [
        {"id": 1, "customer_name": "Công ty <script>alert(1)</script>", "title": "A",
         "stage_name": "Thẩm định", "owner_name": "Trâm Anh",
         "is_overdue": False, "is_stage_delayed": False, "open_issue_count": 0},
        {"id": 2, "customer_name": "Khách hàng B", "title": "B",
         "stage_name": "Giải ngân", "owner_name": "Hòa",
         "is_overdue": True, "is_stage_delayed": False, "open_issue_count": 1},
        {"id": 3, "customer_name": "Khách hàng C", "title": "C",
         "stage_name": "Thẩm định", "owner_name": "Hòa",
         "is_overdue": False, "is_stage_delayed": True, "open_issue_count": 1},
    ]


def qa_source_boundary():
    src_dir = Path(__file__).with_name("_src")
    data = "".join(p.read_text(encoding="ascii") for p in sorted(src_dir.glob("*.txt")))
    source = gzip.decompress(base64.b64decode(data)).decode("utf-8")
    patched = inquiry.patch_source(source)
    assert 'if str(u.get("role") or "") == "Vấn tin":' in patched
    assert patched.index('if u.get("must_change_password")') < patched.index('if str(u.get("role") or "") == "Vấn tin"')
    assert patched.index('if str(u.get("role") or "") == "Vấn tin"') < patched.index('sidebar_user(u)', patched.index('def app():'))
    assert 'return render_inquiry(st, u, DB_PATH, LOGGER)' in patched
    try:
        inquiry.patch_source(patched)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Double inquiry source injection was not rejected")
    loader = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
    assert '_inquiry_role_patch_source(_source)' in loader
    assert 'ROLES.append("Vấn tin")' in loader
    admin = Path(__file__).with_name("mobile_admin_restore_perf_patch.py").read_text(encoding="utf-8")
    assert 'role == "Vấn tin" and is_admin' in admin
    assert 'nr == "Vấn tin" and adminflag' in admin


def qa_actual_read_only_connection():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "inquiry.db"
        with sqlite3.connect(path) as c:
            c.execute("CREATE TABLE sample (id INTEGER)")
            c.execute("INSERT INTO sample VALUES (1)")
        checked = []
        def probe(conn, manager, include_completed):
            assert manager is True and include_completed is False
            assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1
            try:
                conn.execute("INSERT INTO sample VALUES (2)")
            except sqlite3.OperationalError:
                checked.append(True)
            else:
                raise AssertionError("Viewer DB connection permitted a mutation")
            return sample_cases()
        assert len(inquiry._room_cases(path, loader=probe)) == 3
        assert checked
        with sqlite3.connect(path) as c:
            assert c.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1


def qa_two_matrices_only():
    st = FakeUI()
    viewer = {"id": 21, "role": "Vấn tin", "is_admin": 0}
    with patch.object(inquiry, "_room_cases", return_value=sample_cases()):
        inquiry.render_inquiry(st, viewer, "/readonly.db")
    headings = [x for tag, x in st.messages if tag == "subheader"]
    assert headings == ["Theo mục công việc · toàn phòng", "Theo cán bộ · toàn phòng"], headings
    html = [x for tag, x in st.messages if tag == "html"]
    assert len(html) == 2
    assert not any("<script>" in t for t in html)
    assert "&lt;script&gt;" in "".join(html)
    assert st.buttons == ["Đăng xuất"], st.buttons
    stage_rows, staff_rows = inquiry._tables(sample_cases())
    assert len(stage_rows) == 2  # two unique stages
    assert len(staff_rows) == 2  # two unique staff
    for name, *columns in staff_rows:
        entries = [item for column in columns for item in column]
        assert all(name not in item for item in entries), (name, entries)
    # Owner names still appear where needed when grouped by *stage*.
    assert any("Trâm Anh" in item for _, *columns in stage_rows
               for column in columns for item in column)
    assert any("Hòa" in item for _, *columns in stage_rows
               for column in columns for item in column)
    assert sum("Khách hàng B · B" == item for _, *columns in staff_rows
               for column in columns for item in column) == 1
    assert "Hòa" not in "".join(str(col) for _, *columns in staff_rows
                                for col in columns)
    assert "main_page" not in st.session_state
    assert not any("Phê duyệt" in x or "Xuất" in x or "Tạo công việc" in x for x in st.buttons)
    for user in ({"role": "Cán bộ QLKH"}, {"role": "Lãnh đạo phòng", "is_admin": 1}):
        try: inquiry.render_inquiry(st, user, "/readonly.db")
        except PermissionError: pass
        else: raise AssertionError("Non-inquiry role allowed in read-only viewer")


def qa_logout_revoke():
    st = FakeUI(logout=True)
    st.session_state.update(user={"id": 21, "role": "Vấn tin"}, some_token="do-not-retain")
    with patch("khdn_apps.device_login.forget", side_effect=lambda path: st.session_state.update(_device_command="CLEAR")) as forget, patch.object(inquiry, "_room_cases") as read:
        inquiry.render_inquiry(st, {"id": 21, "role": "Vấn tin"}, "/readonly.db")
    forget.assert_called_once_with("/readonly.db")
    read.assert_not_called()
    assert st.session_state == {"_device_command": "CLEAR"}
    assert st.messages[-1] == ("rerun", "triggered")


def qa_backend_permission_checks():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "auth.db"
        with sqlite3.connect(path) as c:
            c.execute("CREATE TABLE users(id INTEGER, role TEXT, is_admin INTEGER, active INTEGER, must_change_password INTEGER, deleted_at TEXT)")
            c.execute("INSERT INTO users VALUES(21,'Vấn tin',1,1,0,NULL)")
            c.execute("CREATE TABLE weekly_plan_items(id INTEGER, user_id INTEGER)")
            c.execute("INSERT INTO weekly_plan_items VALUES(3,21)")
            c.execute("CREATE TABLE customer_work_cases(id INTEGER, owner_user_id INTEGER)")
            c.execute("INSERT INTO customer_work_cases VALUES(4,21)")
        with sqlite3.connect(path) as c:
            assert not authorization.manager({"role": "Vấn tin", "is_admin": 1})
            for fn, args in [(authorization.require_weekly_item, (c,3,21)),
                             (authorization.require_case, (c,4,21)),
                             (authorization.require_admin, (path,21))]:
                try: fn(*args)
                except PermissionError: pass
                else: raise AssertionError(f"Read-only viewer authorized: {fn.__name__}")


if __name__ == "__main__":
    qa_source_boundary()
    qa_actual_read_only_connection()
    qa_two_matrices_only()
    qa_logout_revoke()
    qa_backend_permission_checks()
    print("INQUIRY_READONLY_ROLE_QA_PASS source_gate after_password_before_sidebar full_room read_only_sql two_tables escape_html no_actions logout_revoke backend_denials")
