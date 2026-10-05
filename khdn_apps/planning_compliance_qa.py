"""Business, permissions, rollback, history persistence and real Excel/UI checks.

All records live in a temporary QA DB. No production data or notifications.
"""
from __future__ import annotations

from datetime import date, datetime
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest

from khdn_apps import planning_compliance as core
from khdn_apps import planning_compliance_ui as ui


class ComplianceQA(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix="khdn-compliance-qa-")
        self.db=Path(self.folder.name)/"qa.db"
        self.now=datetime(2026,10,4,20,0)
        self.week=date(2026,9,21)
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER,created_at TEXT);
                INSERT INTO users VALUES(1,'Admin QA','Lãnh đạo phòng',1,1,'2026-08-01 07:00:00');
                INSERT INTO users VALUES(2,'Cán bộ A QA','Cán bộ QLKH',0,1,'2026-08-01 07:00:00');
                INSERT INTO users VALUES(3,'Cán bộ B QA','Cán bộ hỗ trợ',0,1,'2026-08-01 07:00:00');
                INSERT INTO users VALUES(4,'Lãnh đạo QA','Lãnh đạo phòng',0,1,'2026-08-01 07:00:00');
                CREATE TABLE system_settings(key TEXT PRIMARY KEY,value TEXT);
                INSERT INTO system_settings VALUES('workday_end','17:30');
                CREATE TABLE weekly_plans(id INTEGER PRIMARY KEY,user_id INTEGER,week_start TEXT,
                    workflow_status TEXT,submitted_at TEXT,created_at TEXT);
                INSERT INTO weekly_plans VALUES(11,2,'2026-09-21','DA_DUYET','2026-09-21 10:00:00','2026-09-20 16:00:00');
                INSERT INTO weekly_plans VALUES(12,3,'2026-09-21','NHAP',NULL,'2026-09-20 16:00:00');
                CREATE TABLE weekly_plan_actions(id INTEGER PRIMARY KEY,actor_user_id INTEGER,action TEXT,detail TEXT,created_at TEXT);
                INSERT INTO weekly_plan_actions VALUES(1,2,'PLAN_SUBMIT','week=2026-09-21','2026-09-21 09:00:00');
                INSERT INTO weekly_plan_actions VALUES(2,2,'PLAN_SUBMIT','week=2026-09-21','2026-09-21 10:00:00');
                CREATE TABLE weekly_plan_items(id INTEGER PRIMARY KEY,plan_id INTEGER,user_id INTEGER,work_date TEXT,
                    title TEXT,customer_text TEXT,status TEXT,expected_complete_date TEXT,completed_at TEXT,
                    controller_user_id INTEGER,focus_name_snapshot TEXT,created_at TEXT,updated_at TEXT);
                CREATE TABLE weekly_cycle_notification_events(event_code TEXT,subject_key TEXT,user_id INTEGER,created_at TEXT);
            """)
            core.ensure_schema(c,datetime(2026,9,20,16,0))

    def tearDown(self): self.folder.cleanup()

    def conn(self):
        c=sqlite3.connect(self.db,timeout=10)
        c.row_factory=sqlite3.Row
        return c

    def report(self,uid=1,now=None,start=None,end=None,selected=None):
        return core.build_report(self.conn,{"id":uid},start or self.week,end or self.week,selected,now or self.now)

    def staff(self,report,uid): return next(x for x in report['summary'] if x['user_id']==uid)

    def item(self,iid=101,status='PLANNED',due='2026-09-22',done=None,plan=11,uid=2,title='Công việc QA'):
        with self.conn() as c:
            c.execute("INSERT INTO weekly_plan_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (iid,plan,uid,'2026-09-21',title,'Khách hàng QA',status,due,done,4,'Mục QA','2026-09-21 08:00:00','2026-09-21 08:00:00'))

    def test_first_submission_survives_return_and_resubmit(self):
        r=self.report(); s=self.staff(r,2)
        self.assertEqual((s['on_time'],s['late']),(1,0))
        row=next(x for x in r['submissions'] if x['user_id']==2)
        self.assertEqual(row['first_submitted_at'],datetime(2026,9,21,9))
        self.assertEqual(row['submit_count'],2)

    def test_deadline_boundary_and_seconds_round_up(self):
        with self.conn() as c:
            c.execute('DELETE FROM weekly_plan_actions')
            c.execute("UPDATE weekly_plans SET submitted_at='2026-09-21 09:30:00' WHERE id=11")
        self.assertEqual(self.staff(self.report(),2)['on_time'],1)
        # Separate fixture DB to preserve actual immutable prior evidence.
        with self.conn() as c:
            c.execute('DELETE FROM planning_submission_history')
            c.execute("UPDATE weekly_plans SET submitted_at='2026-09-21 09:30:01' WHERE id=11")
        s=self.staff(self.report(),2)
        self.assertEqual((s['late'],s['late_minutes']),(1,1))

    def test_pending_is_not_closed_week_missing(self):
        before=self.staff(self.report(now=datetime(2026,9,21,10,0)),3)
        self.assertEqual((before['pending_overdue'],before['missing']),(1,0))
        exactly=self.staff(self.report(now=datetime(2026,9,25,17,30)),3)
        self.assertEqual(exactly['missing'],0)
        after=self.staff(self.report(now=datetime(2026,9,25,17,30,1)),3)
        self.assertEqual((after['pending_overdue'],after['missing']),(0,1))

    def test_submission_after_week_end_remains_missing(self):
        self.report(now=datetime(2026,9,26,10))
        with self.conn() as c:
            c.execute("UPDATE weekly_plans SET submitted_at='2026-09-28 10:00:00' WHERE id=12")
        s=self.staff(self.report(),3)
        self.assertEqual((s['missing'],s['late']),(1,0))

    def test_unknown_old_weeks_and_retrospective_empty_draft(self):
        with self.conn() as c:
            c.execute("INSERT INTO weekly_plans VALUES(13,2,'2026-09-14','NHAP',NULL,'2026-10-04 19:00:00')")
        r=self.report(start=date(2026,9,14),end=date(2026,9,14))
        s=self.staff(r,2)
        self.assertEqual((s['unknown_weeks'],s['missing']),(1,0))
        self.assertIsNone(s['submission_rate'])

    def test_reminder_is_positive_historical_evidence(self):
        with self.conn() as c:
            c.execute("INSERT INTO weekly_cycle_notification_events VALUES('PLAN_OVERDUE','2026-09-14',3,'2026-09-14 09:31:00')")
        s=self.staff(self.report(start=date(2026,9,14),end=date(2026,9,14)),3)
        self.assertEqual(s['missing'],1)

    def test_new_account_after_deadline_not_penalized(self):
        with self.conn() as c:
            c.execute("INSERT INTO users VALUES(5,'Cán bộ mới QA','Cán bộ QLKH',0,1,'2026-09-22 08:00:00')")
            c.execute("INSERT INTO weekly_plans VALUES(15,5,'2026-09-21','NHAP',NULL,'2026-09-22 09:00:00')")
        s=self.staff(self.report(),5)
        self.assertEqual((s['missing'],s['late'],s['known_weeks']),(0,0,0))

    def test_late_work_keeps_original_deadline_after_extension(self):
        self.item()
        self.report(now=datetime(2026,9,23,10))
        with self.conn() as c:
            c.execute("UPDATE weekly_plan_items SET expected_complete_date='2026-09-29',updated_at='2026-09-24 10:00:00' WHERE id=101")
        r=self.report(now=datetime(2026,9,24,11)); s=self.staff(r,2)
        self.assertEqual((s['ever_overdue'],s['open_overdue']),(1,0))
        e=next(x for x in r['events'] if x['item_id']==101)
        self.assertEqual((e['deadline_at'].date(),e['late_days']),(date(2026,9,22),2))
        self.assertEqual(r['work'][0]['first_due'],date(2026,9,22))

    def test_completion_and_missing_timestamps(self):
        self.item(status='DONE',done='2026-09-23 11:00:00')
        self.item(102,status='DONE',done=None)
        s=self.staff(self.report(),2)
        self.assertEqual((s['completed'],s['completed_late'],s['completion_unknown']),(2,1,1))
        self.assertEqual(s['ontime_work_rate'],0)

    def test_completion_uses_actual_time_instead_of_later_entry_time(self):
        self.item()
        with self.conn() as c:
            c.execute("UPDATE weekly_plan_items SET status='DONE',completed_at='2026-09-22 16:00:00',updated_at='2026-09-24 10:00:00' WHERE id=101")
        r=self.report()
        self.assertEqual(self.staff(r,2)['ever_overdue'],0)
        self.assertEqual(self.staff(r,2)['ontime_work_rate'],1)

    def test_completed_overdue_resolves_at_actual_completion(self):
        self.item(); self.report(now=datetime(2026,9,23,10))
        with self.conn() as c:
            c.execute("UPDATE weekly_plan_items SET status='DONE',completed_at='2026-09-23 16:00:00',updated_at='2026-09-25 10:00:00' WHERE id=101")
        r=self.report()
        event=next(x for x in r['events'] if x['item_id']==101)
        self.assertEqual((event['actual_at'],event['late_days']),(datetime(2026,9,23,16),1))

    def test_live_roster_counts_absence_without_any_plan_and_freezes_cutoff(self):
        with self.conn() as c:
            c.execute("DELETE FROM weekly_plans WHERE id=12")
            core.capture(c,datetime(2026,9,21,9))
            c.execute("UPDATE system_settings SET value='18:00' WHERE key='workday_end'")
        r=self.report()
        self.assertEqual(self.staff(r,3)['missing'],1)
        row=next(x for x in r['submissions'] if x['user_id']==3)
        self.assertEqual((row['source'],row['week_close_at']),('LIVE',datetime(2026,9,25,17,30)))

    def test_unapproved_work_is_not_counted_as_overdue(self):
        self.item(plan=12,uid=3)
        s=self.staff(self.report(),3)
        self.assertEqual((s['work_total'],s['ever_overdue'],s['open_overdue']),(0,0,0))

    def test_cancel_delete_and_transaction_rollback_preserve_evidence(self):
        self.item(); self.report()
        with self.conn() as c:
            before=c.execute('SELECT COUNT(*) FROM planning_work_changes').fetchone()[0]
            c.execute('SAVEPOINT test')
            c.execute("UPDATE weekly_plan_items SET expected_complete_date='2026-10-08',updated_at='2026-10-04 20:00:00' WHERE id=101")
            c.execute('ROLLBACK TO test'); c.execute('RELEASE test')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM planning_work_changes').fetchone()[0],before)
            c.execute("UPDATE weekly_plan_items SET status='CANCELLED',updated_at='2026-10-04 20:00:00' WHERE id=101")
        self.assertEqual(self.staff(self.report(),2)['ever_overdue'],1)
        with self.conn() as c: c.execute('DELETE FROM weekly_plan_items WHERE id=101')
        r=self.report(now=datetime(2026,10,5,20))
        self.assertEqual(self.staff(r,2)['ever_overdue'],1)
        self.assertTrue(any(x['item_id']==101 for x in r['events']))

    def test_initial_save_fill_is_not_deadline_extension(self):
        self.item(due=None)
        with self.conn() as c:
            c.execute("UPDATE weekly_plan_items SET expected_complete_date='2026-09-29',updated_at='2026-09-21 08:00:01' WHERE id=101")
        r=self.report(now=datetime(2026,9,24,11))
        self.assertEqual(self.staff(r,2)['ever_overdue'],0)

    def test_capture_restart_idempotent(self):
        self.item(); self.report()
        with self.conn() as c:
            before={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['planning_work_changes','planning_work_incidents','planning_submission_history','planning_submission_incidents']}
        core.capture_db(self.db,self.now); core.capture_db(self.db,self.now)
        with self.conn() as c:
            after={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in before}
        self.assertEqual(before,after)

    def test_permissions_admin_only_and_current_database(self):
        self.assertEqual({x['user_id'] for x in self.report()['summary']},{2,3})
        for uid in (2,3,4):
            with self.assertRaises(PermissionError): self.report(uid=uid)
        with self.assertRaises(PermissionError): core.build_report(self.conn,{'id':2,'is_admin':1},self.week,self.week,now=self.now)
        snapshot=self.report()
        with self.conn() as c: c.execute('UPDATE users SET is_admin=0 WHERE id=1')
        with self.assertRaises(PermissionError): ui.export_excel(self.conn,{'id':1,'is_admin':1},snapshot)
        with self.conn() as c: c.execute('UPDATE users SET is_admin=1,active=0 WHERE id=1')
        with self.assertRaises(PermissionError): self.report()

    def test_selected_staff_scope_and_excel_integrity(self):
        self.item(title='=HYPERLINK("https://invalid.example","QA")')
        r=self.report(selected=[2]); data=ui.export_excel(self.conn,{'id':1},r)
        self.assertEqual({x['user_id'] for x in r['summary']},{2})
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(data))
        self.assertEqual(book.sheetnames,['Tong_hop_can_bo','Chi_tiet_nop_ke_hoach','Chi_tiet_cong_viec','Lich_su_qua_han'])
        self.assertEqual(book['Chi_tiet_cong_viec']['E6'].data_type,'s')
        self.assertTrue(book['Chi_tiet_cong_viec']['E6'].value.startswith('=HYPERLINK'))
        self.assertEqual(book['Chi_tiet_nop_ke_hoach']['C6'].value.date(),self.week)
        self.assertEqual(book['Tong_hop_can_bo']['K6'].number_format,'0.0%')
        for sheet in book:
            self.assertEqual(sheet.freeze_panes,'C6')
            self.assertTrue(sheet.auto_filter.ref.startswith('A5:'))
            self.assertFalse(any(c.data_type=='f' for row in sheet for c in row))
        with self.assertRaises(PermissionError): ui.export_excel(self.conn,{'id':2},r)
        with self.assertRaises(PermissionError): ui.export_excel(self.conn,{'id':4},r)

    def test_timezone(self):
        self.assertEqual(core.parse_dt('2026-09-21T02:30:00+00:00'),datetime(2026,9,21,9,30))

    def test_real_streamlit_filters_download_and_staff_denial(self):
        from streamlit.testing.v1 import AppTest
        script=f"""
import sqlite3, streamlit as st
from khdn_apps import planning_compliance_ui as ui
def conn():
    c=sqlite3.connect({str(self.db)!r}); c.row_factory=sqlite3.Row; return c
ui.render_report(st,{{'id':st.session_state.get('qa_actor',1)}},conn)
"""
        page=AppTest.from_string(script,default_timeout=20).run()
        self.assertFalse(page.exception,[x.message for x in page.exception])
        self.assertTrue(any(x.label=='Xem thống kê' for x in page.button))
        page.date_input[0].set_value(self.week); page.date_input[1].set_value(self.week)
        next(x for x in page.button if x.label=='Xem thống kê').click().run()
        self.assertFalse(page.exception,[x.message for x in page.exception])
        self.assertTrue(any(x.label=='⬇ Xuất Excel đánh giá cán bộ' for x in page.get('download_button')))
        self.assertTrue(any(x.label=='Tuần không nộp' and x.value=='1' for x in page.metric))
        for uid in (2,3,4):
            page.session_state['qa_actor']=uid; page.run()
            self.assertFalse(page.exception,[x.message for x in page.exception])
            self.assertFalse(page.get('download_button'))
            self.assertFalse(page.metric)


def installed_dashboard_ui():
    """Both downloads are Admin-only in the final installed dashboard."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    script="""
import streamlit as st
from khdn_apps import app
from khdn_apps import weekly_plan as weekly_core
from khdn_apps import weekly_priority_policy_patch as policy
from khdn_apps import customer_work_ui
app.init_db()
policy._ensure_schema(weekly_core,app.get_conn,app.LOGGER)
with app.get_conn() as c:
    ts=policy._now()
    for username,role in [('compliance_leader_qa','Lãnh đạo phòng'),('compliance_staff_qa','Cán bộ QLKH'),('compliance_support_qa','Cán bộ hỗ trợ')]:
        c.execute('''INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at)
            VALUES(?,?,?, ?,0,1,?,?)''',(username,username,'QA_NO_LOGIN',role,ts,ts))
    actor=st.session_state.get('compliance_actor','compliance_leader_qa')
    if actor=='admin':
        if st.session_state.get('compliance_admin_id'):
            u=dict(c.execute('SELECT * FROM users WHERE id=?',(st.session_state['compliance_admin_id'],)).fetchone())
        else:
            u=dict(c.execute('SELECT * FROM users WHERE is_admin=1 ORDER BY id LIMIT 1').fetchone())
            st.session_state['compliance_admin_id']=u['id']
    else:
        u=dict(c.execute('SELECT * FROM users WHERE username=?',(actor,)).fetchone())
    profiles=st.session_state.setdefault('compliance_profiles',{})
    u=profiles.setdefault(actor,u)
    st.session_state['compliance_viewer_id']=u['id']
customer_work_ui.render_leader_dashboard(st,u,app.get_conn,logger=app.LOGGER)
"""
    page=AppTest.from_string(script,default_timeout=30).run()

    def check_exports(allowed):
        assert not page.exception,[x.message for x in page.exception]
        assert any(x.label=='Xem thống kê' for x in page.button)==allowed
        assert any(x.label=='⬇️ Xuất toàn bộ Công việc khách hàng · Excel' for x in page.get('download_button'))==allowed

    check_exports(False)
    assert page.title,'The leader lost the room dashboard together with exports'
    for actor in ('compliance_staff_qa','compliance_support_qa'):
        page.session_state['compliance_actor']=actor; page.run(); check_exports(False)
    page.session_state['compliance_actor']='admin'; page.run()
    check_exports(True)
    next(x for x in page.button if x.label=='Xem thống kê').click().run()
    assert not page.exception,[x.message for x in page.exception]
    assert any(x.label=='⬇ Xuất Excel đánh giá cán bộ' for x in page.get('download_button'))
    uid=page.session_state['compliance_viewer_id']
    report=page.session_state[f'planning_compliance_report_{uid}']['report']
    assert any(x['name']=='compliance_staff_qa' for x in report['summary'])
    # The page intentionally retains its old Admin profile. Current DB rights
    # still control both download entry points and clear prepared data.
    with app.get_conn() as c:
        old=dict(c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
        c.execute("UPDATE users SET is_admin=0,role='Lãnh đạo phòng' WHERE id=?",(uid,))
    try:
        page.run(); check_exports(False)
        assert page.title,'A former Admin who is a leader must retain room control'
        assert not any(x.label=='⬇ Xuất Excel đánh giá cán bộ' for x in page.get('download_button'))
        assert f'planning_compliance_report_{uid}' not in page.session_state
        assert 'p11_customer_work_excel_cache' not in page.session_state
        from khdn_apps import planning_operational_phase11_patch as p11
        assert not p11._customer_work_export_allowed(app.get_conn,{'id':uid,'is_admin':1})
        try:
            ui.export_excel(app.get_conn,{'id':uid,'is_admin':1},report)
        except PermissionError:
            pass
        else:
            raise AssertionError('Revoked Admin exported the old statistics snapshot')
    finally:
        with app.get_conn() as c:
            c.execute('UPDATE users SET is_admin=?,role=? WHERE id=?',(old['is_admin'],old['role'],uid))
    print('PLANNING_COMPLIANCE_INSTALLED_DASHBOARD_QA_PASS admin_only both_exports leader_room_preserved qlkh support stale_profile_revoked cached_data_cleared')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ComplianceQA)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print('PLANNING_COMPLIANCE_QA_PASS',result.testsRun,'business authorization history Excel UI cases; isolated DB only')
