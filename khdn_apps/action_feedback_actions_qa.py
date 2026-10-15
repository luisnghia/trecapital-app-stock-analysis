"""Exercise committed work actions through the final installed UI renderers.

Called by runtime_page_qa with its isolated SQLite database. No real users,
sessions, work records or Push endpoints are used.
"""
from __future__ import annotations


SCRIPT = '''
import streamlit as st
from datetime import date
from unittest.mock import patch
from khdn_apps import app, weekly_plan as core, weekly_priority_policy_patch as policy
from khdn_apps import customer_work as cw, customer_work_ui as cui
from khdn_apps import planning_operational_phase3_weekly as week
from khdn_apps import planning_operational_phase4_patch as p4
from khdn_apps import planning_operational_phase7_patch as p7
from khdn_apps import planning_dashboard_consolidation_patch as consolidation
from khdn_apps import planning_room_dashboard_detail_patch as room
from khdn_apps import weekly_performance_phase2_patch as phase2
from khdn_apps.action_feedback_patch import run_with_feedback

ws = date(2026,12,7)
phase2._ensure_schema(policy,core,app.get_conn,app.LOGGER)
with app.get_conn() as c:
    ts = policy._now()
    for name,role,admin in [('support','Cán bộ hỗ trợ',0),('qlkh','Cán bộ QLKH',0),
                            ('leader','Lãnh đạo phòng',0),('admin','Lãnh đạo phòng',1)]:
        c.execute("""INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at)
                     VALUES(?,?,'QA_NO_LOGIN',?,?,1,?,?)""",('feedback_'+name,'FEEDBACK '+name,role,admin,ts,ts))
    users = {name:dict(c.execute('SELECT * FROM users WHERE username=?',('feedback_'+name,)).fetchone())
             for name in ('support','qlkh','leader','admin')}
    if not st.session_state.get('feedback_seeded'):
        items={}; plans={}
        for name,u in users.items():
            pid=core.ensure_plan(c,int(u['id']),ws)
            c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET' WHERE id=?",(pid,))
            c.execute("""INSERT INTO weekly_plan_items(plan_id,user_id,work_date,title,status,controller_user_id,
                         expected_complete_date,created_at,updated_at) VALUES(?,?,?,'FEEDBACK work','PLANNED',?,?,?,?)""",
                         (pid,u['id'],ws.isoformat(),users['leader']['id'],'2026-12-08',ts,ts))
            items[name]=int(c.execute('SELECT last_insert_rowid()').fetchone()[0]);plans[name]=pid
        c.execute("INSERT INTO customers(cif,customer_name,qlkh_user_id,active,created_at,updated_at) VALUES('FEEDBACK_QA','FEEDBACK customer',?,1,?,?)",
                  (users['qlkh']['id'],ts,ts))
        customer=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        stage=c.execute('SELECT id FROM work_stage_catalog WHERE active=1 ORDER BY sort_order,id LIMIT 1').fetchone()[0]
        c.execute("""INSERT INTO customer_work_cases(case_code,customer_id,title,case_type,owner_user_id,controller_user_id,
                     current_stage_id,expected_complete_at,status,plan_approval_status,created_at,updated_at)
                     VALUES('FEEDBACK_QA',?,'FEEDBACK case','Tín dụng',?,?,?,'2026-12-08 17:00:00','ACTIVE','PENDING',?,?)""",
                  (customer,users['qlkh']['id'],users['leader']['id'],stage,ts,ts))
        st.session_state['feedback_case']=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        st.session_state['feedback_items']=items;st.session_state['feedback_plans']=plans
        st.session_state['feedback_seeded']=True
    actor=st.session_state.get('feedback_actor','support');u=users[actor]
    iid=st.session_state['feedback_items'][actor];pid=st.session_state['feedback_plans'][actor]
    item=dict(c.execute('SELECT * FROM weekly_plan_items WHERE id=?',(iid,)).fetchone())
    plan=dict(c.execute('SELECT * FROM weekly_plans WHERE id=?',(pid,)).fetchone())
    case=cw.get_case(c,st.session_state['feedback_case'])
    st.session_state['feedback_user_ids']={name:row['id'] for name,row in users.items()}

def render():
    app.inject_css()
    mode=st.session_state.get('feedback_mode','progress')
    if mode=='progress':
        week.render_week_update_form(st,u,policy,core,app.get_conn,item,app.LOGGER)
    elif mode=='board':
        week.render_week_board(st,policy,core,app.get_conn,int(u['id']),ws,[item],plan['workflow_status'])
    elif mode=='close':
        metrics=dict(completed=1,total=1,ontime_rate=100,overdue_open=0,q2_delayed=0,emergent=0,progress=100)
        week._render_self_close(st,u,policy,app.get_conn,ws,plan,metrics)
    elif mode=='returned':
        policy._render_staff_week(st,u,core,app.get_conn,ws,plan,[item],[],logger=app.LOGGER)
    elif mode=='plan_decision':
        owner=users['qlkh'];target=st.session_state['feedback_plans']['qlkh']
        with app.get_conn() as c:
            pending=dict(c.execute('SELECT * FROM weekly_plans WHERE id=?',(target,)).fetchone())
        pending['full_name']=owner['full_name']
        with patch.object(p4,'_pending_approval_data',return_value=(int(u['id']),[],[],[pending],[])):
            p4._render_approval_items(st,u,policy,core,cw,cui,app.get_conn,app.LOGGER)
    elif mode=='case_decision':
        consolidation._render_case_approval_card(st,policy,cw,app.get_conn,case,int(u['id']),app.LOGGER)
    elif mode=='case_move':
        with app.get_conn() as c:
            request=dict(c.execute('SELECT * FROM case_reschedule_requests WHERE id=?',(st.session_state['feedback_request'],)).fetchone())
        room._render_case_move_card(st,cw,cui,app.get_conn,request,int(u['id']),app.LOGGER)
    elif mode=='week_move':
        with app.get_conn() as c:
            request=dict(c.execute('SELECT * FROM weekly_plan_reschedule_requests WHERE id=?',(st.session_state['feedback_request'],)).fetchone())
        room._weekly_move_card(st,policy,app.get_conn,request,int(u['id']))
    elif mode=='cancel_decision':
        p7._P13_SAVED_WEEK_CANCEL_RENDERER(st,u,policy,app.get_conn,app.LOGGER)
run_with_feedback(st,render)
'''


def installed_actions_ui():
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app, customer_work as cw
    from khdn_apps import planning_operational_phase7_patch as p7
    from khdn_apps.action_feedback_patch import TITLE, SECONDS

    page = AppTest.from_string(SCRIPT, default_timeout=30).run()

    def check():
        assert not page.exception, [e.message for e in page.exception]

    def show(actor, mode):
        page.session_state['feedback_actor'] = actor
        page.session_state['feedback_mode'] = mode
        page.run(); check()
        assert not page.get('toast'), 'Navigation must not replay saved confirmations'

    def saved(key, expected):
        page.button(key=key).click().run(); check()
        toasts = page.get('toast')
        assert len(toasts) == 1, (key, [x.proto.body for x in toasts])
        assert TITLE in toasts[0].proto.body and expected in toasts[0].proto.body, (key,toasts[0].proto.body)
        assert toasts[0].proto.duration == SECONDS, key
        page.run(); check()
        assert not page.get('toast'), (key, 'confirmation replayed')

    check()
    for actor in ('support','qlkh','leader','admin'):
        show(actor, 'progress')
        iid = page.session_state['feedback_items'][actor]
        pid = page.session_state['feedback_plans'][actor]
        uid = page.session_state['feedback_user_ids'][actor]
        # Validation failure is not a saved operation.
        page.selectbox(key=f'p7_status_{iid}').select('CANCELLED').run(); check()
        page.button(key=f'p7_update_save_{iid}').click().run(); check()
        assert page.error and not page.get('toast'), actor
        with app.get_conn() as c:
            assert c.execute('SELECT status FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0]=='PLANNED'
        page.selectbox(key=f'p7_status_{iid}').select('IN_PROGRESS').run(); check()
        page.text_area(key=f'p7_result_{iid}').input('Kết quả QA\nGiữ đủ nội dung').run(); check()
        saved(f'p7_update_save_{iid}', 'Đã lưu tiến độ và kết quả')
        with app.get_conn() as c:
            row=c.execute('SELECT status,actual_result FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()
            assert tuple(row)==('IN_PROGRESS','Kết quả QA\nGiữ đủ nội dung'), (actor,tuple(row))
            assert c.execute("SELECT COUNT(*) FROM weekly_plan_actions WHERE item_id=? AND action='EXEC_UPDATE_PHASE3'",(iid,)).fetchone()[0]==1
            c.execute("UPDATE weekly_plans SET workflow_status='NHAP' WHERE id=?",(pid,))
        show(actor,'board')
        saved(f'p13_remove_{uid}_{iid}', 'Đã bỏ công việc')
        with app.get_conn() as c:
            assert c.execute('SELECT status FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0]=='CANCELLED'
            c.execute("UPDATE weekly_plan_items SET status='DONE' WHERE id=?",(iid,))
            c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET' WHERE id=?",(pid,))
        show(actor,'close')
        saved(f'p3_close_{pid}', 'Đã chốt tuần')
        with app.get_conn() as c:
            row=c.execute('SELECT workflow_status,classification_locked FROM weekly_plans WHERE id=?',(pid,)).fetchone()
            assert tuple(row)==('DA_CHOT',1), (actor,tuple(row))
            c.execute("UPDATE weekly_plans SET workflow_status='TRA_LAI' WHERE id=?",(pid,))
        show(actor,'returned')
        saved(f'return_to_draft_{pid}', 'Đã mở bản nháp')
        with app.get_conn() as c:
            assert c.execute('SELECT workflow_status FROM weekly_plans WHERE id=?',(pid,)).fetchone()[0]=='NHAP'

    # Exercise each decision in the same handlers leaders and Admin use.
    for actor in ('leader','admin'):
        uid=page.session_state['feedback_user_ids'][actor]
        owner=page.session_state['feedback_user_ids']['qlkh']
        pid=page.session_state['feedback_plans']['qlkh']
        iid=page.session_state['feedback_items']['qlkh']
        case_id=page.session_state['feedback_case']
        for approve in (True,False):
            with app.get_conn() as c:
                c.execute("UPDATE weekly_plans SET workflow_status='DA_NOP' WHERE id=?",(pid,))
            show(actor,'plan_decision')
            if not approve:
                page.text_area(key=f'p4_plan_note_{pid}').input('Bổ sung kết quả đầu ra').run();check()
            saved(f"p4_plan_{'yes' if approve else 'back'}_{pid}", 'Đã phê duyệt' if approve else 'Đã trả lại')
            with app.get_conn() as c:
                assert c.execute('SELECT workflow_status FROM weekly_plans WHERE id=?',(pid,)).fetchone()[0]==('DA_DUYET' if approve else 'TRA_LAI')
                c.execute("UPDATE customer_work_cases SET plan_approval_status='PENDING' WHERE id=?",(case_id,))
            show(actor,'case_decision')
            saved(f"pd_case_{'yes' if approve else 'no'}_{case_id}", 'Đã phê duyệt' if approve else 'Đã từ chối')
            with app.get_conn() as c:
                assert c.execute('SELECT plan_approval_status FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()[0]==('APPROVED' if approve else 'REJECTED')
            req,_=cw.request_reschedule(app.get_conn,case_id,owner,'2026-12-20 15:30:00','Dời hạn QA')
            page.session_state['feedback_request']=req
            with app.get_conn() as c:
                before=c.execute('SELECT expected_complete_at FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()[0]
            show(actor,'case_move')
            saved(f"room_cr_{'yes' if approve else 'no'}_{req}", 'Đã phê duyệt' if approve else 'Đã từ chối')
            with app.get_conn() as c:
                actions_before=c.execute('SELECT COUNT(*) FROM case_actions WHERE case_id=?',(case_id,)).fetchone()[0]
            page.button(key=f"room_cr_{'yes' if approve else 'no'}_{req}").click().run();check()
            notices=page.get('toast')
            assert len(notices)==1 and 'đã được xử lý trước đó' in notices[0].proto.body
            assert TITLE not in notices[0].proto.body, 'A stale decision is not a new success'
            with app.get_conn() as c:
                assert c.execute('SELECT COUNT(*) FROM case_actions WHERE case_id=?',(case_id,)).fetchone()[0]==actions_before
                assert c.execute('SELECT status FROM case_reschedule_requests WHERE id=?',(req,)).fetchone()[0]==('APPROVED' if approve else 'REJECTED')
                after=c.execute('SELECT expected_complete_at FROM customer_work_cases WHERE id=?',(case_id,)).fetchone()[0]
                assert after==('2026-12-20 15:30:00' if approve else before)
                c.execute("""INSERT INTO weekly_plan_reschedule_requests(item_id,requested_by,old_work_date,proposed_work_date,reason,status,requested_at)
                             VALUES(?,?,'2026-12-07','2026-12-09','Dời ngày QA','PENDING',?)""",(iid,owner,cw.now_str()))
                req=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
                before=c.execute('SELECT work_date FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0]
            page.session_state['feedback_request']=req
            show(actor,'week_move')
            saved(f"room_wr_{'yes' if approve else 'no'}_{req}", 'Đã phê duyệt' if approve else 'Đã từ chối')
            with app.get_conn() as c:
                assert c.execute('SELECT status FROM weekly_plan_reschedule_requests WHERE id=?',(req,)).fetchone()[0]==('APPROVED' if approve else 'REJECTED')
                assert c.execute('SELECT work_date FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0]==('2026-12-09' if approve else before)
                c.execute("UPDATE weekly_plan_items SET status='IN_PROGRESS' WHERE id=?",(iid,))
            req=p7._request_cancel(app.get_conn,iid,owner,'Hủy QA')
            show(actor,'cancel_decision')
            if not approve:
                page.button(key=f'p7_cancel_no_{req}').click().run();check()
                assert page.error and not page.get('toast'), 'Rejected cancellation requires a reason'
                page.text_input(key=f'p7_cancel_decision_note_{req}').input('Tiếp tục thực hiện').run();check()
            saved(f"p7_cancel_{'yes' if approve else 'no'}_{req}", 'Đã phê duyệt' if approve else 'Đã từ chối')
            with app.get_conn() as c:
                assert c.execute('SELECT status FROM weekly_plan_cancel_requests WHERE id=?',(req,)).fetchone()[0]==('APPROVED' if approve else 'REJECTED')
                assert c.execute('SELECT status FROM weekly_plan_items WHERE id=?',(iid,)).fetchone()[0]==('CANCELLED' if approve else 'IN_PROGRESS')

    print('ACTION_FEEDBACK_ACTIONS_UI_QA_PASS four_roles progress remove close returned_draft leader_admin approve return reject reschedule cancel validation_no_success no_replay persisted_results')
