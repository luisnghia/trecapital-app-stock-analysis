"""Date, lifecycle, ownership and rollback regression checks in temporary DBs."""
from datetime import date, datetime, timedelta
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from khdn_apps import weekly_entry_edit_patch as entry
from khdn_apps import weekly_plan as core
from khdn_apps import weekly_priority_policy_patch as policy


class EntryQA(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="weekly-entry-qa-")
        self.db = Path(self.folder.name) / "qa.db"
        self.ws = date(2026, 10, 5)
        self.clock = patch.object(entry.weekly_push, "local_now", return_value=datetime(2026, 10, 5, 8, 30))
        self.clock.start()
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER,manager_user_id INTEGER);
                INSERT INTO users VALUES(1,'Admin QA','Admin',1,1,4),(2,'Hỗ trợ QA','Cán bộ hỗ trợ',0,1,4),
                    (3,'QLKH QA','Cán bộ QLKH',0,1,4),(4,'Lãnh đạo QA','Lãnh đạo phòng',0,1,NULL),
                    (5,'Đã khóa QA','Cán bộ QLKH',0,0,4),(6,'Ngoài quyền QA','Khác',0,1,4);
                CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT,qlkh_user_id INTEGER,active INTEGER);
                INSERT INTO customers VALUES(10,'00123','Khách hàng QA',3,1);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY);
                CREATE TABLE work_stage_catalog(id INTEGER PRIMARY KEY,name TEXT);
                INSERT INTO work_stage_catalog VALUES(1,'Tiếp cận');
                CREATE TABLE customer_work_cases(id INTEGER PRIMARY KEY,case_code TEXT,title TEXT,case_type TEXT,customer_id INTEGER,
                    owner_user_id INTEGER,expected_complete_at TEXT,controller_user_id INTEGER,important_category_id INTEGER,
                    priority_quadrant INTEGER,status TEXT,current_stage_id INTEGER,focus_category_id INTEGER,focus_name_snapshot TEXT);
                INSERT INTO customer_work_cases VALUES(20,'CVQA','Workflow QA','Tín dụng',10,3,'2026-10-02',4,NULL,4,'ACTIVE',1,NULL,NULL);
            """)
        policy._ensure_schema(core, self.conn)
        with self.conn() as c:
            for name, ddl in [("expected_complete_date", "TEXT"), ("controller_user_id", "INTEGER"), ("controller_name_snapshot", "TEXT"), ("linked_case_id", "INTEGER"), ("priority_quadrant", "INTEGER"), ("approval_status", "TEXT"), ("approved_by_user_id", "INTEGER"), ("approved_at", "TEXT")]:
                if name not in policy._cols(c, "weekly_plan_items"):
                    c.execute(f"ALTER TABLE weekly_plan_items ADD COLUMN {name} {ddl}")
            ts = policy._now()
            for n in (1, 2, 3):
                c.execute("INSERT INTO weekly_focus_categories(id,department_key,apply_year,code,name,active,created_at,updated_at) VALUES(?,'LEADER:4',2026,?,?,1,?,?)", (100 + n, f'ENTRY{n}', f'Mục QA {n}', ts, ts))
            for uid in range(1, 7):
                core.ensure_plan(c, uid, self.ws)

    def tearDown(self):
        self.clock.stop()
        self.folder.cleanup()

    def conn(self):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def payload(self, **changes):
        data = {"title": "Công việc QA", "work_date": self.ws.isoformat(), "due_date": "2026-10-09", "controller": "4", "focus": "101", "risk": "NO", "note": "Ghi chú QA"}
        data.update(changes)
        return data

    def save(self, uid=3, **changes):
        return entry.save_item(self.conn, policy, core, uid, self.ws, self.payload(**changes))

    def row(self, iid):
        with self.conn() as c:
            return dict(c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (iid,)).fetchone())

    def status(self, uid, status, locked=0):
        with self.conn() as c:
            c.execute("UPDATE weekly_plans SET workflow_status=?,classification_locked=? WHERE user_id=?", (status, locked, uid))

    def test_all_roles_create_each_day_and_edit_without_duplicates(self):
        for uid in (1, 2, 3, 4):
            for n in range(7):
                day = self.ws + timedelta(days=n)
                iid = self.save(uid, title=f'QA {uid} ngày {n}', work_date=day.isoformat(), due_date=day.isoformat(), focus=str(101 + n % 3))
                self.assertEqual(self.row(iid)["work_date"], day.isoformat())
            token = entry.begin_edit(self.conn, uid, self.ws, iid)
            edited = entry.save_item(self.conn, policy, core, uid, self.ws, self.payload(title='Đã sửa QA', work_date='2026-10-06', due_date='2026-10-08'), iid=iid, expected_token=token['token'])
            self.assertEqual(edited, iid)
            self.assertEqual(self.row(iid)['title'], 'Đã sửa QA')
            with self.conn() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM weekly_plan_items WHERE user_id=?', (uid,)).fetchone()[0], 7)
                audit = json.loads(c.execute("SELECT detail FROM weekly_plan_actions WHERE item_id=? AND action='DRAFT_EDIT'", (iid,)).fetchone()[0])
                self.assertEqual(audit['before']['work_date'], '2026-10-11')
                self.assertEqual(audit['after']['work_date'], '2026-10-06')
                self.assertEqual(policy._q2_focus_count([dict(x) for x in c.execute('SELECT * FROM weekly_plan_items WHERE user_id=?', (uid,))]), 3)

    def test_returned_plan_starts_new_draft_without_approval(self):
        for uid in (1, 2, 3, 4):
            iid = self.save(uid)
            self.status(uid, 'TRA_LAI')
            with self.conn() as c:
                c.execute("UPDATE weekly_plans SET return_note='Lý do QA' WHERE user_id=?", (uid,))
            token = entry.begin_edit(self.conn, uid, self.ws, iid)
            entry.save_item(self.conn, policy, core, uid, self.ws, self.payload(title='Sửa theo trả lại QA'), iid=iid, expected_token=token['token'])
            with self.conn() as c:
                plan = entry._plan(c, uid, self.ws)
                self.assertEqual((plan['workflow_status'], plan['return_note']), ('NHAP', 'Lý do QA'))
                self.assertEqual(c.execute("SELECT COUNT(*) FROM weekly_plan_actions WHERE actor_user_id=? AND action='RETURN_TO_DRAFT'", (uid,)).fetchone()[0], 1)
            self.assertNotEqual(self.row(iid)['approval_status'], 'APPROVED')

    def test_other_owner_and_locked_states_are_rejected(self):
        iid = self.save()
        for uid in (1, 2, 4):
            with self.assertRaises(PermissionError):
                entry.begin_edit(self.conn, uid, self.ws, iid)
            with self.assertRaises(PermissionError):
                entry.save_item(self.conn, policy, core, uid, self.ws, self.payload(), iid=iid, expected_token=entry.item_token(self.row(iid)))
        for status in ('DA_NOP', 'DA_DUYET', 'DA_CHOT', 'DA_DANH_GIA'):
            self.status(3, status)
            with self.assertRaises(PermissionError):
                entry.begin_edit(self.conn, 3, self.ws, iid)
            with self.assertRaises(PermissionError):
                self.save()
        self.status(3, 'NHAP', 1)
        with self.assertRaises(PermissionError):
            entry.begin_edit(self.conn, 3, self.ws, iid)

    def test_revoked_account_and_plan_state_rechecked_on_save(self):
        iid = self.save()
        token = entry.begin_edit(self.conn, 3, self.ws, iid)
        for uid in (5, 6, 999):
            with self.assertRaises(PermissionError):
                self.save(uid)
        with self.conn() as c:
            c.execute('UPDATE users SET active=0 WHERE id=3')
        with self.assertRaises(PermissionError):
            entry.save_item(self.conn, policy, core, 3, self.ws, self.payload(title='Không được lưu'), iid=iid, expected_token=token['token'])
        with self.conn() as c:
            c.execute('UPDATE users SET active=1 WHERE id=3')
        self.status(3, 'DA_NOP')
        with self.assertRaises(PermissionError):
            entry.save_item(self.conn, policy, core, 3, self.ws, self.payload(), iid=iid, expected_token=token['token'])
        self.assertEqual(self.row(iid)['title'], 'Công việc QA')

    def test_invalid_dates_and_catalog_entries_do_not_write(self):
        for change in [{'work_date':'2026-10-12'}, {'work_date':'2026-10-04'}, {'due_date':'2026-10-04'}, {'due_date':'2026-02-30'}, {'focus':'999'}, {'controller':'2'}, {'customer_id':999}, {'title':'   '}]:
            with self.assertRaises(ValueError):
                self.save(**change)
        with self.conn() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM weekly_plan_items').fetchone()[0], 0)

    def test_classification_uses_due_date_and_distinct_focus(self):
        for payload, q in [({'focus':'101'},2), ({'focus':'NONE','risk':'YES'},1), ({'focus':'NONE','risk':'NO'},3), ({'focus':'NONE','due_date':'2026-10-20','risk':''},4)]:
            iid = self.save(**payload)
            self.assertEqual(self.row(iid)['priority_quadrant'], q)
        with self.assertRaises(ValueError):
            self.save(focus='NONE', risk='')
        with self.conn() as c:
            c.execute('UPDATE weekly_focus_categories SET active=0 WHERE id=101')
        with self.assertRaises(ValueError):
            self.save()

    def test_linked_work_inherits_q4_due_and_controller(self):
        iid = self.save(customer_id=10, linked_case_id=20, focus='101', controller='2', due_date='2026-12-31')
        row = self.row(iid)
        self.assertEqual((row['priority_quadrant'], row['expected_complete_date'], row['controller_user_id']), (4, '2026-10-02', 4))
        with self.assertRaises(ValueError):
            self.save(customer_id=10, linked_case_id=20)
        token = entry.begin_edit(self.conn, 3, self.ws, iid)
        entry.save_item(self.conn, policy, core, 3, self.ws, self.payload(customer_id=10, linked_case_id=20, title='Sửa việc liên kết'), iid=iid, expected_token=token['token'])
        self.assertEqual(self.row(iid)['linked_case_id'], 20)
        with self.assertRaises(ValueError):
            self.save(2, customer_id=10, linked_case_id=20)

    def test_linked_q2_without_legacy_mapping_is_preserved(self):
        with self.conn() as c:
            c.execute("UPDATE customer_work_cases SET priority_quadrant=2,focus_name_snapshot='Trọng tâm lịch sử QA' WHERE id=20")
        iid = self.save(customer_id=10, linked_case_id=20)
        self.assertEqual((self.row(iid)['priority_quadrant'], self.row(iid)['focus_name_snapshot']), (2, 'Trọng tâm lịch sử QA'))

    def test_concurrent_edit_is_detected_even_same_timestamp(self):
        iid = self.save()
        token = entry.begin_edit(self.conn, 3, self.ws, iid)
        with self.conn() as c:
            c.execute("UPDATE weekly_plan_items SET title='Phiên khác QA' WHERE id=?", (iid,))
        with self.assertRaises(ValueError):
            entry.save_item(self.conn, policy, core, 3, self.ws, self.payload(), iid=iid, expected_token=token['token'])
        self.assertEqual(self.row(iid)['title'], 'Phiên khác QA')

    def test_audit_failure_rolls_back_data(self):
        iid = self.save()
        token = entry.begin_edit(self.conn, 3, self.ws, iid)
        before = self.row(iid)
        with self.conn() as c:
            c.execute("CREATE TRIGGER qa_reject_edit BEFORE INSERT ON weekly_plan_actions WHEN NEW.action='DRAFT_EDIT' BEGIN SELECT RAISE(ABORT,'QA rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            entry.save_item(self.conn, policy, core, 3, self.ws, self.payload(title='Không được lưu QA', focus='102'), iid=iid, expected_token=token['token'])
        self.assertEqual(self.row(iid), before)

    def test_cap_applies_to_create_and_emergent_uses_approved_plan(self):
        for n in range(7):
            self.save(title=f'QA {n}')
        with self.assertRaises(ValueError):
            self.save()
        self.status(3, 'DA_DUYET')
        for n in range(2):
            iid = entry.save_item(self.conn, policy, core, 3, self.ws, self.payload(title=f'Phát sinh QA {n}'), emergent=True)
            row = self.row(iid)
            self.assertEqual((row['is_emergent'], row['approval_status'], row['approved_by_user_id']), (1, 'APPROVED', 3))


def installed_entry_ui():
    """Exercise installed role routes and the real submit/de-duplication wrapper."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app, customer_work, potential_customer_patch as prospects
    script = """
import streamlit as st
from datetime import date
from unittest.mock import patch
import importlib
from khdn_apps import app, weekly_plan as core, weekly_plan_ui as ui, weekly_priority_policy_patch as policy
bridge=importlib.import_module('khdn_apps.legacy_fast_form')
app.init_db();policy._ensure_schema(core,app.get_conn,app.LOGGER)
ws=date(2026,10,5);ts=policy._now()
with app.get_conn() as c:
    for name,role,admin in [('support','Cán bộ hỗ trợ',0),('qlkh','Cán bộ QLKH',0),('leader','Lãnh đạo phòng',0),('admin','Cán bộ QLKH',1)]:
        c.execute('''INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at)
            VALUES(?,?,'QA_NO_LOGIN',?,?,1,?,?)''',('entry_ui_'+name,'Entry UI QA '+name,role,admin,ts,ts))
    name=st.session_state.get('entry_ui_actor','support')
    u=dict(c.execute('SELECT * FROM users WHERE username=?',('entry_ui_'+name,)).fetchone())
    if not st.session_state.get('entry_ui_seeded'):
        for person in c.execute("SELECT * FROM users WHERE username LIKE 'entry_ui_%'").fetchall():
            core.ensure_plan(c,person['id'],ws)
            scope=policy._scope_key(c,person['id'])
            c.execute('''INSERT OR IGNORE INTO weekly_focus_categories(department_key,apply_year,code,name,active,created_at,updated_at)
                VALUES(?,2026,'ENTRY_UI_QA','Mục UI QA',1,?,?)''',(scope,ts,ts))
        st.session_state['entry_ui_seeded']=True
def component(**kwargs):
    key=str(kwargs.get('key') or '')
    if key.startswith('weekly_entry_'):
        st.session_state['_entry_ui_fields']=kwargs['fields']
        payload=st.session_state.pop('_entry_ui_payload',None)
        if payload is not None:
            seq=int(st.session_state.get('_entry_ui_seq',0))+1;st.session_state['_entry_ui_seq']=seq
            return {'submit_id':f'qa-{seq}','values':payload}
    return None
with patch.object(bridge,'_component',component),patch.object(policy,'_default_week',lambda _:ws):
    ui.render_page(st,u,app.get_conn,page_title=None,logger=app.LOGGER)
"""
    page = AppTest.from_string(script, default_timeout=30).run()

    def check():
        assert not page.exception, [x.message for x in page.exception]

    def payload(**changes):
        fields = page.session_state['_entry_ui_fields']
        data = {x['name']: x.get('default', '') for x in fields}
        for name in ('controller', 'focus'):
            if name not in data:  # Linked work inherits its classification.
                continue
            if not str(data.get(name) or '').isdigit():
                field = next(x for x in fields if x['name'] == name)
                data[name] = next(x['value'] for x in field['options'] if x['value'].isdigit())
        data.update(changes)
        page.session_state['_entry_ui_payload'] = data
        page.run()
        check()

    for name in ('support', 'qlkh', 'leader', 'admin'):
        page.session_state['entry_ui_actor'] = name
        page.run(); check()
        if name in {'leader', 'admin'}:
            next(x for x in page.button if x.label == 'Kế hoạch tuần').click().run(); check()
        adds = [x for x in page.button if str(x.key or '').startswith('p13_quick_add_')]
        assert len(adds) == 5 and len({x.label for x in adds}) == 5, name
        assert 'Thứ 4' in adds[2].label and '07/10' in adds[2].label
        adds[2].click().run(); check()
        fields = page.session_state['_entry_ui_fields']
        day = next(x for x in fields if x['name'] == 'work_date')
        assert day['default'] == '2026-10-07' and len(day['options']) == 7 and not day.get('disabled'), (name, day)
        payload(title='ENTRY_UI_WORK_'+name, work_date='2026-10-09', due_date='2026-10-09')
        with app.get_conn() as c:
            item = dict(c.execute('SELECT * FROM weekly_plan_items WHERE title=?', ('ENTRY_UI_WORK_'+name,)).fetchone())
            uid = int(item['user_id'])
            count = c.execute('SELECT COUNT(*) FROM weekly_plan_items WHERE user_id=?', (uid,)).fetchone()[0]
        assert item['work_date'] == '2026-10-09'
        # Reproduce the reported order: weekly work exists first, then a new
        # Customer Work/customer is created, then the weekly work is edited.
        customer_name='ENTRY_LINK_CUSTOMER_'+name
        cid,_=prospects.create_prospect(app.get_conn,uid,customer_name,force=True,logger=app.LOGGER)
        case_id,_=customer_work.create_case(app.get_conn,uid,cid,'ENTRY_LINK_CASE_'+name,
                                           '2026-11-12 17:00:00',owner_uid=uid,logger=app.LOGGER)
        with app.get_conn() as c:
            c.execute('UPDATE customer_work_cases SET controller_user_id=?,priority_quadrant=4 WHERE id=?',
                      (item['controller_user_id'],case_id))
            assert c.execute('SELECT active FROM customers WHERE id=?',(cid,)).fetchone()[0]==0
        key = f"weekly_draft_edit_{uid}_2026-10-05_{item['id']}"
        next(x for x in page.button if x.key == key).click().run(); check()
        customer_pick=next(x for x in page.selectbox if x.label=='Khách hàng')
        customer_pick.select_index(next(n for n,label in enumerate(customer_pick.options) if label.startswith(customer_name))).run(); check()
        case_pick=next(x for x in page.selectbox if x.label=='Liên kết Công việc khách hàng (không bắt buộc)')
        case_pick.select_index(1).run(); check()
        assert next(x for x in page.session_state['_entry_ui_fields'] if x['name'] == 'title')['default'] == item['title']
        payload(title='ENTRY_UI_EDITED_'+name, work_date='2026-10-06', due_date='2026-10-08')
        with app.get_conn() as c:
            after = dict(c.execute('SELECT * FROM weekly_plan_items WHERE id=?', (item['id'],)).fetchone())
            assert c.execute('SELECT COUNT(*) FROM weekly_plan_items WHERE user_id=?', (uid,)).fetchone()[0] == count
            assert (after['title'], after['work_date']) == ('ENTRY_UI_EDITED_'+name, '2026-10-06')
            assert (after['customer_id'],after['linked_case_id'])==(cid,case_id)
            c.execute("UPDATE weekly_plans SET workflow_status='TRA_LAI',return_note='Điều chỉnh QA' WHERE id=?", (item['plan_id'],))
        page.run(); check()
        next(x for x in page.button if x.key == key).click().run(); check()
        payload(title='ENTRY_UI_RETURNED_'+name, work_date='2026-10-11', due_date='2026-10-11')
        with app.get_conn() as c:
            plan = entry._plan(c, uid, date(2026, 10, 5))
            assert plan['workflow_status'] == 'NHAP'
            assert c.execute('SELECT COUNT(*) FROM weekly_plan_items WHERE user_id=?', (uid,)).fetchone()[0] == count
            assert c.execute("SELECT COUNT(*) FROM weekly_plan_actions WHERE actor_user_id=? AND action='RETURN_TO_DRAFT'", (uid,)).fetchone()[0] == 1
        # Weekend work remains visible and its edit route survives another rerun.
        page.run(); check()
        assert any(x.key == key for x in page.button)
        with app.get_conn() as c:
            c.execute("UPDATE weekly_plans SET workflow_status='DA_NOP' WHERE id=?", (item['plan_id'],))
        page.run(); check()
        assert not any(x.label == '✏️ Sửa công việc' for x in page.button), name
    print('WEEKLY_ENTRY_INSTALLED_UI_QA_PASS support qlkh leader admin new_customer_after_plan prospect_visible linked_case_saved exact_clicked_day draft_edit returned_edit weekend rerun locked_submit no_duplicate actual_DB')


def installed_manager_customer_ui():
    """The live adjustment form sees prospects created after it was opened."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app, customer_work, potential_customer_patch as prospects
    script="""
import streamlit as st
from datetime import date
from khdn_apps import app, weekly_plan as core, weekly_priority_policy_patch as policy
from khdn_apps import planning_operational_phase3_weekly as board
from unittest.mock import patch
import importlib
bridge=importlib.import_module('khdn_apps.legacy_fast_form')
app.init_db();policy._ensure_schema(core,app.get_conn,app.LOGGER)
ws=date(2026,10,5);ts=policy._now()
name=st.session_state.get('manager_customer_actor','leader')
with app.get_conn() as c:
    u=dict(c.execute('SELECT * FROM users WHERE username=?',('entry_ui_'+name,)).fetchone())
    pid=core.ensure_plan(c,u['id'],ws)
    title='MANAGER_CUSTOMER_WEEK_'+name
    row=c.execute('SELECT * FROM weekly_plan_items WHERE title=?',(title,)).fetchone()
if not row:
    core.save_items(app.get_conn,u['id'],ws,[{'work_date':ws.isoformat(),'title':title}])
    with app.get_conn() as c:
        leader=c.execute("SELECT id FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY id LIMIT 1").fetchone()[0]
        c.execute("UPDATE weekly_plan_items SET expected_complete_date='2026-11-12',controller_user_id=?,priority_quadrant=4 WHERE title=?",(leader,title))
with app.get_conn() as c:
    item=dict(c.execute('SELECT * FROM weekly_plan_items WHERE title=?',(title,)).fetchone())
    plan=dict(c.execute('SELECT * FROM weekly_plans WHERE id=?',(pid,)).fetchone())
    focus=policy._focus_categories(c,policy._scope_key(c,u['id']),ws.year,False)
st.session_state['manager_customer_item_id']=item['id']
st.session_state['manager_customer_user_id']=u['id']
def component(**kwargs):
    if str(kwargs.get('key') or '').startswith('weekly_manager_edit_'):
        st.session_state['_manager_customer_fields']=kwargs['fields']
        st.session_state['_manager_customer_columns']=kwargs.get('columns')
        data=st.session_state.pop('_manager_customer_payload',None)
        if data is not None:
            seq=int(st.session_state.get('_manager_customer_seq',0))+1
            st.session_state['_manager_customer_seq']=seq
            return {'submit_id':f'manager-qa-{seq}','values':data}
    return None
with patch.object(bridge,'_component',component):
    board.manager_edit_item(st,u,policy,core,app.get_conn,plan,item,focus,app.LOGGER)
"""
    page=AppTest.from_string(script,default_timeout=30).run()

    def save():
        fields=page.session_state['_manager_customer_fields']
        page.session_state['_manager_customer_payload']={x['name']:x.get('default','') for x in fields}
        page.run()
        assert not page.exception,[x.message for x in page.exception]

    for actor in ('leader','admin'):
        page.session_state['manager_customer_actor']=actor;page.run()
        assert not page.exception,[x.message for x in page.exception]
        iid=page.session_state['manager_customer_item_id'];uid=page.session_state['manager_customer_user_id']
        label='MANAGER_NEW_CUSTOMER_'+actor
        assert not any(label in str(x) for x in next(x for x in page.selectbox if x.label=='Khách hàng').options)
        cid,_=prospects.create_prospect(app.get_conn,uid,label,force=True,logger=app.LOGGER)
        case_id,_=customer_work.create_case(app.get_conn,uid,cid,'MANAGER_NEW_CASE_'+actor,
                                            '2026-11-12 17:00:00',owner_uid=uid,logger=app.LOGGER)
        with app.get_conn() as c:
            ts=policy._now()
            important_id=int(c.execute('INSERT INTO important_categories(name,active,created_at,updated_at) VALUES(?,1,?,?)',('MANAGER_LINK_FOCUS_'+actor,ts,ts)).lastrowid)
            controller=c.execute('SELECT controller_user_id FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0]
            # Resolve the owner's catalog after its case controller is saved:
            # legacy users derive their room scope from Customer Work.
            c.execute('UPDATE customer_work_cases SET controller_user_id=?,important_category_id=?,priority_quadrant=2 WHERE id=?',(controller,important_id,case_id))
            focus_id=int(c.execute('''INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,active,legacy_category_id,created_at,updated_at)
                VALUES(?,2026,?,?,1,?,?,?)''',(policy._scope_key(c,uid),'MGRLINK_'+actor,'MANAGER_LINK_FOCUS_'+actor,important_id,ts,ts)).lastrowid)
            focus=dict(c.execute('SELECT * FROM weekly_focus_categories WHERE id=?',(focus_id,)).fetchone())
        page.run()
        assert not page.exception,[x.message for x in page.exception]
        customer=next(x for x in page.selectbox if x.label=='Khách hàng')
        customer.select_index(next(n for n,x in enumerate(customer.options) if x.startswith(label))).run()
        linked=next(x for x in page.selectbox if x.label=='Liên kết Công việc khách hàng (không bắt buộc)')
        assert any('MANAGER_NEW_CASE_'+actor in x for x in linked.options)
        linked.select_index(1).run()
        fields={x['name']:x for x in page.session_state['_manager_customer_fields']}
        assert fields['title']['default']=='MANAGER_CUSTOMER_WEEK_'+actor
        assert fields['due_date']['default']=='2026-11-12' and fields['due_date']['disabled']
        assert fields['controller']['default']==str(controller) and fields['controller']['disabled']
        assert 'focus' not in fields and 'nonfocus_q' not in fields
        assert page.session_state['_manager_customer_columns']==2 and not page.text_input and not page.text_area
        save()
        with app.get_conn() as c:
            item=dict(c.execute('SELECT * FROM weekly_plan_items WHERE id=?',(iid,)).fetchone())
            assert (item['customer_id'],item['customer_text'])==(cid,label)
            actual=(item['linked_case_id'],item['expected_complete_date'],item['controller_user_id'],item['priority_quadrant'],item['focus_category_id'])
            expected=(case_id,'2026-11-12',controller,2,focus['id'])
            assert actual==expected,(actor,actual,expected)
            assert c.execute("SELECT COUNT(*) FROM weekly_plan_actions WHERE item_id=? AND actor_user_id=? AND action='MANAGER_EDIT_PHASE3'",(iid,uid)).fetchone()[0]==1
        page.run()
        assert next(x for x in page.selectbox if x.label=='Liên kết Công việc khách hàng (không bắt buộc)').value['id']==case_id
        next(x for x in page.selectbox if x.label=='Liên kết Công việc khách hàng (không bắt buộc)').select_index(0).run()
        save()
        with app.get_conn() as c:
            assert c.execute('SELECT linked_case_id FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0] is None
        # Restore the relation, then changing the customer must clear it.
        next(x for x in page.selectbox if x.label=='Liên kết Công việc khách hàng (không bắt buộc)').select_index(1).run()
        save()
        next(x for x in page.selectbox if x.label=='Khách hàng').select_index(0).run()
        save()
        with app.get_conn() as c:
            item=dict(c.execute('SELECT * FROM weekly_plan_items WHERE id=?',(iid,)).fetchone())
            assert (item['customer_id'],item['linked_case_id'])==(None,None)
            assert c.execute('SELECT COUNT(*) FROM weekly_plan_items WHERE title=?',('MANAGER_CUSTOMER_WEEK_'+actor,)).fetchone()[0]==1
    print('WEEKLY_MANAGER_CUSTOMER_UI_QA_PASS leader admin new_customer_after_plan explicit_case_pick source_due_controller_Q2 persisted_link reopened_same_link unlink change_customer stable_item audit zero_keystroke_form')


def installed_customer_date_ui():
    """Create Customer Work through the final form for each role, persisting due dates."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    script = """
import streamlit as st
from unittest.mock import patch
import importlib
from khdn_apps import app, weekly_priority_policy_patch as policy, customer_work as core, customer_work_ui as ui
from khdn_apps import global_zero_keystroke_patch as zero, customer_work_refinement_patch as refinement, worktype_contact_card_patch as worktype
bridge=importlib.import_module('khdn_apps.legacy_fast_form')
app.init_db();ts=policy._now()
with app.get_conn() as c:
    name=st.session_state.get('customer_date_ui_actor','support')
    u=dict(c.execute('SELECT * FROM users WHERE username=?',('entry_ui_'+name,)).fetchone())
    c.execute("INSERT OR IGNORE INTO task_types(name,module_scope,sla_hours,active,created_at,updated_at) VALUES('DATE_UI_QA','PLAN',8,1,?,?)",(ts,ts))
    if not c.execute("SELECT id FROM customers WHERE customer_name='DATE_UI_CUSTOMER_QA'").fetchone():
        c.execute("INSERT INTO customers(customer_name,cif,active,created_at,updated_at) VALUES('DATE_UI_CUSTOMER_QA','DATEQA',1,?,?)",(ts,ts))
    customer=dict(c.execute("SELECT * FROM customers WHERE customer_name='DATE_UI_CUSTOMER_QA'").fetchone())
st.session_state['cw_customer_pick']=int(customer['id'])
def component(**kwargs):
    key=str(kwargs.get('key') or '')
    if key.startswith('p17_customer_work_create_'):
        st.session_state['_customer_date_fields']=kwargs['fields']
        st.session_state['_customer_date_columns']=kwargs.get('columns')
        payload=st.session_state.pop('_customer_date_payload',None)
        if payload is not None:
            seq=int(st.session_state.get('_customer_date_seq',0))+1;st.session_state['_customer_date_seq']=seq
            return {'submit_id':f'customer-qa-{seq}','values':payload}
    return None
with patch.object(bridge,'_component',component):
    zero._customer_create_fast(policy,st,u,app.get_conn,core,ui,refinement,worktype,app.LOGGER)
"""
    for n, name in enumerate(('support', 'qlkh', 'leader', 'admin')):
        page = AppTest.from_string(script, default_timeout=30)
        page.session_state['customer_date_ui_actor'] = name
        page.run()
        assert not page.exception, [x.message for x in page.exception]
        fields = page.session_state['_customer_date_fields']
        by_name = {x.get('name'): x for x in fields if x.get('name')}
        assert by_name['due_date']['type'] == 'date' and not by_name['due_date'].get('disabled')
        assert page.session_state['_customer_date_columns'] == 4
        payload = {key: x.get('default', '') for key, x in by_name.items()}
        for key in ('case_type', 'stage', 'owner', 'controller'):
            if not str(payload.get(key) or '').isdigit():
                payload[key] = next(x['value'] for x in by_name[key]['options'] if x['value'].isdigit())
        payload.update({'title': 'CUSTOMER_DATE_UI_'+name, 'focus':'NONE', 'due_date': f'2026-11-{10+n:02d}',
                        'contact_1_name':'Người liên hệ QA','contact_1_phone':'0900000000',
                        'contact_1_role': next(x['value'] for x in by_name['contact_1_role']['options'] if x['value'])})
        page.session_state['_customer_date_payload'] = payload
        page.run()
        assert not page.exception, [x.message for x in page.exception]
        with app.get_conn() as c:
            rows = c.execute('SELECT * FROM customer_work_cases WHERE title=?', ('CUSTOMER_DATE_UI_'+name,)).fetchall()
            assert len(rows) == 1, (name, [x.value for x in page.error])
            assert rows[0]['expected_complete_at'] == f'2026-11-{10+n:02d} 17:00:00'
        page.run()
        assert not page.exception, [x.message for x in page.exception]
        with app.get_conn() as c:
            assert c.execute('SELECT COUNT(*) FROM customer_work_cases WHERE title=?', ('CUSTOMER_DATE_UI_'+name,)).fetchone()[0] == 1
    print('CUSTOMER_DATE_INSTALLED_UI_QA_PASS support qlkh leader admin final_zero_keystroke_layout real_create due_date_persistence rerun_no_duplicate')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EntryQA))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('WEEKLY_ENTRY_EDIT_QA_PASS', result.testsRun, 'all_roles seven_days returned_lifecycle no_duplicate ownership locked_state freshness classification source_inheritance rollback')
