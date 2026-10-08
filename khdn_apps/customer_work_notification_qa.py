"""Assignment integration QA; synthetic database and fake push provider only."""
from __future__ import annotations
from khdn_apps.security_qa_fixtures import push_keys

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from khdn_apps import customer_work as core, customer_work_notifications as work
from khdn_apps import notifications as notify, weekly_push as push
from khdn_apps.notification_ui_patch import _notification_route


class AssignmentQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "assignment.db"
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER,last_login_at TEXT);
                INSERT INTO users VALUES
                (1,'Support QA','Cán bộ hỗ trợ',0,1,''),
                (2,'QLKH QA','Cán bộ QLKH',0,1,''),
                (3,'Leader QA','Lãnh đạo phòng',0,1,''),
                (4,'Admin QA','Lãnh đạo phòng',1,1,''),
                (5,'Assigning manager QA','Lãnh đạo phòng',1,1,''),
                (6,'Unrelated QA','Cán bộ QLKH',0,1,''),
                (7,'Inactive QA','Cán bộ hỗ trợ',0,0,'');
                CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT,qlkh_user_id INTEGER,active INTEGER);
                INSERT INTO customers VALUES(1,'QA123','KH QA',2,1);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY);
                CREATE TABLE task_actions(id INTEGER PRIMARY KEY,task_id INTEGER,actor_user_id INTEGER,action TEXT,detail TEXT,created_at TEXT);
            """)
        core.ensure_schema(self.conn)
        work.ensure_schema(self.db)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            with c:yield c
        finally:c.close()

    def create(self, owner=2, actor=5):
        return core.create_case(self.conn, actor, 1, "Công việc được giao QA",
                                "2026-12-10 17:00:00", owner_uid=owner)[0]

    def test_all_roles_exact_owner_deep_link_and_duplicate_cursor_replay(self):
        cases = {uid:self.create(uid) for uid in (1,2,3,4)}
        self.assertEqual(work.process_actions(self.db), 4)
        self.assertEqual(work.process_actions(self.db), 0)
        with self.conn() as c:
            notify._state_set(c, work.CURSOR, '0')
        self.assertEqual(work.process_actions(self.db), 0)
        for uid,cid in cases.items():
            items = notify.list_notifications(self.db, uid)
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item['customer_work_case_id'], cid)
            self.assertIsNone(item['task_id'])
            self.assertEqual(item['event_key'], work.EVENT_KEY)
            self.assertIn('KH QA', item['body'])
            self.assertIn('Công việc được giao QA', item['body'])
            self.assertIn('2026-12-10', item['body'])
            self.assertEqual(item['deep_link'], f"/?khdn_notification={item['id']}")
            self.assertEqual(_notification_route({'role':'Cán bộ QLKH'}, item), 'customer_work')
            self.assertIsNone(notify.get_notification(self.db,item['id'],6))
        self.assertEqual(notify.unread_count(self.db,5),0)
        self.assertEqual(notify.unread_count(self.db,6),0)
        with self.conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM weekly_push_queue').fetchone()[0],4)

    def test_preferences_inactive_self_and_metadata(self):
        notify.set_preference(self.db,2,work.EVENT_KEY,False)
        cid=self.create()
        # An existing assignment can outlive account activation; new assignments
        # to a disabled account are now rejected by the mutation boundary.
        with self.assertRaises(PermissionError): self.create(7)
        with self.conn() as c: c.execute("UPDATE users SET active=1 WHERE id=7")
        self.create(7)
        with self.conn() as c: c.execute("UPDATE users SET active=0 WHERE id=7")
        self.create(5)
        with self.conn() as c:
            c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,5,'CREATE_METADATA_CONTACTS_P17','{}','2026-10-07')",(cid,))
        self.assertEqual(work.process_actions(self.db),0)
        notify.set_preference(self.db,2,work.EVENT_KEY,True)
        self.create();self.assertEqual(work.process_actions(self.db),1)

    def test_no_historical_blast_or_rolled_back_action(self):
        self.create()
        with self.conn() as c:c.execute('DELETE FROM notification_state WHERE key=?',(work.CURSOR,))
        self.assertEqual(work.process_actions(self.db),0)
        with self.conn() as c:
            c.execute("CREATE TRIGGER qa_create_failure BEFORE INSERT ON case_actions WHEN NEW.action='CREATE' BEGIN SELECT RAISE(ABORT,'rollback QA'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.create()
        self.assertEqual(work.process_actions(self.db),0)
        with self.conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM customer_work_cases').fetchone()[0],1)
            c.execute('DROP TRIGGER qa_create_failure')
        self.create()
        self.assertEqual(work.process_actions(self.db),1)
        self.assertEqual(notify.unread_count(self.db,2),1)

    def test_atomic_cursor_queue_and_notification(self):
        self.create()
        with self.conn() as c:cursor=notify._state_get(c,work.CURSOR)
        original=push.enqueue
        def fail_after_insert(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError('queue failure QA')
        with patch.object(push,'enqueue',fail_after_insert):
            with self.assertRaises(RuntimeError):work.process_actions(self.db)
        with self.conn() as c:
            self.assertEqual(notify._state_get(c,work.CURSOR),cursor)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM notifications').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM weekly_push_queue').fetchone()[0],0)
        self.assertEqual(work.process_actions(self.db),1)

    def test_pending_delivery_respects_current_owner_revocation_and_preferences(self):
        for mode in ('owner','inactive','pref'):
            cid=self.create();self.assertEqual(work.process_actions(self.db),1)
            nid=notify.list_notifications(self.db,2)[0]['id']
            with self.conn() as c:
                if mode=='owner':c.execute('UPDATE customer_work_cases SET owner_user_id=6 WHERE id=?',(cid,))
                if mode=='inactive':c.execute('UPDATE users SET active=0 WHERE id=2')
                if mode=='pref':notify._state_set(c,'qa_mode',mode)
            if mode=='pref':notify.set_preference(self.db,2,work.EVENT_KEY,False)
            with patch.object(notify,'_send_notification_push') as transport:
                self.assertEqual(push.flush(self.db,event_key=work.EVENT_KEY),0)
                transport.assert_not_called()
            self.assertEqual(notify.get_notification(self.db,nid,2)['push_status'],'SKIPPED')
            with self.conn() as c:c.execute('UPDATE users SET active=1 WHERE id=2')
            notify.set_preference(self.db,2,work.EVENT_KEY,True)

    def test_push_all_devices_payload_and_retry_recovery(self):
        self.create();self.assertEqual(work.process_actions(self.db),1)
        for i in (1,2):notify.save_subscription(self.db,2,{'endpoint':f'https://fcm.googleapis.com/qa{i}','keys':push_keys()})
        calls=[]
        def send(**kwargs):calls.append(kwargs)
        with patch.dict(os.environ,{'KHDN_VAPID_PRIVATE_KEY':'qa-not-real','KHDN_VAPID_PUBLIC_KEY':'qa-not-real'}):
            with patch('pywebpush.webpush',send):
                self.assertEqual(push.flush(self.db,event_key=work.EVENT_KEY),1)
                self.assertEqual(push.flush(self.db,event_key=work.EVENT_KEY),0)
        self.assertEqual(len(calls),2)
        payload=json.loads(calls[0]['data'])
        self.assertIn('Công việc khách hàng',payload['title'])
        self.assertEqual(payload['url'],notify.list_notifications(self.db,2)[0]['deep_link'])
        self.assertEqual({x['subscription_info']['endpoint'] for x in calls},{'https://fcm.googleapis.com/qa1','https://fcm.googleapis.com/qa2'})
        self.create();work.process_actions(self.db)
        now=time.time()
        with patch.object(notify,'_send_notification_push',side_effect=RuntimeError('fake retry')):
            push.flush(self.db,now_ts=now,event_key=work.EVENT_KEY)
        nid=notify.list_notifications(self.db,2)[0]['id']
        with self.conn() as c:self.assertEqual(c.execute('SELECT state FROM weekly_push_queue WHERE notification_id=?',(nid,)).fetchone()[0],'RETRY')
        with patch.dict(os.environ,{'KHDN_VAPID_PRIVATE_KEY':'qa-not-real','KHDN_VAPID_PUBLIC_KEY':'qa-not-real'}),patch('pywebpush.webpush',send):
            self.assertEqual(push.flush(self.db,now_ts=now+61,event_key=work.EVENT_KEY),1)

    def test_event_filter_leaves_weekly_delivery_to_existing_worker(self):
        with self.conn() as c:weekly_id=push.enqueue(c,2,'Weekly QA','Unchanged weekly delivery')
        self.create();work.process_actions(self.db)
        with patch.object(notify,'_send_notification_push') as transport:
            def sent(db,nid):
                with self.conn() as c:c.execute("UPDATE notifications SET push_status='SENT' WHERE id=?",(nid,))
            transport.side_effect=sent
            self.assertEqual(push.flush(self.db,event_key=work.EVENT_KEY),1)
            self.assertNotEqual(transport.call_args.args[1],weekly_id)
        with self.conn() as c:self.assertEqual(c.execute('SELECT state FROM weekly_push_queue WHERE notification_id=?',(weekly_id,)).fetchone()[0],'PENDING')

    def test_upgrade_existing_inbox_retains_old_notifications(self):
        old=Path(self.tmp.name)/'old.db'
        with sqlite3.connect(old) as c:
            c.executescript("""CREATE TABLE users(id INTEGER PRIMARY KEY);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY);
                INSERT INTO users VALUES(2); INSERT INTO tasks VALUES(99);
                CREATE TABLE notifications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,task_id INTEGER,event_key TEXT NOT NULL,source_action_id INTEGER,title TEXT NOT NULL,body TEXT NOT NULL,deep_link TEXT,created_at TEXT NOT NULL,read_at TEXT,push_status TEXT DEFAULT 'PENDING',pushed_at TEXT,attempt_count INTEGER DEFAULT 0,last_error TEXT,UNIQUE(user_id,source_action_id,event_key));
                INSERT INTO notifications(id,user_id,task_id,event_key,source_action_id,title,body,created_at) VALUES(8,2,99,'assignment',11,'Existing QA','Keep existing inbox','2026-10-01');""")
        notify.ensure_schema(old)
        item=notify.get_notification(old,8,2)
        self.assertEqual(item['title'],'Existing QA')
        self.assertEqual(item['source_action_id'],11)
        self.assertIsNone(item['customer_work_case_id'])


def run():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AssignmentQA)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    print('CUSTOMER_WORK_NOTIFICATION_QA_PASS all_roles exact_owner no_broadcast prefs no_self inactive deep_link durable_queue replay_dedupe rollback all_devices retry revoked_scope')


def installed_notification_ui():
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    page=AppTest.from_file(str(Path(__file__).with_name('online_entry.py')),default_timeout=30).run()
    assert not page.exception,[x.message for x in page.exception]
    users={}
    with app.get_conn() as c:
        ts=core.now_str()
        for name,role,admin in [('support','Cán bộ hỗ trợ',0),('qlkh','Cán bộ QLKH',0),('leader','Lãnh đạo phòng',0),('admin','Lãnh đạo phòng',1),('sender','Lãnh đạo phòng',1)]:
            username='assignment_ui_'+name
            c.execute("INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at) VALUES(?,?,'QA_NO_LOGIN',?,?,1,0,?,?)",(username,'Assignment QA '+name,role,admin,ts,ts))
            users[name]=dict(c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone())
        c.execute("INSERT INTO customers(cif,customer_name,qlkh_user_id,active,created_at,updated_at) VALUES('ASSIGNMENT_UI_QA','Khách hàng thông báo QA',?,1,?,?)",(users['qlkh']['id'],ts,ts))
        customer_id=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
    work.ensure_schema(app.DB_PATH)
    cases={name:core.create_case(app.get_conn,users['sender']['id'],customer_id,
           'Công việc thông báo QA '+name,'2026-12-10 17:00:00',owner_uid=users[name]['id'])[0]
           for name in ('support','qlkh','leader','admin')}
    assert work.process_actions(app.DB_PATH)==4
    for name,case_id in cases.items():
        u=users[name];uid=u['id']
        item=notify.list_notifications(app.DB_PATH,uid)[0]
        page.session_state['user']=u
        page.session_state['_khdn_notification_dialog_open']=True
        page.session_state['_khdn_notification_selected']=None
        page.run()
        assert not page.exception,[x.message for x in page.exception]
        assert any(x.label==notify.EVENT_LABELS[work.EVENT_KEY] for x in page.checkbox)
        button=next(x for x in page.button if x.key==f"notif_open_{item['id']}")
        assert button.label=='Mở công việc khách hàng' and not button.disabled
        button.click().run()
        assert not page.exception,[x.message for x in page.exception]
        assert page.session_state['main_page']=='customer_work'
        assert page.session_state['main_section']=='plan'
        assert page.session_state['cw_case_id']==case_id
        assert not page.session_state['_khdn_notification_dialog_open']
        # Fresh login landing must not overwrite the notification's exact route.
        del page.session_state['cw_landing_token']
        del page.session_state['cw_case_id']
        page.session_state['main_page']='work_today'
        page.query_params['khdn_notification']=str(item['id'])
        page.run()
        assert not page.exception,[x.message for x in page.exception]
        assert page.session_state['main_page']=='customer_work'
        assert page.session_state['cw_case_id']==case_id
        assert notify.get_notification(app.DB_PATH,item['id'],uid)['read_at']
    # A notification remains personal; another account cannot use its deep link.
    item=notify.list_notifications(app.DB_PATH,users['qlkh']['id'])[0]
    page.session_state['user']=users['support']
    page.session_state['main_page']='work_today'
    del page.session_state['cw_case_id']
    page.query_params['khdn_notification']=str(item['id'])
    page.run()
    assert not page.exception,[x.message for x in page.exception]
    assert 'cw_case_id' not in page.session_state
    # A revoked owner cannot open the case from their old personal notification.
    with app.get_conn() as c:c.execute('UPDATE customer_work_cases SET owner_user_id=? WHERE id=?',(users['sender']['id'],cases['qlkh']))
    page.session_state['user']=users['qlkh']
    # Let the existing business-data refresh guard settle after the QA mutation.
    # Its automatic rerun otherwise clears transient UI feedback from the click.
    page.run()
    assert not page.exception,[x.message for x in page.exception]
    page.query_params['khdn_notification']=str(item['id'])
    page.run()
    assert not page.exception,[x.message for x in page.exception]
    assert 'cw_case_id' not in page.session_state
    warnings=[x.proto.body for x in page.get('toast')]
    assert any('không còn quyền' in x for x in warnings), {
        'warnings':warnings,
        'query':dict(page.query_params),
        'user_id':page.session_state['user']['id'],
        'notification_id':item['id'],
    }
    print('CUSTOMER_WORK_NOTIFICATION_INSTALLED_UI_QA_PASS support qlkh leader admin preference_visible inbox_button exact_case fresh_login_push_link read_persistence foreign_notification_denied revoked_owner_denied')


if __name__=='__main__':run()
