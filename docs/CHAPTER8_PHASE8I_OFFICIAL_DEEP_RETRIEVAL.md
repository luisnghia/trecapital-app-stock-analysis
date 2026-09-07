# Chapter 8 Phase 8I — Official Document Deep Retrieval V54

## Objective

Phase 8H correctly converted open Chapter 8 dimensions into targeted web searches, but a live DGC run still left 42 source-locked dimensions open because search snippets did not expose enough usable evidence. Phase 8I does **not** relax the evidence standard. It goes deeper into registered company/IR domains and mines original report/disclosure text instead.

## Retrieval flow

1. Run the existing Phase 8C → 8H research pipeline.
2. Recalculate the Chapter 8 dimension coverage matrix.
3. Select only dimensions that are both **source-locked** and still open.
4. Follow registered company/IR roots through a bounded same-domain crawl (depth <= 2 by default).
5. Prioritize annual reports, governance reports, sustainability/ESG reports, AGM materials, resolutions, disclosures, IR pages, human-resource material, capital-allocation disclosures and explicit buyback documents.
6. Open relevant HTML/PDF text and extract windows that explicitly match the planned dimension terms.
7. Merge new rows as `Candidate — analyst verify`; no evidence is promoted automatically.
8. Recompute coverage and research gaps without touching analyst assessment/status/confidence.

## Hard boundaries

- Chapter 7 manager master remains the management identity/background SSOT.
- Trecapital canonical data / Module 1 remains the financial SSOT.
- Manager IDs can only be matched from Chapter 7 names already present in the source text.
- Q43 remains exactly the fourteen Shearn employee-relation prompts.
- Q46 remains exactly the five Shearn capital-allocation actions. `Discipline / hurdle evidence` is context-only and is never a sixth action.
- Q47 requires explicit buyback/repurchase language. A decline in shares outstanding alone is not buyback evidence.
- Missing official evidence remains `Unknown` / an open Research Gap.
- V54 produces no management score, automatic competence conclusion, MOS/Research Gate change, or BUY/HOLD/SELL signal.

## Production integration

`chapter8_page_support.py` continues importing `chapter8_research_v52`, the compatibility module. On the V54 branch that compatibility module re-exports `chapter8_research_v54`, so there is no parallel Streamlit page state or second database.

## Acceptance philosophy

CI uses a live DGC run to verify the canonical financial bridge, bounded official retrieval, source-locks, analyst boundary, and production health. The public website is allowed to change; therefore CI does not require a fixed count of newly closed gaps. A run that finds no qualifying official text must leave those dimensions open rather than manufacture evidence.
