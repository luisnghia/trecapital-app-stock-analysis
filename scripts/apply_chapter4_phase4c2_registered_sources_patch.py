from __future__ import annotations

"""Idempotently wire registered direct Q16/Q19 sources into Phase 4C.2."""

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter4_evidence_c2.py")
text = PATH.read_text(encoding="utf-8")

import_block = '''from modules.deep_company_analysis.chapter4_c2_registered_sources import (
    fetch_registered_pricing_raw,
    fetch_registered_q19_raw,
)
'''
marker = '''from modules.deep_company_analysis.chapter4_evidence import (
    OFFICIAL_EVIDENCE_STATUS_PREFIX,
    _clean_lines,
    _context,
    _norm,
    _source_quality,
)
'''
if import_block not in text:
    if marker not in text:
        raise SystemExit("chapter4_evidence import marker not found")
    text = text.replace(marker, marker + import_block, 1)

old_pricing = '''        raw = pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame()
        candidates = _pricing_candidate_rows(raw)
        return candidates, {"queries": queries, "search": search_audit, "official": official_audit}
'''
new_pricing = '''        registered_df, registered_audit = fetch_registered_pricing_raw(self.raw_dir, safe)
        if not registered_df.empty:
            raw_frames.append(registered_df)

        raw = pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame()
        candidates = _pricing_candidate_rows(raw)
        return candidates, {
            "queries": queries,
            "search": search_audit,
            "official": official_audit,
            "registered": registered_audit,
        }
'''
if old_pricing in text:
    text = text.replace(old_pricing, new_pricing, 1)
elif new_pricing not in text:
    raise SystemExit("Pricing integration marker not found")

old_q19 = '''        raw, audit = _search_rows(
            self.raw_dir, queries, max_results_per_query=3, source_method="Q19 competitor targeted search snippet"
        )
        candidates = _q19_candidate_rows(raw)
        return universe, candidates, {"queries": queries, "search": audit}
'''
new_q19 = '''        raw, audit = _search_rows(
            self.raw_dir, queries, max_results_per_query=3, source_method="Q19 competitor targeted search snippet"
        )
        registered_df, registered_audit = fetch_registered_q19_raw(self.raw_dir, safe)
        if not registered_df.empty:
            raw = pd.concat([raw, registered_df], ignore_index=True, sort=False) if not raw.empty else registered_df
            raw = raw.drop_duplicates(subset=["Nguồn/URL", "Trích yếu"], keep="first").reset_index(drop=True)
        candidates = _q19_candidate_rows(raw)
        return universe, candidates, {"queries": queries, "search": audit, "registered": registered_audit}
'''
if old_q19 in text:
    text = text.replace(old_q19, new_q19, 1)
elif new_q19 not in text:
    raise SystemExit("Q19 integration marker not found")

PATH.write_text(text, encoding="utf-8")
print("Phase 4C.2 registered-source patch applied")
