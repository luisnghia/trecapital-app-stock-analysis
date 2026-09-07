# Chapter 8 Phase 8M / V58 — Real Official Document Acceptance

## Objective

Run the V57 local-file/PDF ingestion path against **real DGC issuer documents** from the official Duc Giang Chemicals website and measure candidate coverage against the historical V54 state where 40 source-locked dimensions were still open.

## Real-source manifest

The acceptance manifest contains real issuer-hosted PDFs for:

1. DGC Annual Report 2025 (published 2026-04-07).
2. DGC Corporate Governance Report 2025 (published 2026-01-30).
3. DGC 2025 AGM Minutes/Resolution (published 2025-04-01).
4. DGC board-nomination disclosure dated 2026-08-05.

Each document has both an official landing page and a direct `ducgiangchem.vn` PDF URL. These entries are retrieval targets, **not pre-approved investment evidence**.

## Acceptance logic

1. Refresh DGC canonical data from the Trecapital SSOT.
2. Load the exact V54 coverage snapshot captured after the Phase 8I DGC acceptance; it contains 48 source-locked dimensions, of which 40 were still open.
3. Download the real issuer PDFs from their official URLs.
4. Feed the real bytes through the Phase 8L `OfficialFileIngestionAgent`.
5. Require ticker match + verified official URL provenance before any row can become a candidate.
6. Compare candidate-covered dimensions from the real documents with the exact 40 historical V54 open keys.
7. Report which historical gaps receive new candidate coverage and which remain open.

## Analyst boundary

All output rows remain `Candidate — analyst verify`. V58 does not auto-promote evidence, does not write analyst assessment/status/confidence, does not create manager identities, and does not generate management scores or investment signals. Q43 remains 14 source-locked dimensions; Q46 remains exactly five Shearn capital-allocation actions; Q47 still requires explicit buyback evidence and never treats share-count decline alone as proof.

## Interpretation

A V58 historical gap counted as "newly candidate-covered" only means that a real official document contains text matching the source-locked evidence pattern. It does **not** mean the question is analytically closed. The analyst must inspect the source, decide whether the excerpt is relevant and sufficiently explicit, then promote it manually if appropriate.
