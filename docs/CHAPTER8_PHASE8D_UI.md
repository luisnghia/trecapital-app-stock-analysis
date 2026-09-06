# Chapter 8 Phase 8D — Streamlit Analyst Workspace V45

## Scope

Phase 8D connects the source-locked Chapter 8 Q39–Q47 contract (Phase 8A), structured Trecapital/Chapter 7 bridge (Phase 8B), and evidence research assistant (Phase 8C) into an analyst-facing Streamlit workspace.

The new route is `pages/09_Phan_tich_chuyen_sau_Chuong_8.py`, linked from the shared Trecapital sidebar.

## Analyst workflow

1. Select ticker and reuse the newest local Trecapital canonical bundle, or explicitly click **Cập nhật canonical**.
2. Review Phase 8B structured context:
   - Chapter 7 manager master remains the manager identity/background SSOT.
   - Trecapital canonical financial data / Module 1 remains the financial SSOT.
   - Q45 cost context, Q46 five excess-FCF uses, and Q47 explicit buyback context are read-only research support.
3. Click **Tự nghiên cứu Q39–Q47** to run Phase 8C.
4. Open candidate source links, select only evidence the analyst has verified, then click **Promote evidence đã chọn**.
5. Optionally merge machine-discovered research gaps into the analyst Research Gap workflow.
6. Edit Q39–Q47 research status, confidence, analyst assessment, source-locked tables, evidence matrix, gaps, and management events.
7. Save the current workspace or create a point-in-time snapshot.

## Non-overwrite contract

- Research candidates never write directly into `analyst_assessment`, `question_status`, or `confidence`.
- Promotion is an explicit analyst action and is deduplicated.
- Research gap sync appends new gaps while preserving existing analyst-edited rows/notes.
- Unknown remains valid when evidence is incomplete.
- No automatic management score is produced.
- No MOS, Research Gate, or BUY/HOLD/SELL field is changed by Chapter 8.

## Persistence

`modules/deep_company_analysis/chapter8_store.py` stores the complete analyst-owned payload in `data_cache/deep_company_analysis_chapter8.db` and provides snapshot history. Phase 8C raw research candidates remain session research outputs until the analyst promotes evidence.

## Acceptance V45

The V45 CI gate performs:

- Python compile for new storage/workspace/UI/QA files.
- Chapter 8 Phase 8A–8D deterministic tests.
- Live DGC Trecapital canonical refresh and Phase 8B/8D integration acceptance.
- Full Deep Company Analysis regression.
- Streamlit health smoke for the Chapter 8 page.
- Offline ZIP integrity check and artifact upload.

The acceptance runner explicitly verifies that an existing analyst assessment survives candidate promotion and persistence/snapshot round-trip unchanged.
