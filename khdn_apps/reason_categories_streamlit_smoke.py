"""Streamlit AppTest smoke QA for reason-category UI and permissions.

This creates an isolated temporary DB and runs simulated Streamlit sessions. External
logo/device-cookie/auto-refresh integrations are skipped so the test focuses on page
rendering, navigation permissions, and the reason-category manager itself.
"""
from pathlib import Path
import base64
import gzip
import os
import sqlite3
import sys
import tempfile

_app_root=str(Path(__file__).resolve().parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0,_app_root)

from streamlit.testing.v1 import AppTest
from khdn_apps.mobile_nav_patch import patch_source as mobile_patch
from khdn_apps.reason_categories_patch import patch_source as reason_patch


def transformed_source():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    source=gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    source=reason_patch(mobile_patch(source))
    # AppTest smoke should not depend on public network/custom browser components.
    source=source.replace("    ensure_bidv_logo()\n","    pass  # AppTest: skip external logo fetch\n",1)
    source=source.replace("    device_login.sync(DB_PATH)\n","    pass  # AppTest: skip device cookie component\n",1)
    source=source.replace("    realtime_refresh_watch(u)\n","    pass  # AppTest: skip fragment auto refresh\n",1)
    return source


def no_exceptions(at,label):
    if len(at.exception):
        msgs=[str(x.value) for x in at.exception]
        raise AssertionError(f"{label} Streamlit exceptions: {msgs}")


def button_labels(at):
    return [str(x.label) for x in at.button]


def run():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="khdn_streamlit_reason_") as td:
        tdir=Path(td)
        db=tdir/"qa.db"
        qa_file=root/"_reason_categories_apptest_runtime.py"
        old_env={k:os.environ.get(k) for k in ("KHDN_DB_PATH","KHDN_DATA_DIR","KHDN_CLOUD_MODE","KHDN_ADMIN_PASSWORD")}
        try:
            os.environ["KHDN_DB_PATH"]=str(db)
            os.environ["KHDN_DATA_DIR"]=str(tdir)
            os.environ["KHDN_CLOUD_MODE"]="0"
            os.environ["KHDN_ADMIN_PASSWORD"]="Admin@123"
            qa_file.write_text(transformed_source(),encoding="utf-8")

            # 1) Anonymous/login screen must render without a blank-page exception.
            at_login=AppTest.from_file(str(qa_file),default_timeout=30).run(timeout=30)
            no_exceptions(at_login,"login")
            login_inputs=[str(x.label) for x in at_login.text_input]
            assert "Tên đăng nhập" in login_inputs and "Mật khẩu" in login_inputs

            # Prepare admin and a non-admin Leader for direct page-state tests.
            with sqlite3.connect(db) as c:
                c.row_factory=sqlite3.Row
                c.execute("UPDATE users SET must_change_password=0 WHERE username='admin'")
                ts="2026-09-12 23:30:00"
                c.execute("""INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at)
                             VALUES('leader_qa','Lãnh đạo QA','x','Lãnh đạo phòng',0,1,0,?,?)""",(ts,ts))
                c.commit()
                admin=dict(c.execute("SELECT * FROM users WHERE username='admin'").fetchone())
                leader=dict(c.execute("SELECT * FROM users WHERE username='leader_qa'").fetchone())

            # 2) Admin reason page: all six Admin functions retained and manager renders.
            at_admin=AppTest.from_file(str(qa_file),default_timeout=30)
            at_admin.session_state["user"]=admin
            at_admin.session_state["main_page"]="admin"
            at_admin.session_state["admin_view"]="reasons"
            at_admin.run(timeout=30)
            no_exceptions(at_admin,"admin reasons")
            labels="\n".join(button_labels(at_admin))
            for expected in ("Người dùng","Khách hàng CIF","Loại công việc","Nhóm nguyên nhân","Audit","Sao lưu"):
                assert expected in labels, f"Admin navigation missing {expected}"
            subs=[str(x.value) for x in at_admin.subheader]
            assert any("Nhóm nguyên nhân trả lại / hủy" in x for x in subs)
            reason_inputs=[str(x.label) for x in at_admin.text_input]
            assert reason_inputs.count("Tên nhóm nguyên nhân mới")==2
            assert not any("Mô tả" in x for x in reason_inputs)

            # 3) Non-admin Leader may manage reasons, but must not receive other Admin functions.
            at_leader_admin=AppTest.from_file(str(qa_file),default_timeout=30)
            at_leader_admin.session_state["user"]=leader
            at_leader_admin.session_state["main_page"]="admin"
            at_leader_admin.session_state["admin_view"]="reasons"
            at_leader_admin.run(timeout=30)
            no_exceptions(at_leader_admin,"leader reasons")
            leader_labels="\n".join(button_labels(at_leader_admin))
            assert "Nhóm nguyên nhân" in leader_labels
            for forbidden in ("👥  Người dùng","🏢  Khách hàng CIF","🧩  Loại công việc","🧾  Audit","💾  Sao lưu"):
                assert forbidden not in leader_labels, f"Leader gained forbidden Admin function: {forbidden}"

            # 4) Leader work-management page remains clean; reason master is not rendered there.
            at_leader_work=AppTest.from_file(str(qa_file),default_timeout=30)
            at_leader_work.session_state["user"]=leader
            at_leader_work.session_state["main_page"]="leader"
            at_leader_work.run(timeout=30)
            no_exceptions(at_leader_work,"leader work")
            work_subs=[str(x.value) for x in at_leader_work.subheader]
            assert not any("Nhóm nguyên nhân" in x for x in work_subs)

            print("KHDN_REASON_STREAMLIT_SMOKE PASS login admin_reasons leader_reason_only leader_work_clean",flush=True)
        finally:
            try:
                qa_file.unlink(missing_ok=True)
            except Exception:
                pass
            for k,v in old_env.items():
                if v is None:
                    os.environ.pop(k,None)
                else:
                    os.environ[k]=v


if __name__=="__main__":
    run()
