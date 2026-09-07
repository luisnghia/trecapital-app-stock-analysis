# Formula / Logic Explanation — Chapter 9 Phase 9J V71

## Scope

Phase 9J contains **no financial valuation formula** and no management-quality score. Its derived logic is limited to deterministic research-source fingerprinting, source-drift detection, completeness metadata, and persistence of analyst-written synthesis.

## 1. Source-section fingerprint

For each Phase 9I handoff section, rows are normalized into JSON-compatible records. Dictionary keys are sorted and DataFrame/list-of-dict rows are sorted by their canonical JSON representation so row order alone does not change the result.

For a normalized section `S`:

`section_hash = SHA256(canonical_json(S))`

Sections covered:

- `question_ledger`
- `manager_roster`
- `evidence_ledger`
- `research_gap_ledger`
- `chapter_readiness`
- `lineage_warning_table`

## 2. Overall source fingerprint

The overall baseline combines:

- source question range;
- manager identity SSOT label;
- handoff state;
- ready-for-analyst-synthesis flag;
- six section hashes;
- source counts.

`source_fingerprint = SHA256(canonical_json(overall_payload))`

This is a research-audit fingerprint only. It has no economic or valuation meaning.

## 3. Source drift

Let:

- `F_saved` = source fingerprint captured when the analyst last saved the synthesis;
- `F_current` = fingerprint built from current saved Chapters 7–9 research.

Then:

- if no `F_saved`: `No baseline`;
- if `F_saved == F_current`: `Unchanged`;
- if `F_saved != F_current`: `Changed — analyst review required`.

Section-level fingerprints are compared to identify which source packages changed.

Critically, source drift does **not** execute any of the following:

- change Draft/Reviewed/Finalized;
- change analyst confidence;
- rewrite analyst synthesis;
- classify management;
- change MOS;
- change investment Research Gate;
- emit BUY/HOLD/SELL.

## 4. Text-completeness tally

The workspace summary reports how many analyst-owned synthesis sections contain non-empty text out of eight fields. This is a **workflow completeness count only**.

`completed_text_sections = count(non_empty analyst text fields)`

It is not a score, rating, probability, quality percentile, or investment signal.

## 5. Persistence

The synthesis store writes the analyst workspace and captured source baseline to a separate SQLite database. Snapshot rows are append-only audit copies; loading a snapshot is read-only and does not restore current state.

## Boundary

No financial valuation formula, WACC, DCF, MOS, management weighted score, portfolio-sizing formula, or investment recommendation is introduced in Phase 9J.
