# Chapter 10 Phase 10D / V77 — Source Research & Research Assistant Bridge

## Scope

Source lock remains Michael Shearn, *The Investment Checklist*, Chapter 10 — **Evaluating Growth Opportunities**, Q53-Q57, printed pages 281-303. Phase 10D consumes the 34 evidence dimensions locked in V75 and the read-only canonical data bridge from V76.

The book frames Chapter 10 around whether growth is organic or acquisition-led, management's motivation to grow, whether historical growth has been profitable, the durability/runway of future growth, and whether growth is disciplined or too fast. V77 does not add a new checklist criterion.

## What V77 adds

- A deterministic research plan for all 34 source-locked dimensions.
- Question-level English/Vietnamese search vocabulary derived from the Chapter 10 dimensions.
- Candidate-evidence normalization with stable candidate IDs and source grading.
- Deterministic matching helpers for routing snippets/documents to possible dimensions.
- Research-gap output for dimensions with no candidate evidence.
- Explicit analyst-selection boundary before a candidate can be promoted into Chapter 10 evidence.

## Research hierarchy

Preferred research order is official company filings / investor relations, regulators and exchange disclosures, then independent sources for corroboration/context. Search snippets remain candidates until the analyst verifies the underlying source.

## Analyst ownership

Candidate evidence is not a fact merely because the assistant found it. `promote_selected_candidates()` requires explicit selected candidate IDs. Promotion appends evidence only and does **not** change question status, confidence, analyst assessment, dimension status, growth mode, growth forecast, valuation, MOS, Research Gate, or investment action.

## Boundaries retained

V77 adds no weighted Growth Score, no automatic forecast, no BUY/HOLD/SELL, no duplicate financial SSOT, no CCC recomputation, no Streamlit UI/store, and no change to MOS or the Investment Research Gate.

## Next phase

**Phase 10E — analyst workspace/store/UI and research-promotion workflow.** It should expose the V77 research plan/candidates/gaps inside the Chapter 10 workspace while keeping every qualitative conclusion analyst-owned.
