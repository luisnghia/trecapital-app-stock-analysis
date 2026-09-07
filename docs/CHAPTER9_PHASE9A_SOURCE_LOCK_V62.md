# Chapter 9 Phase 9A — Source Lock V62

## Scope

Phase 9A starts Chapter 9 of Michael Shearn's *The Investment Checklist* as a strict source-locked analyst contract. It intentionally does **not** add UI, persistence, web research, financial-data bridges, management scoring, MOS/Research Gate logic, or investment signals.

**Chapter 9 title:** `Assessing the Quality of Management—Positive and Negative Traits`

Source-locked checklist questions:

- Q48 — `Does the CEO love the money or the business?`
- Q49 — `Can you identify a moment of integrity for the manager?`
- Q50 — `Are managers clear and consistent in their communications and actions with stakeholders?`
- Q51 — `Does management think independently and remain unswayed by what others in their industry are doing?`
- Q52 — `Is the CEO self-promoting?`

Book pages used by the source lock: Q48 p.256, Q49 p.264, Q50 p.268, Q51 p.275, Q52 p.276.

## Chapter 9 framing preserved

Chapter 9 follows Chapter 8's examination of how management operates the business and turns to the positive and negative traits of managers themselves. The source stresses character and values, including passion for the business, integrity, humility and consistency of behavior over time. Phase 9A treats these ideas as research subjects, never as automatically scored facts.

For Q48, the source explicitly lists six research prompts under how to identify passion. V62 preserves those six prompts verbatim as evidence rows, without weights or points:

1. Is the business a career or just a job for the manager?
2. Would the CEO refuse to sell the business, no matter what the price?
3. Is the manager interested in money or motivated by money?
4. Does the manager focus on appearances instead of the business?
5. What type of philanthropic endeavors is the manager involved in?
6. Are the managers lifelong learners who focus on continuous improvement?

Detailed sub-dimension taxonomies for Q49-Q52 are deliberately deferred until they are separately source-verified. Phase 9A does not infer or invent them.

## Architecture boundaries

- **AI/Data = Research Assistant; analyst = decision owner.**
- **Chapter 7 manager master remains the manager identity/background SSOT.** Chapter 9 cannot create a parallel manager registry.
- Question status and confidence start at `Unknown`.
- Evidence can support, counter or remain neutral/mixed; the module does not translate evidence direction into a management grade.
- Qualitative behavioral evidence uses event/publication/as-of dates. It is not transformed into artificial TTM/T12M observations.
- No auto-promoted evidence.
- No automatic management score.
- No automatic investment signal.
- No BUY/HOLD/SELL, MOS or Research Gate change.
- No web research, database/store, UI, or canonical financial-data bridge is added in Phase 9A.

## Files

- `modules/deep_company_analysis/chapter9.py`
- `modules/deep_company_analysis/test_chapter9_phase9a.py`
- `scripts/qa_chapter9_source_lock_v62.py`
- `.github/workflows/chapter9-phase9a-source-lock-v62.yml`

## Acceptance

V62 is accepted only if the exact Chapter 9 title, Q48-Q52 texts, source pages and six Q48 passion prompts are preserved; Chapter 7 remains manager SSOT; the module stays Unknown-first and analyst-controlled; the full Deep Company Analysis regression and production Streamlit health remain green.
