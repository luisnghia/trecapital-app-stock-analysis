# Formula Explanation — Chapter 10 Phase 10G / V80

V80 adds no new financial valuation formula. Its only deterministic calculations are audit utilities.

## Source baseline fingerprint

The source baseline is `SHA256(canonical_json(source-facing workspace state))`, where the state contains only Q53-Q57 research status/confidence, 34 dimension statuses, promoted evidence, research gaps and growth events. Canonical financial SSOT values are deliberately excluded.

## Delta classification

For each tracked analyst field:

- `Unchanged`: canonical before equals canonical after.
- `Added`: before is empty and after is non-empty.
- `Removed`: before is non-empty and after is empty.
- `Changed`: both are non-empty and differ.

The classification is descriptive only. `Changed` never means better or worse growth quality.

## Version lineage

Snapshots are sorted by stored `created_at` then snapshot ID. Historical source freshness is not inferred from current data. Missing historical metadata stays missing.

## Explicit re-review

A re-review records `last_re_review_at`, `last_re_review_note`, and analyst-selected `last_re_review_sections`. It does not mutate Research Status, Confidence, Growth Mode, analyst assessment, or final growth synthesis.

## Financial boundary

V80 does not calculate CAGR, sustainable growth, cash-conversion cycle, intrinsic value, MOS, weighted growth score, or investment recommendation. Existing canonical financial/data SSOT remains authoritative.
