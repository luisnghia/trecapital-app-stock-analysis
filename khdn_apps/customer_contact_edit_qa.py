"""Test the installed contact editor using fake users in the runtime QA DB."""
from __future__ import annotations


def browser_contact_messages():
    """Optional Node check uses the actual fields and shipped iframe JS."""
    import json
    from pathlib import Path
    import shutil
    import subprocess
    import tempfile
    from types import SimpleNamespace
    from unittest.mock import patch
    from khdn_apps import planning_operational_phase10_patch as p10
    node = shutil.which('node')
    if node is None:
        return
    defaults = [{'name':'QA A','phone':'0900000001','role':'Giám đốc'},
                {'name':'QA B','phone':'0900000002','role':'Chức vụ cũ QA'},
                {'name':'','phone':'','role':''}]
    data = {'customer_id':1}
    for n,item in enumerate(defaults,1):
        prefix = 'contact' if n == 1 else f'contact{n}'
        data.update({f'{prefix}_{k}':v for k,v in item.items()})
    captured = {}
    def component(fields, button_label, **kwargs):
        captured.update(fields=fields,buttonLabel=button_label,resetToken=kwargs['reset_token'],columns=kwargs['columns'])
    with patch.object(p10,'legacy_fast_form',component):
        p10._render_contact_edit_fast(SimpleNamespace(session_state={}),1,1,data,defaults)
    with tempfile.TemporaryDirectory() as folder:
        fixture = Path(folder)/'contacts.json'
        fixture.write_text(json.dumps(captured,ensure_ascii=False))
        result = subprocess.run([node,str(Path(__file__).with_name('customer_contact_browser_qa.mjs')),str(fixture)],
                                capture_output=True,text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout.strip())


def installed_contact_ui():
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app, planning_operational_phase10_patch as p10, customer_work as core
    assert getattr(app.realtime_refresh_watch, "_khdn_mobile_guard", False), "Periodic reruns can interrupt contacts"
    script = '''
import streamlit as st
import importlib
from unittest.mock import patch
from khdn_apps import app, customer_work as core, customer_work_ui as ui
from khdn_apps import planning_operational_phase10_patch as p10
bridge = importlib.import_module('khdn_apps.legacy_fast_form')
app.init_db()
with app.get_conn() as c:
    ts = core.now_str()
    for name, role, admin in [('support','Cán bộ hỗ trợ',0), ('qlkh','Cán bộ QLKH',0),
                              ('leader','Lãnh đạo phòng',0), ('admin','Lãnh đạo phòng',1),
                              ('other_leader','Lãnh đạo phòng',0), ('other_staff','Cán bộ QLKH',0)]:
        c.execute("""INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at)
            VALUES(?,?,'QA_NO_LOGIN',?,?,1,?,?)""", ('contact_ui_'+name, 'CONTACT_UI_'+name, role, admin, ts, ts))
    users = {name: dict(c.execute('SELECT * FROM users WHERE username=?', ('contact_ui_'+name,)).fetchone())
             for name in ['support','qlkh','leader','admin','other_leader','other_staff']}
    if not st.session_state.get('contact_ui_seeded'):
        c.execute("INSERT INTO customers(cif,customer_name,active,created_at,updated_at) VALUES('CONTACT_UI_QA','CONTACT_UI_CUSTOMER',1,?,?)", (ts,ts))
        cid = int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        c.execute("""INSERT INTO customer_work_cases(case_code,customer_id,title,case_type,owner_user_id,plan_requested_by,
                     controller_user_id,expected_complete_at,status,plan_approval_status,created_at,updated_at)
                     VALUES('CONTACT_UI_QA',?,'CONTACT_UI_WORK','CONTACT_UI_TYPE',?,? ,?,'2026-11-01 17:00:00',
                     'OPEN','APPROVED',?,?)""", (cid,users['support']['id'],users['support']['id'],users['leader']['id'],ts,ts))
        case_id = int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        originals = [{'name':'QA A','phone':'0900000001','role':'Giám đốc'},
                     {'name':'QA B','phone':'0900000002','role':'Chức vụ cũ QA'}]
        p10._write_case_contacts(c,case_id,originals,ts)
        p10._sync_customer_contacts(c,cid,originals,users['support']['id'],ts,case_id)
        st.session_state['contact_ui_case'] = case_id
        st.session_state['contact_ui_customer'] = cid
        st.session_state['contact_ui_seeded'] = True
    case_id = int(st.session_state['contact_ui_case'])
    actor = st.session_state.get('contact_ui_actor','support')
    u = users[actor]
    if st.session_state.get('contact_ui_owner_self',True):
        c.execute('UPDATE customer_work_cases SET owner_user_id=? WHERE id=?', (u['id'],case_id))
def component(**kwargs):
    if str(kwargs.get('key','')).startswith('p10_contact_edit_fast_'):
        st.session_state['contact_ui_fields'] = kwargs['fields']
        st.session_state['contact_ui_key'] = kwargs['key']
        st.session_state['contact_ui_token'] = kwargs['resetToken']
        st.session_state['contact_ui_columns'] = kwargs['columns']
        queued = st.session_state.pop('contact_ui_submit',None)
        if queued is not None:
            st.session_state['contact_ui_last_submit'] = (kwargs['key'],queued)
        previous = st.session_state.get('contact_ui_last_submit')
        if previous and previous[0] == kwargs['key']: return previous[1]
    return None
with patch.object(bridge,'_component',component):
    ui._case_detail(st,u,app.get_conn,case_id,logger=app.LOGGER)
'''
    page = AppTest.from_string(script, default_timeout=30).run()

    def check():
        assert not page.exception, [x.message for x in page.exception]
        assert not any(x.label.startswith(('Người liên hệ ', 'SĐT ')) for x in page.text_input)
        assert not any(x.label.startswith('Chức vụ ') for x in page.selectbox)
        assert not any(x.label == 'Lưu thông tin liên hệ' for x in page.button)

    def state():
        with app.get_conn() as c:
            case = dict(c.execute('SELECT * FROM customer_work_cases WHERE id=?', (page.session_state['contact_ui_case'],)).fetchone())
            master = [dict(x) for x in c.execute('SELECT * FROM customer_contact_master WHERE customer_id=? ORDER BY slot',
                                               (page.session_state['contact_ui_customer'],))]
            audits = [dict(x) for x in c.execute("SELECT * FROM case_actions WHERE case_id=? AND action='CONTACT_UPDATE_P10' ORDER BY id",
                                               (page.session_state['contact_ui_case'],))]
        return case, master, audits

    def submit(values, number):
        page.session_state['contact_ui_submit'] = {'submit_id': 'contact-qa-'+str(number), 'values': values}
        page.run(); check()

    check()
    fields = page.session_state['contact_ui_fields']
    by_name = {x['name']: x for x in fields}
    assert len(by_name) == 9 and page.session_state['contact_ui_columns'] == 4
    assert by_name['contact_1_phone']['default'] == '0900000001'
    assert by_name['contact_2_role']['default'] == 'Chức vụ cũ QA'
    assert 'Chức vụ cũ QA' in [x['value'] for x in by_name['contact_2_role']['options']]
    key, token, before = page.session_state['contact_ui_key'], page.session_state['contact_ui_token'], state()
    page.run(); check()
    assert (page.session_state['contact_ui_key'],page.session_state['contact_ui_token']) == (key,token)
    assert state() == before, 'Rendering or reruns wrote contacts'
    # Neither an empty form nor a partially filled optional row can write.
    submit({name:'' for name in by_name},1)
    assert any('tối thiểu 1' in x.value for x in page.error) and state() == before
    values = {name:x['default'] for name,x in by_name.items()}
    values['contact_3_name'] = 'Incomplete QA'
    submit(values,2)
    assert any('Dòng chưa đủ' in x.value for x in page.error) and state() == before
    allowed_fields = {f'{prefix}_{field}' for prefix in ('contact','contact2','contact3') for field in ('name','phone','role')} | {'updated_at'}
    for number,actor in enumerate(['support','qlkh','leader','admin'],3):
        page.session_state['contact_ui_actor'] = actor; page.run(); check()
        start, _, audits = state()
        values = {x['name']:x.get('default','') for x in page.session_state['contact_ui_fields']}
        for slot in (1,2,3):
            values.update({f'contact_{slot}_name': f'QA {actor} {slot}',
                           f'contact_{slot}_phone': f'09000000{number}{slot}',
                           f'contact_{slot}_role': 'Giám đốc'})
        submit(values,number)
        case, master, after_audits = state()
        assert len(after_audits) == len(audits)+1 and len(master) == 3
        with app.get_conn() as c:
            uid = int(c.execute('SELECT id FROM users WHERE username=?',('contact_ui_'+actor,)).fetchone()[0])
        for slot in (1,2,3):
            prefix = 'contact' if slot == 1 else f'contact{slot}'
            for field in ('name','phone','role'):
                assert case[f'{prefix}_{field}'] == values[f'contact_{slot}_{field}']
                assert master[slot-1][f'contact_{field}'] == values[f'contact_{slot}_{field}']
            assert master[slot-1]['updated_by'] == uid and master[slot-1]['source_case_id'] == case['id']
        assert after_audits[-1]['actor_user_id'] == uid
        assert {k:v for k,v in start.items() if k not in allowed_fields} == {k:v for k,v in case.items() if k not in allowed_fields}
        page.run(); check(); assert state() == (case,master,after_audits)
        # A second explicit save of unchanged values is one event; its retained
        # component value must not create another update on the automatic rerun.
        submit(values,number+100)
        count = len(state()[2]); page.run(); check(); assert len(state()[2]) == count
    # Restrict the case back to the staff owner. Controller edits remain allowed;
    # a different leader only sees the table, while other staff sees no contacts.
    page.session_state['contact_ui_owner_self'] = False
    with app.get_conn() as c:
        owner = int(c.execute("SELECT id FROM users WHERE username='contact_ui_support'").fetchone()[0])
        c.execute('UPDATE customer_work_cases SET owner_user_id=? WHERE id=?', (owner,page.session_state['contact_ui_case']))
    page.session_state['contact_ui_actor'] = 'leader'; page.run(); check()
    assert any(x.label == '✏️ Sửa thông tin liên hệ' for x in page.expander)
    key_before, token_before = page.session_state['contact_ui_key'], page.session_state['contact_ui_token']
    with app.get_conn() as c:
        c.execute("UPDATE customer_work_cases SET note='Other case change QA',updated_at='2026-10-05 14:00:00' WHERE id=?",
                  (page.session_state['contact_ui_case'],))
    page.run(); check()
    assert (page.session_state['contact_ui_key'],page.session_state['contact_ui_token']) == (key_before,token_before)
    values = {x['name']:x.get('default','') for x in page.session_state['contact_ui_fields']}
    values['contact_1_name'] = 'Controller edit QA'
    for slot in (2,3):
        for field in ('name','phone','role'): values[f'contact_{slot}_{field}'] = ''
    submit(values,600)
    controlled_case, controlled_master, controlled_audits = state()
    assert controlled_case['contact_name'] == 'Controller edit QA' and controlled_case['owner_user_id'] == owner
    assert controlled_case['contact2_name'] is None and controlled_case['contact3_name'] is None and len(controlled_master) == 1
    assert controlled_audits[-1]['actor_user_id'] == controlled_case['controller_user_id']
    for actor in ['other_leader','other_staff']:
        page.session_state['contact_ui_actor'] = actor; page.run(); check()
        assert not any(x.label == '✏️ Sửa thông tin liên hệ' for x in page.expander)
    # Server-side checks cover a concurrent edit and revoked authority under a
    # write lock; transaction failures roll case/master/audit back together.
    case, master, audits = state()
    contacts = p10._case_contact_values(case)
    token = p10._contact_token(case)
    with app.get_conn() as c:
        other = int(c.execute("SELECT id FROM users WHERE username='contact_ui_other_leader'").fetchone()[0])
    try:
        p10._save_contact_edit(app.get_conn,core,case['id'],other,contacts,token)
        raise AssertionError('Out-of-scope leader accepted')
    except PermissionError: pass
    assert state() == (case,master,audits)
    with app.get_conn() as c:
        c.execute("UPDATE customer_work_cases SET contact_name='Concurrent QA' WHERE id=?", (case['id'],))
    changed = state()
    try:
        p10._save_contact_edit(app.get_conn,core,case['id'],owner,contacts,token)
        raise AssertionError('Stale contacts accepted')
    except ValueError: pass
    assert state() == changed
    case, master, audits = state(); token = p10._contact_token(case)
    with app.get_conn() as c:
        c.execute('UPDATE users SET active=0 WHERE id=?',(owner,))
    try:
        p10._save_contact_edit(app.get_conn,core,case['id'],owner,contacts,token)
        raise AssertionError('Inactive actor accepted')
    except PermissionError: pass
    assert state() == (case,master,audits)
    with app.get_conn() as c:
        c.execute('UPDATE users SET active=1 WHERE id=?',(owner,))
        c.execute("""CREATE TRIGGER qa_contact_rollback BEFORE INSERT ON case_actions
                     WHEN NEW.action='CONTACT_UPDATE_P10' BEGIN SELECT RAISE(ABORT,'QA rollback'); END""")
    try:
        import sqlite3
        p10._save_contact_edit(app.get_conn,core,case['id'],owner,contacts,token)
        raise AssertionError('Rollback trigger ignored')
    except sqlite3.IntegrityError: pass
    assert state() == (case,master,audits)
    with app.get_conn() as c: c.execute('DROP TRIGGER qa_contact_rollback')
    print('CUSTOMER_CONTACT_EDIT_INSTALLED_UI_QA_PASS support qlkh leader admin controller readonly_other_leader no_native_contact_fields stable_draft_identity submit_only validation leading_zero three_contacts shared_master no_duplicate stale_edit revoked_actor atomic_rollback periodic_refresh_disabled')
