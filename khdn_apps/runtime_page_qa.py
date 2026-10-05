"""Open the installed production entrypoint using an isolated temporary database."""
import os
from pathlib import Path
import tempfile


def _weekly_focus_submission_ui():
    """Exercise the final overlay stack and persist a valid submission in QA DB."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app as app

    for name, category_ids, disabled in (
        ("same_category", [101, 101, 101], True),
        ("two_categories", [101, 101, 102], True),
        ("three_categories", [101, 101, 102, 103], False),
    ):
        script = """
import streamlit as st
from datetime import date, timedelta
from khdn_apps import app as app
from khdn_apps import weekly_plan as core
from khdn_apps import weekly_priority_policy_patch as policy
app.init_db()
policy._ensure_schema(core, app.get_conn, app.LOGGER)
ws = date(2026, 10, 5)
with app.get_conn() as c:
    u = dict(c.execute('SELECT * FROM users ORDER BY id LIMIT 1').fetchone())
    # The submission screen is shared by all roles; render its staff view.
    u.update(role='Cán bộ QLKH', is_admin=0)
    pid = core.ensure_plan(c, int(u['id']), ws)
    if not st.session_state.get('weekly_focus_qa_seeded'):
        c.execute('DELETE FROM weekly_plan_items WHERE plan_id=?', (pid,))
        c.execute("UPDATE weekly_plans SET workflow_status='NHAP' WHERE id=?", (pid,))
        ts = policy._now()
        scope = policy._scope_key(c, int(u['id']))
        for cid in (101, 102, 103):
            c.execute('''INSERT OR IGNORE INTO weekly_focus_categories(
                id,department_key,apply_year,code,name,created_at,updated_at)
                VALUES(?,?,2026,?,?,?,?)''',
                (cid,scope,f'QA{cid}',f'Mục trọng tâm QA {cid}',ts,ts))
        for idx, cid in enumerate(CATEGORY_IDS):
            c.execute('''INSERT INTO weekly_plan_items(
                plan_id,user_id,work_date,title,category,purposes_json,status,
                priority_quadrant,focus_category_id,focus_code_snapshot,
                focus_name_snapshot,created_at,updated_at)
                VALUES(?,?,?,?,?,'[]','PLANNED',2,?,?,?,?,?)''',
                (pid,int(u['id']),(ws+timedelta(days=idx)).isoformat(),
                 f'Công việc QA {idx+1}','Kế hoạch tuần',cid,f'QA{cid}',
                 f'Mục trọng tâm QA {cid}',ts,ts))
        st.session_state['weekly_focus_qa_seeded'] = True
    plan = dict(c.execute('SELECT * FROM weekly_plans WHERE id=?', (pid,)).fetchone())
    items = core.load_items(c, int(u['id']), ws)
    focus = policy._focus_categories(c, policy._scope_key(c, int(u['id'])), ws.year, False)
policy._render_staff_week(st,u,core,app.get_conn,ws,plan,items,focus,logger=app.LOGGER)
""".replace("CATEGORY_IDS", repr(category_ids))
        page = AppTest.from_string(script, default_timeout=30).run()
        assert not page.exception, (name, [e.message for e in page.exception])
        expected = f"{len(set(category_ids))} mục"
        assert any(x.label == "Q2 · Trọng tâm" and x.value == expected for x in page.metric), name
        submit = next(x for x in page.button if x.label == "📤 Nộp kế hoạch")
        assert submit.disabled == disabled, (name, submit.disabled)
        if not disabled:
            submit.click().run()
            assert not page.exception, (name, [e.message for e in page.exception])
            with app.get_conn() as c:
                plan = c.execute("SELECT id,workflow_status FROM weekly_plans WHERE week_start='2026-10-05'").fetchone()
                assert plan['workflow_status'] == 'DA_NOP', dict(plan)
                pending = c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE plan_id=? AND approval_status='PENDING'", (plan['id'],)).fetchone()[0]
                assert pending == len(category_ids), pending
    print("KHDN_WEEKLY_FOCUS_SUBMISSION_UI_QA PASS distinct_categories final_overlay_stack submit_persistence")


def run():
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="khdn-page-qa-") as folder:
        os.environ["KHDN_DATA_DIR"] = folder
        os.environ["KHDN_DB_PATH"] = str(Path(folder) / "qa.db")
        os.environ["KHDN_REQUIRE_VOLUME"] = "0"
        import secrets
        os.environ["KHDN_ADMIN_PASSWORD"] = secrets.token_urlsafe(24)
        from streamlit.testing.v1 import AppTest
        page = AppTest.from_file(str(root / "online_entry.py"), default_timeout=30).run()
        assert not page.exception, [e.message for e in page.exception]
        page.run()
        assert not page.exception, [e.message for e in page.exception]

        from khdn_apps.action_feedback_qa import run_feedback_qa, installed_feedback_ui
        run_feedback_qa()
        installed_feedback_ui()

        # Regression guard: the final runtime must own Catalog after reruns.  The
        # Q2-first weekly policy intentionally supersedes the older V3 hotfix and
        # renders the same native command-button navigation without st.tabs().
        from khdn_apps import customer_work_ui as customer_work_ui
        catalog_renderer = customer_work_ui.render_catalog_page
        allowed = {
            "khdn_apps.planning_usability_v3_hotfix",
            "khdn_apps.weekly_priority_policy_patch",
        }
        assert catalog_renderer.__module__ in allowed, (
            "Catalog renderer fell back after rerun",
            catalog_renderer.__module__,
            getattr(catalog_renderer, "__qualname__", ""),
        )
        print(
            "KHDN_CATALOG_RERUN_NAV_QA PASS",
            catalog_renderer.__module__,
            getattr(catalog_renderer, "__qualname__", ""),
        )

        # Render the actual generated settings section, then submit its form.
        import ast
        import textwrap
        catalog = ast.parse((root / "catalog_input_fast_patch.py").read_text(encoding="utf-8"))
        block = next(n.value.value for n in ast.walk(catalog)
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "task_type_block" for t in n.targets))
        settings = textwrap.dedent(block.split('if admin_view == "types":', 1)[1].split("# Exact V2.14", 1)[0])
        script = (
            "import khdn_apps.app as m\n"
            "m.init_db()\n"
            "u = dict(m.qdf('SELECT * FROM users ORDER BY id LIMIT 1').iloc[0])\n"
            "exec(" + repr(settings) + ", dict(vars(m), u=u))\n"
        )
        calendar = AppTest.from_string(script, default_timeout=30).run()
        assert not calendar.exception, [e.message for e in calendar.exception]
        assert any(x.label == "Giờ kết thúc ngày làm việc" for x in calendar.time_input)
        assert any(x.label == "Giờ bắt đầu ngày làm việc" for x in calendar.time_input)
        for item in calendar.checkbox:
            if item.label == "Loại trừ thời gian nghỉ ngoài giờ làm việc":
                item.set_value(True)
        next(x for x in calendar.button if x.label == "Lưu giờ làm việc").click()
        calendar.run()
        assert not calendar.exception, [e.message for e in calendar.exception]
        import sqlite3
        with sqlite3.connect(os.environ["KHDN_DB_PATH"]) as c:
            settings_saved = dict(c.execute("SELECT key,value FROM system_settings").fetchall())
        assert settings_saved["workday_enabled"] == "1"
        assert settings_saved["workday_start"] == "07:30"
        assert settings_saved["workday_end"] == "17:30"
        assert settings_saved["lunch_break_start"] == "11:30"
        assert settings_saved["lunch_break_end"] == "13:30"
        print("KHDN_CALENDAR_SETTINGS_UI_QA PASS render save persistence")

        _weekly_focus_submission_ui()

        from khdn_apps.planning_compliance_qa import installed_dashboard_ui
        installed_dashboard_ui()

        from khdn_apps.room_workload_partition_qa import installed_dashboard_ui as room_workload_ui
        room_workload_ui()

        from khdn_apps.weekly_schedule_export_qa import installed_weekly_ui
        installed_weekly_ui()

        from khdn_apps.weekly_entry_edit_qa import installed_entry_ui, installed_customer_date_ui
        installed_entry_ui()
        installed_customer_date_ui()

        from khdn_apps.customer_contact_edit_qa import installed_contact_ui, browser_contact_messages
        browser_contact_messages()
        installed_contact_ui()

        from khdn_apps.operational_review_table_qa import installed_review_ui
        installed_review_ui()

        print("KHDN_RUNTIME_PAGE_QA PASS initial_open rerun isolated_database")


if __name__ == "__main__":
    run()
