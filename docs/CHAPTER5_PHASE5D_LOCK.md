# Chapter 5 — Phase 5D End-to-End Lock & QA

## Purpose

Phase 5D closes the implementation cycle for Michael Shearn Chapter 5 — **Measuring the Operating and Financial Health of the Business** — after:

- Phase 5A: source-locked analyst workspace;
- Phase 5B: Trecapital canonical quantitative bridge;
- Phase 5C: source-first Research Assistant evidence bridge.

Phase 5D does **not** introduce a new score or automatic investment judgement. It separates two concepts that must never be conflated:

1. **Implementation Lock** — the module architecture/methodology still obeys source questions, Trecapital Single Source of Truth, no-fabrication, and analyst-ownership rules.
2. **Research Readiness** — the current ticker has enough canonical context and candidate evidence for the analyst to continue research.

`Implementation Lock = PASS` is not an investment score, not Research Gate, and not BUY/HOLD/SELL.

## Source-locked question set

The locked Chapter 5 question set is exactly:

- Q21 — What are the fundamentals of the business?
- Q22 — What are the operating metrics of the business that you need to monitor?
- Q23 — What are the key risks the business faces?
- Q24 — How does inflation affect the business?
- Q25 — Is the business's balance sheet strong or weak?
- Q26 — What is the return on invested capital for the business?

The module may add analytical tools beneath those questions but may not replace the questions with a mechanical score.

## Hard Implementation Lock checks

Phase 5D requires all of the following to pass:

- exact Q21–Q26 source-lock remains intact;
- Q23 still maintains the 17 Shearn risk examples as the fresh-record seed while preserving analyst deletion/edit ownership;
- no Confidence field exists anywhere in Chapter 5 payloads;
- all Chapter 5 core auto-conclusion guardrails remain `False`;
- all Phase 5C evidence/no-fabrication guardrails remain `False`;
- if Phase 5B context exists, all quantitative auto-conclusion guardrails remain `False`;
- canonical financial context identifies the Trecapital/canonical pipeline;
- candidate evidence maps only to Q21–Q26;
- Research Assistant merge cannot overwrite analyst-owned question objects/registers;
- missing evidence remains a Research Gap and is never converted to Low Risk/Strong/Good.

## Research Readiness

Readiness is ticker-specific and intentionally separate from the Implementation Lock.

For each Q21–Q26 the panel reports:

- Candidate Evidence count;
- Source A count;
- Counter-Evidence Candidate count;
- canonical quantitative availability where relevant;
- a readiness label.

For Q22/Q25/Q26, missing canonical quantitative context causes a readiness gap but does not make the business weak and does not fail the general methodology architecture.

For Q21/Q23/Q24, canonical quantitative context is not required by the readiness engine because the question is primarily qualitative/operational/risk/inflation research.

## Counter-evidence rule

Counter-evidence is explicitly displayed to reduce confirmation bias. However, Phase 5D never fabricates counter-evidence just to obtain a balanced-looking table.

If no counter-evidence candidate is found, the UI states that absence clearly and reminds the analyst that **no counter-evidence found does not mean safe/good**.

## Cross-question diagnostics

Phase 5D reuses Chapter 5 cross-question diagnostics, including Chapter 4 ↔ Chapter 5 consistency checks, for example:

- Q24 Inflation Resilience vs Chapter 4 Q16 Pricing Power;
- Q26 Reinvestment Runway vs Chapter 4 Q15 moat trend;
- high ROIC with short/no reinvestment runway.

These are review diagnostics only. They never overwrite the analyst's Chapter 4 or Chapter 5 judgement.

## DGC end-to-end acceptance

The DGC lock workflow must confirm:

- DGC canonical data refresh uses the existing Trecapital Module-1 source/normalization/cache pipeline;
- Q22 quantitative context is available;
- Q25 balance-sheet quantitative context is available;
- Q26 canonical/analytical ROIC views are available;
- real source-first Candidate Evidence exists for every Q21–Q26;
- at least one Source A candidate exists;
- no synthetic evidence or parallel financial source is introduced;
- candidate merge preserves all analyst-owned fields;
- all implementation guardrails remain `False`;
- full Deep Analysis regression and Streamlit page smoke test pass.

## UI

Phase 5D adds a panel below Phase 5C:

**🔒 Phase 5D — Chapter 5 End-to-End Lock & QA**

It displays:

- Implementation Lock status;
- number of research-ready questions;
- cross-question diagnostic count;
- wrapped Implementation Lock table;
- wrapped ticker Research Readiness table;
- explicit counter-evidence absence warning;
- lock semantics and guardrails.

New Phase 5D tables use `st.html()` with wrapping (`white-space: normal`, `overflow-wrap: anywhere`, `table-layout: fixed`) to prevent long text from spilling outside cells.

## Change-control rule after lock

After Phase 5D is accepted, Chapter 5 is **methodology-locked**. Future Chapter 5 changes are allowed for bug fixes, data-source compatibility, UI quality, or explicitly approved methodology changes, but every change must rerun:

- Chapter 5 regression;
- full Deep Analysis regression;
- DGC source-first/canonical E2E lock diagnostic;
- Streamlit smoke test.

No merge to `main` is implied by this lock.
