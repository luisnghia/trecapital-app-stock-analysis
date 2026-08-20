from dataclasses import dataclass
import pandas as pd
from modules.investment_checklist.trecapital_bridge import CurrentRepoDataProvider

@dataclass
class Company:
    ticker: str
    market_cap_bil: float
    current_price: float

@dataclass
class ValuationRange:
    weighted_vnd: float
    mos_to_weighted_pct: float

def df(ticker,op,ebitda,pretax,debt,net_debt,fcf):
    return pd.DataFrame([{"ticker":ticker,"period":"2026 TTM","operating_profit_bil":op,"ebitda_bil":ebitda,"pretax_profit_bil":pretax,"interest_bearing_debt_bil":debt,"net_debt_bil":net_debt,"free_cash_flow_bil":fcf}])

def test_fpt_bridge_module1_module2():
    x=CurrentRepoDataProvider(Company("FPT",210000,105000),df("FPT",12000,14500,11500,8000,-5000,9000),ValuationRange(135000,22.2222)).get_inventory_source_data(None)
    assert x.tev==205000 and x.ebit==12000 and x.target_price==135000 and round(x.mos,4)==0.2222

def test_vcb_bridge_does_not_fake_interest_expense():
    x=CurrentRepoDataProvider(Company("VCB",600000,65000),df("VCB",50000,52000,48000,100000,85000,42000)).get_inventory_source_data(None)
    assert x.interest_expense is None and x.total_debt==100000

def test_hpg_bridge_cyclical_facts_without_parallel_roic():
    d=df("HPG",18000,26000,16500,70000,50000,10000); d["roic_standard_pct"]=12.3
    x=CurrentRepoDataProvider(Company("HPG",180000,27000),d).get_inventory_source_data(None)
    assert x.tev==230000 and x.normalized_earnings==16500 and not hasattr(x,"roic")
