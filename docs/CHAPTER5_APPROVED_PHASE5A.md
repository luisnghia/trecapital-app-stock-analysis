# Chapter 5 — APPROVED Phase 5A Source-Locked Core

Status: **APPROVED by analyst/user on 2026-09-04**.

Source framework: Michael Shearn, *The Investment Checklist*, Chapter 5 — **Measuring the Operating and Financial Health of the Business**.

Questions:

- Q21 — What are the fundamentals of the business?
- Q22 — What are the operating metrics of the business that you need to monitor?
- Q23 — What are the key risks the business faces?
- Q24 — How does inflation affect the business?
- Q25 — Is the business's balance sheet strong or weak?
- Q26 — What is the return on invested capital for the business?

## User-approved amendments

1. **No Confidence field in Chapter 5.** Confidence was intentionally removed from Q21–Q26, child tables, persistence payload and UI because it adds complexity without enough value for this workflow.
2. **Q23 starts with Shearn's operational-risk examples.** The analyst may add unlimited additional risks. Shearn defaults retain `Origin = Shearn`; additional risks default to `Origin = Analyst-defined`.

## Q23 default Shearn risk universe

The following are the operational-risk examples Shearn explicitly lists in Chapter 5:

1. Overcapacity
2. Commoditization
3. Deregulation
4. Increased power among suppliers
5. Shifts in technology
6. Changes in laws and regulations
7. Product obsolescence
8. Patent expirations
9. Development of new product lines where the business has limited expertise
10. The emergence of competitors
11. Brand erosion
12. Overreliance on too few customers
13. Limited geographic distribution
14. Research and development failure
15. Business-development failure
16. Merger or acquisition failure
17. A weak product pipeline

These are **examples to investigate**, not assertions that every risk applies to every business. Every default begins with `Applicability = Review`, `Frequency = Unknown`, and `Severity = Unknown`.

## Phase 5A architecture

### Q21 — Fundamental Driver Map

- Fundamental Driver
- Why It Creates Value
- Economic Linkage
- Measure / KPI
- Current Assessment
- Trend
- Leading / Lagging
- Supporting Evidence
- Counter-Evidence
- Deterioration Test
- Analyst Conclusion

### Q22 — Operating Metric Monitor

- Operating Metric Registry
- 3–5 year Metric Driver History
- Temporary vs Structural assessment
- Metric-definition compatibility note for peer comparisons

Phase 5A does not yet auto-populate canonical metrics; that belongs to Phase 5B.

### Q23 — Risk Underwriter Register

Every risk supports:

- Applicability
- Exposure Mechanism
- Frequency
- Severity
- Historical Company Evidence
- Peer / Historical Case
- Financial Consequence
- Mitigation
- Mitigation Evidence
- Early Warning Indicator
- Review Trigger
- Counter-Evidence
- Trend
- Analyst Assessment
- Evidence

Risk logic follows Shearn's insurance-underwriter framing: **Frequency + Severity + historical evidence**. Media attention is not a risk rating. Missing data is not low risk.

### Q24 — Inflation Resilience Map

Four mechanisms are kept separate:

- Pricing pass-through
- Cost flexibility
- Capital replacement burden
- Debt / interest exposure

Overall inflation resilience remains analyst-owned.

### Q25 — Balance Sheet Resilience workspace

Phase 5A stores:

- debt purpose/motivation;
- debt instrument/facility register;
- fixed/floating rate;
- maturity;
- secured/recourse structure;
- hidden/off-balance-sheet obligations;
- covenants;
- liquidity/refinancing/financial-flexibility analyst assessment.

Canonical leverage, interest coverage and stress testing belong to Phase 5B.

### Q26 — ROIC Quality & Reinvestment skeleton

The workspace explicitly separates:

- **Trecapital Canonical ROIC** — Single Source of Truth;
- Shearn analytical variants: with cash, ex excess cash, including goodwill, ex goodwill, gross-asset adjusted, off-balance-sheet adjusted;
- ROIC adjustment register;
- reinvestment/incremental ROIC register.

Phase 5A never selects the best ROIC methodology automatically.

## Persistence

Database: `data_cache/deep_company_analysis_chapter5.db`

Tables:

- `chapter5_current`
- `chapter5_fundamentals`
- `chapter5_metric_registry`
- `chapter5_metric_history`
- `chapter5_risks`
- `chapter5_inflation_exposures`
- `chapter5_debt_instruments`
- `chapter5_off_balance_obligations`
- `chapter5_covenants`
- `chapter5_roic_variants`
- `chapter5_roic_adjustments`
- `chapter5_reinvestment`
- `chapter5_evidence`
- `chapter5_research_gaps`
- `chapter5_snapshots`

SQLite stores analyst workspace, evidence and snapshots. Financial source-of-truth remains the canonical Trecapital Data Layer.

## Immutable analyst boundary

Data/AI must not automatically set:

- fundamental conclusion;
- critical operating metric;
- risk level;
- inflation resilience;
- balance-sheet strength;
- ROIC quality;
- reinvestment quality/runway;
- Research Gate;
- BUY/HOLD/SELL.

## Phase 5A acceptance rules

- Q21–Q26 all exist.
- No key/column named Confidence anywhere in Chapter 5 payload.
- All 17 Shearn Q23 risks exist by default.
- Analyst-defined risks can be appended and persist.
- Shearn risk `Origin` cannot be silently changed.
- A catastrophic risk with unknown frequency is surfaced as a Research Gap/consistency warning rather than treated as low risk.
- High current ROIC plus no reinvestment runway does not become an automatic compounder conclusion.
- Canonical ROIC is separated from Shearn analytical variants.
- Save/load/snapshot persistence works.
- Research Assistant guardrails remain disabled.

## Next phase after Phase 5A acceptance

**Phase 5B — Quantitative Bridge**: canonical 10Y operating/financial history, debt/liquidity/coverage, ROIC variants and distortion diagnostics, reinvestment quantitative bridge, plus dedicated formula documentation.
