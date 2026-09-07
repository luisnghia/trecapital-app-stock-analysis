# Chapter 9 Phase 9L / V73 — Analyst Synthesis History & Delta Review

## Purpose

Phase 9L adds a read-only, cross-snapshot history layer for the analyst-owned **Management Synthesis — Chapters 7–9** created in Phases 9J–9K. It answers a narrow audit question: **what changed in the analyst synthesis record between stored versions, and which stored source baseline/re-review metadata belongs to each version?**

This phase does **not** decide whether management improved or deteriorated. It does not generate a Management Quality Score, character classification, investment signal, MOS change, investment Research Gate, portfolio-sizing input, or BUY/HOLD/SELL recommendation.

## Source and ownership contract

- Q33–Q52 source research remains owned by Chapters 7–9.
- Chapter 7 manager master remains the manager identity/role SSOT.
- Management Synthesis text, status and confidence remain analyst-owned.
- Phase 9L compares only fields actually stored in Management Synthesis payloads and immutable snapshots.
- Historical source freshness is **not reconstructed** from today's Chapter 7–9 state. The history layer shows the baseline fingerprint, source-capture time, analyst-review time and explicit re-review metadata stored in each version.
- Snapshots remain immutable/read-only; Phase 9L has no restore or overwrite operation.

## Backend

New pure module:

`modules/deep_company_analysis/chapter9_synthesis_history.py`

It provides:

- `compare_synthesis_versions(before, after, ...)`
- `build_version_lineage(records)`
- `synthesis_history_summary(before, after)`

The tracked fields include synthesis status/confidence, Chapters 7–9 takeaways, strengths, concerns, material unknowns, evidence that would change the analyst view, final synthesis, analyst note, stored source fingerprint/counts/handoff state, source capture/review timestamps, and explicit re-review timestamp/note/sections.

## Neutral delta vocabulary

Only structural record labels are used:

- `Unchanged`
- `Added`
- `Removed`
- `Changed`

These labels never mean better/worse management. The UI explicitly states this distinction.

## Version lineage

The immutable lineage table shows, for every supplied snapshot:

- Version / Snapshot ID
- Created At
- Schema Version
- Synthesis Status
- Analyst Confidence
- stored Source Baseline fingerprint (short display only)
- Source Captured At
- Analyst Reviewed At
- Last Re-review At
- Last Re-review Sections
- whether Final Synthesis is present

Rows are sorted deterministically oldest-to-newest by stored `created_at`, then snapshot ID. Missing historical metadata is left blank rather than inferred.

## Streamlit analyst workspace integration

Phase 9L is integrated additively into the existing unified Management Synthesis workspace; no standalone page is created.

The analyst can:

1. review the immutable version-lineage table;
2. choose one snapshot as `Before`;
3. compare it with another snapshot or `Current saved workspace`;
4. view changed-field counts and an optional changed-only delta table;
5. explicitly write a runtime log entry for the delta review.

The feature is read-only with respect to snapshots and current workspace.

## Consolidated report integration

`modules/deep_company_analysis/chapter9_synthesis_report.py` now adds a read-only **Phase 9L — Management Synthesis Version Lineage** section to the consolidated report.

It shows immutable snapshot lineage and compares the latest immutable snapshot with the current saved workspace. Any difference is labelled as a record delta only.

## App-rule compliance

- **Source fidelity:** only stored Management Synthesis/snapshot metadata are compared; no historical facts are invented.
- **SSOT:** no new manager table or research SSOT is introduced.
- **Auditability:** immutable snapshot IDs/timestamps/source-baseline/re-review fields remain visible.
- **Runtime log:** event `phase9l_synthesis_delta_view` uses the existing Chapter 9 JSONL log path.
- **Terminology help:** Version Lineage, Snapshot, Delta, Source Baseline and Re-review Lineage are explained in the UI.
- **Heat/status display:** green means no tracked record change; amber means a record delta exists. These colors do not express management quality.
- **Read-only tables:** lineage/delta tables use `static_table_html(...)` + `st.html(...)` so long text wraps.
- **Financial display rules:** not applicable. Phase 9L introduces no financial amount, percentage, ratio or valuation formula.

## Persistence compatibility

No database migration is required. Phase 9L reuses:

- `management_synthesis_current`
- `management_synthesis_snapshots`
- `SCHEMA_VERSION = 2`

No SQL column/table shape changes are introduced.

## Acceptance boundary

Phase 9L must preserve all of the following as `False`:

- automatic workspace status change
- automatic confidence change
- automatic analyst text change
- automatic management score
- automatic character classification
- automatic investment signal
- MOS/investment Research Gate change

## Next phase

After V73 is stable, the next logical step is **Phase 9M — management-synthesis change rationale / decision-journal linkage**, where analyst-authored reasons can be tied to version deltas without AI rewriting or scoring the management thesis.
