# Formula / SSOT Explanation — Chapter 11 Phase 11D / V85

V85 is a research-routing layer, not a financial-calculation engine.

## No new formulas

The Research Assistant does **not** calculate or recalculate acquisition valuation, leverage, dilution, customer retention, employee retention, synergy realization, or post-deal returns. It only attaches candidate research evidence to the 15 source-locked Chapter 11 dimensions.

The following terms remain canonical SSOT dependencies from V84/upstream data and are **not calculated by V85**: revenue, segment revenue, operating expenses, operating margin, debt, interest expense, customer retention, employee count/turnover, acquisition consideration, EBIT, EBITDA, free cash flow, book value, cash, debt coverage, equity issuance and shares outstanding.

In particular V85 does not calculate:

- EV / EBIT
- EV / EBITDA
- EV / FCF
- acquisition premium to book value
- acquisition leverage or debt-coverage ratios
- equity dilution
- implied synergy-adjusted acquisition multiples
- forecast synergy realization

If these values exist in canonical SSOT, later UI/workspace code may display/read them. If they are absent, the related research dimension remains Unknown or an open research gap; V85 does not manufacture a replacement value.

## Deterministic Research Assistant mechanics

`research_plan()` produces one plan row per source-locked dimension. `candidate_id()` hashes the dimension ID plus source URL/file, source title and evidence text to create a stable candidate identity. `build_candidates()` deduplicates candidates by that identity. `research_gaps()` reports dimensions for which no candidate is currently present.

`promote_selected_candidates()` is the authorization boundary: only Candidate IDs explicitly selected by the analyst/UI are appended to workspace evidence. Promotion does not change question status, confidence, analyst assessment or dimension status.

## Investment boundary

No M&A score, weighted score, automatic acquisition-success conclusion, synergy forecast, BUY/HOLD/SELL, intrinsic-value/MOS change, or Investment Research Gate change is permitted in V85.
