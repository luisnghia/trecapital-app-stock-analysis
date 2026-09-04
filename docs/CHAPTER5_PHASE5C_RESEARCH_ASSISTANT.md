# Chapter 5 — Phase 5C Research Assistant

## Source lock

Primary framework: Michael Shearn, *The Investment Checklist*, Chapter 5 — **Measuring the Operating and Financial Health of the Business**.

The six source questions remain unchanged:

- Q21 — What are the fundamentals of the business?
- Q22 — What are the operating metrics of the business that you need to monitor?
- Q23 — What are the key risks the business faces?
- Q24 — How does inflation affect the business?
- Q25 — Is the business's balance sheet strong or weak?
- Q26 — What is the return on invested capital for the business?

Phase 5C does not replace the analyst workspace from Phase 5A or the canonical quantitative bridge from Phase 5B. It adds a source-first research layer.

## Core boundary

**AI / automation = Research Assistant. Analyst = final decision maker.**

Phase 5C may:

- search for candidate evidence and counter-evidence;
- extract evidence candidates from registered first-party/official company pages and annual reports;
- classify source quality and question relevance;
- surface candidate causal language for Q22 that still requires analyst verification;
- identify evidence gaps;
- append candidate rows to the Evidence Matrix and Research Gaps table.

Phase 5C may not:

- overwrite analyst Q21–Q26 fields;
- auto-select the most important fundamental;
- mark an operating KPI critical;
- fabricate reasons for KPI changes;
- set Q23 Frequency or Severity;
- infer risk magnitude from media attention;
- treat missing evidence as low risk;
- auto-set Inflation Resilience;
- auto-set Balance Sheet Strong/Weak;
- fabricate debt maturity, covenant, headroom or off-balance-sheet obligations;
- assume all cash is excess cash;
- auto-label ROIC as high quality or infer a compounder;
- fabricate incremental ROIC when project capital/earnings are unsupported;
- change Research Gate;
- emit BUY/HOLD/SELL.

## Evidence workflow

1. Analyst presses **Nghiên cứu tự động Q21–Q26**.
2. The agent executes focused searches by question group and attempts direct extraction from registered official sources.
3. Search/navigation links alone are never promoted to evidence.
4. Candidate evidence is normalized into Q21–Q26 with source quality, direction and explicitness notes.
5. The UI shows both supporting and contradicting candidates.
6. Research gaps are generated when coverage is missing/thin or when canonical quantitative context still lacks explanatory disclosure.
7. Analyst may press **Lưu Candidate Evidence + Research Gaps**.
8. Saved evidence remains **Candidate — Analyst verify**. No analyst snapshot is created because saving candidates is not analyst confirmation.

## Source hierarchy

- **A — Company/Official disclosure**: company IR, annual report, financial/disclosure/regulatory source.
- **B — Independent financial source**: independent financial-data/news source suitable for cross-checking.
- **C — Secondary/context source**: contextual material only; critical claims should be verified against A/B where possible.

For DGC, the first-party extraction layer reuses the Trecapital registered DGC IR pages and 2025 annual report already used by the Deep Analysis source-first architecture.

## Question-specific research intent

### Q21 — Fundamentals

Search for explicit operational/value drivers such as volume, price, mix, capacity/utilization, unit costs, market share, input costs, customers/orders and margin drivers. A keyword hit is only a **driver candidate**; materiality remains analyst judgement.

### Q22 — Operating metrics

Search for explicitly disclosed operating KPIs and 3–5 year reasons for changes. Causal language is surfaced as a candidate but must be verified in the underlying source. Phase 5C never manufactures causality from correlations in financial data.

### Q23 — Key risks

Search for company disclosures, historical events, peer/historical cases, mitigation and counter-evidence relevant to the current risk universe. No Frequency/Severity is assigned automatically.

### Q24 — Inflation

Search for input-cost inflation, energy/freight/wage costs, price pass-through, pass-through lag, volume/customer impact, replacement-capital burden and debt-rate exposure. Evidence does not automatically imply resilience.

### Q25 — Balance sheet

Search for maturity, fixed/floating rate, secured/unsecured, recourse, covenant/headroom, refinancing, guarantees, leases and other off-balance-sheet commitments. Missing disclosure remains a Research Gap, never a fabricated row.

### Q26 — ROIC and reinvestment

Search for reinvestment projects, capacity expansion, project capital, organic/M&A growth, project-return disclosures and runway/constraints. Canonical ROIC remains the Single Source of Truth from Phase 5B. Incremental ROIC is not inferred unless both invested capital and attributable economics are supportable.

## Audit and persistence

Raw search logs and Phase 5C evidence caches are written below `data_cache/deep_company_analysis_evidence/`.

Candidate evidence persists through the existing Chapter 5 `evidence_matrix`. Suggested gaps persist through `research_gaps_table`. Existing analyst fields and manual rows are preserved.

## Acceptance lock

Phase 5C is accepted only if:

- targeted Phase 5C tests pass;
- full Deep Analysis regression passes;
- DGC source-first diagnostic runs without synthetic evidence;
- Streamlit smoke test passes;
- all Phase 5C guardrail flags are false;
- candidate refresh does not overwrite analyst judgement;
- package build includes source code, tests and this documentation.
