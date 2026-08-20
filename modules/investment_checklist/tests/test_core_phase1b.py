from __future__ import annotations

from datetime import date

import pytest

from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError

CATALOG = "modules/investment_checklist/catalog/question_catalog_prd.csv"


def make_repo(tmp_path):
    r=SQLiteChecklistRepository(tmp_path / "checklist.db", CATALOG); r.initialize(); return r


def make_company(repo):
    return repo.upsert_company_ref(host_company_key="TICKER:FPT",ticker="FPT",company_name="FPT Corp",exchange="HOSE",industry_name="Technology")


def test_seeds_59_questions_and_10_criteria(tmp_path):
    r=make_repo(tmp_path)
    assert len(r.list_questions())==59
    assert len(r.list_screening_criteria())==10


def test_unknown_is_not_neutral(tmp_path):
    r=make_repo(tmp_path); cid=make_company(r); rid=r.create_review(cid,date(2026,6,30))
    with pytest.raises(ValidationError):
        r.save_assessment(review_id=rid,question_id="Q10",analyst_answer="Chưa biết churn",status="research_gap",assessment=0,confidence=2,materiality=5)
    r.save_assessment(review_id=rid,question_id="Q10",analyst_answer="Chưa đủ dữ liệu",status="research_gap",assessment=None,confidence=2,materiality=5)
    m=r.review_metrics(rid)
    assert m["research_gaps"]==1 and m["critical_unknowns"]==1 and m["answered"]==0


def test_versioning_and_reason_for_change(tmp_path):
    r=make_repo(tmp_path); cid=make_company(r); rid=r.create_review(cid,date(2026,6,30))
    r.save_assessment(review_id=rid,question_id="Q26",analyst_answer="ROIC tốt",status="answered",assessment=2,confidence=4,materiality=5)
    with pytest.raises(ValidationError):
        r.save_assessment(review_id=rid,question_id="Q26",analyst_answer="ROIC giảm",status="answered",assessment=1,confidence=4,materiality=5)
    r.save_assessment(review_id=rid,question_id="Q26",analyst_answer="ROIC giảm",status="answered",assessment=1,confidence=4,materiality=5,change_reason="ROIC TTM giảm")
    hist=r.assessment_history(cid,"Q26")
    assert {x["version_no"] for x in hist}=={1,2}


def test_explicit_carry_forward_only(tmp_path):
    r=make_repo(tmp_path); cid=make_company(r); r1=r.create_review(cid,date(2025,12,31)); r.save_assessment(review_id=r1,question_id="Q16",analyst_answer="Pricing power",status="answered",assessment=2,confidence=4,materiality=5); r.finalize_review(r1)
    r2=r.create_review(cid,date(2026,6,30)); assert r.latest_assessment(r2,"Q16") is None
    r.confirm_unchanged(r2,"Q16"); x=r.latest_assessment(r2,"Q16")
    assert x["assessment"]==2 and x["analyst_confirmed"]==1 and x["copied_from_assessment_id"] is not None


def test_finalized_review_is_read_only_and_snapshot_immutable(tmp_path):
    r=make_repo(tmp_path); cid=make_company(r); rid=r.create_review(cid,date(2026,6,30)); r.save_assessment(review_id=rid,question_id="Q01",analyst_answer="Yes",status="answered",assessment=1,confidence=4,materiality=3); sid=r.finalize_review(rid); before=r.get_snapshot(sid)["payload"]
    with pytest.raises(ValidationError):
        r.save_assessment(review_id=rid,question_id="Q01",analyst_answer="Changed",status="answered",assessment=2,confidence=5,materiality=3,change_reason="x")
    after=r.get_snapshot(sid)["payload"]
    assert before==after


def test_table_11_tally_only_yes(tmp_path):
    r=make_repo(tmp_path); cid=make_company(r); rid=r.create_review(cid,date(2026,6,30),"screening")
    criteria=r.list_screening_criteria()
    for i,c in enumerate(criteria):
        val="yes" if i<6 else ("no" if i<8 else "unknown")
        r.save_screening(review_id=rid,criterion_code=c["criterion_code"],analyst_value=val,confidence=3)
    assert r.quality_tally(rid)==6


def test_table_12_formula_snapshot(tmp_path):
    r=make_repo(tmp_path); cid=make_company(r); rid=r.create_review(cid,date(2026,6,30)); r.save_inventory_snapshot(company_ref_id=cid,as_of_date=date(2026,6,30),review_id=rid,tev=1200,ebit=100,ebitda=150,normalized_earnings=80,total_debt=300,interest_expense=20,fcf_current=60,market_cap=1000,dividend_per_share=1000,market_price=50000,target_price=70000,mos=0.2857)
    x=r.inventory_history(cid)[0]
    assert x["tev_ebit"]==12 and x["tev_ebitda"]==8 and round(x["pretax_earnings_yield"],4)==0.0667 and x["ebit_interest"]==5
