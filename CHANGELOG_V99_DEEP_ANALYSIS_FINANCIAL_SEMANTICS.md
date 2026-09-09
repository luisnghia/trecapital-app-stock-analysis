# V99 — Deep Company Analysis Financial Semantics & TTM Provenance

## Added
- Explicit canonical fields for consolidated PAT and parent-attributable PAT.
- `net_profit_scope`, `period_display`, `ttm_end_period`, and comparability metadata.
- Read-only DCA semantic/provenance helper and Chapter 6 display panel.
- V99 deterministic tests and machine-readable acceptance QA.
- Dedicated GitHub Actions workflow and offline artifact.

## Fixed
- FireAnt income line 19 and line 21 are no longer collapsed into one generic PAT field.
- EPS is no longer derived from an explicitly consolidated-only PAT.
- EPS-based valuation fallback is blocked when only consolidated PAT is explicit; valuation formulas themselves are unchanged.
- TTM flow values are no longer created from incomplete 1–3 quarter sums.
- Visible TTM periods identify their ending quarter when known, e.g. `TTM đến Q2/2026`.

## Boundaries retained
- No overall score.
- No BUY/HOLD/SELL.
- No automatic analyst assessment.
- No new valuation/MOS formula.
- No second financial SSOT.
- AI remains Research Assistant; analyst remains conclusion owner.
