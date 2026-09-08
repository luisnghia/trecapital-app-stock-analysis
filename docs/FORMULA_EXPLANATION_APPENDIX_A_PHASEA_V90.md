# Formula Explanation — Appendix A Phase A / V90

Appendix A introduces **no new financial formulas** and no investment score.

## Deterministic logic added

The V90 contract performs only normalization and research-completeness operations:

- Source class normalization: `Primary | Secondary | Unknown`.
- Section coverage normalization: `Unknown | Partial | Covered | N/A`.
- Unknown-first initialization for all four Appendix A sections.
- Research-gap warnings are generated only when a section is `Unknown` or `Partial`.
- Interview source-response text and analyst commentary are separate fields.

These operations do not assign source credibility, investment attractiveness, valuation, margin of safety, expected return, acquisition quality, management quality, or any weighted score.

## SSOT boundary

V90 does not import or recreate revenue, earnings, cash flow, balance-sheet, valuation, market-price or company-master calculations. Existing Deep Company Analysis/canonical data remains the single source of truth for company and financial data.

## Investment boundary

No function in V90 is permitted to:

- emit BUY/HOLD/SELL;
- alter intrinsic value or MOS;
- alter the Investment Research Gate;
- automatically accept/reject a human source;
- convert source passion, availability, tenure, friendliness or referral count into a numeric credibility score;
- infer analyst conclusions from interview notes.

The analyst remains the owner of all conclusions. AI/Data is limited to Research Assistant behavior and deterministic organization of evidence.
