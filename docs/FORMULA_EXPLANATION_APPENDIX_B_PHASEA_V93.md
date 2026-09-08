# Formula Explanation — Appendix B Phase A / V93

## No new financial formulas

Appendix B is qualitative interview guidance. **V93 introduces no new financial formulas, valuation formulas, management scores, weights, or derived investment metrics.** Existing canonical financial/data SSOT remains authoritative.

## Deterministic normalization only

The module performs only non-investment transformations:

- ticker normalization: trim + uppercase;
- source lock reset to the canonical Appendix B label;
- section status allowlist: `Unknown`, `Partial`, `Covered`, `N/A`;
- invalid section states fall back to `Unknown`;
- invalid/non-list session, contextual-check, and research-gap payloads fall back to empty lists;
- face-to-face caveat values are normalized to a non-scoring review-state allowlist.

These transformations do not calculate management quality, credibility, expected returns, intrinsic value, Margin of Safety, or Research Gate state.

## Research completeness warnings

`research_gap_warnings()` only identifies source-locked Appendix B sections that remain `Unknown` or `Partial`. It does not rank the company, management team, or interview outcome and does not mutate any upstream DCA state.

## SSOT policy

V93 references interview/research concepts only. It does not create copies of revenue, earnings, cash flow, balance-sheet, valuation, market-price, MOS, or other canonical financial fields.

## Decision ownership

AI/Data = Research Assistant. Analyst = owner of interpretation and final conclusion.
