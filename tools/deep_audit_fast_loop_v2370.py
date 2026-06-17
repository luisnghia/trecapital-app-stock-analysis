from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.deep_audit_loop_v2370 import run_one_round

def subprocess_ok(cmd, timeout=180):
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return {"cmd":" ".join(cmd),"returncode":p.returncode,"ok":p.returncode==0,"output_tail":p.stdout[-5000:]}

def run_inprocess_round(round_no:int):
    # Reuse run_one_round but monkey patch heavy subprocess section by directly replicating via a lighter mode is hard.
    # Instead, call only financial/static checks by setting subprocess_ok to no-op not possible from import.
    # We'll simply run official one full round separately and then use run_one_round with heavy subprocess disabled by local env? Not implemented.
    return run_one_round(round_no)

# For speed, implement direct subprocess once and then invoke selected in-process assertions by calling the full function only once.
def main():
    start=time.time()
    official=[]
    for cmd in ([sys.executable,"-m","compileall","-q","."],[sys.executable,"tools/run_formula_regression_check.py"],[sys.executable,"tools/run_module2_self_check.py"]):
        official.append(subprocess_ok(cmd, timeout=240))
    official_ok=all(x["ok"] for x in official)
    # Run one full round (covers all in-process checks); repeat a lightweight repetition of formula_regression twice.
    full=[]
    r=run_one_round(1); full.append({k:v for k,v in r.items() if k!='details'})
    # Because run_one_round itself includes subprocesses, do not repeat it. Repeat official formula checks once more.
    repeat=[]
    for i in range(2,4):
        cmd=[sys.executable,"tools/run_formula_regression_check.py"]
        res=subprocess_ok(cmd,timeout=180); res["round"]=i; repeat.append(res)
        print(f"LIGHT ROUND {i}: {'OK' if res['ok'] else 'FAIL'}")
    passed=official_ok and full[0]["issue_count"]==0 and all(x["ok"] for x in repeat)
    summary={"passed":passed,"mode":"bounded convergence: official compile/formula/module2 once + one full deep audit + two repeated formula rounds","elapsed_seconds":round(time.time()-start,2),"official":official,"full_deep_rounds":full,"repeat_rounds":[{"round":x["round"],"ok":x["ok"],"returncode":x["returncode"]} for x in repeat]}
    out=ROOT/"reports"/"V23_70_deep_audit_fast_summary.json"
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if passed else 1
if __name__=='__main__':
    raise SystemExit(main())
