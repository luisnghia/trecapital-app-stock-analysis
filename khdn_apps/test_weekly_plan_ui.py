"""Streamlit AppTest smoke checks for Weekly Plan role-specific UI."""
from __future__ import annotations

from streamlit.testing.v1 import AppTest


HARNESS = r'''
import sqlite3
import tempfile
from pathlib import Path
import streamlit as st
from khdn_apps.weekly_plan_v7 import weekly_plan_page

role = __ROLE__
tmp = tempfile.mkdtemp(prefix="khdn-weekly-ui-")
db = Path(tmp) / "ui.db"

def get_conn():
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

with get_conn() as c:
    c.execute("""CREATE TABLE users(
        id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, role TEXT,
        active INTEGER DEFAULT 1, is_admin INTEGER DEFAULT 0)""")
    c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(1,'ui01','UI Test',?,1,0)", (role,))
    c.commit()

user = {"id": 1, "username": "ui01", "full_name": "UI Test", "role": role, "is_admin": 0}

def page_title(title, subtitle):
    st.markdown(f"## {title}")
    st.caption(subtitle)

weekly_plan_page(user, get_conn, page_title, pill_nav=None)
'''


def _run(role: str):
    script = HARNESS.replace("__ROLE__", repr(role))
    app = AppTest.from_string(script, default_timeout=15)
    app.run(timeout=15)
    if app.exception:
        raise AssertionError(f"Streamlit render failed for {role}: {app.exception}")
    return app


def _radio_options(app):
    if not app.radio:
        return []
    return [str(x) for x in app.radio[0].options]


def main():
    officer = _run("Cán bộ QLKH")
    officer_options = _radio_options(officer)
    assert any("Tuần của tôi" in x for x in officer_options)
    assert any("8 tuần" in x for x in officer_options)
    assert any("Xuất báo cáo" in x for x in officer_options)
    assert not any("Duyệt & đánh giá" in x for x in officer_options)
    assert not any("Tổng quan phòng" in x for x in officer_options)

    # NT1: due-date urgency is derived, not re-entered through a second checkbox.
    checkbox_labels = [str(x.label) for x in officer.checkbox]
    assert not any("Có hạn hoàn thành trong 7 ngày tới" in x for x in checkbox_labels)
    assert any("chỉ tiêu" in x.lower() or "rủi ro" in x.lower() for x in checkbox_labels)

    leader = _run("Lãnh đạo phòng")
    leader_options = _radio_options(leader)
    assert any("Kế hoạch của tôi" in x for x in leader_options)
    assert any("Duyệt & đánh giá" in x for x in leader_options)
    assert any("Trọng tâm Q2" in x for x in leader_options)
    assert any("Tổng quan phòng" in x for x in leader_options)

    denied = _run("Ban Giám đốc")
    assert any("không có quyền" in str(e.value).lower() for e in denied.error)
    assert not denied.radio

    print("KHDN Weekly Plan Streamlit UI smoke tests: OK")


if __name__ == "__main__":
    main()
