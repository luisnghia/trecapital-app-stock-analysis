"""Planning activity integration gates; synthetic DB and fake Push only."""
from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from khdn_apps import notifications as notify, weekly_push as push
from khdn_apps import planning_work_notifications as activity
from khdn_apps import weekly_plan_notifications as weekly
from khdn_apps import customer_work as cases, customer_work_notifications as assignment
from khdn_apps import weekly_entry_edit_patch as entry, weekly_plan as core
from khdn_apps import weekly_priority_policy_patch as policy
from khdn_apps.weekly_entry_edit_qa import EntryQA


class PlanningActivityQA(unittest.TestCase):
    def setUp(self):
        self.fixture = EntryQA()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.db, self.conn, self.ws = self.fixture.db, self.fixture.conn, self.fixture.ws
        with self.conn() as c:
            c.execute('DROP TABLE customer_work_cases')
            c.execute('DROP TABLE work_stage_catalog')
            c.execute("INSERT INTO users VALUES(7,'Room admin QA','Lãnh đạo phòng',1,1,4),(8,'Other leader QA','Lãnh đạo phòng',0,1,NULL),(9,'Unrelated staff QA','Cán bộ QLKH',0,1,8)")
            c.execute('UPDATE users SET manager_user_id=4 WHERE id IN (1,2,3,4)')
        cases.ensure_schema(self.conn)
        with self.conn() as c:
            c.execute('ALTER TABLE customer_work_cases ADD COLUMN controller_user_id INTEGER')
        assignment.ensure_schema(self.db)
        activity.ensure_schema(self.db)
        weekly.process_new_work(self.db)

    def save(self, uid=3, **values):
        return entry.save_item(self.conn, policy, core, uid, self.ws, self.fixture.payload(**values))

    def edit(self, iid, uid=3, **values):
        row = self.fixture.row(iid)
        return entry.save_item(self.conn, policy, core, uid, self.ws, self.fixture.payload(**values),
                               iid=iid, expected_token=entry.item_token(row))

    def recipients(self, column, target, event=None):
        with self.conn() as c:
            return {r[0] for r in c.execute(f'SELECT user_id FROM notifications WHERE {column}=? AND (? IS NULL OR event_key=?)',(target,event,event))}

    def new_case(self, owner=3, actor=None):
        cid = cases.create_case(self.conn, actor or owner, 10, 'Công việc khách hàng QA',
                                '2026-12-10 17:00:00', owner_uid=owner)[0]
        with self.conn() as c:c.execute('UPDATE customer_work_cases SET controller_user_id=4 WHERE id=?',(cid,))
        return cid

    def test_actual_create_and_edit_for_every_role_scoped_recipients(self):
        for uid in (1,2,3,4):
            iid = self.save(uid)
            expected = {uid,4,7}
            self.assertEqual(len(weekly.process_new_work(self.db)),len(expected))
            self.assertEqual(activity.process_actions(self.db),0)
            self.assertEqual(self.recipients('weekly_plan_item_id',iid),expected)
            self.edit(iid,uid,title=f'Đã sửa QA {uid}')
            self.assertEqual(activity.process_actions(self.db),len(expected))
            with self.conn() as c:
                rows=c.execute('SELECT * FROM notifications WHERE weekly_plan_item_id=?',(iid,)).fetchall()
                self.assertEqual(len(rows),2*len(expected))
                self.assertTrue(all(r['deep_link']==f"/?khdn_notification={r['id']}" for r in rows))
                self.assertTrue(all(r['task_id'] is None for r in rows))
        self.assertEqual(notify.unread_count(self.db,8),0)
        self.assertEqual(notify.unread_count(self.db,9),0)

    def test_preferences_inactive_noop_and_two_same_second_edits(self):
        notify.set_preference(self.db,4,'weekly_update',False)
        with self.conn() as c:c.execute('UPDATE users SET active=0 WHERE id=7')
        iid=self.save()
        self.assertEqual(len(weekly.process_new_work(self.db)),1)
        self.edit(iid,title='Lần sửa thứ nhất')
        self.edit(iid,title='Lần sửa thứ hai')
        self.assertEqual(activity.process_actions(self.db),2)
        self.edit(iid,title='Lần sửa thứ hai')
        self.assertEqual(activity.process_actions(self.db),0)
        with self.conn() as c:
            ids=c.execute('SELECT source_action_id FROM notifications WHERE weekly_plan_item_id=? AND source_action_id IS NOT NULL',(iid,)).fetchall()
            self.assertEqual(len({r[0] for r in ids}),2)
        self.assertEqual(self.recipients('weekly_plan_item_id',iid),{3})

    def test_customer_create_updates_and_assignment_not_duplicated(self):
        for uid in (1,2,3,4):
            cid=self.new_case(uid,8)
            self.assertEqual(assignment.process_actions(self.db),1)
            activity.process_actions(self.db)
            self.assertEqual(self.recipients('customer_work_case_id',cid),{uid,4,7})
            inbox=notify.list_notifications(self.db,uid)
            self.assertEqual(sum(x['customer_work_case_id']==cid for x in inbox),1)
            cases.approve_case_plan(self.conn,cid,4,True,'Duyệt QA')
            self.assertEqual(activity.process_actions(self.db),len({uid,4,7}))
        cid=self.new_case(3)
        with self.conn() as c:c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,3,'CREATE_METADATA_CONTACTS_P17','{}','2026-10-05')",(cid,))
        self.assertEqual(assignment.process_actions(self.db),0)
        self.assertEqual(activity.process_actions(self.db),3)
        self.assertEqual(self.recipients('customer_work_case_id',cid),{3,4,7})
        notify.set_preference(self.db,3,activity.CASE_EVENT,False)
        cases.add_issue(self.conn,cid,3,'Vướng mắc QA')
        self.assertEqual(activity.process_actions(self.db),2)

    def test_initial_baseline_replay_and_atomic_failure(self):
        iid=self.save();weekly.process_new_work(self.db)
        self.edit(iid,title='Thay đổi trước cài đặt')
        with self.conn() as c:
            c.execute('DELETE FROM notification_state WHERE key IN (?,?)',(activity.WEEKLY_CURSOR,activity.CASE_CURSOR))
        self.assertEqual(activity.process_actions(self.db),0)
        self.edit(iid,title='Thay đổi sau cài đặt')
        with self.conn() as c:before=notify._state_get(c,activity.WEEKLY_CURSOR)
        initial=notify.unread_count(self.db,3)
        original=push.enqueue
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError('Synthetic rollback')
        with patch.object(push,'enqueue',fail):
            with self.assertRaises(RuntimeError):activity.process_actions(self.db)
        with self.conn() as c:self.assertEqual(notify._state_get(c,activity.WEEKLY_CURSOR),before)
        self.assertEqual(notify.unread_count(self.db,3),initial)
        self.assertEqual(activity.process_actions(self.db),3)
        with self.conn() as c:notify._state_set(c,activity.WEEKLY_CURSOR,before)
        self.assertEqual(activity.process_actions(self.db),0)

    def test_direct_classification_notification_deduplicates_journal(self):
        iid=self.save();weekly.process_new_work(self.db)
        with self.conn() as c:
            policy._set_classification(c,iid,4,102,None,None,'Điều chỉnh QA')
        self.assertEqual(activity.process_actions(self.db),2)
        with self.conn() as c:
            aid=c.execute("SELECT id FROM weekly_plan_actions WHERE item_id=? AND action='CLASSIFICATION_CHANGE'",(iid,)).fetchone()[0]
            self.assertEqual(c.execute('SELECT COUNT(*) FROM notifications WHERE source_action_id=? AND event_key=?',(aid,'weekly_update')).fetchone()[0],3)

    def test_concurrent_new_work_scan_and_delivery_revocation(self):
        iid=self.save()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:weekly.process_new_work(self.db),range(2)))
        self.assertEqual(sum(len(x) for x in results),3)
        self.assertEqual(self.recipients('weekly_plan_item_id',iid),{3,4,7})
        with self.conn() as c:
            c.execute('UPDATE weekly_plan_items SET user_id=2 WHERE id=?',(iid,))
            c.execute("UPDATE users SET role='Cán bộ QLKH',is_admin=0 WHERE id=7")
        with patch.object(notify,'_send_notification_push') as transport:
            push.flush(self.db,event_key='weekly_update')
        sent={x.args[1] for x in transport.call_args_list}
        for uid in (3,7):
            n=notify.list_notifications(self.db,uid)[0]
            self.assertEqual(n['push_status'],'SKIPPED')
            self.assertNotIn(n['id'],sent)

    def test_existing_fast_worker_and_fake_all_device_transport(self):
        iid=self.save()
        for uid in (3,4,7):
            for device in (1,2):
                notify.save_subscription(self.db,uid,{'endpoint':f'https://push.example.test/{uid}/{device}','keys':{'p256dh':'QA','auth':'QA'}})
        stop=threading.Event();calls=[]
        def fake(**kwargs):
            calls.append(kwargs)
            stop.set()
        with patch.dict(os.environ,{'KHDN_VAPID_PRIVATE_KEY':'FAKE','KHDN_VAPID_PUBLIC_KEY':'FAKE'}),patch('pywebpush.webpush',fake),patch.object(notify,'process_task_actions'),patch.object(notify,'process_sla_alerts'):
            notify.worker_loop(self.db,stop,poll_seconds=2)
        self.assertEqual(len(calls),6)
        self.assertEqual({x['subscription_info']['endpoint'] for x in calls},
                         {f'https://push.example.test/{u}/{d}' for u in (3,4,7) for d in (1,2)})
        self.assertTrue(all(json.loads(x['data'])['url'].startswith('/?khdn_notification=') for x in calls))
        self.assertTrue(all(x['push_status']=='SENT' for u in (3,4,7) for x in notify.list_notifications(self.db,u)))
        self.assertEqual(self.recipients('weekly_plan_item_id',iid),{3,4,7})


def installed_activity_ui():
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    from khdn_apps.notification_ui_patch import _notification_route
    page=AppTest.from_file(str(Path(__file__).with_name('online_entry.py')),default_timeout=30).run()
    assert not page.exception,[x.message for x in page.exception]
    users={};ws=date(2026,10,5)
    with app.get_conn() as c:
        ts=cases.now_str()
        for name,role,admin in [('support','Cán bộ hỗ trợ',0),('qlkh','Cán bộ QLKH',0),('leader','Lãnh đạo phòng',0),('admin','Lãnh đạo phòng',1)]:
            username='planning_activity_ui_'+name
            c.execute("INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at) VALUES(?,?,'QA_NO_LOGIN',?,?,1,0,?,?)",(username,'Planning activity QA '+name,role,admin,ts,ts))
            users[name]=dict(c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone())
            core.ensure_plan(c,users[name]['id'],ws)
    activity.ensure_schema(app.DB_PATH);weekly.process_new_work(app.DB_PATH)
    items={}
    with patch.object(entry.weekly_push,'local_now',return_value=datetime(2026,10,5,8,30)):
        for name,u in users.items():
            payload={'title':'Kế hoạch thông báo QA '+name,'work_date':ws.isoformat(),'due_date':'2026-10-09','controller':str(users['leader']['id']),'focus':'NONE','risk':'NO','note':'QA'}
            iid=entry.save_item(app.get_conn,policy,core,u['id'],ws,payload)
            weekly.process_new_work(app.DB_PATH)
            with app.get_conn() as c:row=dict(c.execute('SELECT * FROM weekly_plan_items WHERE id=?',(iid,)).fetchone())
            payload['title']+=' đã sửa'
            entry.save_item(app.get_conn,policy,core,u['id'],ws,payload,iid=iid,expected_token=entry.item_token(row))
            activity.process_actions(app.DB_PATH)
            items[name]=next(x for x in notify.list_notifications(app.DB_PATH,u['id']) if x['weekly_plan_item_id']==iid and x['source_action_id'])
    for name,u in users.items():
        item=items[name]
        assert _notification_route(u,item)=='weekly_plan'
        page.session_state['user']=u
        page.session_state['_khdn_notification_dialog_open']=True
        page.session_state['_khdn_notification_selected']=None
        page.run()
        assert not page.exception,[x.message for x in page.exception]
        assert any(x.label==notify.EVENT_LABELS['weekly_update'] for x in page.checkbox)
        assert any(x.label==notify.EVENT_LABELS[activity.CASE_EVENT] for x in page.checkbox)
        button=next(x for x in page.button if x.key==f"notif_open_{item['id']}")
        assert button.label=='Mở tuần của công việc' and not button.disabled
        button.click().run()
        assert not page.exception,[x.message for x in page.exception]
        assert page.session_state['main_page']=='weekly_plan'
        assert page.session_state['main_section']=='plan'
        assert page.session_state['policy_week_view']=='plan'
        assert page.session_state['policy_week_offset']==(ws-policy._default_week(core)).days//7
        assert not page.session_state['_khdn_notification_dialog_open']
        assert notify.get_notification(app.DB_PATH,item['id'],u['id'])['read_at']
        del page.session_state['cw_landing_token']
        page.session_state['main_page']='work_today'
        page.query_params['khdn_notification']=str(item['id'])
        page.run()
        assert not page.exception,[x.message for x in page.exception]
        assert page.session_state['main_page']=='weekly_plan'
    with app.get_conn() as c:
        leader_item=dict(c.execute('SELECT * FROM notifications WHERE user_id=? AND weekly_plan_item_id=? ORDER BY id DESC LIMIT 1',(users['leader']['id'],items['qlkh']['weekly_plan_item_id'])).fetchone())
    page.session_state['user']=users['leader']
    page.query_params['khdn_notification']=str(leader_item['id']);page.run()
    assert not page.exception,[x.message for x in page.exception]
    assert page.session_state['policy_week_view']=='room'
    page.session_state['user']=users['support'];page.session_state['main_page']='work_today'
    page.query_params['khdn_notification']=str(items['qlkh']['id']);page.run()
    assert not page.exception,[x.message for x in page.exception]
    assert page.session_state['main_page']=='work_today'
    print('PLANNING_WORK_NOTIFICATION_INSTALLED_UI_QA_PASS support qlkh leader admin new edit preferences inbox correct_week fresh_login_push_link read_persistence manager_room foreign_notification_denied')


def run():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlanningActivityQA))
    if not result.wasSuccessful():raise SystemExit(1)
    print('PLANNING_WORK_NOTIFICATION_QA_PASS all_roles actual_create actual_edit scoped_recipients prefs inactive no_historical_blast journal_replay rollback classification_dedupe concurrent_scan revoked_scope fast_worker all_devices')


if __name__=='__main__':run()
