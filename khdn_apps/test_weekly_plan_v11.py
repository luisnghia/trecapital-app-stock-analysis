"""Tests for Weekly Plan V11 period filters and filtered dashboards."""
from __future__ import annotations

from datetime import date

from streamlit.testing.v1 import AppTest

from khdn_apps.weekly_plan_v11 import _period_bounds


PERSONAL_HARNESS = r'''
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path
import streamlit as st
from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps.weekly_plan_v11 import weekly_plan_page

tmp=tempfile.mkdtemp(prefix="khdn-v11-personal-")
db=Path(tmp)/"ui.db"
def get_conn():
    c=sqlite3.connect(db); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
with get_conn() as c:
    c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,role TEXT,active INTEGER DEFAULT 1,is_admin INTEGER DEFAULT 0)")
    c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(1,'cb01','Cán bộ A','Cán bộ QLKH',1,0)")
    c.commit()
v6._init_v6_schema(get_conn)
year,week,monday,sunday=wp._iso_week(); plan=wp._get_or_create_plan(get_conn,1,year,week,monday,sunday); focus=wp._focus_df(get_conn,year,True); fid=int(focus.iloc[0]['id'])
with get_conn() as c:
    c.execute("INSERT INTO weekly_tasks(plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,planned_hours,actual_hours,status,is_emergent,defer_count,completed_at,created_at,updated_at) VALUES(?,?,?,?,0,0,'Q2',?,?,?,'COMPLETED',0,0,?,?,?)",(int(plan['id']),'Việc dashboard','Đầu ra',fid,(monday+timedelta(days=4)).isoformat(),2.0,2.0,wp._now(),wp._now(),wp._now()))
    c.execute("UPDATE weekly_plans SET status='REVIEWED',closed_at=?,reviewed_at=?,updated_at=? WHERE id=?",(wp._now(),wp._now(),wp._now(),int(plan['id'])))
    c.execute("INSERT INTO weekly_reviews(plan_id,self_score,strengths,limitations,causes,next_actions,leader_score,leader_comment,progress_score,quality_score,week_score,grade,created_at,updated_at) VALUES(?,4,'Tốt','Ít tồn tại','Không','Tiếp tục',4,'Duy trì chất lượng',100,80,90,'A',?,?)",(int(plan['id']),wp._now(),wp._now()))
    c.commit()
st.session_state['weekly_plan_view']='personal'
user={'id':1,'username':'cb01','full_name':'Cán bộ A','role':'Cán bộ QLKH','is_admin':0}
def page_title(title,subtitle): st.markdown(f'## {title}'); st.caption(subtitle)
weekly_plan_page(user,get_conn,page_title,pill_nav=None)
'''


ROOM_HARNESS = r'''
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path
import streamlit as st
from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps.weekly_plan_v11 import weekly_plan_page

tmp=tempfile.mkdtemp(prefix="khdn-v11-room-")
db=Path(tmp)/"ui.db"
def get_conn():
    c=sqlite3.connect(db); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
with get_conn() as c:
    c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,role TEXT,active INTEGER DEFAULT 1,is_admin INTEGER DEFAULT 0)")
    c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(1,'cb01','Cán bộ A','Cán bộ QLKH',1,0)")
    c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(2,'ld01','Lãnh đạo','Lãnh đạo phòng',1,0)")
    c.commit()
v6._init_v6_schema(get_conn)
year,week,monday,sunday=wp._iso_week(); plan=wp._get_or_create_plan(get_conn,1,year,week,monday,sunday); focus=wp._focus_df(get_conn,year,True); fid=int(focus.iloc[0]['id'])
with get_conn() as c:
    c.execute("INSERT INTO weekly_tasks(plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,planned_hours,actual_hours,status,is_emergent,defer_count,completed_at,created_at,updated_at) VALUES(?,?,?,?,0,0,'Q2',?,?,?,'COMPLETED',0,0,?,?,?)",(int(plan['id']),'Việc phòng','Đầu ra',fid,(monday+timedelta(days=4)).isoformat(),2.0,2.0,wp._now(),wp._now(),wp._now()))
    c.execute("UPDATE weekly_plans SET status='REVIEWED',closed_at=?,reviewed_at=?,updated_at=? WHERE id=?",(wp._now(),wp._now(),wp._now(),int(plan['id'])))
    c.execute("INSERT INTO weekly_reviews(plan_id,self_score,strengths,limitations,causes,next_actions,leader_score,leader_comment,progress_score,quality_score,week_score,grade,created_at,updated_at) VALUES(?,4,'Tốt','Theo dõi hồ sơ','Không','Tiếp tục',4,'Tốt',100,80,90,'A',?,?)",(int(plan['id']),wp._now(),wp._now()))
    c.commit()
st.session_state['weekly_plan_view']='room'
user={'id':2,'username':'ld01','full_name':'Lãnh đạo','role':'Lãnh đạo phòng','is_admin':0}
def page_title(title,subtitle): st.markdown(f'## {title}'); st.caption(subtitle)
weekly_plan_page(user,get_conn,page_title,pill_nav=None)
'''


def _run(script):
    app=AppTest.from_string(script,default_timeout=20)
    app.run(timeout=20)
    if app.exception:
        raise AssertionError(f"V11 dashboard render failed: {app.exception}")
    return app


def main():
    assert _period_bounds('Tuần',date(2026,9,12))==(date(2026,9,7),date(2026,9,13))
    assert _period_bounds('Tháng',date(2026,2,10))==(date(2026,2,1),date(2026,2,28))
    assert _period_bounds('Quý',date(2026,8,10))==(date(2026,7,1),date(2026,9,30))

    personal=_run(PERSONAL_HARNESS)
    labels=[str(x.label) for x in personal.selectbox]
    assert any('Kỳ xem' in x for x in labels)
    assert personal.plotly_chart

    room=_run(ROOM_HARNESS)
    labels=[str(x.label) for x in room.selectbox]
    assert any('Kỳ xem' in x for x in labels)
    assert any('Phòng' in x for x in labels)
    assert any('Cán bộ' in x for x in labels)
    assert room.plotly_chart

    print('KHDN Weekly Plan V11 filter/drill-down tests: OK')


if __name__=='__main__':
    main()
