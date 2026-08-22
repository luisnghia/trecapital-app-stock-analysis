from __future__ import annotations

import json, sqlite3, uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from ..catalog.catalog import SCREENING_CRITERIA, load_questions
from ..db.schema import SCHEMA_SQL
from ..services.formulas import inventory_metrics


class ValidationError(ValueError):
    pass


class SQLiteChecklistRepository:
    def __init__(self, db_path: str | Path, question_catalog_path: str | Path):
        self.db_path = Path(db_path)
        self.question_catalog_path = Path(question_catalog_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        try:
            yield c; c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()

    @staticmethod
    def _d(row): return dict(row) if row else None
    @staticmethod
    def _date(v): return v.isoformat() if isinstance(v, date) else str(v)

    def initialize(self):
        with self._conn() as c:
            c.executescript(SCHEMA_SQL)
            # Backward-compatible local/dev migrations. Production PostgreSQL uses ADD COLUMN IF NOT EXISTS.
            cols = {str(r[1]) for r in c.execute("PRAGMA table_info(opportunity_inventory_snapshots)")}
            if "ccc_days" not in cols:
                c.execute("ALTER TABLE opportunity_inventory_snapshots ADD COLUMN ccc_days REAL")
            review_cols = {str(r[1]) for r in c.execute("PRAGMA table_info(research_reviews)")}
            if "review_reason" not in review_cols:
                c.execute("ALTER TABLE research_reviews ADD COLUMN review_reason TEXT")
            if "finalize_reason" not in review_cols:
                c.execute("ALTER TABLE research_reviews ADD COLUMN finalize_reason TEXT")
            for q in load_questions(self.question_catalog_path):
                c.execute("""INSERT INTO checklist_questions(question_id,question_no,group_name,question_vi,guidance,research_mode,supporting_tool)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(question_id) DO UPDATE SET question_no=excluded.question_no,group_name=excluded.group_name,
                question_vi=excluded.question_vi,guidance=excluded.guidance,research_mode=excluded.research_mode,supporting_tool=excluded.supporting_tool""",
                (q['question_id'],q['question_no'],q['group_name'],q['question_vi'],q['guidance'],q['research_mode'],q['supporting_tool']))
            for i,(code,en,vi) in enumerate(SCREENING_CRITERIA,1):
                c.execute("""INSERT INTO screening_criteria(criterion_code,criterion_name_en,criterion_name_vi,display_order) VALUES(?,?,?,?)
                ON CONFLICT(criterion_code) DO UPDATE SET criterion_name_en=excluded.criterion_name_en,criterion_name_vi=excluded.criterion_name_vi,display_order=excluded.display_order""",(code,en,vi,i))

    def _audit(self,c,company_ref_id=None,review_id=None,actor=None,action='',entity_type='',entity_id=None,before=None,after=None):
        c.execute("""INSERT INTO audit_logs(company_ref_id,review_id,actor,action,entity_type,entity_id,before_json,after_json,correlation_id)
        VALUES(?,?,?,?,?,?,?,?,?)""",(company_ref_id,review_id,actor,action,entity_type,None if entity_id is None else str(entity_id),
        None if before is None else json.dumps(before,ensure_ascii=False,default=str),None if after is None else json.dumps(after,ensure_ascii=False,default=str),str(uuid.uuid4())))

    def list_company_refs(self):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM checklist_company_refs WHERE is_active=1 ORDER BY ticker")]

    def upsert_company_ref(self,*,host_company_key,ticker,company_name,exchange='UNKNOWN',industry_name='',company_type='normal',currency='VND',host_metadata=None,actor='system'):
        key=str(host_company_key).strip(); ticker=str(ticker).strip().upper(); name=str(company_name).strip()
        if not key or not ticker or not name: raise ValidationError('host_company_key, ticker và tên doanh nghiệp là bắt buộc.')
        with self._conn() as c:
            before=self._d(c.execute("SELECT * FROM checklist_company_refs WHERE host_company_key=?",(key,)).fetchone())
            c.execute("""INSERT INTO checklist_company_refs(host_company_key,ticker,exchange,company_name,industry_name,company_type,currency,host_metadata_json,updated_at)
            VALUES(?,?,?,?,?,?,?,?,datetime('now')) ON CONFLICT(host_company_key) DO UPDATE SET ticker=excluded.ticker,exchange=excluded.exchange,
            company_name=excluded.company_name,industry_name=excluded.industry_name,company_type=excluded.company_type,currency=excluded.currency,
            host_metadata_json=excluded.host_metadata_json,is_active=1,updated_at=datetime('now')""",
            (key,ticker,str(exchange or 'UNKNOWN').upper(),name,str(industry_name or ''),company_type,currency,json.dumps(host_metadata or {},ensure_ascii=False,default=str)))
            row=self._d(c.execute("SELECT * FROM checklist_company_refs WHERE host_company_key=?",(key,)).fetchone()); cid=row['id']
            self._audit(c,company_ref_id=cid,actor=actor,action='create' if before is None else 'sync',entity_type='company_ref',entity_id=cid,before=before,after=row)
            return cid

    def get_company_ref(self,company_ref_id,conn=None):
        if conn is not None: return self._d(conn.execute("SELECT * FROM checklist_company_refs WHERE id=?",(company_ref_id,)).fetchone())
        with self._conn() as c: return self._d(c.execute("SELECT * FROM checklist_company_refs WHERE id=?",(company_ref_id,)).fetchone())
    def get_company_ref_by_host_key(self,key):
        with self._conn() as c: return self._d(c.execute("SELECT * FROM checklist_company_refs WHERE host_company_key=?",(str(key),)).fetchone())

    def list_questions(self):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM checklist_questions WHERE active=1 ORDER BY question_no")]
    def get_question(self,qid):
        with self._conn() as c: return self._d(c.execute("SELECT * FROM checklist_questions WHERE question_id=?",(qid,)).fetchone())

    def list_reviews(self,cid):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM research_reviews WHERE company_ref_id=? ORDER BY as_of_date DESC,id DESC",(cid,))]
    def get_review(self,rid,conn=None):
        if conn is not None: return self._d(conn.execute("SELECT * FROM research_reviews WHERE id=?",(rid,)).fetchone())
        with self._conn() as c: return self._d(c.execute("SELECT * FROM research_reviews WHERE id=?",(rid,)).fetchone())
    def create_review(self,cid,as_of_date,review_type='full',analyst_user_id='analyst',review_reason=None):
        if review_type not in {'full','delta','screening'}: raise ValidationError('review_type không hợp lệ')
        # None is accepted only for legacy/import/test callers. Production UI always passes an explicit reason.
        if review_reason is not None and not str(review_reason).strip(): raise ValidationError('Lý do tạo review là bắt buộc.')
        reason = str(review_reason).strip() if review_reason is not None else 'Legacy/imported review — reason not recorded'
        asof=self._date(as_of_date)
        with self._conn() as c:
            p=c.execute("SELECT id FROM research_reviews WHERE company_ref_id=? AND status='completed' AND as_of_date<=? ORDER BY as_of_date DESC,id DESC LIMIT 1",(cid,asof)).fetchone()
            cur=c.execute("INSERT INTO research_reviews(company_ref_id,review_type,as_of_date,status,prior_review_id,analyst_user_id,review_reason) VALUES(?,?,?,'in_progress',?,?,?)",(cid,review_type,asof,p['id'] if p else None,analyst_user_id,reason)); rid=cur.lastrowid
            self._audit(c,company_ref_id=cid,review_id=rid,actor=analyst_user_id,action='create',entity_type='review',entity_id=rid,after=self.get_review(rid,conn=c)); return rid
    def _editable(self,c,rid):
        r=self.get_review(rid,conn=c)
        if not r: raise ValidationError('Review không tồn tại.')
        if r['status']=='completed': raise ValidationError('Review đã finalize và bị khóa.')
        return r

    def latest_assessment(self,rid,qid,conn=None):
        sql="SELECT * FROM analyst_assessments WHERE review_id=? AND question_id=? ORDER BY version_no DESC,id DESC LIMIT 1"
        if conn is not None: return self._d(conn.execute(sql,(rid,qid)).fetchone())
        with self._conn() as c: return self._d(c.execute(sql,(rid,qid)).fetchone())
    def prior_assessment(self,rid,qid,conn=None):
        def f(c):
            r=self.get_review(rid,conn=c)
            if not r or not r['prior_review_id']: return None
            return self.latest_assessment(r['prior_review_id'],qid,conn=c)
        if conn is not None: return f(conn)
        with self._conn() as c: return f(c)
    def assessment_history(self,cid,qid):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT a.*,r.as_of_date,r.review_type,r.status review_status FROM analyst_assessments a JOIN research_reviews r ON r.id=a.review_id WHERE a.company_ref_id=? AND a.question_id=? ORDER BY r.as_of_date DESC,a.version_no DESC",(cid,qid))]
    def save_assessment(self,*,review_id,question_id,analyst_answer,status,assessment=None,confidence=None,materiality=None,change_reason='',actor='analyst',copied_from_assessment_id=None,analyst_confirmed=0):
        if status not in {'answered','research_gap','needs_review','na','not_reviewed'}: raise ValidationError('Status không hợp lệ')
        if status in {'research_gap','na','not_reviewed'} and assessment is not None: raise ValidationError('Status này không được gán Assessment; Unknown khác Neutral.')
        if status in {'answered','needs_review'} and assessment not in {-2,-1,0,1,2}: raise ValidationError('Assessment -2..+2 là bắt buộc.')
        if status in {'answered','needs_review','research_gap'} and (confidence not in {1,2,3,4,5} or materiality not in {1,2,3,4,5}): raise ValidationError('Confidence/Materiality 1..5 là bắt buộc.')
        with self._conn() as c:
            r=self._editable(c,review_id); old=self.latest_assessment(review_id,question_id,conn=c)
            if old and old['assessment'] != assessment and old['assessment'] is not None and assessment is not None and not str(change_reason).strip(): raise ValidationError('Reason for Change là bắt buộc khi Assessment thay đổi.')
            v=(old['version_no'] if old else 0)+1
            cur=c.execute("""INSERT INTO analyst_assessments(company_ref_id,review_id,question_id,version_no,analyst_answer,assessment,confidence,materiality,status,change_reason,analyst_confirmed,copied_from_assessment_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(r['company_ref_id'],review_id,question_id,v,analyst_answer,assessment,confidence,materiality,status,str(change_reason or '').strip(),analyst_confirmed,copied_from_assessment_id)); aid=cur.lastrowid
            after=self._d(c.execute("SELECT * FROM analyst_assessments WHERE id=?",(aid,)).fetchone()); self._audit(c,company_ref_id=r['company_ref_id'],review_id=review_id,actor=actor,action='append_version',entity_type='analyst_assessment',entity_id=aid,before=old,after=after); return aid
    def confirm_unchanged(self,rid,qid,actor='analyst'):
        with self._conn() as c:
            self._editable(c,rid); prior=self.prior_assessment(rid,qid,conn=c)
        if not prior: raise ValidationError('Không có prior assessment để carry-forward.')
        return self.save_assessment(review_id=rid,question_id=qid,analyst_answer=prior['analyst_answer'] or '',status=prior['status'],assessment=prior['assessment'],confidence=prior['confidence'],materiality=prior['materiality'],change_reason='Confirmed unchanged',actor=actor,copied_from_assessment_id=prior['id'],analyst_confirmed=1)
    def latest_assessments_for_review(self,rid,conn=None):
        sql="""SELECT a.* FROM analyst_assessments a JOIN (SELECT question_id,MAX(version_no) mv FROM analyst_assessments WHERE review_id=? GROUP BY question_id)x ON x.question_id=a.question_id AND x.mv=a.version_no WHERE a.review_id=? ORDER BY CAST(SUBSTR(a.question_id,2) AS INTEGER)"""
        def f(c): return [dict(r) for r in c.execute(sql,(rid,rid))]
        if conn is not None: return f(conn)
        with self._conn() as c: return f(c)
    def review_metrics(self,rid,conn=None):
        def f(c):
            xs=self.latest_assessments_for_review(rid,conn=c); na=sum(x['status']=='na' for x in xs); ans=sum(x['status']=='answered' for x in xs); den=59-na
            return {'answered':ans,'na':na,'denominator':den,'research_completion':ans/den if den else 1.0,'critical_unknowns':sum(x['status']=='research_gap' and x['materiality']==5 for x in xs),'research_gaps':sum(x['status']=='research_gap' for x in xs),'needs_review':sum(x['status']=='needs_review' for x in xs),'red_flags':sum(x['status'] in {'answered','needs_review'} and x['assessment']==-2 for x in xs),'recorded_questions':len(xs)}
        if conn is not None: return f(conn)
        with self._conn() as c: return f(c)

    def list_screening_criteria(self):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM screening_criteria ORDER BY display_order")]
    def latest_screening(self,rid,code,conn=None):
        sql="SELECT * FROM screening_assessments WHERE review_id=? AND criterion_code=? ORDER BY version_no DESC,id DESC LIMIT 1"
        if conn is not None: return self._d(conn.execute(sql,(rid,code)).fetchone())
        with self._conn() as c: return self._d(c.execute(sql,(rid,code)).fetchone())
    def latest_screening_for_review(self,rid,conn=None):
        sql="""SELECT s.* FROM screening_assessments s JOIN(SELECT criterion_code,MAX(version_no) mv FROM screening_assessments WHERE review_id=? GROUP BY criterion_code)x ON x.criterion_code=s.criterion_code AND x.mv=s.version_no WHERE s.review_id=? ORDER BY s.criterion_code"""
        def f(c): return [dict(r) for r in c.execute(sql,(rid,rid))]
        if conn is not None: return f(conn)
        with self._conn() as c: return f(c)
    def prior_screening(self,rid,code,conn=None):
        def f(c):
            r=self.get_review(rid,conn=c); return None if not r or not r['prior_review_id'] else self.latest_screening(r['prior_review_id'],code,conn=c)
        if conn is not None: return f(conn)
        with self._conn() as c: return f(c)
    def save_screening(self,*,review_id,criterion_code,analyst_value,confidence=None,note='',actor='analyst',copied_from_screening_id=None,analyst_confirmed=0):
        if analyst_value not in {'yes','no','unknown','na'}: raise ValidationError('Table 1.1 value không hợp lệ.')
        with self._conn() as c:
            r=self._editable(c,review_id); old=self.latest_screening(review_id,criterion_code,conn=c); v=(old['version_no'] if old else 0)+1
            cur=c.execute("INSERT INTO screening_assessments(company_ref_id,review_id,criterion_code,version_no,analyst_value,confidence,note,copied_from_screening_id,analyst_confirmed) VALUES(?,?,?,?,?,?,?,?,?)",(r['company_ref_id'],review_id,criterion_code,v,analyst_value,confidence,note,copied_from_screening_id,analyst_confirmed)); sid=cur.lastrowid
            after=self._d(c.execute("SELECT * FROM screening_assessments WHERE id=?",(sid,)).fetchone()); self._audit(c,company_ref_id=r['company_ref_id'],review_id=review_id,actor=actor,action='append_version',entity_type='screening_assessment',entity_id=sid,before=old,after=after); return sid
    def confirm_screening_unchanged(self,rid,code,actor='analyst'):
        with self._conn() as c:
            self._editable(c,rid); p=self.prior_screening(rid,code,conn=c)
        if not p: raise ValidationError('Không có prior Table 1.1 để carry-forward.')
        return self.save_screening(review_id=rid,criterion_code=code,analyst_value=p['analyst_value'],confidence=p['confidence'],note=p['note'] or '',actor=actor,copied_from_screening_id=p['id'],analyst_confirmed=1)
    def quality_tally(self,rid,conn=None):
        def f(c): return sum(x['analyst_value']=='yes' for x in self.latest_screening_for_review(rid,conn=c))
        if conn is not None: return f(conn)
        with self._conn() as c: return f(c)
    def screening_matrix_latest(self):
        with self._conn() as c:
            out=[]
            for co in c.execute("SELECT * FROM checklist_company_refs WHERE is_active=1 ORDER BY ticker"):
                rv=c.execute("SELECT * FROM research_reviews WHERE company_ref_id=? ORDER BY as_of_date DESC,id DESC LIMIT 1",(co['id'],)).fetchone()
                if not rv: continue
                row={'Ticker':co['ticker'],'Company':co['company_name'],'As of':rv['as_of_date']}; tally=0
                for cr in c.execute("SELECT * FROM screening_criteria ORDER BY display_order"):
                    s=self.latest_screening(rv['id'],cr['criterion_code'],conn=c); val=s['analyst_value'] if s else 'unknown'; row[cr['criterion_name_vi']]=val; tally += val=='yes'
                row['Total ✓']=tally; out.append(row)
            return out
    def screening_history_matrix(self,cid):
        """Return one Table 1.1 row per review using the latest version of each criterion."""
        with self._conn() as c:
            reviews=[dict(r) for r in c.execute("SELECT * FROM research_reviews WHERE company_ref_id=? ORDER BY as_of_date DESC,id DESC",(cid,))]
            criteria=[dict(r) for r in c.execute("SELECT * FROM screening_criteria ORDER BY display_order")]
            all_rows=[dict(r) for r in c.execute("SELECT * FROM screening_assessments WHERE company_ref_id=? ORDER BY review_id,criterion_code,version_no,id",(cid,))]
        latest={}
        for s in all_rows:
            latest[(s['review_id'],s['criterion_code'])]=s
        out=[]
        for rv in reviews:
            row={'Review #':rv['id'],'As of':rv['as_of_date'],'Type':rv['review_type'],'Status':rv['status']}; tally=0
            for cr in criteria:
                s=latest.get((rv['id'],cr['criterion_code'])); val=s['analyst_value'] if s else 'unknown'
                row[cr['criterion_name_vi']]=val; tally += val=='yes'
            row['Total ✓']=tally; out.append(row)
        return out

    def save_inventory_snapshot(self,*,company_ref_id,as_of_date,review_id=None,tev=None,ebit=None,ebitda=None,normalized_earnings=None,total_debt=None,interest_expense=None,fcf_current=None,market_cap=None,dividend_per_share=None,market_price=None,fcf_estimate=None,target_price=None,ccc_days=None,mos=None,thesis_direction='unknown',note='',actor='analyst',data_origin='manual',source_as_of_date=None):
        if thesis_direction not in {'up','flat','down','unknown'} or data_origin not in {'manual','host_data_layer','mixed'}: raise ValidationError('Inventory metadata không hợp lệ.')
        asof=self._date(as_of_date); met=inventory_metrics(tev=tev,ebit=ebit,ebitda=ebitda,normalized_earnings=normalized_earnings,total_debt=total_debt,interest_expense=interest_expense,fcf_current=fcf_current,market_cap=market_cap,dividend_per_share=dividend_per_share,market_price=market_price,target_price=target_price)
        with self._conn() as c:
            if review_id is None:
                x=c.execute("SELECT id FROM research_reviews WHERE company_ref_id=? ORDER BY as_of_date DESC,id DESC LIMIT 1",(company_ref_id,)).fetchone(); review_id=x['id'] if x else None
            q=self.quality_tally(review_id,conn=c) if review_id else 0; rm=self.review_metrics(review_id,conn=c) if review_id else {'answered':0,'research_completion':0.0,'critical_unknowns':0,'red_flags':0}
            v=c.execute("SELECT COALESCE(MAX(version_no),0) v FROM opportunity_inventory_snapshots WHERE company_ref_id=? AND as_of_date=?",(company_ref_id,asof)).fetchone()['v']+1
            fields={'company_ref_id':company_ref_id,'as_of_date':asof,'version_no':v,'data_origin':data_origin,'source_as_of_date':source_as_of_date,'tev':tev,'ebit':ebit,'ebitda':ebitda,'normalized_earnings':normalized_earnings,'total_debt':total_debt,'interest_expense':interest_expense,'fcf_current':fcf_current,'market_cap':market_cap,'dividend_per_share':dividend_per_share,'market_price':market_price,'fcf_estimate':fcf_estimate,'target_price':target_price,'ccc_days':ccc_days,**met,'quality_tally':q,'checklist_answered':rm['answered'],'research_completion':rm['research_completion'],'critical_unknowns':rm['critical_unknowns'],'red_flags':rm['red_flags'],'mos':mos,'thesis_direction':thesis_direction,'last_review_id':review_id,'note':str(note or '').strip()}
            cur=c.execute(f"INSERT INTO opportunity_inventory_snapshots({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",tuple(fields.values())); iid=cur.lastrowid
            self._audit(c,company_ref_id=company_ref_id,review_id=review_id,actor=actor,action='create_snapshot',entity_type='opportunity_inventory',entity_id=iid,after=self._d(c.execute("SELECT * FROM opportunity_inventory_snapshots WHERE id=?",(iid,)).fetchone())); return iid
    def inventory_history(self,cid):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM opportunity_inventory_snapshots WHERE company_ref_id=? ORDER BY as_of_date DESC,version_no DESC",(cid,))]
    def latest_inventory_all(self):
        with self._conn() as c:
            out=[]
            for co in c.execute("SELECT * FROM checklist_company_refs WHERE is_active=1 ORDER BY ticker"):
                inv=c.execute("SELECT * FROM opportunity_inventory_snapshots WHERE company_ref_id=? ORDER BY as_of_date DESC,version_no DESC,id DESC LIMIT 1",(co['id'],)).fetchone()
                if inv: d=dict(inv); d['ticker']=co['ticker']; d['company_name']=co['company_name']; out.append(d)
            return out

    def _snapshot_payload(self,c,rid):
        from ..services.evidence_workspace import snapshot_evidence_for_review

        rv=self.get_review(rid,conn=c); co=self.get_company_ref(rv['company_ref_id'],conn=c); inv=c.execute("SELECT * FROM opportunity_inventory_snapshots WHERE company_ref_id=? AND as_of_date<=? ORDER BY as_of_date DESC,version_no DESC,id DESC LIMIT 1",(rv['company_ref_id'],rv['as_of_date'])).fetchone()
        return {'snapshot_schema':'phase1b-review-v2-evidence','generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'company':co,'review':rv,'metrics':self.review_metrics(rid,conn=c),'quality_tally':self.quality_tally(rid,conn=c),'assessments':self.latest_assessments_for_review(rid,conn=c),'screening':self.latest_screening_for_review(rid,conn=c),'opportunity_inventory':dict(inv) if inv else None,'research_evidence':snapshot_evidence_for_review(self,rid,conn=c)}
    def finalize_review(self,rid,actor='analyst',finalize_reason=None):
        if finalize_reason is not None and not str(finalize_reason).strip(): raise ValidationError('Lý do chốt review là bắt buộc.')
        reason = str(finalize_reason).strip() if finalize_reason is not None else 'Legacy/imported finalize — reason not recorded'
        with self._conn() as c:
            rv=self._editable(c,rid); c.execute("UPDATE research_reviews SET status='completed',finalize_reason=?,completed_at=datetime('now') WHERE id=?",(reason,rid)); payload=self._snapshot_payload(c,rid)
            v=c.execute("SELECT COALESCE(MAX(snapshot_version),0) v FROM data_snapshots WHERE review_id=? AND snapshot_type='review'",(rid,)).fetchone()['v']+1
            cur=c.execute("INSERT INTO data_snapshots(company_ref_id,review_id,as_of_date,snapshot_type,snapshot_version,payload_json) VALUES(?,?,?,'review',?,?)",(rv['company_ref_id'],rid,rv['as_of_date'],v,json.dumps(payload,ensure_ascii=False,default=str))); sid=cur.lastrowid
            self._audit(c,company_ref_id=rv['company_ref_id'],review_id=rid,actor=actor,action='finalize',entity_type='review',entity_id=rid,before=rv,after={'status':'completed','snapshot_id':sid,'finalize_reason':reason}); return sid
    def list_snapshots(self,cid):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT id,company_ref_id,review_id,as_of_date,snapshot_type,snapshot_version,created_at FROM data_snapshots WHERE company_ref_id=? ORDER BY as_of_date DESC,id DESC",(cid,))]
    def get_snapshot(self,sid):
        with self._conn() as c:
            r=c.execute("SELECT * FROM data_snapshots WHERE id=?",(sid,)).fetchone()
            if not r: return None
            d=dict(r); d['payload']=json.loads(d.pop('payload_json')); return d
    def record_sync(self,*,company_ref_id,source_module,status,source_as_of_date=None,payload_hash=None,detail=''):
        if status not in {'success','partial','failed','skipped'}: raise ValidationError('sync status không hợp lệ')
        with self._conn() as c: return c.execute("INSERT INTO integration_sync_log(company_ref_id,source_module,source_as_of_date,payload_hash,status,detail) VALUES(?,?,?,?,?,?)",(company_ref_id,source_module,source_as_of_date,payload_hash,status,detail)).lastrowid
    def list_sync_logs(self,cid,limit=100):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM integration_sync_log WHERE company_ref_id=? ORDER BY id DESC LIMIT ?",(cid,int(limit)))]
    def list_audit_logs(self,cid,limit=200):
        with self._conn() as c: return [dict(r) for r in c.execute("SELECT * FROM audit_logs WHERE company_ref_id=? ORDER BY id DESC LIMIT ?",(cid,int(limit)))]
