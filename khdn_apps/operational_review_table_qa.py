"""Exercise the installed leader review and history with an isolated QA database."""
from __future__ import annotations


def installed_review_ui():
    from streamlit.testing.v1 import AppTest
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

    def selector(page):
        return next(x for x in page.selectbox if x.label == 'Chọn công việc cần đánh giá')

    check(page)
    ids = list(page.session_state['ops_review_qa_ids'])
    assert len(selector(page).options) == 3 and selector(page).value is None
    table = next(x.proto.body for x in page.get('html') if "class='ops-review-table'" in x.proto.body)
    assert 'Khách hàng &lt;script&gt;QA&lt;/script&gt;' in table and '<script>QA</script>' not in table
    assert 'Giá trị (tỷ đồng)' in table and '>2</td>' in table
    selector(page).set_value(str(ids[0])).run(); check(page)
    assert len(page.select_slider) == 2
    # Preserve the selected database ID when order changes, then clear it when
    # the owner filter removes the task instead of scoring a row at that position.
    with app.get_conn() as c:
        c.execute("UPDATE tasks SET end_time='2026-10-05 10:00:00' WHERE id=?",(ids[0],))
    page.run(); check(page)
    assert selector(page).value == str(ids[0])
    other=int(app.qdf("SELECT id FROM users WHERE username='ops_review_qa_other'").iloc[0].id)
    next(x for x in page.selectbox if x.label=='Phạm vi Cán bộ QLKH').set_value(other).run(); check(page)
    assert len(selector(page).options)==1 and selector(page).value is None
    assert len(page.select_slider)==0
    next(x for x in page.selectbox if x.label=='Phạm vi Cán bộ QLKH').set_value(0).run()
    selector(page).set_value(str(ids[0])).run(); check(page)
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
    assert selector(page).value is None
    with app.get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM evaluations WHERE task_id=?',(ids[0],)).fetchone()[0]==1
    # Admin runs the same installed route and saves the high-score/no-comment case.
    page.session_state['ops_review_qa_actor']='admin'; page.run()
    selector(page).set_value(str(ids[1])).run(); check(page)
    for slider in page.select_slider: slider.set_value(9.0)
    next(x for x in page.button if x.label=='⭐ Lưu đánh giá & kết thúc').click().run(); check(page)
    with app.get_conn() as c:
        evaluation=dict(c.execute('SELECT * FROM evaluations WHERE task_id=?',(ids[1],)).fetchone())
        admin=int(c.execute("SELECT id FROM users WHERE username='ops_review_qa_admin'").fetchone()[0])
        assert evaluation['evaluator_user_id']==admin and evaluation['quality_score']==9
        assert c.execute('SELECT status FROM tasks WHERE id=?',(ids[2],)).fetchone()[0]=='PENDING_REVIEW'
    # Saved scores and task detail history also use HTML, including audit text.
    page.session_state['leader_qlkh_view']='history'; page.run(); check(page)
    history=next(x for x in page.selectbox if x.label=='Chọn hồ sơ và vòng đánh giá để xem lịch sử')
    history.set_value(str(ids[0])+':1').run(); check(page)
    assert any('OPS_REVIEW_QA_COMMENT' in x.proto.body for x in page.get('html'))
    page.run(); check(page)
    # Same renderer on support/QLKH data; their original SQL still limits scope.
    for actor,expected in [('owner',1),('other',0),('support',1)]:
        page.session_state['ops_review_qa_actor']=actor; page.run(); check(page)
        choices=[x for x in page.selectbox if x.label=='Chọn công việc cần đánh giá']
        assert len(choices)==(1 if expected else 0)
        if expected:
            assert len(choices[0].options)==expected
            choices[0].set_value(str(ids[2])).run(); check(page)
            assert any(x.value=='QA_SELECTED_TASK='+str(ids[2]) for x in page.caption)
    print('OPS_REVIEW_INSTALLED_UI_QA_PASS leader admin real_scoring ownership audit required_comment no_duplicate scope_change stable_ID escaped_HTML history support_qlkh_scope no_DataFrame')
