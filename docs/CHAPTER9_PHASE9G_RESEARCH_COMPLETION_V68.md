# Chapter 9 — Phase 9G / V68
## Research Completion Gate & Source Coverage Closure

### Scope

Phase 9G adds a **research-process closure layer** to Chapter 9 Q48–Q52. It does **not** add a management-quality score, positive/negative character classifier, valuation input, MOS change, investment Research Gate, or BUY/HOLD/SELL signal.

Source lock remains:

- Michael Shearn — *The Investment Checklist* — Chapter 9 — Q48–Q52.
- Exactly 26 Phase 9B source dimensions: Q48=6, Q49=4, Q50=8, Q51=3, Q52=5.
- Chapter 7 manager master is the only Manager ID / role SSOT.
- Q48 and Q52 remain CEO-specific.

### Why Phase 9G exists

The previous phases can collect candidates, promote verified evidence, maintain research gaps, and let the analyst answer Q48–Q52. Phase 9G answers a narrower operational question: **which source dimensions remain unresearched, unverified, unsupported by source lineage, or blocked by missing manager identity?**

The output is a closure/readiness checklist, not an opinion about management.

## Dimension closure logic

Each of the 26 dimensions is classified into one of these process states:

1. **Blocked — manager scope**: Chapter 7 manager master is missing/unusable, or Q48/Q52 does not have an explicit CEO/Tổng Giám đốc.
2. **Closed — verified evidence**: at least one evidence row is explicitly analyst-verified/promoted and has both source URL/file and a usable evidence/reference field.
3. **Review — source lineage incomplete**: evidence is marked verified/promoted but the source/reference trail is incomplete.
4. **Review — evidence verification**: evidence exists but is not explicitly analyst-verified/promoted.
5. **Open — research gap**: a dimension-linked research gap remains open.
6. **Closed — analyst accepted known unknown**: the analyst explicitly closed a documented gap after review. This preserves the absence of evidence instead of fabricating evidence.
7. **Open — no coverage**: no linked verified evidence and no explicitly closed gap exists.

An empty search result never closes a dimension automatically.

## Question completion logic

Q48–Q52 becomes **Ready — research closure complete** only when:

- all source dimensions for that question are Closed;
- no dimension is Open, Blocked, or Review;
- the analyst has set Research Status to `Answered` or `N/A`;
- Analyst Confidence is not `Unknown`;
- Analyst Assessment contains an analyst-written conclusion.

The app never changes those analyst-owned fields automatically.

The chapter-level Research Completion Gate has only three process states:

- **Blocked — research incomplete**;
- **Review — analyst closure required**;
- **Ready — research closure complete**.

These states describe research readiness only. `Ready` does not mean management is high quality and does not imply a Buy decision.

## App-building rules applied in V68

V68 explicitly follows `Nguyen tac xay dung app.docx`:

- **Source fidelity:** Chapter 9 source contract and Chapter 7 manager SSOT are unchanged.
- **External-source discipline:** the existing Phase 9D research stack continues to prioritize official/company documents and reputable evidence sources; Phase 9G does not invent a new source adapter.
- **Formula/logic documentation:** a dedicated V68 formula/logic explanation file is included even though Phase 9G has no financial valuation formula.
- **Cross-module consistency:** no second manager master or duplicated manager identity table is created.
- **Heat / importance display:** Research Completion Gate uses red / amber / emerald status presentation for blocked / review / ready. This color indicates workflow urgency, not management quality.
- **Terminology explanation:** the UI includes definitions for Research Completion Gate, Source Dimension, Source Lineage, Verified Evidence, Known Unknown, and Closure Status.
- **Runtime log:** Phase 9G appends JSONL diagnostic events to `data_cache/logs/deep_company_analysis_chapter9.log`; logging failure never breaks the workspace.
- **Table rendering:** Phase 9G read-only closure tables use `st.html()` with the shared wrapped-cell HTML formatter (`white-space: normal`, `overflow-wrap: anywhere`, `table-layout: fixed`). Editable analyst tables retain the existing data-editor workflow.

Financial display-format rules are not applicable to Phase 9G because this phase contains no financial amounts, percentages, or valuation ratios.

## Analyst boundary

AI/Data may:

- identify uncovered dimensions;
- identify missing source lineage;
- identify open gaps;
- show manager-scope blockers;
- tally closure counts;
- propose a next research action.

Only the analyst may:

- promote/verify evidence;
- close a research gap as a known unknown;
- set Research Status;
- set Confidence;
- write Analyst Assessment;
- interpret management quality;
- make an investment decision.

## Files

- `modules/deep_company_analysis/chapter9_completion.py`
- `modules/deep_company_analysis/chapter9_page_support.py`
- `modules/deep_company_analysis/test_chapter9_phase9g.py`
- `scripts/qa_chapter9_research_completion_v68.py`
- `docs/FORMULA_EXPLANATION_CHAPTER9_PHASE9G_V68.md`
- `.github/workflows/chapter9-phase9g-research-completion-v68.yml`

## Next phase

Phase 9H should integrate Chapter 9 closure/readiness into the consolidated Deep Company Analysis history/report layer and delta review, while preserving the same source and analyst-control boundaries.
