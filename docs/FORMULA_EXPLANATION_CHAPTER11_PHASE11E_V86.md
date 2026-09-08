# Formula / Logic Explanation — Chapter 11 Phase 11E V86

V86 introduces no new financial formula and no M&A scoring formula.

## Persistence logic

The durable record is the normalized Chapter 11 analyst payload:

`stored_payload = chapter11.normalize_payload(analyst_payload)`

This intentionally drops any field outside the Chapter 11 contract. Therefore canonical financial fields and derived valuation metrics are not copied into the Chapter 11 database.

## Research status summary

The store exposes only a descriptive completion summary:

`Answered count / 2 | Partial count | Unknown count | N/A count`

This is a research-completeness descriptor only. It is not an M&A quality rating and carries no weight.

## Candidate promotion

A candidate enters durable evidence only when its stable Candidate ID is explicitly selected by the analyst. Re-promoting the same Candidate ID is idempotent and does not create duplicates.

Promotion does not mutate Question Status, Confidence, Analyst Assessment or Dimension Status.

## Explicit non-formulas

V86 does **not calculate** EV/EBIT, EV/EBITDA, EV/FCF, book-value premium, leverage, debt coverage, dilution, synergy value, acquisition ROI or any weighted M&A score. Where these values are needed by Chapter 11 research, they remain upstream canonical SSOT dependencies established in prior phases.
