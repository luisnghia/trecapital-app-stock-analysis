# Chapter 8 Phase 8K / V56 — Direct Official Source Adapters

## Goal

Phase 8J showed that search-engine indexing can return zero official archive rows even when direct exchange-hosted disclosures exist. V56 adds an explicit ingestion path for direct official URLs from the company/IR site, HOSE/HSX, HNX and SSC.

## Boundaries

- Chapter 7 remains the manager identity/background SSOT.
- Trecapital canonical Module 1 remains the financial SSOT.
- Only official allow-listed domains are accepted.
- A fetched document must explicitly match the requested ticker before extraction.
- Evidence is extracted only for currently open source-locked Q39–Q47 dimensions.
- Every extracted row remains `Candidate — analyst verify` and `Select=False`.
- No automatic promotion, Analyst Assessment, confidence/status mutation, management score, MOS/Research Gate change, or BUY/HOLD/SELL output.
- Q43 remains 14 source-locked employee dimensions.
- Q46 remains exactly five Shearn capital-allocation actions.
- Q47 still requires explicit buyback/repurchase language; share-count decline is not proof.

## UI behavior

Chapter 8 now includes a Phase 8K panel where the analyst can paste one or more direct official URLs. The app validates domains, fetches text/PDF directly, rejects wrong-ticker documents, then merges any extracted rows into the existing research candidate list. The analyst must still open/read the source and explicitly promote selected evidence.

## Why no undocumented exchange API

V56 does not hard-code reverse-engineered/private exchange endpoints. It uses public official URLs and stable hostname validation, which is safer and easier to audit. Direct exchange APIs can be added later only after an official/public contract is verified.
