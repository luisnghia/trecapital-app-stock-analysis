from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import appendix_c as appc
from modules.deep_company_analysis import appendix_c_history as hist
from modules.deep_company_analysis import appendix_c_workspace as ws

rows = ws.build_live_rows("QA", owner_payloads={})
payload = hist.build_snapshot_payload(rows)
errors = list(appc.validate_source_lock()) + list(ws.validate_read_only_rows(rows)) + list(hist.validate_snapshot_payload(payload))
contract = hist.closure_contract()
report = {
    "phase": "Appendix C Phase C V98",
    "acceptance": "FAIL" if errors else "PASS",
    "errors": errors,
    "question_coverage": contract["question_coverage"],
    "question_count": len(rows),
    "section_count": contract["section_coverage"],
    "source_print_pages": contract["appendix_c_source_pages"],
    "snapshot_fingerprint": hist.snapshot_fingerprint(payload),
    **{k: v for k, v in contract.items() if k not in {"question_coverage", "section_coverage", "appendix_c_source_pages"}},
}
Path("reports").mkdir(exist_ok=True)
Path("reports/APPENDIX_C_PHASEC_CLOSURE_V98.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(1 if errors else 0)
