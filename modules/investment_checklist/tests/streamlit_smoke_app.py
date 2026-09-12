from pathlib import Path
import tempfile

from modules.investment_checklist.contracts import AnalystContext, CompanyContext, HostContext
from modules.investment_checklist.ui import render_investment_checklist

DB = Path(tempfile.gettempdir()) / "trecapital_checklist_streamlit_smoke.db"
host = HostContext(
    company=CompanyContext(
        company_key="TICKER:FPT-SMOKE",
        ticker="FPT",
        company_name="FPT Corp",
        exchange="HOSE",
        industry_name="Technology",
        company_type="normal",
    ),
    analyst=AnalystContext(user_id="qa", display_name="QA"),
    shared_db_path=DB,
)
render_investment_checklist(host)
