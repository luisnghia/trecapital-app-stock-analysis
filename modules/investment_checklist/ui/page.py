from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from ..contracts import HostContext, TrecapitalDataProvider, TrecapitalThemeAdapter
from ..repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from ..services.integration_service import ChecklistIntegrationService, build_repository
from .present import ASSESSMENT_LABELS, SCREENING_SYMBOL, STATUS_LABELS, THESIS_SYMBOL, fmt_pct, fmt_ratio, fmt_price

FALLBACK_CSS = """
<style>
.checklist-module .muted{color:#667085;font-size:.88rem}.checklist-module .locked{display:inline-block;padding:.2rem .55rem;border-radius:999px;background:#EEF2F6;color:#344054;font-size:.82rem}.checklist-module .guide{padding:.75rem .9rem;border-left:4px solid #B68A3A;background:#FFFDF8;border-radius:6px;margin:.4rem 0 .8rem}.checklist-module .principle{padding:.75rem .9rem;border:1px solid #D7CFBE;background:#F8F5ED;border-radius:8px;margin:.5rem 0}
</style>
"""


def _idx(options, value, default=0):
    try: return options.index(value)
    except ValueError: return default

def _map(rows, key): return {r[key]: r for r in rows}

def _num(raw: str, label: str):
    raw=(raw or '').strip().replace(',','')
    if not raw: return None
    try: return float(raw)
    except ValueError as exc: raise ValidationError(f"{label}: giá trị không hợp lệ: {raw}") from exc

def _txt(v): return '' if v is None else str(v)

def _review_label(r): return f"{r['as_of_date']} | {r['review_type']} | {r['status']} | #{r['id']}"

def _group_progress(repo, rid):
    qs=repo.list_questions(); am=_map(repo.latest_assessments_for_review(rid),'question_id'); rows=[]
    for group in dict.fromkeys(q['group_name'] for q in qs):
        group_q=[q for q in qs if q['group_name']==group]; xs=[am.get(q['question_id']) for q in group_q]
        na=sum(bool(x) and x['status']=='na' for x in xs); answered=sum(bool(x) and x['status']=='answered' for x in xs); gaps=sum(bool(x) and x['status']=='research_gap' for x in xs); needs=sum(bool(x) and x['status']=='needs_review' for x in xs); den=len(group_q)-na
        rows.append({'Nhóm':group,'Đã trả lời':answered,'N/A':na,'Research Gap':gaps,'Cần xem lại':needs,'Tổng áp dụng':den,'Hoàn thành':answered/den if den else 1.0})
    return pd.DataFrame(rows)

def _inventory_table(repo):
    rows=repo.latest_inventory_all()
    if not rows: st.info('Chưa có dữ liệu Table 1.2.'); return
    out=[]
    for x in rows:
        out.append({'Mã':x['ticker'],'Doanh nghiệp':x['company_name'],'As of':x['as_of_date'],'Origin':x.get('data_origin','manual'),'TEV/EBIT':fmt_ratio(x['tev_ebit']),'TEV/EBITDA':fmt_ratio(x['tev_ebitda']),'TEV/Norm.E':fmt_ratio(x['tev_normalized_earnings']),'Pre-tax yield':fmt_pct(x['pretax_earnings_yield']),'Debt/EBITDA':fmt_ratio(x['debt_ebitda']),'EBIT/Interest':fmt_ratio(x['ebit_interest']),'FCF Yield EV':fmt_pct(x['fcf_yield_ev']),'FCF Yield Mkt':fmt_pct(x['fcf_yield_market']),'Dividend Yield':fmt_pct(x['dividend_yield']),'Giá':fmt_price(x['market_price']),'Target':fmt_price(x['target_price']),'Price/Target':fmt_pct(x['price_vs_target']),'T1.1':f"{x['quality_tally'] or 0}/10",'Q answered':x['checklist_answered'] or 0,'Completion':fmt_pct(x['research_completion']),'Critical ?':x['critical_unknowns'] or 0,'Red flags':x['red_flags'] or 0,'MOS':fmt_pct(x['mos']),'Δ Thesis':THESIS_SYMBOL.get(x['thesis_direction'],'?')})
    st.dataframe(pd.DataFrame(out),use_container_width=True,hide_index=True)


def render_investment_checklist(host: HostContext, *, repo: Optional[SQLiteChecklistRepository]=None, data_provider: Optional[TrecapitalDataProvider]=None, theme: Optional[TrecapitalThemeAdapter]=None) -> None:
    """Native Trecapital Phase 1B UI. No AI and no st.set_page_config call."""
    if theme: theme.inject_module_css()
    else: st.markdown(FALLBACK_CSS,unsafe_allow_html=True)
    repo=repo or build_repository(host); integration=ChecklistIntegrationService(repo,host,data_provider); cid=integration.sync_company_context(); company=repo.get_company_ref(cid); actor=host.analyst.user_id
    st.markdown('<div class="checklist-module">',unsafe_allow_html=True)
    st.subheader('Investment Research & Checklist System')
    st.caption('Phase 1B — Table 1.1 + Table 1.2 + Q01–Q59 + versioning + immutable snapshots. Không AI.')
    st.markdown(f"**{company['ticker']} — {company['company_name']}** · {company['industry_name'] or 'Chưa gán ngành'}")
    st.markdown('<div class="principle"><b>Nguyên tắc:</b> AI chưa tham gia Phase 1. Analyst tự trả lời, tự đánh giá; Unknown khác Neutral; mọi thay đổi được lưu version; review đã finalize là read-only.</div>',unsafe_allow_html=True)

    reviews=repo.list_reviews(cid); review=None; left,right=st.columns([2.4,1])
    if reviews:
        ids=[r['id'] for r in reviews]; state=f"checklist_review_{company['host_company_key']}"; desired=st.session_state.get(state); index=ids.index(desired) if desired in ids else 0
        rid=left.selectbox('Review',ids,index=index,format_func=lambda x:_review_label(next(r for r in reviews if r['id']==x)),key=f'review_select_{cid}'); st.session_state[state]=rid; review=repo.get_review(rid)
    else: left.info('Chưa có review cho mã này.')
    with right.popover('➕ Tạo review mới',use_container_width=True):
        asof=st.date_input('As-of date',value=date.today(),key=f'new_review_date_{cid}'); rtype=st.selectbox('Loại review',['full','screening','delta'],key=f'new_review_type_{cid}')
        if st.button('Tạo review',use_container_width=True,key=f'create_review_{cid}'):
            rid=repo.create_review(cid,asof,rtype,actor); st.session_state[f"checklist_review_{company['host_company_key']}"]=rid; st.rerun()
    if review:
        st.caption(f"Review #{review['id']} · {review['as_of_date']} · {review['review_type']} · {review['status']}")
        if review['status']=='completed': st.markdown('<span class="locked">🔒 Completed — read only</span>',unsafe_allow_html=True)

    home,t11,t12,workspace,history=st.tabs(['🏠 Research Home','📋 Table 1.1','📊 Table 1.2','🧠 Analyst Workspace Q01–Q59','🕘 Snapshot & History'])
    with home:
        if not review: st.info('Tạo review để bắt đầu nghiên cứu.')
        else:
            m=repo.review_metrics(review['id']); cols=st.columns(6); cols[0].metric('Table 1.1',f"{repo.quality_tally(review['id'])}/10"); cols[1].metric('Checklist answered',f"{m['answered']}/59"); cols[2].metric('Research completion',f"{m['research_completion']*100:.1f}%"); cols[3].metric('Research gaps',m['research_gaps']); cols[4].metric('Critical unknowns',m['critical_unknowns']); cols[5].metric('Red flags (-2)',m['red_flags'])
            st.caption('Research Completion = Answered / (59 − N/A). Research Gap không được tính là Answered và không bị quy đổi thành Assessment 0.')
            g=_group_progress(repo,review['id']); g['Hoàn thành']=g['Hoàn thành'].map(lambda x:f'{x*100:.1f}%'); st.dataframe(g,use_container_width=True,hide_index=True)

    with t11:
        st.markdown('#### Table 1.1 — Quality Criteria Matrix'); st.caption('✓ = Có · X = Không có · — = Chưa biết · N/A = Không áp dụng. Total chỉ đếm ✓, không tạo BUY/SELL.')
        matrix=repo.screening_matrix_latest()
        if matrix:
            df=pd.DataFrame(matrix)
            for col in df.columns:
                if col not in {'Ticker','Company','As of','Total ✓'}: df[col]=df[col].map(SCREENING_SYMBOL)
            st.dataframe(df,use_container_width=True,hide_index=True)
        if review and review['status']!='completed':
            criteria=repo.list_screening_criteria(); cur=_map(repo.latest_screening_for_review(review['id']),'criterion_code'); priors={c['criterion_code']:repo.prior_screening(review['id'],c['criterion_code']) for c in criteria}
            if any(priors.values()) and st.button('↪ Confirm toàn bộ Table 1.1 unchanged từ review trước',key=f'carry_sc_{review["id"]}'):
                for c in criteria:
                    if priors[c['criterion_code']]: repo.confirm_screening_unchanged(review['id'],c['criterion_code'],actor=actor)
                st.rerun()
            with st.form(f'screen_form_{review["id"]}'):
                values=[]; options=['yes','no','unknown','na']
                for c in criteria:
                    old=cur.get(c['criterion_code']); prior=priors[c['criterion_code']]; st.markdown(f"**{c['display_order']}. {c['criterion_name_vi']}** · `{c['criterion_name_en']}`")
                    a,b,d=st.columns([1.4,1.2,4]); val=a.selectbox('Kết luận',options,index=_idx(options,old['analyst_value'] if old else 'unknown',2),format_func=lambda x:{'yes':'✓ Có','no':'X Không','unknown':'— Chưa biết','na':'N/A'}[x],key=f"sc_v_{review['id']}_{c['criterion_code']}"); conf=b.selectbox('Confidence',[1,2,3,4,5],index=_idx([1,2,3,4,5],old['confidence'] if old and old['confidence'] else 3,2),key=f"sc_c_{review['id']}_{c['criterion_code']}"); note=d.text_input('Ghi chú / bằng chứng analyst',value=old['note'] if old else '',key=f"sc_n_{review['id']}_{c['criterion_code']}")
                    if prior: d.caption(f"Prior: {SCREENING_SYMBOL.get(prior['analyst_value'],'—')} · conf {prior['confidence'] or '—'}")
                    values.append((c['criterion_code'],val,conf,note))
                if st.form_submit_button('Lưu Table 1.1 — tạo version mới',type='primary',use_container_width=True):
                    for code,val,conf,note in values: repo.save_screening(review_id=review['id'],criterion_code=code,analyst_value=val,confidence=conf,note=note,actor=actor)
                    st.rerun()
        elif review: st.info('Review đã khóa. Tạo review mới để cập nhật Table 1.1.')

    with t12:
        st.markdown('#### Table 1.2 — Opportunity Inventory'); st.caption('Tự đọc dữ liệu chuẩn hóa từ Module 1/2 khi có. Manual override được lưu thành snapshot riêng; không ghi đè lịch sử.')
        _inventory_table(repo); pre=integration.get_inventory_prefill()
        if pre:
            with st.expander('🔗 Dữ liệu hiện có từ Trecapital Data Layer'):
                st.json(pre.__dict__)
                if st.button('Lưu snapshot từ Data Layer',key=f'host_inv_{cid}'):
                    integration.save_host_inventory_snapshot(company_ref_id=cid,review_id=review['id'] if review else None,data=pre); st.rerun()
        inv_hist=repo.inventory_history(cid); latest=inv_hist[0] if inv_hist else {}; premap=pre.__dict__ if pre else {}
        def base(k): return latest.get(k) if latest.get(k) is not None else premap.get(k)
        with st.form(f'inv_form_{cid}'):
            default_date=date.fromisoformat(pre.as_of_date[:10]) if pre and len(pre.as_of_date)>=10 and pre.as_of_date[:10].count('-')==2 else (date.fromisoformat(review['as_of_date']) if review else date.today()); asof=st.date_input('As-of date',value=default_date)
            c=st.columns(4); tev=c[0].text_input('TEV (tỷ)',value=_txt(base('tev'))); ebit=c[1].text_input('EBIT (tỷ)',value=_txt(base('ebit'))); ebitda=c[2].text_input('EBITDA (tỷ)',value=_txt(base('ebitda'))); norm=c[3].text_input('Normalized earnings (tỷ)',value=_txt(base('normalized_earnings')))
            c=st.columns(4); debt=c[0].text_input('Total debt (tỷ)',value=_txt(base('total_debt'))); interest=c[1].text_input('Interest expense (tỷ)',value=_txt(base('interest_expense'))); fcf=c[2].text_input('Current FCF (tỷ)',value=_txt(base('fcf_current'))); mcap=c[3].text_input('Market cap (tỷ)',value=_txt(base('market_cap')))
            c=st.columns(4); dps=c[0].text_input('Dividend/share (VND)',value=_txt(base('dividend_per_share'))); price=c[1].text_input('Market price (VND)',value=_txt(base('market_price'))); fcf_est=c[2].text_input('FCF Estimate',value=_txt(base('fcf_estimate'))); target=c[3].text_input('Target price (VND)',value=_txt(base('target_price')))
            c=st.columns([1,1,3]); mos_default=(latest.get('mos') if latest.get('mos') is not None else premap.get('mos')) or 0.0; mos=c[0].number_input('MOS (%)',value=float(mos_default)*100,step=1.0); thesis=c[1].selectbox('Δ Thesis',['unknown','up','flat','down'],index=_idx(['unknown','up','flat','down'],latest.get('thesis_direction') or 'unknown'),format_func=lambda x:{'unknown':'?','up':'↑ Cải thiện','flat':'→ Không đổi','down':'↓ Suy giảm'}[x]); note=c[2].text_input('Ghi chú',value=latest.get('note') or '')
            if st.form_submit_button('Lưu Inventory Snapshot',type='primary',use_container_width=True):
                try:
                    payload={'tev':_num(tev,'TEV'),'ebit':_num(ebit,'EBIT'),'ebitda':_num(ebitda,'EBITDA'),'normalized_earnings':_num(norm,'Normalized earnings'),'total_debt':_num(debt,'Total debt'),'interest_expense':_num(interest,'Interest expense'),'fcf_current':_num(fcf,'FCF'),'market_cap':_num(mcap,'Market cap'),'dividend_per_share':_num(dps,'Dividend/share'),'market_price':_num(price,'Market price'),'fcf_estimate':_num(fcf_est,'FCF estimate'),'target_price':_num(target,'Target price')}
                    repo.save_inventory_snapshot(company_ref_id=cid,as_of_date=asof,review_id=review['id'] if review else None,mos=mos/100 if mos else None,thesis_direction=thesis,note=note,actor=actor,data_origin='mixed' if pre else 'manual',source_as_of_date=pre.as_of_date if pre else None,**payload); st.rerun()
                except ValidationError as exc: st.error(str(exc))
        if inv_hist:
            with st.expander('Lịch sử Table 1.2'): st.dataframe(pd.DataFrame(inv_hist),use_container_width=True,hide_index=True)

    with workspace:
        st.markdown('#### Analyst Workspace — Q01–Q59')
        if not review: st.info('Tạo review để làm checklist.')
        else:
            qs=repo.list_questions(); groups=list(dict.fromkeys(q['group_name'] for q in qs)); c1,c2=st.columns([1.2,2.8]); group=c1.selectbox('Nhóm',groups,key=f'q_group_{review["id"]}'); qg=[q for q in qs if q['group_name']==group]; qids=[q['question_id'] for q in qg]; qid=c2.selectbox('Câu hỏi',qids,format_func=lambda x:f"{x} — {next(q for q in qg if q['question_id']==x)['question_vi']}",key=f'q_sel_{review["id"]}_{group}')
            q=next(q for q in qs if q['question_id']==qid); current=repo.latest_assessment(review['id'],qid); prior=repo.prior_assessment(review['id'],qid)
            st.markdown(f"### {qid}. {q['question_vi']}"); st.markdown(f"<div class='guide'><b>Hướng dẫn tự phân tích:</b> {q['guidance']}</div>",unsafe_allow_html=True); st.caption(f"Supporting tool (Phase sau): {q['supporting_tool'] or 'Không có'}")
            a,b=st.columns(2); a.markdown('**Current review**'); a.write(current or 'Chưa có version'); b.markdown('**Prior completed review**'); b.write(prior or 'Không có prior assessment')
            if review['status']!='completed':
                if prior and st.button('↪ Confirm unchanged từ review trước',key=f'carry_{review["id"]}_{qid}'): repo.confirm_unchanged(review['id'],qid,actor=actor); st.rerun()
                statuses=['not_reviewed','answered','research_gap','needs_review','na']; status=st.selectbox('Status',statuses,index=_idx(statuses,current['status'] if current else (prior['status'] if prior else 'not_reviewed')),format_func=lambda x:STATUS_LABELS[x],key=f'status_{review["id"]}_{qid}')
                with st.form(f'assess_{review["id"]}_{qid}'):
                    answer=st.text_area('Câu trả lời của analyst',value=(current['analyst_answer'] if current else (prior['analyst_answer'] if prior else '')) or '',height=180)
                    if status in {'answered','needs_review'}:
                        opts=[-2,-1,0,1,2]; base_ass=current['assessment'] if current and current['assessment'] is not None else (prior['assessment'] if prior and prior['assessment'] is not None else 0); assessment=st.radio('Assessment',opts,index=_idx(opts,base_ass,2),horizontal=True,format_func=lambda x:ASSESSMENT_LABELS[x])
                    else: assessment=None; st.caption('Status này không được quy đổi thành điểm Assessment.')
                    if status in {'answered','needs_review','research_gap'}:
                        cc=st.columns(2); base_conf=current['confidence'] if current and current['confidence'] else (prior['confidence'] if prior and prior['confidence'] else 3); base_mat=current['materiality'] if current and current['materiality'] else (prior['materiality'] if prior and prior['materiality'] else 3); confidence=cc[0].slider('Confidence',1,5,int(base_conf)); materiality=cc[1].slider('Materiality',1,5,int(base_mat))
                    else: confidence=materiality=None
                    reason=st.text_input('Reason for Change',help='Bắt buộc nếu Assessment thay đổi so với version hiện tại.')
                    if st.form_submit_button('Lưu phiên bản mới',type='primary',use_container_width=True):
                        try: repo.save_assessment(review_id=review['id'],question_id=qid,analyst_answer=answer,status=status,assessment=assessment,confidence=confidence,materiality=materiality,change_reason=reason,actor=actor); st.rerun()
                        except ValidationError as exc: st.error(str(exc))
            else: st.info('Review đã completed. Hãy tạo review mới để cập nhật.')
            hist=repo.assessment_history(cid,qid)
            if hist: st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)

    with history:
        st.markdown('#### Snapshot & History')
        if not review: st.info('Chưa có review.')
        else:
            m=repo.review_metrics(review['id']); c=st.columns(3); c[0].metric('Answered',m['answered']); c[1].metric('Research gaps',m['research_gaps']); c[2].metric('Completion',f"{m['research_completion']*100:.1f}%")
            if review['status']!='completed':
                ok=st.checkbox('Tôi hiểu review sẽ bị khóa sau khi finalize.',key=f'fin_{review["id"]}')
                if st.button('🔒 Finalize & Create Immutable Snapshot',type='primary',disabled=not ok,key=f'final_{review["id"]}'): repo.finalize_review(review['id'],actor=actor); st.rerun()
            snaps=repo.list_snapshots(cid)
            if snaps:
                st.dataframe(pd.DataFrame(snaps),use_container_width=True,hide_index=True); sid=st.selectbox('View as-of snapshot',[s['id'] for s in snaps],format_func=lambda x:f"Snapshot #{x} — {next(s for s in snaps if s['id']==x)['as_of_date']}"); st.json(repo.get_snapshot(sid)['payload'])
            else: st.info('Chưa có snapshot.')
            with st.expander('Audit log'):
                logs=repo.list_audit_logs(cid,200); st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True) if logs else st.caption('Chưa có log.')
            with st.expander('Integration sync log'):
                logs=repo.list_sync_logs(cid,100); st.dataframe(pd.DataFrame(logs),use_container_width=True,hide_index=True) if logs else st.caption('Chưa có sync log.')
    st.markdown('</div>',unsafe_allow_html=True)
