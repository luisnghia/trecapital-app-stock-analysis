"""Tests for Weekly Plan V12 configurable parameters and admin UI."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v12 as v12


ADMIN_HARNESS = r'''
import sqlite3
import tempfile
from pathlib import Path
import streamlit as st
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps.weekly_plan_v12 import weekly_admin_panel

tmp=tempfile.mkdtemp(prefix="khdn-v12-admin-")
db=Path(tmp)/"admin.db"
def get_conn():
    c=sqlite3.connect(db); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
with get_conn() as c:
    c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,role TEXT,active INTEGER DEFAULT 1,is_admin INTEGER DEFAULT 0)")
    c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(9,'admin','Admin Test','Cán bộ QLKH',1,1)")
    c.commit()
v6._init_v6_schema(get_conn)
weekly_admin_panel({'id':9,'username':'admin','full_name':'Admin Test','role':'Cán bộ QLKH','is_admin':1},get_conn)
'''


def main():
    tmp=tempfile.TemporaryDirectory(); db=Path(tmp.name)/"v12.db"
    def get_conn():
        c=sqlite3.connect(db); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
    with get_conn() as c:
        c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,role TEXT,active INTEGER DEFAULT 1,is_admin INTEGER DEFAULT 0)")
        c.execute("INSERT INTO users VALUES(1,'cb01','Cán bộ A','Cán bộ QLKH',1,0)")
        c.execute("INSERT INTO users VALUES(9,'admin','Admin Test','Cán bộ QLKH',1,1)")
        c.commit()
    v6._init_v6_schema(get_conn); v12._init_v12_schema(get_conn)

    assert abs(v12._param(get_conn,'q2_target_pct')-60.0)<1e-9
    assert int(round(v12._param(get_conn,'max_planned_tasks')))==7
    assert int(round(v12._param(get_conn,'min_q2_tasks')))==3

    # Change task limits and verify submission validation actually consumes them.
    v12._save_parameter_group(get_conn,{'id':9},{'max_planned_tasks':8,'min_q2_tasks':4})
    sample=pd.DataFrame([
        {'quadrant':'Q2','is_emergent':0,'planned_hours':2.0,'expected_result':'Đầu ra'} for _ in range(3)
    ])
    errors=v12._validate_submit_configured(get_conn,sample)
    assert any('tối thiểu 4' in x for x in errors)
    sample4=pd.concat([sample,pd.DataFrame([{'quadrant':'Q2','is_emergent':0,'planned_hours':2.0,'expected_result':'Đầu ra'}])],ignore_index=True)
    assert not any('tối thiểu' in x for x in v12._validate_submit_configured(get_conn,sample4))

    # Change quadrant weights and verify progress scoring consumes the parameters.
    v12._save_parameter_group(get_conn,{'id':9},{'weight_q1':1,'weight_q2':3,'weight_q3':0,'weight_q4':0})
    scoring=pd.DataFrame([
        {'quadrant':'Q1','status':'COMPLETED','completed_at':'2026-09-10 10:00:00','due_date':'2026-09-10'},
        {'quadrant':'Q2','status':'NOT_STARTED','completed_at':None,'due_date':'2026-09-10'},
    ])
    assert abs(v12._progress_score_configured(get_conn,scoring)-25.0)<1e-9

    # Create evaluated plan so admin unlock controls have a real target.
    year,week,monday,sunday=wp._iso_week(); plan=wp._get_or_create_plan(get_conn,1,year,week,monday,sunday)
    with get_conn() as c:
        c.execute("UPDATE weekly_plans SET status='REVIEWED',closed_at=?,reviewed_at=?,updated_at=? WHERE id=?",(wp._now(),wp._now(),wp._now(),int(plan['id'])))
        c.execute("INSERT INTO weekly_reviews(plan_id,self_score,strengths,limitations,causes,next_actions,leader_score,leader_comment,progress_score,quality_score,week_score,grade,created_at,updated_at) VALUES(?,4,'Tốt','Tồn tại','Nguyên nhân','Đề xuất',4,'Nhận xét',100,80,90,'A',?,?)",(int(plan['id']),wp._now(),wp._now()))
        c.commit()

    app=AppTest.from_string(ADMIN_HARNESS,default_timeout=20); app.run(timeout=20)
    if app.exception:
        raise AssertionError(f"V12 admin render failed: {app.exception}")
    text=[]
    for name in ('markdown','caption','info','warning','error'):
        try: text.extend(str(x.value) for x in getattr(app,name))
        except Exception: pass
    joined='\n'.join(text)
    assert 'Quản trị Kế hoạch tuần' in joined
    assert 'Tham số Kế hoạch tuần' in joined

    # Non-admin server-side guard.
    denied_script=ADMIN_HARNESS.replace("'is_admin':1","'is_admin':0")
    denied=AppTest.from_string(denied_script,default_timeout=20); denied.run(timeout=20)
    assert any('không có quyền quản trị' in str(e.value).lower() for e in denied.error)

    print('KHDN Weekly Plan V12 parameter/admin tests: OK')


if __name__=='__main__':
    main()
