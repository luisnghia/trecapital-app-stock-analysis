# Chapter 8 Phase 8O / V60 — Gap-Directed High-Resolution OCR

## Purpose

V59 proved that scanned official PDFs can yield real Chapter 8 evidence, but broad OCR sampling is expensive and still leaves many source-locked dimensions open. V60 makes the second OCR pass explicitly gap-directed.

## Pipeline

1. Build the target table only from currently open source-locked Q39–Q47 dimensions.
2. Run a low-cost sampled OCR pass across the scanned PDF.
3. Score each OCR page only against terms belonging to those open dimensions.
4. Select a bounded set of positive-score pages and their immediate neighbors.
5. Re-render only those original PDF pages at high resolution and OCR them again.
6. Remap every `[[OCR_PAGE:n]]` marker back to the original PDF page number.
7. Send the combined text through the existing Chapter 8 candidate extractor.

## Default bounds

- coarse OCR: 110 dpi, up to 36 sampled pages, 4 workers;
- high-resolution OCR: 220 dpi, up to 10 selected original pages;
- neighbor radius: 1 page;
- Vietnamese + English Tesseract language packs;
- the underlying V59 per-page and wall-clock guards remain active.

## Evidence boundary

V60 does not approve evidence. All OCR-derived rows remain `Candidate — analyst verify` with `Select=False` and original-page provenance. It does not write analyst assessment, confidence, question status, management score, MOS, Research Gate, BUY/HOLD/SELL, or any other investment conclusion.

Chapter 7 remains the manager identity/background SSOT. Trecapital canonical remains the financial SSOT.

## Source locks preserved

- Q43: exactly 14 employee-relation dimensions.
- Q46: exactly five Shearn capital-allocation actions; discipline/hurdle context is not a sixth action.
- Q47: explicit buyback/repurchase evidence is required; share-count decline alone is not proof.

## Live acceptance baseline

The verified V59 DGC acceptance reduced the historical V54 open source-locked dimension set from 40 to 39 by adding candidate coverage for `Q46:shearn_action_5`. V60 therefore measures *additional* candidate coverage against the remaining 39 dimensions rather than resetting the baseline.
