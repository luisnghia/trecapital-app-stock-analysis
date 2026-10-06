"""Compare installed application flows in an isolated synthetic database.

Run from the installed Docker app root, after its installer chain, for each
revision on the same machine:
  python khdn_apps/performance_flow_probe.py . /tmp/flows.json --rounds 5 --cards 160

Reports AppTest script/interaction wall time, not browser frame or network time.
No production database or account is read. The bootstrap password is random.
"""
import argparse, cProfile, io, json, os, pathlib, pstats, secrets, statistics, sys, tempfile, time

p=argparse.ArgumentParser();p.add_argument('build');p.add_argument('output');p.add_argument('--rounds',type=int,default=3);p.add_argument('--cards',type=int,default=160)
args=p.parse_args();assert args.rounds > 0 and args.cards >= 2;args.output=str(pathlib.Path(args.output).resolve());root=pathlib.Path(args.build).resolve();sys.path.insert(0,str(root))
temp=tempfile.TemporaryDirectory(prefix='khdn-perf-')
os.environ.update(KHDN_DATA_DIR=temp.name,KHDN_DB_PATH=str(pathlib.Path(temp.name)/'perf.db'),KHDN_REQUIRE_VOLUME='0',KHDN_ADMIN_PASSWORD=secrets.token_urlsafe(24))
os.chdir(root)
from streamlit.testing.v1 import AppTest
entry=str(root/'khdn_apps/online_entry.py')
wrapper=f'''import cProfile, io, pathlib, pstats, time
import streamlit as st
start=time.perf_counter()
profile = cProfile.Profile() if st.session_state.get('perf_profile') else None
if profile: profile.enable()
try:
    exec(compile(pathlib.Path({entry!r}).read_text(),{entry!r},'exec'),{{'__name__':'__main__','__file__':{entry!r}}})
finally:
    st.session_state['_perf_application_ms']=(time.perf_counter()-start)*1000
    if profile:
        profile.disable()
        profile.dump_stats({(args.output+'.prof')!r})
        out=io.StringIO();pstats.Stats(profile,stream=out).sort_stats('cumulative').print_stats(65)
        pathlib.Path({(args.output+'.profile.txt')!r}).write_text(out.getvalue())
'''
page=AppTest.from_string(wrapper,default_timeout=60).run()
assert not page.exception,[e.message for e in page.exception]
from khdn_apps import app,customer_work as core,customer_work_ui as ui
print('INSTALLED',ui.render_cases_page.__module__,ui._case_detail.__module__,flush=True)
roles=[('qlkh','Cán bộ QLKH',0),('support','Cán bộ hỗ trợ',0),('leader','Lãnh đạo phòng',0),('admin','Lãnh đạo phòng',1)]
with app.get_conn() as c:
 ts=core.now_str()
 for name,role,admin in roles:
  c.execute("INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at) VALUES(?,?,'QA_NO_LOGIN',?,?,1,0,?,?)",('perf_'+name,'PERF '+name,role,admin,ts,ts))
 users={name:dict(c.execute('SELECT * FROM users WHERE username=?',('perf_'+name,)).fetchone()) for name,_,_ in roles}
 stage=c.execute('SELECT id FROM work_stage_catalog WHERE active=1 ORDER BY sort_order,id LIMIT 1').fetchone()[0]
 for i in range(args.cards):
  owner=users['qlkh' if i%2 else 'support']['id']
  c.execute('INSERT INTO customers(cif,customer_name,qlkh_user_id,active,created_at,updated_at) VALUES(?,?,?,1,?,?)',(f'PERF{i}',f'Khách hàng kiểm tra {i}',owner,ts,ts))
  cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  c.execute("INSERT INTO customer_work_cases(case_code,customer_id,owner_user_id,title,case_type,current_stage_id,stage_started_at,controller_user_id,expected_complete_at,status,plan_approval_status,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'2026-12-01 17:00:00','ACTIVE','APPROVED',?,?,?)",(f'PERF{i}',cid,owner,f'Công việc kiểm tra {i}','Tín dụng',stage,ts,users['leader']['id'],'Ghi chú dài kiểm tra hiệu năng và giữ nguyên dữ liệu.\n'*8,ts,ts))
 case_id=c.execute('SELECT id FROM customer_work_cases ORDER BY id LIMIT 1').fetchone()[0]
results={}
for role,_,_ in roles:
 u=users[role];page.session_state['user']=u;page.session_state['cw_landing_token']=f"{u['id']}:{u.get('last_login_at','')}"
 for route in ('customer_work','work_today','weekly_plan','work_dashboard'):
  if route=='work_dashboard' and role not in ('leader','admin'):continue
  page.session_state['main_section']='plan';page.session_state['main_page']=route;page.session_state['cw_view']='processing'
  if 'cw_case_id' in page.session_state:del page.session_state['cw_case_id']
  page.run();assert not page.exception,(role,route,[e.message for e in page.exception])
  times=[];application_times=[]
  for _ in range(args.rounds):
   t=time.perf_counter();page.run();times.append((time.perf_counter()-t)*1000)
   application_times.append(page.session_state['_perf_application_ms'])
   assert not page.exception,(role,route,[e.message for e in page.exception])
  results[f'{role}/{route}']={'median_ms':round(statistics.median(times),2),'application_ms':round(statistics.median(application_times),2),'times_ms':[round(t,2) for t in times],'buttons':len(page.button),'html':len(page.get('html')),'route':page.session_state['main_page']}
  print(role,route,results[f'{role}/{route}'],flush=True)
  if role=='admin' and route=='customer_work':
   page.session_state['perf_profile']=True;page.run();page.session_state['perf_profile']=False
 # Full detail input page on the same overlay stack.
 with app.get_conn() as c:
  own_case=c.execute('SELECT id FROM customer_work_cases WHERE owner_user_id=? ORDER BY id LIMIT 1',(u['id'],)).fetchone()
 page.session_state['main_page']='customer_work';page.session_state['cw_case_id']=int(own_case[0]) if own_case else case_id;page.run()
 assert not page.exception,(role,'detail',[e.message for e in page.exception])
 times=[]
 for _ in range(args.rounds):
  t=time.perf_counter();page.run();times.append((time.perf_counter()-t)*1000)
  assert not page.exception,(role,'detail',[e.message for e in page.exception])
 results[f'{role}/detail']={'median_ms':round(statistics.median(times),2),'times_ms':[round(t,2) for t in times],'text_inputs':[x.label for x in page.text_input],'text_areas':[x.label for x in page.text_area]}
 print(role,'detail',results[f'{role}/detail'],flush=True)
 # Measure actual command-button interactions, including any requested rerun.
 del page.session_state['cw_case_id'];page.session_state['main_page']='customer_work';page.run()
 for destination in ('work_today','customer_work'):
  durations=[]
  for _ in range(args.rounds):
   origin='customer_work' if destination=='work_today' else 'work_today'
   page.session_state['main_page']=origin;page.run()
   button=next(x for x in page.button if str(x.key or '').startswith('khdn_subtab_') and str(x.key).endswith('_'+destination))
   t=time.perf_counter();button.click().run();durations.append((time.perf_counter()-t)*1000)
   assert not page.exception,(role,'navigation',[e.message for e in page.exception])
   assert page.session_state['main_page']==destination
  results[f'{role}/click_{destination}']={'median_ms':round(statistics.median(durations),2),'times_ms':[round(t,2) for t in durations]}
  print(role,'click',destination,results[f'{role}/click_{destination}'],flush=True)
pathlib.Path(args.output).write_text(json.dumps({'cards':args.cards,'rounds':args.rounds,'routes':results},ensure_ascii=False,indent=2))
