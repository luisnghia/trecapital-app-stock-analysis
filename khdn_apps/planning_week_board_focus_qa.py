from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_week_board_focus_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "mon_fri_board": "Kế hoạch Thứ 2 → Thứ 6" in src and "Thứ 6" in src,
    "five_day_columns": "st.columns(5" in src,
    "focus_priority_source": "_focus_rows(policy" in src and "Công việc ưu tiên *" in src,
    "focus_q2": "priority_q = 2 if focus else 4" in src,
    "self_owner_default": "index=0" in src and "disabled=True" in src,
    "attention_detail": "compact=False" in src and "original_card" in src,
    "focus_snapshot": "focus_name_snapshot" in src and "focus_category_id" in src,
    "hotfix_installs": "_week_board_focus.install" in hotfix,
    "hotfix_version": any(f'VERSION = "{v}"' in hotfix for v in ("2.2.0", "2.1.0", "2.0.0")),
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"PLANNING_WEEK_BOARD_FOCUS_QA_FAIL {bad} {checks}")
print(f"PLANNING_WEEK_BOARD_FOCUS_QA_PASS {checks}")
