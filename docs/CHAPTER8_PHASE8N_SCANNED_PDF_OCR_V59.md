# Chapter 8 Phase 8N / V59 — Scanned Official PDF OCR

## Purpose
V58 proved that real DGC official PDFs could be downloaded but several issuer PDFs had no embedded text layer. V59 adds a bounded OCR fallback so scanned official PDFs can become **evidence candidates** without lowering the Chapter 8 evidence standard.

## Runtime
- `pdftoppm` renders bounded grayscale JPEG pages.
- Tesseract runs with `vie+eng` language packs.
- OCR only runs after normal PDF text extraction returns empty.
- Page markers `[[OCR_PAGE:n]]` are injected close to every OCR text chunk so evidence windows retain page provenance.
- Default bounds: 170 dpi, maximum 80 pages per PDF, 2 OCR workers.

## Evidence boundary
OCR does **not** make a row analyst-approved evidence. Every OCR-derived row remains `Candidate — analyst verify`, `Select=False`; no automatic promotion, analyst assessment, confidence, status, management score, MOS/Research Gate or BUY/HOLD/SELL signal is written.

Chapter 7 remains the manager identity/background SSOT. Trecapital canonical / Module 1 remains the financial SSOT. Q43 remains exactly 14 dimensions, Q46 exactly five capital-allocation actions, and Q47 still requires explicit buyback/repurchase evidence.

## V59 acceptance
The live acceptance downloads the real DGC official-document manifest used by V58, executes OCR where embedded text is missing, measures candidate coverage against the historical V54 40-gap baseline, exports page-provenance candidates and runs the full Deep Company Analysis regression plus Streamlit health check.
