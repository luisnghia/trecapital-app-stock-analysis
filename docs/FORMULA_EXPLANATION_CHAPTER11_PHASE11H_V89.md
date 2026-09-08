# Formula / Deterministic Logic — Chapter 11 Phase 11H / V89

V89 adds no valuation or financial formula. It only exposes stored analyst research history deterministically.

## Source-baseline fingerprint
`SHA256(canonical JSON(question_status, confidence, dimension_status, evidence, research_gaps, ma_events))`

Canonical financial/market values are deliberately excluded, so Chapter 11 does not become a duplicate financial SSOT.

## Neutral delta
For each tracked analyst-owned field:
- same canonical value → `Unchanged`
- empty before, populated after → `Added`
- populated before, empty after → `Removed`
- otherwise different → `Changed`

These labels have no positive/negative meaning and do not imply M&A success, quality or investment merit.

## Version lineage
Lineage displays only metadata persisted with immutable snapshots: snapshot id/time, schema version, saved research status, source-baseline fingerprint, analyst review/re-review metadata and whether final analyst synthesis is present. Historical source freshness is never reconstructed from current information.

## Explicit re-review
Re-review stores only analyst-confirmed timestamp, note and selected sections. It does not mutate Research Status, Confidence, Analyst Assessment, M&A synthesis text, valuation, MOS, Investment Research Gate or investment action.
