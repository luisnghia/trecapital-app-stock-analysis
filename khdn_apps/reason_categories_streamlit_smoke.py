"""Streamlit AppTest smoke QA for reason-category UI and V2.14-style catalog render."""
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
from khdn_apps.performance_patch import patch_source as performance_patch
from khdn_apps.input_batch_patch import patch_source as input_batch_patch


def transformed_source():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    source=gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    source=input_batch_patch(performance_patch(reason_patch(mobile_patch(source))))
    source=source.replace("    ensure_bidv_logo()\n","    pass  # AppTest: skip external logo fetch\n",1)
    source=source.replace("    device_login.sync(DB_PATH)\n","    pass  # AppTest: skip device cookie component\n",1)
    source=source.replace("        realtime_refresh_watch(u)\n","        pass  # AppTest: skip fragment auto refresh\n",1)
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
        tdir=Path(td); db=tdir/"qa.db"; qa_file=root/"_reason_categories_apptest_runtime.py"
        old_env={k:os.environ.get(k) for k in ("KHDN_DB_PATH","KHDN_DATA_DIR","KHDN_CLOUD_MODE","KHDN_ADMIN_PASSWORD")}
        try:
            os.environ["KHDN_DB_PATH"]=str(db); os.environ["KHDN_DATA_DIR"]=str(tdir); os.environ["KHDN_CLOUD_MODE"]="0"; os.environ["KHDN_ADMIN_PASSWORD"]="Admin@123"
            qa_file.write_text(transformed_source(),encoding="utf-8")

            at_login=AppTest.from_file(str(qa_file),default_timeout=30).run(timeout=30)
            no_exceptions(at_login,"login")
            login_inputs=[str(x.label) for x in at_login.text_input]
            assert "Tên đăng nhập" in login_inputs and "Mật khẩu" in login_inputs

            with sqlite3.connect(db) as c:
                c.row_factory=sqlite3.Row
                c.execute("UPDATE users SET must_change_password=0 WHERE username='admin'")
                ts="2026-09-13 17:00:00"
                c.execute("""INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at)
                             VALUES('leader_qa','Lãnh đạo QA','x','Lãnh đạo phòng',0,1,0,?,?)""",(ts,ts))
                admin_id=int(c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0])
                c.execute("""INSERT INTO reason_categories(reason_type,name,active,created_by,created_at,updated_at)
                             VALUES('RETURN','QA trả lại',1,?,?,?)""",(admin_id,ts,ts))
                c.commit(); admin=dict(c.execute("SELECT * FROM users WHERE username='admin'").fetchone()); leader=dict(c.execute("SELECT * FROM users WHERE username='leader_qa'").fetchone())

            at_admin=AppTest.from_file(str(qa_file),default_timeout=30)
            at_admin.session_state["user"]=admin; at_admin.session_state["main_page"]="admin"; at_admin.session_state["admin_view"]="reasons"
            at_admin.run(timeout=30); no_exceptions(at_admin,"admin reasons")
            labels="\n".join(button_labels(at_admin))
            for expected in ("Người dùng","Khách hàng CIF","Loại công việc","Nhóm nguyên nhân","Audit","Sao lưu"):
                assert expected in labels, f"Admin navigation missing {expected}"
            reason_inputs=[str(x.label) for x in at_admin.text_input]
            assert reason_inputs.count("Tên nhóm nguyên nhân mới")==1, reason_inputs
            assert not any("Mô tả" in x for x in reason_inputs)
            reason_radio_labels=[str(x.label) for x in at_admin.radio]
            assert "Danh mục nguyên nhân" in reason_radio_labels
            assert "Thao tác" not in reason_radio_labels
            assert len(at_admin.dataframe)==1, "Selected reason catalog should render one table like the simple V2.14 page"

            at_types=AppTest.from_file(str(qa_file),default_timeout=30)
            at_types.session_state["user"]=admin; at_types.session_state["main_page"]="admin"; at_types.session_state["admin_view"]="types"
            at_types.run(timeout=30); no_exceptions(at_types,"admin task types")
            type_inputs=[str(x.label) for x in at_types.text_input]
            assert "Tên công việc mới" in type_inputs, type_inputs
            assert len(at_types.dataframe)==1, "Task type page should show its table above the native create form"
            assert not any(str(x.label)=="Thao tác" for x in at_types.radio)

            at_leader_admin=AppTest.from_file(str(qa_file),default_timeout=30)
            at_leader_admin.session_state["user"]=leader; at_leader_admin.session_state["main_page"]="admin"; at_leader_admin.session_state["admin_view"]="reasons"
            at_leader_admin.run(timeout=30); no_exceptions(at_leader_admin,"leader reasons")
            leader_labels="\n".join(button_labels(at_leader_admin))
            assert "Nhóm nguyên nhân" in leader_labels
            for forbidden in ("👥  Người dùng","🏢  Khách hàng CIF","🧩  Loại công việc","🧾  Audit","💾  Sao lưu"):
                assert forbidden not in leader_labels, f"Leader gained forbidden Admin function: {forbidden}"

            at_leader_work=AppTest.from_file(str(qa_file),default_timeout=30)
            at_leader_work.session_state["user"]=leader; at_leader_work.session_state["main_page"]="leader"
            at_leader_work.run(timeout=30); no_exceptions(at_leader_work,"leader work")
            work_subs=[str(x.value) for x in at_leader_work.subheader]
            assert not any("Nhóm nguyên nhân" in x for x in work_subs)

            print("KHDN_REASON_STREAMLIT_SMOKE PASS login admin_reasons_v214 admin_types_v214 leader_reason_only leader_work_clean",flush=True)
        finally:
            try: qa_file.unlink(missing_ok=True)
            except Exception: pass
            for k,v in old_env.items():
                if v is None: os.environ.pop(k,None)
                else: os.environ[k]=v


if __name__=="__main__":
    run()
