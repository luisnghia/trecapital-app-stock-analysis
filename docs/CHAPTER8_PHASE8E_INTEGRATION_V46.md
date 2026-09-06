# Chapter 8 Phase 8E — Unified DCA + Consolidated Report Integration V46

## Scope

Phase 8E integrates the Chapter 8 Q39–Q47 analyst workspace into the main **Phân tích chuyên sâu doanh nghiệp** flow and exposes analyst-owned Chapter 8 state in the printable **Báo cáo tổng hợp toàn bộ nội dung**.

This phase does not change the Chapter 8 source-lock established in V42–V45.

## Integration contract

1. `pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py` gains an eighth tab: **Chương 8 — Năng lực vận hành**.
2. Chapter 8 participates in the existing DCA ticker/session fallback chain and inherits the prior chapter ticker when no Chapter 8 ticker exists yet.
3. The unified DCA page displays a compact research-completeness summary for Q39–Q47: Answered, Partial, promoted evidence, open research gaps, and analyst conclusions.
4. `pages/04_Bao_cao_tong_hop.py` appends a printable Chapter 8 section after the existing consolidated report package.
5. The report section shows the Q39–Q47 research status table and, when present, promoted/manual Evidence Matrix, Research Gaps, Q46 capital-allocation register, and Q47 explicit buyback history.
6. `chapter8_store.py` remains the analyst-owned persistence source for Chapter 8 workspace/snapshots.
7. Chapter 7 remains the management identity/background SSOT. Trecapital canonical Module 1 remains the financial SSOT.

## Analyst boundary

Phase 8E is descriptive integration only. It must never:

- calculate a numerical Management Quality Score;
- create BUY/HOLD/SELL;
- alter MOS;
- mutate Research Gate;
- promote research candidates without an analyst action;
- overwrite Analyst Assessment, confidence or status.

`Unknown`, `Partial`, `N/A`, and open Research Gaps remain valid outcomes when disclosure is insufficient.

## New integration helpers

`modules/deep_company_analysis/chapter8_integration.py` provides pure read-only transformations:

- `build_chapter8_summary(payload)`
- `build_chapter8_status_table(payload)`
- `build_chapter8_report_frames(payload)`

These functions summarize or format persisted analyst state and do not write to any database.

## Acceptance

V46 acceptance requires:

- Phase 8A–8E Chapter 8 tests pass;
- full Deep Company Analysis regression passes;
- unified DCA page compiles and exposes the eighth Chapter 8 tab;
- consolidated report page compiles and contains the Chapter 8 printable section;
- Streamlit health smoke passes for both the unified DCA page and consolidated report page;
- acceptance probe confirms all Q39–Q47 are preserved in source order;
- analyst assessment remains verbatim;
- automatic management score = false;
- automatic investment signal = false.
