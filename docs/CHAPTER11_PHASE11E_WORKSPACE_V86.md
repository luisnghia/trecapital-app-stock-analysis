# Chapter 11 — Phase 11E / V86

## Scope

Implements the analyst workspace, persistence store, Streamlit review surface and explicit Research Assistant candidate-promotion workflow for Michael Shearn, *The Investment Checklist*, Chapter 11 — **Evaluating Mergers & Acquisitions**.

Source lock remains unchanged:

- Q58 — **How does management make M&A decisions?**
- Q59 — **Have past acquisitions been successful?**
- 15 source-locked evidence dimensions: Q58 = 8, Q59 = 7.

## Analyst ownership

AI/Data remains a Research Assistant. Candidate evidence is not part of the durable Chapter 11 evidence set until the analyst explicitly selects and promotes it. Promotion never changes Research Status, Confidence, Analyst Assessment or dimension status automatically.

The workspace lets the analyst maintain:

- question research status;
- confidence;
- analyst assessment;
- per-dimension evidence status;
- candidate evidence under review;
- explicitly promoted evidence;
- open research gaps.

## Persistence contract

`chapter11_store.py` persists only the Chapter 11 analyst-owned payload normalized by `chapter11.normalize_payload()` plus explicitly promoted evidence already contained in that contract.

It does **not** persist a duplicate copy of canonical financial/market SSOT. Extra keys such as synthetic `canonical_financials` or valuation metrics are removed by normalization before persistence.

## UI

Dedicated page: `pages/09_Phan_tich_MA.py`

Shared navigation now exposes **Chương 11 — Mergers & Acquisitions**.

## Boundaries

V86 does not create or alter:

- M&A score or weighted M&A score;
- automatic acquisition-success/failure conclusion;
- automatic synergy forecast;
- BUY/HOLD/SELL or portfolio signal;
- intrinsic value or MOS;
- Investment Research Gate;
- canonical financial/data SSOT.

## QA

Dedicated deterministic tests cover persistence round-trip, explicit promotion, idempotent candidate promotion, non-contract financial-field removal, source-lock preservation and research-gap neutrality. Dedicated GitHub Actions also runs full DCA regression, Streamlit health, offline ZIP validation and artifact upload.
