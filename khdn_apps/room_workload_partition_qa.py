"""Workload conservation, warning transitions and final dashboard regression QA."""
from collections import Counter
from datetime import datetime, timedelta
from html.parser import HTMLParser

from khdn_apps import customer_work as core
from khdn_apps import planning_operational_phase3_dashboard as dashboard


def semantic_checks():
    reference = datetime(2026,10,5,12)
    cases=[]
    for number in range(8):
        cases.append(core.enrich_case({
            'id':number+1,'customer_name':f'QA Khách hàng {number}',
            'title':f'QA Công việc {number}','owner_name':f'QA Cán bộ {number%2}',
            'stage_name':f'QA Mục {number%3}','status':'ACTIVE','sla_hours':1,
            'stage_started_at':(reference-timedelta(hours=48 if number&1 else 0)).isoformat(),
            'open_issue_count':int(bool(number&2)),
            'expected_complete_at':(reference+timedelta(days=-1 if number&4 else 1)).isoformat(),
        },reference))
    snapshots=[dict(x) for x in cases]
    columns=dashboard._workload_lists(cases)
    assert list(map(len,columns))==[1,1,2,4],list(map(len,columns))
    assert Counter(text for col in columns for text in col)==Counter(dashboard._list_items(cases))
    assert cases==snapshots,'Grouping changed the underlying warning flags'
    for key in ('stage_name','owner_name'):
        for name in {x[key] for x in cases}:
            rows=[x for x in cases if x[key]==name]
            output=dashboard._workload_lists(rows)
            assert Counter(text for col in output for text in col)==Counter(dashboard._list_items(rows))
    # Clearing the main warning reveals the next warning, rather than losing work.
    work=dict(cases[-1]); assert dashboard._workload_bucket(work)=='OVERDUE'
    work['expected_complete_at']=(reference+timedelta(days=1)).isoformat()
    work=core.enrich_case(work,reference); assert dashboard._workload_bucket(work)=='ISSUES'
    work['open_issue_count']=0; assert dashboard._workload_bucket(work)=='DELAYED'
    work['stage_started_at']=reference.isoformat()
    work=core.enrich_case(work,reference); assert dashboard._workload_bucket(work)=='PROCESSING'
    # Distinct works with identical visible text still count as two works.
    same=[dict(cases[0],id=901),dict(cases[0],id=902)]
    assert sum(map(len,dashboard._workload_lists(same)))==2
    assert dashboard._workload_lists([])==[[],[],[],[]]
    print('ROOM_WORKLOAD_PARTITION_QA_PASS eight_warning_combinations conservation transitions identical_labels empty flags_preserved')


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        elif tag in {'td','th'}: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in {'td','th'} and self.cell is not None:
            self.row.append(''.join(self.cell)); self.cell=None
        elif tag=='tr' and self.row is not None:
            self.rows.append(self.row); self.row=None


def installed_dashboard_ui():
    """Seed only the temporary runtime QA DB and render the installed overlay stack."""
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    script="""
import streamlit as st
from khdn_apps import app,customer_work as core,customer_work_ui
from khdn_apps import weekly_plan,weekly_priority_policy_patch as policy
app.init_db(); policy._ensure_schema(weekly_plan,app.get_conn,app.LOGGER)
core.ensure_schema(app.get_conn,app.LOGGER)
with app.get_conn() as c:
    ts=core.now_str()
    for username,role in [('room_table_qa_leader','Lãnh đạo phòng'),('room_table_qa_staff','Cán bộ QLKH')]:
        c.execute('''INSERT OR IGNORE INTO users(username,full_name,password_hash,role,is_admin,active,created_at,updated_at)
            VALUES(?,?,?, ?,0,1,?,?)''',(username,username,'QA_NO_LOGIN',role,ts,ts))
    owner=int(c.execute("SELECT id FROM users WHERE username='room_table_qa_staff'").fetchone()[0])
    actor=st.session_state.get('room_table_qa_actor','admin')
    query="SELECT * FROM users WHERE is_admin=1 ORDER BY id LIMIT 1" if actor=='admin' else "SELECT * FROM users WHERE username='room_table_qa_leader'"
    u=dict(c.execute(query).fetchone())
    if not st.session_state.get('room_table_qa_seeded'):
        c.execute('''INSERT INTO customers(cif,customer_name,created_at,updated_at)
            VALUES('ROOM_TABLE_QA','ROOM_TABLE_QA_CUSTOMER',?,?)''',(ts,ts))
        customer=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        c.execute('''INSERT INTO work_stage_catalog(name,sla_hours,created_at,updated_at)
            VALUES('ROOM_TABLE_QA_STAGE',1,?,?)''',(ts,ts))
        stage=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
        for number in range(11):
            title=f'ROOM_TABLE_QA_WORK_{number:02d}' if number<8 else 'ROOM_TABLE_QA_DUP' if number<10 else 'ROOM_TABLE_QA_COMPLETED'
            c.execute('''INSERT INTO customer_work_cases(customer_id,owner_user_id,title,current_stage_id,
                stage_started_at,expected_complete_at,status,plan_approval_status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,'APPROVED',?,?)''',
                (customer,owner,title,stage,'2000-01-01 08:00:00' if number<8 and number&1 else ts,
                 '2000-01-01 17:30:00' if number<8 and number&4 else '2099-01-01 17:30:00',
                 'COMPLETED' if number==10 else 'ACTIVE',ts,ts))
            case=int(c.execute('SELECT last_insert_rowid()').fetchone()[0])
            if number<8 and number&2:
                c.execute('''INSERT INTO case_issues(case_id,stage_id,issue_text,opened_by,opened_at)
                    VALUES(?,?,'ROOM_TABLE_QA_ISSUE',?,?)''',(case,stage,u['id'],ts))
        st.session_state['room_table_qa_seeded']=True
customer_work_ui.render_leader_dashboard(st,u,app.get_conn,logger=app.LOGGER)
"""
    page=AppTest.from_string(script,default_timeout=30).run()
    def check_tables(page):
        assert not page.exception,[x.message for x in page.exception]
        tables=[]
        for element in page.get('html'):
            body=element.proto.body
            if "class='p3-table'" in body and 'ROOM_TABLE_QA_' in body:
                parsed=TableParser(); parsed.feed(body); tables.append(parsed.rows)
        assert len(tables)==2,('Final workload tables missing',len(tables))
        for table in tables:
            heads=table[0]
            joined=''.join(cell for row in table[1:] for cell in row[1:])
            for number in range(8):
                title=f'ROOM_TABLE_QA_WORK_{number:02d}'
                assert joined.count(title)==1,(heads,title,joined.count(title))
                label='Quá hạn' if number&4 else 'Có vướng mắc' if number&2 else 'Bị chậm' if number&1 else 'Đang xử lý'
                column=heads.index(label)
                assert sum(row[column].count(title) for row in table[1:])==1,(heads,title,label)
            assert joined.count('ROOM_TABLE_QA_DUP')==2,'Distinct work identities were collapsed'
            assert 'ROOM_TABLE_QA_COMPLETED' not in joined
            assert sum(row[heads.index('Đang xử lý')].count('ROOM_TABLE_QA_DUP') for row in table[1:])==2
        assert any(dashboard.WORKLOAD_GROUP_NOTE==x.value for x in page.caption)
    check_tables(page)
    page.run(); check_tables(page)
    page.session_state['room_table_qa_actor']='leader'; page.run(); check_tables(page)
    with app.get_conn() as c:
        assert c.execute("SELECT COUNT(*) FROM customer_work_cases WHERE title LIKE 'ROOM_TABLE_QA_%'").fetchone()[0]==11
        assert c.execute("SELECT COUNT(*) FROM case_issues WHERE issue_text='ROOM_TABLE_QA_ISSUE' AND resolved_at IS NULL").fetchone()[0]==4
    print('ROOM_WORKLOAD_INSTALLED_UI_QA_PASS admin leader rerun actual_SQL both_tables exclusive_columns no_lost_work original_issues_preserved')


if __name__=='__main__':
    semantic_checks()
