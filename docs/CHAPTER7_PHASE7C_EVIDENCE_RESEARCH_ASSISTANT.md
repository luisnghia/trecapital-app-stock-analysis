# Chapter 7 Phase 7C — Management Evidence & Research Assistant

## Scope

Phase 7C extends the source-locked Q33–Q38 Chapter 7 workspace with a focused evidence assistant. It searches management-related public web sources, grades source quality A/B/C, surfaces candidate evidence/counter-evidence, supports optional deep text extraction from public HTML/PDF sources, generates research gaps, and requires an explicit analyst **Promote** action before any candidate enters the persisted Evidence Matrix.

## Source and analyst boundary

- AI/Data = Research Assistant; Analyst = investment analyst and owner of conclusions.
- No automatic OO1/OO2/OO3/LT1/LT2/HH1/HH2 classification.
- No automatic Lion/Hyena label or numerical Management Quality score.
- No automatic positive/negative conclusion for outside management.
- Insider trading evidence is not a BUY/SELL signal.
- No MOS, Research Gate, BUY/HOLD/SELL, or Chapter 7 Completion Gate.
- Final source closure remains Phase 7D.
- Management/career/ownership/insider information remains event/as-of data; Phase 7C never fabricates TTM.

## Research coverage

- **Q33:** current leader identity/role, appointment/tenure, founder/family/internal/external background, actual ownership.
- **Q34:** outside-management transition, prior industry/customer overlap, first major actions, learning/culture/stakeholder evidence, early outcomes.
- **Q35:** evidence/counter-evidence relevant to the exact seven Table 7.1 dimensions. Text cues are not classifications.
- **Q36:** career biography/chronology and operating/functional experience, targeting up to five confirmed managers.
- **Q37:** compensation/remuneration, performance horizon, actual shares vs options/RSU/ESOP/unvested awards.
- **Q38:** registered vs executed insider transactions, dates and before/after ownership from original disclosures.

## Source grades

- **A — Company/Official disclosure:** company IR, exchange, regulator or known first-party source.
- **B — Independent financial source/research:** financial data/news/research source used for cross-checking.
- **C — Secondary/context source:** context only; analyst should verify against higher-quality originals.

## Deep extraction

The assistant may fetch selected public HTML/PDF sources and extract relevant source text. PDF extraction is text-only; no OCR is performed. Scanned/image-only PDFs remain unresolved and are surfaced as a gap rather than inferred.

## Persistence

Phase 7C reuses `chapter7_evidence` and `chapter7_research_gaps`. Candidate results remain session research artifacts until the analyst selects them and presses **Promote evidence đã chọn + lưu Research Gaps**. Promotion is deduplicated and does not mutate Q33–Q38 conclusions, final management classification, Lion/Hyena classification, insider behavior conclusion, or analyst summary.
