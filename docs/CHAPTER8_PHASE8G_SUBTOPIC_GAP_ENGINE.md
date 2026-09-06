# Chapter 8 Phase 8G — Dimension/Subtopic Gap Engine V52

## Purpose

V52 fixes a research-completeness weakness exposed by the DGC live acceptance: a large number of A-quality candidates can still be concentrated in a single subtopic. Candidate volume therefore must not be treated as complete Chapter 8 evidence coverage.

The V52 engine audits each Q39–Q47 against question-specific research dimensions and persists missing dimensions through the existing Chapter 8 Research Gap schema. It does not create a new storage stack and does not write analyst conclusions.

## Source locks

- **Chapter 7 manager master** remains the single source of truth for manager identity/background. Chapter 8 never creates replacement Manager IDs.
- **Trecapital canonical financial data / Module 1** remains the financial single source of truth.
- **Q43** uses all **14** Shearn employee-relation prompts exactly as locked in `chapter8.EMPLOYEE_RELATION_DIMENSIONS`.
- **Q46** uses exactly the **five** Shearn capital-allocation actions in `chapter8.CAPITAL_ALLOCATION_ACTIONS`. `Discipline / hurdle evidence` is tracked as context only and is never a sixth action.
- **Q47** requires explicit buyback authorization/execution/price/context evidence. Share-count decline is context only and never proves a buyback.
- No management score, MOS change, Research Gate change or BUY/HOLD/SELL signal is produced.

## Coverage behavior

`build_dimension_coverage()` scans research-candidate title, subtopic and extracted evidence text for question-specific evidence terms. A dimension is only marked `Candidate coverage — analyst verify` when at least one A-quality company/exchange/regulator candidate is present. Secondary-only evidence remains a source-quality gap.

`build_question_coverage_summary()` reports counts only:

- Dimensions Required
- Dimensions Covered
- Dimensions Open
- Whether manager scope is required
- Manager-scoped candidate count

It intentionally does **not** calculate a percentage or score.

`enhanced_research_gaps()` keeps the existing Chapter 8 Research Gap schema and adds:

- evidence gaps,
- source-quality gaps,
- dimension/subtopic gaps,
- manager identity gaps, and
- manager-scoped evidence gaps when Chapter 7 identities exist but the research candidates are not tied to them.

## Why this matters for DGC

V51 found 130 Chapter 8 candidates, but examples of concentration were visible: Q43 candidates were heavily concentrated in recruitment-related evidence and Q46 candidates in dividend-related evidence. V52 therefore keeps the missing Shearn dimensions open even when total candidate count is high.

This is a research-control improvement, not a negative management conclusion. `Unknown` and `Open` remain valid until the analyst verifies/promotes evidence and enters a judgment.

## Production wiring

The existing Chapter 8 Streamlit workspace now imports `Chapter8ResearchAgent` from `chapter8_research_v52`. The wrapper reuses Phase 8C search/extraction unchanged, then replaces the coarse research-gap output with the V52 dimension-level audit. Existing save/snapshot/evidence-promotion architecture is unchanged.
