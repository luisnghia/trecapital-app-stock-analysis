from __future__ import annotations

"""Remove two non-fatal runtime warnings found by the V49 live DGC Ch1–Ch8 acceptance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CH5 = ROOT / "modules" / "deep_company_analysis" / "chapter5_quant.py"
CH7 = ROOT / "modules" / "deep_company_analysis" / "chapter7_closure.py"


def patch_chapter5_copy_warning() -> bool:
    text = CH5.read_text(encoding="utf-8")
    old = '        work = work[~work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]\n'
    new = '        work = work[~work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)].copy()\n'
    if new in text:
        print("Chapter 5 SettingWithCopy cleanup already applied.")
        return False
    if old not in text:
        raise SystemExit("Chapter 5 expected period-filter line not found; refusing blind patch.")
    CH5.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Patched Chapter 5 period filter with explicit .copy().")
    return True


def patch_chapter7_mixed_value_column() -> bool:
    text = CH7.read_text(encoding="utf-8")
    replacements = {
        '{"Metric": "Known role episodes", "Value": len(rows), "Boundary": "Source chronology"}':
            '{"Metric": "Known role episodes", "Value": str(len(rows)), "Boundary": "Source chronology"}',
        '{"Metric": "Functional categories observed", "Value": len(functions), "Boundary": "Research cue only"}':
            '{"Metric": "Functional categories observed", "Value": str(len(functions)), "Boundary": "Research cue only"}',
        '{"Metric": "Potential career gaps", "Value": potential_gaps, "Boundary": "Potential gap ≠ unemployment/problem"}':
            '{"Metric": "Potential career gaps", "Value": str(potential_gaps), "Boundary": "Potential gap ≠ unemployment/problem"}',
        '{"Metric": "Unresolved career gaps", "Value": unresolved_gaps, "Boundary": "Unknown if source does not explain"}':
            '{"Metric": "Unresolved career gaps", "Value": str(unresolved_gaps), "Boundary": "Unknown if source does not explain"}',
    }
    changed = False
    for old, new in replacements.items():
        if new in text:
            continue
        if old not in text:
            raise SystemExit(f"Chapter 7 expected audit row not found: {old}")
        text = text.replace(old, new, 1)
        changed = True
    if changed:
        CH7.write_text(text, encoding="utf-8")
        print("Patched Chapter 7 career audit Value column to a homogeneous display type.")
    else:
        print("Chapter 7 mixed Value-column cleanup already applied.")
    return changed


def main() -> None:
    patch_chapter5_copy_warning()
    patch_chapter7_mixed_value_column()


if __name__ == "__main__":
    main()
