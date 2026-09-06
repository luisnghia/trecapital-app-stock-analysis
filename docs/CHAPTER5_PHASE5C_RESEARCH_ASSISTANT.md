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
- append candidate rows to the Evidence Matrix and Research Gaps table;
- maintain a source registry and a retrieval-attempt audit trail, including failed official documents.

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
2. For a ticker with a registered first-party domain, the first search query for each focus is constrained to that company/IR domain. One broad query is retained to find independent/counter-evidence.
3. The agent attempts direct extraction from registered official HTML/PDF sources.
4. Search/navigation links alone are never promoted to evidence.
5. Candidate evidence is normalized into Q21–Q26 with source quality, direction and explicitness notes.
6. Known company-domain and regulatory-domain search snippets receive correct **Source A provenance**, but remain **Candidate — Analyst verify**.
7. Candidate display order is question first and then source grade A → B → C. Ordering does not create a score or conclusion.
8. Research gaps are generated when coverage is missing/thin or when canonical quantitative context still lacks explanatory disclosure.
9. Analyst may press **Lưu Candidate Evidence + Research Gaps**.
10. Saved evidence remains **Candidate — Analyst verify**. No analyst snapshot is created because saving candidates is not analyst confirmation.

## Source hierarchy

- **A — Company/Official disclosure**: company IR, annual report, financial/disclosure/regulatory source.
- **B — Independent financial source**: independent financial-data/news source suitable for cross-checking.
- **C — Secondary/context source**: contextual material only; critical claims should be verified against A/B where possible.

For DGC, the first-party extraction layer reuses the Trecapital registered DGC IR pages and annual-report/shareholder-meeting disclosures already used by the Deep Analysis source-first architecture.

### Registered-source management

Phase 5C builds a deduplicated source catalog for the active ticker from:

1. Chapter-2/Chapter-5 registered official HTML pages;
2. Chapter-2/Chapter-5 registered official PDFs;
3. the Trecapital `KNOWN_COMPANY_DOMAINS` company/IR registry.

The catalog records source kind, label, URL, domain, source grade and registry origin. It is research metadata only; presence in the registry does not mean a document was successfully retrieved or that its contents support a conclusion.

When no company domain is registered, Phase 5C does **not** invent one. It falls back to broad research and leaves official-source coverage as a gap until a valid source is registered or discovered and verified.

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

## Retrieval / download audit

Every Phase-5C run now retains a structured `attempts` trail inside `source_audit` and the persisted Chapter-5 cache. Each attempt records, where available:

- channel: focused web search or direct official retrieval;
- question focus;
- source kind and label;
- URL/path and domain;
- success/failure state;
- HTTP/retrieval status;
- number of extracted/search rows;
- error or reason when retrieval produced no usable document/evidence.

Official PDF/HTML failures are **never silently dropped**. They remain in `failed_sources` even when other fallback sources succeed. A search-engine block is also recorded separately from direct-official retrieval so the analyst can distinguish “search failed” from “official document failed”.

A successfully downloaded document that yields zero Q21–Q26 topic rows is logged as **retrieved successfully / zero extracted rows**, rather than being mislabeled as a network failure. Conversely, an official PDF that returns no extractable text is a failed retrieval attempt and remains visible in the audit.

These failures are research-completeness information only. They do not imply low risk, weak fundamentals, poor management or any investment conclusion.

## Audit and persistence

Raw search logs and Phase 5C evidence caches are written below `data_cache/deep_company_analysis_evidence/`.

The final Phase-5C cache stores:

- registered source catalog;
- focused-search summaries;
- direct official retrieval attempts;
- normalized `attempts`;
- `failed_sources`;
- attempt summary counts;
- evidence coverage by Q21–Q26;
- candidate evidence rows.

Candidate evidence persists through the existing Chapter 5 `evidence_matrix`. Suggested gaps persist through `research_gaps_table`. Existing analyst fields and manual rows are preserved.

## Acceptance lock

Phase 5C is accepted only if:

- targeted Phase 5C tests pass;
- source-audit tests confirm first-party search priority and failed-document preservation;
- full Deep Analysis regression passes;
- DGC source-first diagnostic runs without synthetic evidence;
- Streamlit smoke test passes;
- all Phase 5C guardrail flags are false;
- candidate refresh does not overwrite analyst judgement;
- package build includes source code, tests and this documentation.
