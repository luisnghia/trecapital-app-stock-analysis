# Formula / Logic Explanation — Chapter 9 Phase 9K V72

## Scope

Phase 9K contains **no financial valuation formula**. It does not calculate intrinsic value, WACC, ROIC, MOS, target price, portfolio sizing, or investment recommendation.

The phase implements deterministic source-freshness and explicit re-review workflow logic for the analyst-owned management synthesis covering Q33–Q52.

## 1. Source signature

Phase 9K reuses the Phase 9J source fingerprint.

For each source section `S_i`:

`section_fingerprint_i = SHA256(canonical_json(S_i))`

The six source sections are:

1. `question_ledger`
2. `manager_roster`
3. `evidence_ledger`
4. `research_gap_ledger`
5. `chapter_readiness`
6. `lineage_warning_table`

The overall fingerprint hashes:

- source question range;
- Chapter 7 manager SSOT label;
- handoff state;
- handoff readiness boolean;
- six section fingerprints;
- deterministic record counts.

DataFrame/list record ordering is canonicalized before hashing, so row order alone does not create artificial source drift.

## 2. Source Freshness state

Let:

- `F_saved` = analyst-reviewed saved fingerprint;
- `F_current` = fingerprint of current saved Chapters 7–9 research package.

Then:

### No Baseline

`F_saved is blank`

Result:

`No Baseline — analyst review baseline not captured`

### Current

`F_saved == F_current`

Result:

`Current — analyst-reviewed baseline matches current Q33–Q52`

### Needs Re-review

`F_saved != F_current`

Result:

`Needs Re-review — Q33–Q52 source research changed`

These are **workflow states only**. They are not management-quality states.

## 3. Changed-source checklist

For each of the six source sections:

`Changed_i = (saved_section_fingerprint_i != current_section_fingerprint_i)`

The checklist reports either:

- `Changed — review required`; or
- `Unchanged`.

The checklist does not decide whether the changed evidence is positive, negative, material, immaterial, favorable, or unfavorable.

## 4. Ordinary save rule

### First save

When there is no source baseline yet, the first synthesis save captures the initial Q33–Q52 baseline.

### Save after baseline exists

Once a baseline exists, normal Save never changes it.

If source drift exists:

`saved synthesis text := current analyst text`

but:

`F_saved := previous F_saved`

Therefore:

`Source Freshness remains Needs Re-review`

until the analyst performs explicit re-review acceptance.

This prevents an unrelated text edit from silently accepting new source research.

## 5. Explicit re-review acceptance

The analyst must explicitly confirm the re-review in the UI.

After confirmation:

`F_saved := F_current`

and the app records:

- `last_re_review_at`;
- `last_re_review_note`;
- `last_re_review_sections`.

The following analyst-owned fields are invariant under re-review acceptance:

- `workspace_status`;
- `analyst_confidence`;
- Chapter 7 takeaway;
- Chapter 8 takeaway;
- Chapter 9 takeaway;
- management strengths;
- management concerns;
- management unknowns;
- evidence that would change the view;
- final management synthesis;
- analyst note.

The app does not automatically rewrite or downgrade any of these fields.

## 6. Snapshot rule

A normal synthesis snapshot captures exactly the current workspace and its currently saved baseline.

It does **not** call baseline capture automatically.

Therefore a snapshot can correctly preserve a historical state where:

`workspace_status = Finalized`

and

`Source Freshness = Needs Re-review`

This is intentional audit behavior.

Explicit re-review acceptance creates an immutable snapshot of the newly accepted reviewed state.

## 7. Consolidated-report rule

The consolidated report loads:

- the current saved analyst synthesis workspace; and
- the current Phase 9I Q33–Q52 handoff.

It derives Source Freshness in read-only mode.

If source drift exists, the report continues to display the saved analyst synthesis but labels it `Needs Re-review` and displays the changed-section checklist.

The report does not write to any store and cannot accept a new baseline.

## 8. Schema V2 compatibility

Phase 9K changes only JSON payload schema from 1 to 2.

No SQL-column migration is required because the new fields live in `payload_json`.

V1 payload normalization adds blank defaults for the three new audit fields and preserves all V1 analyst text/source metadata.

## 9. Invariants

For all Phase 9K operations:

- `automatic_management_score = False`
- `automatic_character_classification = False`
- `automatic_investment_signal = False`
- `mos_or_investment_research_gate_changed = False`

Chapter 7 manager master remains the only manager identity/role SSOT.
