# Chapter 9 Phase 9I — Cross-Chapter Management Synthesis Handoff V70

## Purpose

Phase 9I creates a **read-only management research handoff** across Chapters 7–9 of the Deep Company Analysis workflow:

- **Chapter 7 — Q33–Q38:** management background, classification, career, compensation/ownership and insider context.
- **Chapter 8 — Q39–Q47:** how management operates the business.
- **Chapter 9 — Q48–Q52:** positive/negative management-trait research.

The phase does **not** create a Management Quality Score and does not write a final management synthesis for the analyst.

## Source / ownership lock

1. Chapter 7 remains the only **manager identity/role SSOT**: `Chapter 7 manager master`.
2. Chapter 8 and Chapter 9 may reference Chapter 7 Manager IDs but cannot create a replacement manager master.
3. Q33–Q52 Research Status / Confidence / Analyst Assessment or Conclusion are copied from their owning chapter and are never rewritten by Phase 9I.
4. `Unknown` is a valid research state and is never treated as a negative trait.
5. Chapter 9 retains the exact V63 contract of **26 source dimensions**: Q48=6, Q49=4, Q50=8, Q51=3, Q52=5.

## Backend

`modules/deep_company_analysis/chapter9_synthesis.py`

The module is pure/descriptive and provides:

- `build_manager_roster()` — Chapter 7-only manager reference.
- `build_question_ledger()` — Q33–Q52 analyst-owned research ledger in source order.
- `build_evidence_ledger()` — cross-chapter evidence lineage.
- `build_gap_ledger()` — cross-chapter research gap audit trail/open-gap view.
- `build_lineage_warnings()` — identifies Manager IDs referenced by evidence/gaps but absent from Chapter 7; it does not invent/fix IDs.
- `build_chapter_readiness()` — research/closure readiness for Chapters 7, 8 and 9.
- `build_management_handoff()` — immutable derived handoff package.

## Handoff readiness semantics

`ready_for_analyst_synthesis` is **research workflow metadata only**.

- Chapter 7 must have source closure ready **and analyst confirmation**.
- Chapter 8 must pass its Chapter 8 Research Completion Gate.
- Chapter 9 must have a `Ready — research closure complete` Phase 9G gate.
- Any unreconciled nonblank Manager ID not present in Chapter 7 blocks the handoff until identity is corrected in Chapter 7.

A Ready handoff means only: **the research package is sufficiently closed to hand to the analyst for synthesis**. It does not mean management is good, bad, investable, or non-investable.

## Consolidated report integration

`pages/04_Bao_cao_tong_hop.py` now includes:

### 🧩 Management Synthesis Handoff — Chapters 7–9

It displays:

- total Q33–Q52 questions;
- manager count from Chapter 7 SSOT;
- cross-chapter evidence count;
- open research gaps;
- manager-lineage warnings;
- per-chapter closure/readiness;
- Chapter 7 manager roster;
- Q33–Q52 analyst-owned question ledger;
- open gap ledger;
- evidence lineage and full gap audit trail in expanders.

Long read-only tables continue the current app rule using `static_table_html()` wrapped in `st.html()`.

## No new persistence / no duplicate manager master

Phase 9I adds **no new SQLite database, store or manager table**. The handoff is computed from the existing analyst-owned Chapter 7, 8 and 9 workspaces. This avoids a fourth copy of management identity/conclusions and preserves the chapter ownership boundaries.

## Explicit non-goals

Phase 9I does not:

- generate an analyst synthesis;
- calculate a Management Quality Score or weighted score;
- automatically classify Lion/Hyena or management character;
- treat evidence additions/absence as good/bad;
- turn insider activity into a trading signal;
- alter valuation, MOS, investment Research Gate or portfolio sizing;
- create BUY/HOLD/SELL;
- mutate Chapter 7, 8 or 9 payloads.

## Acceptance criteria

V70 must demonstrate:

1. exact Q33–Q52 order: 6 + 9 + 5 = 20 questions;
2. Chapter 7 manager master remains the only roster;
3. source-chapter evidence/gap lineage is preserved;
4. unknown Manager IDs create reconciliation warnings, not new managers;
5. analyst-written conclusions are copied verbatim;
6. input payloads remain unchanged;
7. synthesis handoff appears in the existing consolidated report;
8. read-only long tables use the current wrapped `st.html()` rule;
9. no automatic management score/classification/investment signal;
10. full Deep Company Analysis regression and Streamlit health remain green.

## Next phase

**Phase 9J — analyst-owned cross-chapter management synthesis workspace and snapshot.** It can provide a place for the analyst to write the final Chapters 7–9 synthesis and preserve versions/snapshots, while keeping AI/Data as Research Assistant and still avoiding mechanical management scoring or automatic investment conclusions.
