# Chapter 8 Phase 8L / V57 — Official File / PDF Ingestion

## Purpose

V56 added direct official URL ingestion, but CI showed that HOSE/HNX/CDN availability can be blocked even when a valid disclosure URL is known. V57 adds a local ingestion route so the analyst can upload the official disclosure file itself.

## Supported files

- PDF
- DOCX
- TXT
- HTML / HTM

No executable formats are accepted. OCR is not automatic; a scanned PDF with no extractable text remains a research gap rather than being guessed.

## Provenance rules

1. If the analyst supplies a source URL, it must pass the existing V56 official-source allow-list (company/IR, HOSE/HSX, HNX, SSC).
2. If no URL is supplied, the analyst must explicitly confirm that the file came from the selected official issuer.
3. URL-less files are marked `A? — Uploaded official file; provenance analyst verify`, not silently upgraded to a verified A source.
4. The filename or extracted text must match the active ticker before any evidence candidate can be created.

## Analyst boundary

- All extracted rows remain `Candidate — analyst verify`.
- No candidate is auto-selected or auto-promoted.
- No Analyst Assessment, Confidence or Research Status is overwritten.
- Chapter 7 remains the manager identity/background SSOT.
- Trecapital canonical remains the financial SSOT.
- No management score, MOS/Research Gate mutation or BUY/HOLD/SELL is generated.

## Source locks preserved

- Q43 remains exactly 14 source-locked employee dimensions.
- Q46 remains exactly the 5 Shearn capital-allocation actions.
- Q47 still requires explicit repurchase/buyback evidence; share-count decline is not proof.

## UI

Chapter 8 now exposes `Phase 8L — Official File / PDF Ingestion` next to the Phase 8K direct URL route. The analyst uploads file(s), chooses issuer, optionally supplies the official URL, confirms provenance when necessary, and runs local extraction. Results merge into the existing Chapter 8 research candidate state; the analyst then reviews/promotes evidence through the existing workspace.

## Acceptance meaning

The V57 CI fixture is synthetic and is used only to validate the local ingestion contract. It must never be presented as real DGC evidence. Real investment evidence must come from the analyst-supplied official document and remains subject to analyst verification.
