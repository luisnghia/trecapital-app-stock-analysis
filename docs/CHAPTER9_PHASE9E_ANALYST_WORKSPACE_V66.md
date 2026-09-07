# Chapter 9 Phase 9E / V66 — Analyst Workspace + Candidate Promotion + Persistence

## Purpose

Phase 9E turns the Phase 9D Research Assistant output into an analyst-owned, persistent Chapter 9 workspace without changing the Chapter 9 source contract or transferring judgment to the AI.

The implementation follows the existing Chapter 8 pattern:

`Research candidate -> analyst Select -> explicit Promote -> Evidence Matrix -> Save -> Snapshot`

It does **not** implement:

`Research candidate -> automatic conclusion/score/investment signal`.

## Source and identity locks

- Michael Shearn — *The Investment Checklist* — Chapter 9 — Q48-Q52 remains the source lock.
- The 26 Phase 9B dimensions remain unchanged: Q48=6, Q49=4, Q50=8, Q51=3, Q52=5.
- `Chapter 7 manager master` remains the manager identity/background SSOT.
- Chapter 9 does not create replacement Manager IDs.
- Q48 and Q52 are CEO-specific. Candidate promotion requires an exact Manager ID that is scoped as CEO/Tổng Giám đốc by the Phase 9C bridge.
- Q49-Q51 may preserve management-wide evidence without a Manager ID, but any nonblank Manager ID must exist in Chapter 7.

## Analyst-owned promotion

`chapter9_workspace.py` provides a pure promotion layer. A candidate enters the Evidence Matrix only when `Select=True` and it passes source-dimension and manager-lineage validation.

Promotion preserves:

- Candidate ID;
- Question;
- Dimension Key and Dimension;
- Manager ID/name/current role;
- Source family and source grade;
- Explicitness;
- Source title and URL/file;
- source/as-of dates;
- evidence text/reference;
- research direction cue;
- source method and data origin.

The research cue is stored separately from the normalized Evidence Matrix direction so an analyst can audit why the assistant surfaced the candidate. The cue is never treated as an automatic character conclusion.

Repeated promotion is deterministic and deduplicated. Unselected or invalid candidates are ignored. The input candidate set and existing Analyst Assessment / Research Status / Confidence fields are not mutated.

## Q52 financing-context protection

The Phase 9D `Context / exception cue — analyst assess` for debt/equity/acquisition financing remains auditable after promotion and maps to a neutral workspace direction. A financing roadshow therefore does not become automatic counter-evidence/self-promotion merely because it is an investor event.

## Research gaps

Phase 9D dimension-level gaps can be merged into the analyst workspace without overwriting existing analyst notes. Gap identity includes Question + Dimension Key + gap text + status, so distinct source-locked dimensions are not collapsed together.

Missing evidence remains a research gap/Unknown condition and is not transformed into a negative management trait.

## Persistence and snapshots

`chapter9_store.py` mirrors the established Chapter 8 SQLite store pattern:

- current workspace table: `chapter9_current`;
- immutable history table: `chapter9_snapshots`;
- database file: `data_cache/deep_company_analysis_chapter9.db`;
- schema version: 1.

The store persists the analyst workspace only. Raw Phase 9D research candidates remain session/research outputs unless the analyst explicitly promotes them.

A snapshot records the normalized analyst workspace and research-completeness status for later audit/comparison. Loading a snapshot does not overwrite the current record automatically.

## V66 boundary

V66 adds backend analyst workspace transforms, candidate promotion, SQLite persistence, and snapshot history only.

V66 intentionally does **not** add the Chapter 9 Streamlit page/UI. That is the next incremental phase so the storage/promotion contract can be accepted independently before UI wiring.

No V66 component creates or changes:

- Management Quality Score;
- positive/negative character classification;
- BUY/HOLD/SELL;
- MOS;
- Research Gate;
- valuation;
- portfolio decision;
- automatic analyst conclusion.

## Acceptance criteria

1. Only explicitly selected candidates can be promoted.
2. Promotion preserves candidate/source/dimension/manager lineage.
3. Q48/Q52 reject unassigned or non-CEO manager links.
4. Q49-Q51 permit management-wide evidence but reject invented Manager IDs.
5. Wrong Question/Dimension-Key combinations are rejected.
6. Duplicate promotion is idempotent.
7. Analyst Assessment, Research Status, and Confidence are never overwritten by promotion.
8. Research gaps merge at source-dimension level while preserving analyst notes.
9. Save/load is lossless for promoted lineage and analyst-owned fields.
10. Snapshot history is auditable and does not overwrite current workspace.
11. Workspace summary is research-completeness metadata only, never a management/investment score.
12. Full Deep Company Analysis regression and Streamlit production health remain green.

## Next phase

**Phase 9F / V67 — Unified Streamlit Analyst Workspace UI** should wire V63 source contract + V64 manager context + V65 Research Assistant + V66 promotion/store into the existing unified Deep Company Analysis page, following the established Chapter 8 UI pattern. Candidate review must still require explicit analyst selection and promotion.
