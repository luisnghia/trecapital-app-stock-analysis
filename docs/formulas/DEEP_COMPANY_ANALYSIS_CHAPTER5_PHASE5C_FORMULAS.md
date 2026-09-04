# Chapter 5 Phase 5C — Formula & Evidence Boundary

## Scope

Phase 5C introduces **no new financial formula** and does not replace any canonical metric from the Trecapital Data Layer.

All financial calculations displayed in Chapter 5 remain owned by Phase 5B / canonical Trecapital logic and are documented in `DEEP_COMPANY_ANALYSIS_CHAPTER5_FORMULAS.md`.

## Phase 5C operations

Phase 5C performs only evidence operations:

1. keyword/topic matching to map source excerpts to Q21–Q26;
2. source-quality classification (A/B/C);
3. candidate direction tagging (Supporting / Contradicting / Neutral);
4. evidence coverage counts by question;
5. Research Gap generation when evidence coverage is absent/thin.

None of those operations is an investment score or valuation formula.

## Coverage counts

For each question `q`:

`CandidateCount(q) = number of unique candidate evidence rows mapped to q`

`SourceA(q) = number of candidate rows whose source class is A — Company/Official disclosure`

`Supporting(q) = number of candidate rows tagged Supporting — Candidate`

`Counter(q) = number of candidate rows tagged Contradicting — Candidate`

These counts measure **research coverage only**. They must never be used as a proxy for business quality, risk severity, conviction, moat strength or investment attractiveness.

## Source-class mapping

- A: company/IR, annual report, official disclosure/regulatory source.
- B: independent financial source used for cross-checking.
- C: secondary/context source.

Source class is an evidence-quality aid, not a truth score. An analyst still verifies the underlying source and claim.

## Candidate Direction

Direction is a conservative text tag used to display potentially supporting and potentially contradicting facts together. It is not a probability, score, analyst conclusion or automated assessment.

## Q22 causal-language boundary

When source text contains causal language such as `due to`, `driven by`, `because`, `nguyên nhân`, `chủ yếu do`, Phase 5C may tag the row:

`Metric + reason-of-change language candidate — verify explicit causality in source`

The app does **not** calculate or infer causality from revenue, margin, price or volume correlations.

## Q25 strict disclosure boundary

No formula is used to invent maturity, covenant, recourse or off-balance-sheet exposure. If explicit disclosure cannot be found, the result remains a Research Gap.

## Q26 incremental-ROIC boundary

Phase 5C does not compute incremental ROIC from research snippets. A project-return candidate must be supported by sufficiently explicit invested capital and attributable earnings/return information before any analyst calculation is appropriate.

Canonical ROIC remains the Single Source of Truth. Shearn analytical variants remain clearly labelled analytical views and are not recalculated by Phase 5C.

## Hard guardrails

Phase 5C has no numerical threshold that automatically sets:

- Q21 Strong/Deteriorating;
- Q22 Critical KPI;
- Q23 Frequency/Severity;
- Q24 Inflation Resilience;
- Q25 Strong/Weak Balance Sheet;
- Q26 High-quality ROIC/Compounder;
- Research Gate;
- BUY/HOLD/SELL.
