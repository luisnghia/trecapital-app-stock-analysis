from __future__ import annotations
import html, json, re, unicodedata
from datetime import date, datetime, timedelta

VERSION="1.0.0"
STAT={"PLANNED":"○ Kế hoạch","IN_PROGRESS":"▶ Đang thực hiện","DONE":"✓ Hoàn thành","CANCELLED":"× Đã hủy"}
ICONS={"Khách hàng":"🤝","Chăm sóc khách hàng":"🎂","Tín dụng":"📑","Hồ sơ / Dự án":"🏗️","Nội bộ":"👥","Công việc khác":"🗒️"}
PURPOSES=[("Tiền gửi",("tien gui","huy dong")),("Tiền vay",("tien vay","vay von")),("Sinh nhật",("sinh nhat",)),("Chăm sóc khách hàng",("cham soc","cskh")),("Dịch vụ",("dich vu",)),("Ngoại tệ",("ngoai te","fx")),("Bảo lãnh",("bao lanh",)),("Thu nợ",("thu no","don doc no")),("Tài trợ thương mại",("tai tro thuong mai","tttm"))]

def norm(v):
    s=unicodedata.normalize("NFD",str(v or "").lower().strip()).replace("đ","d")
    s="".join(c for c in s if unicodedata.category(c)!="Mn")
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",s)).strip()

def week_start(d=None):
    d=d.date() if isinstance(d,datetime) else (d or date.today())
    return d-timedelta(days=d.weekday())

def day_label(d):
    return f"{['Thứ 2','Thứ 3','Thứ 4','Thứ 5','Thứ 6','Thứ 7','Chủ nhật'][d.weekday()]} · {d:%d/%m}"

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_schema(get_conn,logger=None):
    sql='''
    CREATE TABLE IF NOT EXISTS weekly_plans(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,week_start TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ACTIVE',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,week_start),FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS weekly_plan_items(id INTEGER PRIMARY KEY AUTOINCREMENT,plan_id INTEGER NOT NULL,user_id INTEGER NOT NULL,work_date TEXT NOT NULL,start_time TEXT,daypart TEXT,title TEXT NOT NULL,customer_id INTEGER,customer_text TEXT,category TEXT NOT NULL DEFAULT 'Công việc khác',purposes_json TEXT NOT NULL DEFAULT '[]',source_text TEXT,linked_task_id INTEGER,status TEXT NOT NULL DEFAULT 'PLANNED',reschedule_count INTEGER NOT NULL DEFAULT 0,copied_from_item_id INTEGER,note TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(plan_id) REFERENCES weekly_plans(id) ON DELETE CASCADE,FOREIGN KEY(user_id) REFERENCES users(id),FOREIGN KEY(customer_id) REFERENCES customers(id),FOREIGN KEY(linked_task_id) REFERENCES tasks(id));
    CREATE TABLE IF NOT EXISTS weekly_plan_actions(id INTEGER PRIMARY KEY AUTOINCREMENT,item_id INTEGER,actor_user_id INTEGER NOT NULL,action TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL,FOREIGN KEY(item_id) REFERENCES weekly_plan_items(id) ON DELETE CASCADE,FOREIGN KEY(actor_user_id) REFERENCES users(id));
    CREATE INDEX IF NOT EXISTS idx_wp_user_week ON weekly_plans(user_id,week_start); CREATE INDEX IF NOT EXISTS idx_wpi_user_date ON weekly_plan_items(user_id,work_date); CREATE INDEX IF NOT EXISTS idx_wpi_link ON weekly_plan_items(linked_task_id);'''
    try:
        with get_conn() as c: c.executescript(sql)
        if logger: logger.info("WEEKLY_PLAN_SCHEMA_READY version=%s",VERSION)
    except Exception:
        if logger: logger.exception("WEEKLY_PLAN_SCHEMA_FAILED")
        raise

def ensure_plan(c,uid,ws):
    ts=now(); c.execute("INSERT OR IGNORE INTO weekly_plans(user_id,week_start,status,created_at,updated_at) VALUES(?,?,'ACTIVE',?,?)",(uid,ws.isoformat(),ts,ts))
    return int(c.execute("SELECT id FROM weekly_plans WHERE user_id=? AND week_start=?",(uid,ws.isoformat())).fetchone()[0])

def customers(c,uid):
    return [dict(r) for r in c.execute("SELECT id,cif,customer_name,qlkh_user_id FROM customers WHERE active=1 ORDER BY CASE WHEN qlkh_user_id=? THEN 0 ELSE 1 END,customer_name",(uid,)).fetchall()]

def match_customer(text,cs):
    nt=f" {norm(text)} "; best=None
    for x in cs:
        if x.get("cif") and f" {norm(x['cif'])} " in nt: return x
        full=norm(x.get("customer_name")); core=re.sub(r"\b(cong ty|cty|co phan|cp|tnhh|mot thanh vien|mtv|tong cong ty|tap doan|thuong mai|tm)\b"," ",full); core=re.sub(r"\s+"," ",core).strip()
        for a in sorted({full,core},key=len,reverse=True):
            if len(a)>=3 and (f" {a} " in nt or (len(a)>=6 and a in nt)) and (best is None or len(a)>best[0]): best=(len(a),x)
    return best[1] if best else None

def parse_day(src,ws):
    n=norm(src); m=re.match(r"^(?:t|thu)\s*([2-7])\b",n)
    if m:
        idx=int(m.group(1))-2; rest=re.sub(r"^\s*(?:t|thứ|thu)\s*"+m.group(1)+r"\b[\s,:;\-–—]*","",src,count=1,flags=re.I); return ws+timedelta(days=idx),rest
    names={"thu hai":0,"thu ba":1,"thu tu":2,"thu bon":2,"thu nam":3,"thu sau":4,"thu bay":5,"chu nhat":6,"cn":6}
    for k,i in names.items():
        if n==k or n.startswith(k+" "): return ws+timedelta(days=i)," ".join(src.split()[len(k.split()):]).lstrip(" ,:;-–—")
    return None,src

def parse_line(line,ws,cs,forced=None):
    src=re.sub(r"^[\s•*\-–—]+","",str(line or "")).strip()
    if not src:return None
    d,core=parse_day(src,ws); d=forced or d
    if not d:return {"error":"Chưa nhận diện được ngày (ví dụ T2, T3, Thứ 4).","source_text":src}
    n=norm(core); dp="Sáng" if re.search(r"\b(sang|buoi sang)\b",n) else ("Chiều" if re.search(r"\b(chieu|buoi chieu)\b",n) else ("Tối" if re.search(r"\b(toi|buoi toi)\b",n) else None))
    m=re.search(r"(?<!\d)([01]?\d|2[0-3])\s*(?:h|:)([0-5]\d)?\b",core,flags=re.I); tm=None
    if m: tm=f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"; core=core[:m.start()]+core[m.end():]
    core=re.sub(r"\b(buổi\s+)?(sáng|chiều|tối)\b","",core,count=1,flags=re.I).strip(" ,:;-–—")
    nn=norm(src); purs=[lab for lab,keys in PURPOSES if any(k in nn for k in keys)]
    if any(k in nn for k in ("sinh nhat","cham soc","cskh")): cat="Chăm sóc khách hàng"
    elif any(k in nn for k in ("du an","trinh ho so","tham dinh","phe duyet ho so")): cat="Hồ sơ / Dự án"
    elif any(k in nn for k in ("han muc","lam hm","giai ngan","tin dung","vay von")): cat="Tín dụng"
    elif any(k in nn for k in ("hop","giao ban","dao tao","bao cao","noi bo")): cat="Nội bộ"
    elif any(k in nn for k in ("gap ","goi ","tham ","khach hang","tiep thi","marketing")): cat="Khách hàng"
    else: cat="Công việc khác"
    title=re.split(r"\s+(?:mục\s*đích|muc\s*dich)\s*:\s*",core,maxsplit=1,flags=re.I)[0]
    p=re.split(r"\s+[\-–—]\s+",title,maxsplit=1); title=p[0] if len(p)==2 and any(k in norm(p[1]) for _,ks in PURPOSES for k in ks) else title
    title=re.sub(r"\s+"," ",title).strip() or "Công việc"; title=title[:1].upper()+title[1:]
    cust=match_customer(src,cs)
    return {"work_date":d.isoformat(),"start_time":tm,"daypart":dp,"title":title,"customer_id":int(cust["id"]) if cust else None,"customer_text":str(cust["customer_name"]) if cust else "","category":cat,"purposes":purs,"source_text":src,"linked_task_id":None}

def parse_text(text,ws,cs): return [x for x in (parse_line(line,ws,cs) for line in str(text or "").splitlines()) if x]

def save_items(get_conn,uid,ws,items,logger=None):
    good=[x for x in items if not x.get("error")]; errors=[x.get("error") for x in items if x.get("error")]
    if not good:return 0,errors
    ts=now()
    with get_conn() as c:
        pid=ensure_plan(c,uid,ws)
        for x in good:
            c.execute("""INSERT INTO weekly_plan_items(plan_id,user_id,work_date,start_time,daypart,title,customer_id,customer_text,category,purposes_json,source_text,linked_task_id,status,reschedule_count,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'PLANNED',0,?,?,?)""",(pid,uid,x["work_date"],x.get("start_time"),x.get("daypart"),x["title"],x.get("customer_id"),x.get("customer_text",""),x.get("category","Công việc khác"),json.dumps(x.get("purposes",[]),ensure_ascii=False),x.get("source_text",x["title"]),x.get("linked_task_id"),x.get("note"),ts,ts))
        c.execute("UPDATE weekly_plans SET updated_at=? WHERE id=?",(ts,pid))
    if logger: logger.info("WEEKLY_PLAN_SAVE user=%s week=%s count=%s",uid,ws,len(good))
    return len(good),errors

def load_items(c,uid,ws):
    return [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE user_id=? AND work_date>=? AND work_date<? ORDER BY work_date,COALESCE(start_time,'99:99'),id",(uid,ws.isoformat(),(ws+timedelta(days=7)).isoformat())).fetchall()]

def set_status(get_conn,iid,uid,status,logger=None):
    if status not in STAT: raise ValueError(status)
    with get_conn() as c:
        old=c.execute("SELECT status FROM weekly_plan_items WHERE id=?",(iid,)).fetchone();
        if not old:return
        c.execute("UPDATE weekly_plan_items SET status=?,updated_at=? WHERE id=?",(status,now(),iid)); c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'STATUS',?,?)",(iid,uid,f"{old[0]} -> {status}",now()))
    if logger: logger.info("WEEKLY_PLAN_STATUS item=%s actor=%s status=%s",iid,uid,status)

def move_item(get_conn,iid,uid,new_date,logger=None):
    with get_conn() as c:
        old=c.execute("SELECT work_date FROM weekly_plan_items WHERE id=?",(iid,)).fetchone();
        if not old:return
        c.execute("UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?",(new_date.isoformat(),now(),iid)); c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE',?,?)",(iid,uid,f"{old[0]} -> {new_date.isoformat()}",now()))
    if logger: logger.info("WEEKLY_PLAN_MOVE item=%s date=%s",iid,new_date)

def copy_prev(get_conn,uid,ws,logger=None):
    prev=ws-timedelta(days=7); ts=now(); count=0
    with get_conn() as c:
        p=c.execute("SELECT id FROM weekly_plans WHERE user_id=? AND week_start=?",(uid,prev.isoformat())).fetchone()
        if not p:return 0
        pid=ensure_plan(c,uid,ws)
        for r in c.execute("SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED'",(p[0],)).fetchall():
            nd=date.fromisoformat(str(r["work_date"])[:10])+timedelta(days=7)
            if c.execute("SELECT 1 FROM weekly_plan_items WHERE plan_id=? AND work_date=? AND title=? AND COALESCE(customer_text,'')=COALESCE(?,'')",(pid,nd.isoformat(),r["title"],r["customer_text"])).fetchone():continue
            c.execute("""INSERT INTO weekly_plan_items(plan_id,user_id,work_date,start_time,daypart,title,customer_id,customer_text,category,purposes_json,source_text,linked_task_id,status,reschedule_count,copied_from_item_id,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'PLANNED',0,?,?,?,?)""",(pid,uid,nd.isoformat(),r["start_time"],r["daypart"],r["title"],r["customer_id"],r["customer_text"],r["category"],r["purposes_json"],r["source_text"],r["linked_task_id"],r["id"],r["note"],ts,ts)); count+=1
    if logger: logger.info("WEEKLY_PLAN_COPY user=%s count=%s",uid,count)
    return count

def open_tasks(c,uid):
    return [dict(r) for r in c.execute("""SELECT t.id,t.task_code,t.task_type,t.due_time,t.status,t.customer_id,c.customer_name FROM tasks t JOIN customers c ON c.id=t.customer_id WHERE (t.qlkh_user_id=? OR t.support_user_id=?) AND t.status NOT IN ('CLOSED','CANCELLED') AND NOT EXISTS(SELECT 1 FROM weekly_plan_items w WHERE w.user_id=? AND w.linked_task_id=t.id AND w.status<>'CANCELLED') ORDER BY CASE WHEN t.due_time IS NULL THEN 1 ELSE 0 END,t.due_time,t.id LIMIT 20""",(uid,uid,uid)).fetchall()]

def add_task(get_conn,uid,ws,t,d,logger=None):
    with get_conn() as c:
        if c.execute("SELECT 1 FROM weekly_plan_items WHERE user_id=? AND linked_task_id=? AND status<>'CANCELLED'",(uid,t["id"])).fetchone():return False
        pid=ensure_plan(c,uid,ws); title=f"{t.get('task_type') or 'Xử lý hồ sơ'} · {t.get('customer_name') or ''}"; cat="Tín dụng" if any(k in norm(title) for k in ("giai ngan","han muc","tin dung","bao lanh","lc")) else "Hồ sơ / Dự án"; ts=now()
        c.execute("""INSERT INTO weekly_plan_items(plan_id,user_id,work_date,title,customer_id,customer_text,category,purposes_json,source_text,linked_task_id,status,reschedule_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'[]',?,?,'PLANNED',0,?,?)""",(pid,uid,d.isoformat(),title,t.get("customer_id"),t.get("customer_name",""),cat,f"Từ tác nghiệp {t.get('task_code') or t['id']}",t["id"],ts,ts))
    if logger: logger.info("WEEKLY_PLAN_LINK task=%s user=%s",t["id"],uid)
    return True

def table(st,heads,rows):
    esc=lambda v:html.escape("" if v is None else str(v)); h="".join(f"<th>{esc(x)}</th>" for x in heads); b="".join("<tr>"+"".join(f"<td>{esc(x)}</td>" for x in r)+"</tr>" for r in rows)
    st.html(f'''<div style="overflow-x:auto"><table style="width:100%;table-layout:fixed;border-collapse:collapse"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div><style>table th,table td{{padding:8px 10px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere}}table th{{font-weight:800}}</style>''')

def preview(st,items):
    rows=[]
    for x in items:
        if x.get("error"): rows.append(["⚠️",x.get("source_text",""),x["error"],"",""]);continue
        d=date.fromisoformat(x["work_date"]); when=day_label(d)+(f" · {x['start_time']}" if x.get("start_time") else (f" · {x['daypart']}" if x.get("daypart") else "")); rows.append([when,x["title"],x.get("customer_text") or "—",x["category"],", ".join(x.get("purposes",[])) or "—"])
    table(st,["Ngày","Công việc","Khách hàng","Nhóm","Mục đích"],rows)

def card(st,x,ws,get_conn,uid,logger):
    iid=int(x["id"]); st.markdown(f"**{ICONS.get(x.get('category'),'🗒️')} {html.escape(str(x.get('title') or ''))}**"); meta=" · ".join(v for v in (str(x.get("start_time") or x.get("daypart") or ""),str(x.get("customer_text") or "")," · ".join(json.loads(x.get("purposes_json") or "[]"))) if v); st.caption(meta) if meta else None; st.caption(STAT.get(x.get("status"),x.get("status")))
    a,b,c=st.columns(3)
    if x.get("status")!="IN_PROGRESS" and a.button("▶",key=f"wps{iid}",help="Bắt đầu"): set_status(get_conn,iid,uid,"IN_PROGRESS",logger);st.rerun()
    if x.get("status")!="DONE" and b.button("✓",key=f"wpd{iid}",help="Hoàn thành"): set_status(get_conn,iid,uid,"DONE",logger);st.rerun()
    if c.button("⋯",key=f"wpm{iid}",help="Dời lịch / hủy"): st.session_state[f"wpo{iid}"]=not st.session_state.get(f"wpo{iid}",False);st.rerun()
    if st.session_state.get(f"wpo{iid}"):
        days=[ws+timedelta(days=i) for i in range(7)]; cur=max(0,min(6,date.fromisoformat(str(x["work_date"])[:10]).weekday())); d=st.selectbox("Dời sang",days,index=cur,format_func=day_label,key=f"wpt{iid}"); m1,m2=st.columns(2)
        if m1.button("→ Dời",key=f"wpx{iid}",use_container_width=True): move_item(get_conn,iid,uid,d,logger);st.rerun()
        if x.get("status")!="CANCELLED" and m2.button("× Hủy",key=f"wpc{iid}",use_container_width=True): set_status(get_conn,iid,uid,"CANCELLED",logger);st.rerun()

def render_page(st,u,get_conn,page_title=None,logger=None):
    ensure_schema(get_conn,logger); uid=int(u["id"]); page_title("Kế hoạch công việc","Nhập nhanh như ghi sổ tay · tự chuẩn hóa · theo dõi theo tuần") if page_title else st.title("📅 Kế hoạch công việc"); st.caption(f"Weekly Plan v{VERSION} · Mỗi dòng một việc, không cần form dài.")
    off=st.session_state.setdefault("wp_offset",0); n1,n2,n3,n4=st.columns([1,1.3,1,4])
    if n1.button("← Tuần trước",key="wpp",use_container_width=True): st.session_state.wp_offset-=1;st.rerun()
    if n2.button("Tuần này",key="wpn",use_container_width=True): st.session_state.wp_offset=0;st.rerun()
    if n3.button("Tuần sau →",key="wpq",use_container_width=True): st.session_state.wp_offset+=1;st.rerun()
    ws=week_start()+timedelta(days=7*int(st.session_state.wp_offset)); n4.markdown(f"**{ws:%d/%m} – {(ws+timedelta(days=6)):%d/%m/%Y}**")
    with get_conn() as c: cs=customers(c,uid); items=load_items(c,uid,ws)
    active=[x for x in items if x.get("status")!="CANCELLED"]; a,b,c,d=st.columns(4); a.metric("Tổng việc",len(active));b.metric("Kế hoạch",sum(x["status"]=="PLANNED" for x in active));c.metric("Đang làm",sum(x["status"]=="IN_PROGRESS" for x in active));d.metric("Hoàn thành",sum(x["status"]=="DONE" for x in active))
    views=["📅 Tuần này","☀️ Hôm nay","✨ Gợi ý"]+(["👥 Kế hoạch phòng"] if str(u.get("role") or "")=="Lãnh đạo phòng" or bool(u.get("is_admin")) else []); view=st.radio("Chế độ xem",views,horizontal=True,label_visibility="collapsed",key="wp_view");st.divider()
    if view=="📅 Tuần này":
        with st.expander("⚡ Nhập nhanh kế hoạch",expanded=not items):
            st.caption("Mỗi dòng một việc. Ví dụ: T2 gặp Công ty A - tiền gửi; T3 làm hạn mức Công ty B; T5 9h họp phòng."); text=st.text_area("Kế hoạch",key="wp_text",height=145,placeholder="T2 gặp Công ty ABC - tiếp thị tiền gửi\nT3 làm hạn mức Công ty DEF\nT4 trình hồ sơ dự án Công ty XYZ\nT5 9h họp phòng",label_visibility="collapsed"); q1,q2=st.columns(2)
            if q1.button("✨ Phân tích",key="wpa",use_container_width=True): st.session_state.wp_preview=parse_text(text,ws,cs);st.session_state.wp_preview_week=ws.isoformat()
            if q2.button("⚡ Lưu ngay",key="wpf",use_container_width=True,type="primary"):
                parsed=parse_text(text,ws,cs); bad=[x for x in parsed if x.get("error")]
                if not parsed: st.warning("Chưa có nội dung kế hoạch.")
                elif bad: st.session_state.wp_preview=parsed;st.session_state.wp_preview_week=ws.isoformat();st.warning("Có dòng chưa nhận diện được ngày. Hãy kiểm tra bảng dưới.")
                else: n,_=save_items(get_conn,uid,ws,parsed,logger);st.session_state.wp_text="";st.session_state.pop("wp_preview",None);st.toast(f"Đã thêm {n} công việc.",icon="✅");st.rerun()
            pv=st.session_state.get("wp_preview")
            if pv and st.session_state.get("wp_preview_week")==ws.isoformat():
                preview(st,pv)
                if any(not x.get("error") for x in pv) and st.button("✓ Lưu kế hoạch",key="wpv",type="primary",use_container_width=True): n,e=save_items(get_conn,uid,ws,pv,logger);st.session_state.wp_text="";st.session_state.pop("wp_preview",None);st.toast(f"Đã lưu {n} công việc.",icon="✅");st.rerun()
        x1,x2=st.columns([1,2])
        if x1.button("📋 Sao chép tuần trước",key=f"wpcopy{ws}",use_container_width=True):
            n=copy_prev(get_conn,uid,ws,logger); st.toast(f"Đã sao chép {n} công việc.",icon="✅") if n else st.info("Tuần trước chưa có công việc mới để sao chép."); st.rerun() if n else None
        x2.caption("Dời lịch bằng nút ⋯ trên từng công việc; không cần mở form dài.")
        by={}
        for x in active: by.setdefault(str(x["work_date"])[:10],[]).append(x)
        for col,dd in zip(st.columns(5,gap="small"),[ws+timedelta(days=i) for i in range(5)]):
            with col:
                st.markdown(f"### {day_label(dd)}"); day=by.get(dd.isoformat(),[]); st.caption("Chưa có công việc") if not day else None
                for x in day:
                    with st.container(border=True): card(st,x,ws,get_conn,uid,logger)
                if st.button("＋ Thêm",key=f"wpadd{dd}",use_container_width=True): st.session_state.wp_add=dd.isoformat();st.rerun()
                if st.session_state.get("wp_add")==dd.isoformat():
                    txt=st.text_input("Việc cần làm",key=f"wpaddtxt{dd}",placeholder="Gặp Công ty A - tiền gửi"); y1,y2=st.columns(2)
                    if y1.button("Lưu",key=f"wpaddsave{dd}",type="primary",use_container_width=True):
                        x=parse_line(txt,ws,cs,dd)
                        if x: save_items(get_conn,uid,ws,[x],logger);st.session_state.pop("wp_add",None);st.rerun()
                    if y2.button("Đóng",key=f"wpaddclose{dd}",use_container_width=True): st.session_state.pop("wp_add",None);st.rerun()
    elif view=="☀️ Hôm nay":
        today=date.today().isoformat(); data=[x for x in active if str(x["work_date"])[:10]==today]; st.subheader(f"☀️ Hôm nay · {date.today():%d/%m/%Y}")
        if not data: st.info("Hôm nay chưa có công việc trong kế hoạch.")
        for x in data:
            with st.container(border=True): card(st,x,ws,get_conn,uid,logger)
    elif view=="✨ Gợi ý":
        with get_conn() as c: tasks=open_tasks(c,uid)
        st.subheader("✨ Gợi ý từ hồ sơ đang xử lý");st.caption("Chỉ dùng dữ liệu đã có trong KHDN Ops; không tạo lại hồ sơ tác nghiệp.")
        if not tasks: st.info("Không có hồ sơ đang xử lý chưa được đưa vào kế hoạch.")
        days=[ws+timedelta(days=i) for i in range(5)]
        for t in tasks:
            with st.container(border=True):
                st.markdown(f"**📑 {html.escape(str(t.get('task_type') or 'Hồ sơ'))} · {html.escape(str(t.get('customer_name') or ''))}**"); due=str(t.get("due_time") or "")[:16]; st.caption(f"Hạn xử lý: {due}") if due else None; idx=0
                try:
                    dd=datetime.fromisoformat(str(t.get("due_time"))).date(); idx=dd.weekday() if ws<=dd<ws+timedelta(days=5) else 0
                except Exception: pass
                target=st.selectbox("Đưa vào ngày",days,index=idx,format_func=day_label,key=f"wpsug{t['id']}")
                if st.button("＋ Thêm vào kế hoạch",key=f"wpsugb{t['id']}",use_container_width=True): add_task(get_conn,uid,ws,t,target,logger);st.rerun()
    else:
        with get_conn() as c: rows=c.execute("""SELECT u.full_name,SUM(CASE WHEN w.status<>'CANCELLED' THEN 1 ELSE 0 END),SUM(CASE WHEN w.status='DONE' THEN 1 ELSE 0 END),SUM(CASE WHEN w.category IN ('Khách hàng','Chăm sóc khách hàng') AND w.status<>'CANCELLED' THEN 1 ELSE 0 END),SUM(CASE WHEN w.category='Tín dụng' AND w.status<>'CANCELLED' THEN 1 ELSE 0 END),SUM(CASE WHEN w.category='Hồ sơ / Dự án' AND w.status<>'CANCELLED' THEN 1 ELSE 0 END),SUM(CASE WHEN w.category='Nội bộ' AND w.status<>'CANCELLED' THEN 1 ELSE 0 END) FROM users u LEFT JOIN weekly_plan_items w ON w.user_id=u.id AND w.work_date>=? AND w.work_date<? WHERE u.active=1 GROUP BY u.id,u.full_name ORDER BY u.full_name""",(ws.isoformat(),(ws+timedelta(days=7)).isoformat())).fetchall()
        out=[]
        for r in rows: total=int(r[1] or 0);done=int(r[2] or 0);out.append([r[0],total,int(r[3] or 0),int(r[4] or 0),int(r[5] or 0),int(r[6] or 0),done,f"{done/total*100:.1f}%" if total else "—"])
        st.subheader("👥 Kế hoạch phòng");table(st,["Cán bộ","Tổng","Khách hàng","Tín dụng","Dự án","Nội bộ","Hoàn thành","Tỷ lệ"],out)
