# Chapter 9 Phase 9J / V71 — Analyst-Owned Management Synthesis Workspace + Snapshot

## Purpose

Phase 9J turns the Phase 9I read-only Chapters 7–9 handoff into an **analyst-owned synthesis workspace**. It lets the analyst write and preserve a final management view across Q33–Q52 while keeping every source chapter independent and auditable.

This phase does **not** create a Management Quality Score, character score/classification, investment signal, MOS change, investment Research Gate, portfolio-sizing input, or BUY/HOLD/SELL recommendation.

## Source ownership

- Chapter 7 remains the only manager identity/role source of truth: `Chapter 7 manager master`.
- Chapter 7 Q33–Q38, Chapter 8 Q39–Q47 and Chapter 9 Q48–Q52 remain the source research records.
- Phase 9J does not copy manager records into a replacement manager master.
- Phase 9J does not edit question status, confidence, evidence, gaps, or analyst conclusions inside Chapters 7–9.
- The synthesis workspace uses **saved** Chapter 7–9 records. If the analyst changes a source chapter, that chapter should be saved before a new synthesis baseline is accepted.

## Analyst-owned fields

The workspace stores:

- Workspace Status: Draft / Reviewed / Finalized.
- Analyst Confidence: Unknown / Low / Medium / High.
- Chapter 7 Background / Classification Takeaway.
- Chapter 8 Operating Competence Takeaway.
- Chapter 9 Positive / Negative Traits Takeaway.
- Management Strengths.
- Management Concerns.
- Material Management Unknowns.
- Evidence That Would Change My Management View.
- Final Analyst Management Synthesis.
- Analyst Note / Review Memo.

No field above is auto-written by the Research Assistant.

## Source fingerprint and drift detection

`chapter9_synthesis_workspace.py` derives a stable SHA-256 fingerprint from the Phase 9I handoff sections:

1. Q33–Q52 question ledger.
2. Chapter 7 manager roster.
3. Cross-chapter evidence ledger.
4. Cross-chapter research-gap ledger.
5. Chapter readiness table.
6. Manager-lineage warning table.

The fingerprint is order-insensitive for DataFrame rows so harmless row reordering does not create false source drift.

When the analyst saves the synthesis, Phase 9J captures:

- overall source fingerprint;
- section fingerprints;
- source counts;
- current handoff state;
- source-captured timestamp;
- analyst-reviewed timestamp.

If current Q33–Q52 research later differs from the saved baseline, the app displays:

`Changed — analyst review required`

It also identifies which sections changed. This warning does **not** automatically change Finalized → Draft, confidence, final synthesis text, or any investment field.

## Persistence

Phase 9J uses a separate SQLite file:

`data_cache/deep_company_analysis_management_synthesis.db`

Tables:

- `management_synthesis_current`
- `management_synthesis_snapshots`

This separation prevents the synthesis layer from becoming a new source of truth for manager identities or chapter research.

Snapshots are immutable audit copies. Previewing a snapshot never restores or overwrites current synthesis.

## Unified UI

Phase 9J is embedded inside the existing Chapter 9 tab in:

`modules/deep_company_analysis/chapter9_page_support.py`

The UI provides:

- current source-drift warning;
- current Phase 9I handoff metrics;
- read-only chapter readiness / Q33–Q52 ledger / lineage warnings;
- analyst-owned synthesis fields;
- save synthesis + source baseline;
- immutable synthesis snapshot;
- snapshot history and read-only preview;
- comparison of snapshot baseline versus current Q33–Q52 source package.

No standalone Chapter 9 page is added.

## Boundary guarantees

Phase 9J must always keep these flags conceptually false:

- automatic management score;
- automatic character classification;
- automatic investment signal;
- MOS change;
- investment Research Gate change;
- automatic analyst-text mutation;
- automatic workspace-status mutation after source drift.

## Acceptance criteria

V71 passes only when:

- source fingerprinting is deterministic;
- row order does not create false drift;
- changes to question/evidence/manager/gap/readiness/lineage sections are detectable;
- analyst text is preserved by baseline capture;
- source drift does not mutate Finalized status;
- current workspace and immutable snapshots persist independently;
- UI is wired into the existing Chapter 9 tab;
- source chapters remain untouched;
- all Phase 9A–9J tests, full DCA regression and production Streamlit health pass.

## Next phase

Recommended next step after V71: **Phase 9K — consolidated-report integration of the saved analyst synthesis plus explicit re-review workflow when source drift is detected**, still without management scoring or automatic investment conclusions.
