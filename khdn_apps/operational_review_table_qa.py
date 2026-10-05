"""Exercise direct row events and real scoring with an isolated QA database."""
from __future__ import annotations


def installed_review_ui():
    import json
    import re
    from streamlit.testing.v1 import AppTest
    from streamlit.components.v2.bidi_component.main import _make_trigger_id
    from khdn_apps import app
    script = '''
import streamlit as st
from khdn_apps import app
app.init_db()
with app.get_conn() as c:
    ts=app.now_str()
    for name,role,admin in [('leader','Lãnh đạo phòng',0),('admin','Lãnh đạo phòng',1),
                            ('owner','Cán bộ QLKH',0),('other','Cán bộ QLKH',0),('support','Cán bộ hỗ trợ',0)]:
        c.execute("""INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at)
            VALUES(?,?, 'QA_NO_LOGIN',?,?,1,?,?)""",('ops_review_qa_'+name,'OPS_REVIEW_QA_'+name,role,admin,ts,ts))
    users={name:dict(c.execute('SELECT * FROM users WHERE username=?',('ops_review_qa_'+name,)).fetchone())
           for name in ['leader','admin','owner','other','support']}
    if not st.session_state.get('ops_review_qa_seeded'):
        c.execute("INSERT INTO customers(cif,customer_name,created_at,updated_at) VALUES('OPS_REVIEW_QA','Khách hàng <script>QA</script>',?,?)",(ts,ts))
        cid=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        ids=[]
        for number,status in enumerate(['PENDING_REVIEW','PENDING_REVIEW','PENDING_REVIEW','OPEN']):
            owner=users['other' if number==1 else 'owner']['id']
            c.execute("""INSERT INTO tasks(task_code,customer_id,support_user_id,qlkh_user_id,request_source,
                assigned_at,accepted_at,first_accepted_at,task_type,amount,currency,fx_rate,amount_vnd,
                start_time,end_time,note,status,current_round,created_at,updated_at)
                VALUES(?,?,?,?,'QLKH','2026-10-05 08:00:00','2026-10-05 08:15:00','2026-10-05 08:15:00',
                'OPS_REVIEW_QA_WORK',2000000000,'VND',1,2000000000,'2026-10-05 08:15:00',?,?,?,1,?,?)""",
                (f'OPS_REVIEW_QA_{number}',cid,users['support']['id'],owner,
                 '2026-10-05 09:00:00' if status=='PENDING_REVIEW' else None,'OPS_REVIEW_QA_NOTE',status,ts,ts))
            ids.append(int(c.execute('SELECT last_insert_rowid()').fetchone()[0]))
        st.session_state['ops_review_qa_ids']=ids
        st.session_state['ops_review_qa_seeded']=True
        st.session_state['leader_role_ops_mode']='qlkh'
        st.session_state['leader_qlkh_view']='review'
    actor=st.session_state.get('ops_review_qa_actor','leader')
    u=users[actor]
if actor in ['leader','admin']:
    app.leader_page(u)
elif actor == 'owner' and st.session_state.get('ops_review_qa_native_qlkh'):
    st.session_state['qlkh_view'] = 'review'
    app.qlkh_page(u)
else:
    sql,params=app.visible_tasks_sql(u)
    rows=app.enrich_tasks(app.qdf(sql,params))
    rows=rows[rows.status.eq('PENDING_REVIEW')]
    selected=app.selectable_task_table(rows,'qa_common_eval_table',include_phase=True)
    if selected is not None: st.caption('QA_SELECTED_TASK='+str(int(selected.id)))
'''
    page = AppTest.from_string(script, default_timeout=30).run()

    def check(page):
        assert not page.exception, [e.message for e in page.exception]
        assert len(page.dataframe) == 0, 'Review/history still invokes the failing DataFrame component'

    def bridge(page, key="leader_ql_eval_task_table"):
        return next(x for x in page.get('bidi_component') if x.key == key + '_row_click')

    def click_row(page, row_identity, key="leader_ql_eval_task_table", **overrides):
        component = bridge(page, key)
        data = json.loads(component.proto.json)
        payload = {**data, 'identity': str(row_identity), 'round': 1, **overrides}
        widgets = page._tree.get_widget_states()
        widgets.widgets.add(id=_make_trigger_id(component.proto.id, 'events'),
                            json_trigger_value=json.dumps([{'event': 'row_clicked', 'value': payload}]))
        page._run(widgets)
        check(page)

    def table(page):
        return next(x.proto.body for x in page.get('html') if "class='ops-review-table'" in x.proto.body)

    def check_no_menu(page):
        assert not any(x.label in ['Chọn công việc cần đánh giá', 'Chọn công việc để thao tác',
                                  'Chọn hồ sơ và vòng đánh giá để xem lịch sử'] for x in page.selectbox)
        assert not any(x.label == '⭐ Đánh giá công việc' for x in page.button)
        body = table(page)
        assert 'Mã tác nghiệp</th>' not in body and 'Mã TN</th>' not in body
        assert "tabindex='0'" in body and 'data-ops-row=' in body
        return body

    check(page)
    ids = list(page.session_state['ops_review_qa_ids'])
    assert len(page.select_slider) == 0
    body = check_no_menu(page)
    assert len(re.findall("data-ops-row=", body)) == 3
    assert 'Khách hàng &lt;script&gt;QA&lt;/script&gt;' in body and '<script>QA</script>' not in body
    assert 'Giá trị (tỷ đồng)' in body and '>2</td>' in body
    assert 'OPS_REVIEW_QA_0' not in body
    click_row(page, ids[0], identity=[str(ids[0])])
    assert len(page.select_slider) == 0
    click_row(page, ids[0])
    assert len(page.select_slider) == 2
    assert page.session_state['leader_ql_eval_task_table_selected_row'] == (str(ids[0]), 1)
    assert "aria-selected='true'" in check_no_menu(page)
    # A row's identity remains stable when sorting changes. A scope/round change
    # clears it; out-of-scope or stale browser events cannot open an old form.
    with app.get_conn() as c:
        c.execute("UPDATE tasks SET end_time='2026-10-05 10:00:00' WHERE id=?", (ids[0],))
    page.run(); check(page)
    assert page.session_state['leader_ql_eval_task_table_selected_row'] == (str(ids[0]), 1)
    old_version = json.loads(bridge(page).proto.json)['version']
    other = int(app.qdf("SELECT id FROM users WHERE username='ops_review_qa_other'").iloc[0].id)
    next(x for x in page.selectbox if x.label == 'Phạm vi Cán bộ QLKH').set_value(other).run(); check(page)
    assert len(re.findall("data-ops-row=", table(page))) == 1 and len(page.select_slider) == 0
    click_row(page, ids[0])
    assert len(page.select_slider) == 0 and any('Danh sách đã thay đổi' in x.value for x in page.warning)
    next(x for x in page.selectbox if x.label == 'Phạm vi Cán bộ QLKH').set_value(0).run(); check(page)
    click_row(page, ids[0])
    with app.get_conn() as c:
        c.execute('UPDATE tasks SET current_round=2 WHERE id=?', (ids[0],))
    page.run(); check(page)
    assert len(page.select_slider) == 0
    click_row(page, ids[0], version=old_version)
    assert len(page.select_slider) == 0
    with app.get_conn() as c:
        c.execute('UPDATE tasks SET current_round=1 WHERE id=?', (ids[0],))
    page.run(); click_row(page, ids[0])
    # The existing score rule remains authoritative: no comment below 9 means
    # no evaluation, no CLOSED state and no evaluation audit event.
    next(x for x in page.button if x.label=='⭐ Lưu đánh giá & kết thúc').click().run(); check(page)
    assert any('Điểm dưới 9' in x.value for x in page.error)
    with app.get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM evaluations WHERE task_id=?',(ids[0],)).fetchone()[0]==0
    next(x for x in page.select_slider if x.label=='Chất lượng').set_value(8.5)
    next(x for x in page.select_slider if x.label=='Tiến độ').set_value(9.5)
    next(x for x in page.text_area if x.label=='Góp ý / nhận xét').set_value('OPS_REVIEW_QA_COMMENT')
    next(x for x in page.button if x.label=='⭐ Lưu đánh giá & kết thúc').click().run(); check(page)
    with app.get_conn() as c:
        task=dict(c.execute('SELECT * FROM tasks WHERE id=?',(ids[0],)).fetchone())
        evaluation=dict(c.execute('SELECT * FROM evaluations WHERE task_id=?',(ids[0],)).fetchone())
        leader=int(c.execute("SELECT id FROM users WHERE username='ops_review_qa_leader'").fetchone()[0])
        owner=int(c.execute("SELECT id FROM users WHERE username='ops_review_qa_owner'").fetchone()[0])
        assert task['status']=='CLOSED' and task['closed_time'] and task['evaluated_at']
        assert task['qlkh_user_id']==owner and task['assigned_at']=='2026-10-05 08:00:00'
        assert evaluation['evaluator_user_id']==leader and evaluation['quality_score']==8.5 and evaluation['progress_score']==9.5
        assert evaluation['comment']=='OPS_REVIEW_QA_COMMENT'
        assert c.execute("SELECT COUNT(*) FROM task_actions WHERE task_id=? AND action='EVALUATE' AND actor_user_id=?",(ids[0],leader)).fetchone()[0]==1
    page.run(); check(page)
    assert len(page.select_slider) == 0
    check_no_menu(page)
    with app.get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM evaluations WHERE task_id=?',(ids[0],)).fetchone()[0]==1
    # Admin runs the same installed route and saves the high-score/no-comment case.
    page.session_state['ops_review_qa_actor']='admin'; page.run()
    click_row(page, ids[1])
    for slider in page.select_slider: slider.set_value(9.0)
    next(x for x in page.button if x.label=='⭐ Lưu đánh giá & kết thúc').click().run(); check(page)
    with app.get_conn() as c:
        evaluation=dict(c.execute('SELECT * FROM evaluations WHERE task_id=?',(ids[1],)).fetchone())
        admin=int(c.execute("SELECT id FROM users WHERE username='ops_review_qa_admin'").fetchone()[0])
        assert evaluation['evaluator_user_id']==admin and evaluation['quality_score']==9
        assert c.execute('SELECT status FROM tasks WHERE id=?',(ids[2],)).fetchone()[0]=='PENDING_REVIEW'
    # Saved scores and task detail history also use HTML, including audit text.
    page.session_state['leader_qlkh_view']='history'; page.run(); check(page)
    check_no_menu(page)
    click_row(page, str(ids[0]) + ':1', key='leader_qlkh_history_table')
    assert any('OPS_REVIEW_QA_COMMENT' in x.proto.body for x in page.get('html'))
    page.run(); check(page)
    # All roles use the same direct row mechanism on their original SQL scope.
    for actor, expected in [('owner', 1), ('other', 0), ('support', 1)]:
        page.session_state['ops_review_qa_actor'] = actor; page.run(); check(page)
        components = [x for x in page.get('bidi_component') if x.key == 'qa_common_eval_table_row_click']
        assert len(components) == (1 if expected else 0)
        if expected:
            assert len(re.findall("data-ops-row=", check_no_menu(page))) == expected
            click_row(page, ids[1], key='qa_common_eval_table')
            assert not any(x.value.startswith('QA_SELECTED_TASK=') for x in page.caption)
            click_row(page, ids[2], key='qa_common_eval_table')
            assert any(x.value == 'QA_SELECTED_TASK=' + str(ids[2]) for x in page.caption)
    # The QLKH's original scoring route also opens on a row click and persists
    # the actual owner as evaluator without using the leader's form or powers.
    page.session_state['ops_review_qa_actor'] = 'owner'
    page.session_state['ops_review_qa_native_qlkh'] = True
    page.run(); check(page); check_no_menu(page)
    click_row(page, ids[2], key='eval_task_table')
    assert len(page.select_slider) == 2
    for slider in page.select_slider: slider.set_value(9.0)
    next(x for x in page.button if 'Lưu đánh giá & kết thúc' in x.label).click().run(); check(page)
    with app.get_conn() as c:
        evaluation = dict(c.execute('SELECT * FROM evaluations WHERE task_id=?', (ids[2],)).fetchone())
        owner = int(c.execute("SELECT id FROM users WHERE username='ops_review_qa_owner'").fetchone()[0])
        assert evaluation['evaluator_user_id'] == owner and evaluation['quality_score'] == 9
        assert c.execute('SELECT status FROM tasks WHERE id=?', (ids[2],)).fetchone()[0] == 'CLOSED'
        assert c.execute('SELECT task_code FROM tasks WHERE id=?', (ids[2],)).fetchone()[0] == 'OPS_REVIEW_QA_2'
    page.run(); check(page)
    assert len(page.select_slider) == 0
    print('OPS_REVIEW_INSTALLED_UI_QA_PASS leader admin qlkh direct_row_click no_task_code no_menu real_scoring ownership audit required_comment no_duplicate scope_change stale_event malformed_event round_change stable_ID escaped_HTML history support_qlkh_scope no_DataFrame')
