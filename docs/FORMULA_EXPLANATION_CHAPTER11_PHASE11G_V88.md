# Formula Explanation — Chapter 11 Phase 11G / V88

V88 intentionally introduces no valuation or M&A scoring formula. Its deterministic calculations are bookkeeping functions for analyst-owned research history.

## Source baseline fingerprint

`SHA256(canonical_json(source-facing Chapter 11 workspace state))`

Included state: question status, confidence, dimension status, explicitly promoted evidence, research gaps and M&A events. Non-contract canonical financial fields are discarded by the Chapter 11 normalizer before fingerprinting, so the history layer does not become a duplicate financial SSOT.

## Delta classification

For each tracked analyst-owned field:

- same canonical value → `Unchanged`
- empty before / non-empty after → `Added`
- non-empty before / empty after → `Removed`
- otherwise → `Changed`

No direction, quality or investment meaning is attached to the delta.

## History summary

`changed_fields = Added + Removed + Changed`

The summary explicitly reports false for automatic M&A score, automatic acquisition-success classification, automatic synergy forecast, automatic investment signal, and MOS/Investment Research Gate changes.

## Version lineage

Lineage is ordered by persisted `created_at` then snapshot ID. It reports only metadata stored with each snapshot plus a shortened source baseline fingerprint. Current source freshness is never projected backward into historical versions.

## Re-review

Explicit re-review stores analyst-selected sections, note and UTC timestamp. It is metadata only and does not mutate research status, confidence or analyst conclusions.
