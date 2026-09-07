# Chapter 9 Phase 9H / V69 — Consolidated Report + Snapshot History & Delta Review

## Purpose

Phase 9H connects the analyst-owned Chapter 9 workspace to the existing printable **Báo cáo tổng hợp toàn bộ nội dung** and adds read-only history/delta review across Chapter 9 snapshots.

This phase is descriptive only. A change in a snapshot is a change in the research record, **not** evidence that management became better or worse. Phase 9H does not create a Management Quality Score, character classification, rank, MOS change, investment Research Gate change, or BUY/HOLD/SELL signal.

## Source lock and ownership

- Source lock: **Michael Shearn — The Investment Checklist — Chapter 9 — Q48–Q52**.
- Source dimensions: exactly **26**: Q48=6, Q49=4, Q50=8, Q51=3, Q52=5.
- Manager identity/role SSOT: **Chapter 7 manager master**.
- Q48 and Q52 remain CEO-specific under the existing Chapter 9 bridge rules.
- Research Status, Analyst Confidence and Analyst Assessment remain analyst-owned and are displayed verbatim.
- Unknown, Research Gap and analyst-accepted Known Unknown remain valid research outcomes.

## Consolidated report integration

The printable consolidated report now includes:

1. Chapter 9 research-completeness metrics.
2. Current Phase 9G Research Completion Gate.
3. Q48–Q52 consolidated analyst report.
4. 26 source-dimension closure records.
5. Promoted/manual Evidence Matrix.
6. Research Gaps.
7. Dated Management / Behavior Events.
8. Q48 six source-locked Passion Research Prompts.
9. Snapshot audit trail and Delta Review.

All new read-only Phase 9H tables use the shared `static_table_html()` formatter and actual `st.html(...)` rendering so long text wraps in cells and the printable report remains readable.

## Snapshot comparison contract

Phase 9H compares an immutable baseline snapshot with either another snapshot or the **Current Workspace**. It never restores, overwrites or modifies either side of the comparison.

The delta engine reports five groups of changes:

- Q48–Q52 analyst-field changes: Research Status, Analyst Confidence, Analyst Assessment.
- Evidence changes: Added, Removed, Changed.
- Research-gap changes: Added, Removed, Changed, Closed, Reopened, Status changed.
- Behavior-event changes: Added, Removed, Changed.
- Source-dimension closure changes: Newly closed, Reopened/no longer closed, Closure status changed.

The comparison of Phase 9G closure status uses the **current Chapter 7 manager master** as the shared SSOT for both sides. Phase 9H does not create or persist a second historical manager master.

## Evidence identity and audit behavior

Promoted research evidence uses `Candidate ID` as the preferred stable identity. Manual evidence without a Candidate ID uses a deterministic fingerprint of question, dimension key, manager ID, source and evidence/reference fields. Research gaps and behavior events use deterministic identity fields that exclude status so status changes can be detected as changes rather than false add/remove pairs.

Duplicate identities are kept as separate rows by deterministic occurrence suffixes inside a single comparison. The engine does not delete, merge or rewrite analyst records.

## Runtime diagnostics

The consolidated report offers an explicit button to append a compact `phase9h_delta_review` event to the existing Chapter 9 JSONL diagnostic log:

`data_cache/logs/deep_company_analysis_chapter9.log`

Logging is user-triggered for Delta Review and does not alter analyst workspace state.

## Acceptance boundaries

Phase 9H passes only if all of the following remain true:

- exact Q48–Q52 source range and 26 dimensions;
- Chapter 7 manager master remains SSOT;
- analyst fields remain immutable to the history engine;
- empty/missing evidence is never interpreted as a trait;
- snapshot comparison is read-only;
- no automatic management score/classification/investment signal;
- no MOS or investment Research Gate mutation;
- consolidated report and history tables are rendered with wrapped `st.html()` output;
- full Deep Company Analysis regression and production Streamlit health pass.
