# Chapter 11 — Phase 11G / V88

## Scope

Source lock remains Michael Shearn, *The Investment Checklist*, Chapter 11 — **Evaluating Mergers & Acquisitions**:

- Q58 — How does management make M&A decisions?
- Q59 — Have past acquisitions been successful?

V88 adds analyst-owned immutable research snapshots, neutral version delta, version lineage and explicit analyst re-review metadata. It does not add new book questions or evidence dimensions.

## Architecture

- `chapter11_current` remains the mutable analyst workspace.
- `chapter11_snapshots` is append-only through the application API.
- Snapshot payloads contain only normalized Chapter 11 analyst state, explicitly promoted evidence and analyst-authored M&A synthesis.
- Canonical financial/market data remain read-only in their existing SSOT and are not duplicated into Chapter 11.
- Historical source freshness is not reconstructed from current data.

## Neutral delta contract

Delta values are limited to:

- `Unchanged`
- `Added`
- `Removed`
- `Changed`

A changed field only means that the stored research record differs between versions. It does not mean M&A quality improved or deteriorated.

## Explicit re-review

`mark_explicit_re_review()` records analyst-selected sections, note and UTC timestamp. It never automatically changes question status, confidence, analyst assessment or final M&A synthesis.

## Investment boundary

V88 does **not** create or modify:

- M&A score or weighted score
- acquisition success/failure classification
- synergy forecast
- BUY/HOLD/SELL signal
- intrinsic value or valuation engine
- margin of safety
- Investment Research Gate
- portfolio action

## QA

Dedicated V88 QA covers source lock, 15 evidence dimensions, deterministic fingerprinting, immutable snapshot persistence, neutral delta, stored-only lineage metadata, explicit re-review, SSOT boundary and full Deep Company Analysis regression.
