from pathlib import Path

path = Path("modules/deep_company_analysis/chapter4_lock.py")
text = path.read_text(encoding="utf-8")
old = '''    q16_has_corroboration = isinstance(result.pricing_corroboration, pd.DataFrame) and not result.pricing_corroboration.empty
    covered_ab = int(coverage["Candidates"].fillna(0).astype(int).gt(0).sum()) if not coverage.empty else 0
    gaps = [
        f"Q19 — {row['Q19 logic']}: chưa có evidence A/B đủ điều kiện; giữ Research Gap."
        for _, row in coverage.iterrows() if int(row.get("Candidates") or 0) == 0
    ]
    # Missing failure evidence is acceptable for module lock only when it stays explicit; fabrication would fail.
    failure_gap_visible = bool(len(failures) > 0 or any("Why Competitors Failed" in gap for gap in gaps))
'''
new = '''    corroboration = result.pricing_corroboration if isinstance(result.pricing_corroboration, pd.DataFrame) else pd.DataFrame()
    if not corroboration.empty and "Corroboration status" in corroboration.columns:
        q16_confirmed_corroboration = bool(
            corroboration["Corroboration status"].fillna("").astype(str).str.startswith("Period-level corroboration candidate").any()
        )
    else:
        q16_confirmed_corroboration = False
    covered_ab = int(coverage["Candidates"].fillna(0).astype(int).gt(0).sum()) if not coverage.empty else 0
    gaps = [
        f"Q19 — {row['Q19 logic']}: chưa có evidence A/B đủ điều kiện; giữ Research Gap."
        for _, row in coverage.iterrows() if int(row.get("Candidates") or 0) == 0
    ]
    if not q16_confirmed_corroboration:
        gaps.insert(0, "Q16 — chưa có period-level multi-source corroboration đủ điều kiện; giữ Research Gap và không kết luận Pricing Power.")
    q16_gap_visible = bool(q16_confirmed_corroboration or any(gap.startswith("Q16") for gap in gaps))
    # Missing failure evidence is acceptable for module lock only when it stays explicit; fabrication would fail.
    failure_gap_visible = bool(len(failures) > 0 or any("Why Competitors Failed" in gap for gap in gaps))
'''
if old not in text:
    if "q16_confirmed_corroboration" in text:
        print("Q16 gap semantics already hardened")
        raise SystemExit(0)
    raise SystemExit("Target Q16 block not found")
text = text.replace(old, new, 1)
old_check = '''        ("Q16 has multi-source corroboration candidate", q16_has_corroboration, f"rows={len(result.pricing_corroboration)}"),
'''
new_check = '''        ("Q16 corroboration is confirmed or explicit Research Gap", q16_gap_visible, f"confirmed={q16_confirmed_corroboration}; rows={len(corroboration)}"),
'''
if old_check not in text:
    raise SystemExit("Target Q16 check row not found")
text = text.replace(old_check, new_check, 1)
path.write_text(text, encoding="utf-8")
print("Phase 4D Q16 corroboration/gap semantics hardened")
