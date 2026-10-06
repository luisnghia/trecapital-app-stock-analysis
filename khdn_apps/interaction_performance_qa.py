"""Regression checks for bounded rendering and submit-only detail actions.

These are runtime/communication checks. They do not claim physical Safari latency.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def bridge_checks():
    bridge = importlib.import_module('khdn_apps.legacy_fast_form')
    warnings = []
    state = {}
    fake = SimpleNamespace(session_state=state, warning=warnings.append)
    current = {'submit_id':'first', 'reset_token':'saved-a','values':{'note':'Nội dung mới'}}
    with patch.object(bridge, 'st', fake), patch.object(bridge, '_component', lambda **_: current):
        assert bridge.legacy_fast_form([], 'Lưu', 'qa', reset_token='saved-a') == {'note':'Nội dung mới'}
        assert bridge.legacy_fast_form([], 'Lưu', 'qa', reset_token='saved-a') is None
        current = {'submit_id':'stale', 'reset_token':'saved-a','values':{'note':'Ghi đè'}}
        assert bridge.legacy_fast_form([], 'Lưu', 'qa', reset_token='saved-b') is None
        assert len(warnings) == 1
        current = {'submit_id':'fresh', 'reset_token':'saved-b','values':{'note':'Đúng phiên bản'}}
        assert bridge.legacy_fast_form([], 'Lưu', 'qa', reset_token='saved-b') == {'note':'Đúng phiên bản'}
    print('INTERACTION_BRIDGE_QA_PASS submit_once stale_rejected no_typing_messages')


def installed_pages():
    from streamlit.testing.v1 import AppTest
    script = '''
import streamlit as st
from khdn_apps.interaction_performance import page_rows
rows=[{'id':i} for i in range(st.session_state.get('qa_count',75))]
shown=page_rows(st,rows,'qa')
st.session_state['qa_visible']=[x['id'] for x in shown]
for row in shown:st.text(f"Công việc {row['id']}")
'''
    page = AppTest.from_string(script).run()
    assert not page.exception
    seen = []
    while True:
        ids = page.session_state['qa_visible']
        assert len(ids) <= 24
        seen += ids
        next_button = next(x for x in page.button if x.label == 'Sau →')
        if next_button.disabled:break
        next_button.click().run()
        assert not page.exception
    assert seen == list(range(75)), seen
    next(x for x in page.button if x.label == '← Trước').click().run()
    assert page.session_state['qa_visible'][0] == 48
    page.session_state['qa_count'] = 30; page.run()
    assert page.session_state['qa_visible'] == list(range(24))
    page.session_state['qa_count'] = 5; page.run()
    assert not page.button and page.session_state['qa_visible'] == list(range(5))

    # Closed expanders keep complete counts but skip their hidden card work.
    script = '''
import streamlit as st
from khdn_apps.priority_today_patch import _render_priority_heatmap
from types import SimpleNamespace
st.session_state['qa_cards']=[]
def card(st,x,*args,**kwargs):st.session_state['qa_cards'].append(x['id'])
def sort_parse(v):return None
ui=SimpleNamespace(core=SimpleNamespace(parse_dt=sort_parse,quadrant_label=lambda q:str(q)),_case_card=card)
data=[{'id':i,'quadrant':4,'expected_complete_at':None} for i in range(75)]
_render_priority_heatmap(st,ui,data,None,7,False)
'''
    page = AppTest.from_string(script).run()
    assert not page.exception,[e.message for e in page.exception]
    assert page.session_state['qa_cards'] == []
    page.session_state['today_priority_open_7_4'] = True;page.run()
    assert not page.exception,[e.message for e in page.exception]
    assert len(page.session_state['qa_cards']) == 24
    print('INTERACTION_PAGES_QA_PASS all_rows_reachable ordering next_previous filter_reset lazy_open')


def note_checks():
    from khdn_apps.customer_work_manager_note_history_qa import c, get_conn
    from khdn_apps.customer_work_manager_note_history_patch import update_case_note
    original = c.execute('SELECT note FROM customer_work_cases WHERE id=10').fetchone()[0]
    audits = c.execute('SELECT COUNT(*) FROM case_actions').fetchone()[0]
    try:
        update_case_note(get_conn,10,1,'Ghi đè',expected_note='stale')
        raise AssertionError('Stale note was overwritten')
    except ValueError:pass
    assert c.execute('SELECT note FROM customer_work_cases WHERE id=10').fetchone()[0] == original
    assert c.execute('SELECT COUNT(*) FROM case_actions').fetchone()[0] == audits
    c.execute('UPDATE users SET active=0 WHERE id=1');c.commit()
    try:
        update_case_note(get_conn,10,1,'Không được phép',expected_note=original)
        raise AssertionError('Revoked actor saved a note')
    except PermissionError:pass
    assert c.execute('SELECT COUNT(*) FROM case_actions').fetchone()[0] == audits
    c.execute('UPDATE users SET active=1 WHERE id=1');c.commit()
    assert update_case_note(get_conn,10,1,'Dòng một\nDòng hai',expected_note=original)
    assert c.execute('SELECT note FROM customer_work_cases WHERE id=10').fetchone()[0] == 'Dòng một\nDòng hai'
    print('INTERACTION_NOTE_QA_PASS multiline fresh_authority stale_rejected atomic_audit')


def run():
    bridge_checks();installed_pages();note_checks()


def installed_detail_actions(expect_manager_note=True):
    """Exercise the final detail stack and real saves for each role in QA DB."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    script = '''
import streamlit as st, importlib
from unittest.mock import patch
from khdn_apps import app,customer_work as core,customer_work_ui as ui
bridge=importlib.import_module('khdn_apps.legacy_fast_form')
actor=st.session_state.get('detail_perf_actor','support')
with app.get_conn() as c:
    ts=core.now_str()
    for name,role,admin in [('support','Cán bộ hỗ trợ',0),('qlkh','Cán bộ QLKH',0),('leader','Lãnh đạo phòng',0),('admin','Lãnh đạo phòng',1)]:
        c.execute("INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at) VALUES(?,?,'QA_NO_LOGIN',?,?,1,?,?)",('detail_perf_'+name,'DETAIL PERF '+name,role,admin,ts,ts))
    users={name:dict(c.execute('SELECT * FROM users WHERE username=?',('detail_perf_'+name,)).fetchone()) for name in ('support','qlkh','leader','admin')}
    if 'detail_perf_cases' not in st.session_state:
        ids={}
        stage=c.execute('SELECT id FROM work_stage_catalog WHERE active=1 ORDER BY sort_order,id LIMIT 1').fetchone()[0]
        for name,u in users.items():
            c.execute("INSERT INTO customers(cif,customer_name,active,created_at,updated_at) VALUES(?,?,1,?,?)",('DETAIL_PERF_'+name,'DETAIL PERF '+name,ts,ts))
            cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
            c.execute("INSERT INTO customer_work_cases(case_code,customer_id,title,case_type,owner_user_id,controller_user_id,current_stage_id,stage_started_at,expected_complete_at,status,plan_approval_status,note,created_at,updated_at) VALUES(?,?,'Công việc QA','Tín dụng',?,?,?,?,'2026-12-01 17:00:00','ACTIVE','APPROVED','Ghi chú ban đầu',?,?)",('DETAIL_PERF_'+name,cid,u['id'],users['leader']['id'],stage,ts,ts,ts))
            ids[name]=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        st.session_state['detail_perf_cases']=ids
u=users[actor];case_id=st.session_state['detail_perf_cases'][actor]
st.session_state['detail_perf_fields']={}
def component(**kwargs):
    key=kwargs['key'];st.session_state['detail_perf_fields'][key]=kwargs
    queued=st.session_state.get('detail_perf_submit')
    if queued and queued[0]==key:
        st.session_state.pop('detail_perf_submit')
        st.session_state['detail_perf_last']=(key,queued[1])
    previous=st.session_state.get('detail_perf_last')
    return previous[1] if previous and previous[0]==key else None
with patch.object(bridge,'_component',component):
    ui._case_detail(st,u,app.get_conn,case_id,logger=app.LOGGER)
'''
    page=AppTest.from_string(script,default_timeout=30).run()

    def check():
        assert not page.exception,[x.message for x in page.exception]
        assert not page.text_input and not page.text_area, 'Native detail drafts returned'

    def submit(prefix,values,nonce):
        fields=page.session_state['detail_perf_fields']
        key=next(k for k in fields if k.startswith(prefix))
        payload={'submit_id':nonce,'reset_token':fields[key]['resetToken'],'values':values}
        page.session_state['detail_perf_submit']=(key,payload)
        page.run();check()

    for actor in ('support','qlkh','leader','admin'):
        page.session_state['detail_perf_actor']=actor;page.run();check()
        case_id=page.session_state['detail_perf_cases'][actor]
        with app.get_conn() as c:
            stages=[int(x[0]) for x in c.execute('SELECT id FROM work_stage_catalog WHERE active=1 ORDER BY sort_order,id')]
            audit_before=c.execute('SELECT COUNT(*) FROM case_actions WHERE case_id=?',(case_id,)).fetchone()[0]
        submit('cw_stage_fast_',{'stage_id':str(stages[1]),'note':'Tiến độ QA\nDòng tiếp theo'},actor+'_stage')
        with app.get_conn() as c:
            assert c.execute('SELECT current_stage_id FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()[0]==stages[1]
            assert c.execute('SELECT note FROM case_stage_history WHERE case_id=? ORDER BY id DESC LIMIT 1',(case_id,)).fetchone()[0]=='Tiến độ QA\nDòng tiếp theo'
        submit('cw_issue_fast_',{'issue':'Vướng mắc QA\nGiữ đủ nội dung','severity':'HIGH'},actor+'_issue')
        with app.get_conn() as c:
            issue=c.execute('SELECT * FROM case_issues WHERE case_id=? ORDER BY id DESC LIMIT 1',(case_id,)).fetchone()
            assert issue['severity']=='HIGH' and issue['issue_text']=='Vướng mắc QA\nGiữ đủ nội dung'
        submit('cw_resolve_fast_',{'resolution':'Đã xử lý QA'},actor+'_resolve')
        with app.get_conn() as c:
            assert c.execute('SELECT resolution_text FROM case_issues WHERE id=?',(issue['id'],)).fetchone()[0]=='Đã xử lý QA'
        submit('cw_move_fast_',{'date':'2026-12-20','time':'15:30','reason':'Đổi thời gian QA'},actor+'_move')
        with app.get_conn() as c:
            requests=c.execute('SELECT * FROM case_reschedule_requests WHERE case_id=?',(case_id,)).fetchall()
            assert len(requests)==1 and requests[0]['proposed_due_at']=='2026-12-20 15:30:00'
        if expect_manager_note and actor in ('leader','admin'):
            submit('cw_manager_note_fast_',{'note':'Ghi chú QA\nNội dung đầy đủ'},actor+'_note')
            with app.get_conn() as c:
                assert c.execute('SELECT note FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()[0]=='Ghi chú QA\nNội dung đầy đủ'
                assert c.execute("SELECT COUNT(*) FROM case_actions WHERE case_id=? AND action='NOTE_EDIT'",(case_id,)).fetchone()[0]==1
        submit('p12_case_cancel_fast_',{'reason':'Đề nghị hủy QA'},actor+'_cancel')
        with app.get_conn() as c:
            assert c.execute('SELECT status FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()[0]=='ACTIVE'
            assert c.execute('SELECT status FROM customer_work_cancel_requests WHERE case_id=?',(case_id,)).fetchone()[0]=='PENDING'
            state=(dict(c.execute('SELECT * FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()),c.execute('SELECT COUNT(*) FROM case_actions WHERE case_id=?',(case_id,)).fetchone()[0])
        page.run();check()
        with app.get_conn() as c:
            assert state==(dict(c.execute('SELECT * FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()),c.execute('SELECT COUNT(*) FROM case_actions WHERE case_id=?',(case_id,)).fetchone()[0])
    print('INTERACTION_DETAIL_INSTALLED_QA_PASS support qlkh leader admin local_drafts stage issue resolve reschedule cancel_pending audit no_duplicate manager_note='+str(int(expect_manager_note)))


if __name__ == '__main__':run()
