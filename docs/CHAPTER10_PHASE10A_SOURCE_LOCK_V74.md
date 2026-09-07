# Chapter 10 Phase 10A — Source Lock V74

## Scope

Phase 10A starts Chapter 10 of Michael Shearn's *The Investment Checklist* as a strict source-locked analyst contract. It intentionally does **not** add UI, persistence, web research, canonical financial calculations, forecasting, valuation, MOS/Research Gate logic, growth scoring, or investment signals.

**Chapter 10 title:** `Evaluating Growth Opportunities`

Source-locked checklist questions:

- Q53 — `Does the business grow through mergers and acquisitions, or does it grow organically?`
- Q54 — `What is the management team’s motivation to grow the business?`
- Q55 — `Has historical growth been profitable and will it continue?`
- Q56 — `What are the future growth prospects for the business?`
- Q57 — `Is the management team growing the business too quickly or at a steady pace?`

Book pages used by the source lock: Q53 p.281, Q54 p.282, Q55 p.283, Q56 p.284, Q57 p.296.

## Chapter 10 framing preserved

The source frames Chapter 10 as an evaluation of future growth opportunities rather than a mechanical preference for high growth. The analyst is expected to distinguish organic growth from acquisition-led growth, understand why management wants to grow, test whether historical growth has been profitable, investigate the runway for future growth, and judge whether the pace of expansion is disciplined or too rapid.

Phase 10A therefore keeps every question `Unknown` until the analyst has reviewed evidence. Missing information is a research gap, not an automatic negative conclusion.

## Important source mechanics intentionally deferred

The chapter contains quantitative and operating concepts that must be implemented carefully in later phases using the app's canonical company-data SSOT rather than duplicated formulas. Examples include:

- Q55's comparison of unit growth with gross margin, operating margin, and operating-income economics over multi-year periods.
- Q56's analysis of the duration/runway and drivers of future growth rather than relying only on a single-year growth rate.
- Q57's analysis of whether growth is financed within the business's means, including the cash-conversion-cycle concept and dependence on internal versus external capital.

These are **not** calculated in Phase 10A. Phase 10B will separately source-lock the detailed evidence dimensions/subsections before any financial-data bridge is introduced.

## Architecture boundaries

- **AI/Data = Research Assistant; analyst = decision owner.**
- Q53-Q57 and their wording cannot be overridden by runtime payloads.
- Question status and confidence start at `Unknown`.
- Q53 includes an analyst-owned neutral growth-mode field: `Unknown / Organic / M&A / Mixed / N/A`; the app does not infer it automatically in Phase 10A.
- Evidence can support, counter, or remain neutral/mixed; direction is not converted into a growth-quality grade.
- No auto-promoted evidence.
- No automatic growth score, forecast, CAGR target, sustainable-growth estimate, or valuation conclusion.
- No automatic investment signal.
- No BUY/HOLD/SELL, MOS, target-price, or investment Research Gate change.
- No web research, database/store, UI, or financial-data bridge is added in Phase 10A.
- Chapter 11 Q58-Q59 is explicitly outside this source lock.

## Files

- `modules/deep_company_analysis/chapter10.py`
- `modules/deep_company_analysis/test_chapter10_phase10a.py`
- `scripts/qa_chapter10_source_lock_v74.py`
- `docs/FORMULA_EXPLANATION_CHAPTER10_PHASE10A_V74.md`
- `.github/workflows/chapter10-phase10a-source-lock-v74.yml`

## Acceptance

V74 is accepted only if the exact Chapter 10 title, Q53-Q57 texts and source pages are preserved; the module remains Unknown-first and analyst-controlled; adjacent Chapter 9/11 questions do not bleed into the contract; no duplicate financial SSOT or automatic growth/investment scoring is introduced; the full Deep Company Analysis regression and production Streamlit health remain green.

## Next phase

`Phase 10B — source-locked evidence dimensions for Q53-Q57.`

Phase 10B must source-verify the chapter's named subsections, explicit tests, quantitative concepts, growth-runway checks, and disciplined-growth indicators before implementing research or financial bridges.
