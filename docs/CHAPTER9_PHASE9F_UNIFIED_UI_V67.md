# Chapter 9 Phase 9F — Unified Streamlit Analyst Workspace UI — V67

## Purpose

Phase 9F exposes the already-tested Chapter 9 research stack inside the existing **Phân tích chuyên sâu doanh nghiệp** unified page. It does not redesign the Chapter 9 analytical contract.

The implementation path remains:

`Chapter 7 manager master -> Phase 9B 26 source dimensions -> Phase 9C manager context -> Phase 9D research candidates -> Phase 9E explicit analyst promotion/persistence -> Phase 9F unified UI`

## Source lock preserved

Chapter 9 remains **Michael Shearn — The Investment Checklist — Chapter 9 — Q48-Q52**:

- Q48: 6 source-locked dimensions.
- Q49: 4 source-locked dimensions.
- Q50: 8 source-locked dimensions.
- Q51: 3 source-locked dimensions.
- Q52: 5 source-locked dimensions.
- Total: 26 dimensions.

The UI does not add a new checklist criterion, weight, score, quality rank, or automatic positive/negative character classification.

## Unified page integration

Chapter 9 is added directly after Chapter 8 in:

`pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py`

with option:

`🧠 Chương 9 — Phẩm chất quản lý`

No separate standalone Chapter 9 page is created.

## Analyst workflow

The UI exposes the existing layers in one workflow:

1. Load Chapter 7 manager identities and roles.
2. Show manager/CEO scope and open identity gaps.
3. Run the Phase 9D Evidence Research Assistant.
4. Review source-quality / dimension coverage.
5. Open source links and review evidence candidates.
6. Tick `Select` only after analyst review.
7. Click `Promote evidence đã chọn`.
8. Edit Analyst Research Status, Confidence and Analyst Assessment for Q48-Q52.
9. Review/edit Q48 passion prompts, promoted/manual Evidence Matrix, Research Gaps and dated Behavior Events.
10. Save current Chapter 9 workspace or save an immutable snapshot.

## Manager identity boundary

`Chapter 7 manager master` remains the only manager identity SSOT.

- Q48 and Q52 are CEO-specific.
- A Q48/Q52 research candidate cannot be promoted unless its Manager ID is linked to an explicitly scoped Chapter 7 CEO/Tổng Giám đốc.
- Q49-Q51 can contain management-wide evidence with blank Manager ID, but any nonblank ID must exist in Chapter 7.
- Chapter 9 never creates a replacement Manager ID.

## Candidate boundary

Research output remains `Candidate — analyst verify`.

Search snippets are not treated as final facts. Original source text is preferred when captured. Candidate direction labels remain sorting/research cues only. Promotion requires an explicit analyst action and never writes to Analyst Assessment/Confidence/Research Status.

## Q52 financing-context exception

The source-locked financing-context exception remains visible in the UI. Investor conferences, roadshows, or external promotion associated with debt/equity issuance, acquisition financing, or expansion financing are retained as context and must not be mechanically classified as self-promotion.

## Persistence

Phase 9F uses the V66 persistence layer:

`data_cache/deep_company_analysis_chapter9.db`

with:

- `chapter9_current`
- `chapter9_snapshots`

Snapshot preview is read-only and never auto-restores or overwrites the current workspace.

## Explicit non-goals

Phase 9F does **not** add:

- automatic Management Quality Score;
- automatic positive/negative character classification;
- weighted Q48-Q52 score;
- financial/MOS bridge;
- Research Gate changes;
- BUY/HOLD/SELL signals;
- automatic snapshot restoration;
- a second manager master;
- a standalone Chapter 9 page.

## Acceptance criteria

V67 passes only when:

- the exact Q48-Q52 and 26-dimension source contract remains intact;
- Chapter 9 is wired into the unified Deep Company Analysis page after Chapter 8;
- Research Assistant, source links, candidate selection, explicit promotion, analyst conclusions, evidence/gaps/events, save, snapshot, and read-only snapshot preview are visible;
- Q48/Q52 CEO validation still uses Chapter 7 SSOT;
- Q52 financing exception remains visible;
- no automatic management score, character classification, MOS/Research Gate change, or BUY/HOLD/SELL exists;
- Chapter 9 deterministic tests, full Deep Company Analysis regression, Streamlit health, and offline package validation all pass.

## Next phase

**Phase 9G — Research Completion Gate / Source Coverage Closure.**

The next phase should determine whether each Q48-Q52 question has enough analyst-reviewed evidence and source coverage to be considered research-complete. This must remain a completeness gate only and must not become a management-quality score.
