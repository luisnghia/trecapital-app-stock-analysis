# Chapter 9 Phase 9K / V72 — Consolidated Analyst Synthesis + Explicit Source Re-review

## Purpose

Phase 9K completes the reporting/re-review loop for the analyst-owned Chapters 7–9 management synthesis created in Phase 9J.

The phase has two goals:

1. render the **saved analyst management synthesis** inside `Báo cáo tổng hợp toàn bộ nội dung`; and
2. make source drift actionable through an **explicit analyst re-review workflow** instead of silently accepting a changed Q33–Q52 source baseline.

This phase does **not** create a Management Quality Score, character classification, investment signal, MOS change, investment Research Gate, portfolio-sizing input, or BUY/HOLD/SELL conclusion.

## Source boundary

- Question range remains **Q33–Q52**.
- Chapter 7 manager master remains the only manager identity/role SSOT.
- Chapter 8 and Chapter 9 evidence/gaps continue to reference Chapter 7 manager IDs.
- The source fingerprint remains based on six Phase 9I handoff sections:
  - Q33–Q52 Question Ledger;
  - Chapter 7 Manager Roster;
  - Cross-Chapter Evidence Ledger;
  - Research Gap Ledger;
  - Chapter Research / Closure Readiness;
  - Manager Lineage Warnings.

## New source-freshness states

The report and synthesis workspace expose three process-only states:

- **Current** — the saved analyst-reviewed source baseline matches current saved Q33–Q52 research.
- **Needs Re-review** — one or more source sections changed after the last accepted baseline.
- **No baseline** — the analyst has not yet captured an initial source baseline.

These states describe source freshness only. They do not say whether management is good or bad.

## Important V72 behavior change

After an initial baseline exists, the ordinary **Save Management Synthesis** action no longer accepts a changed source baseline.

When source drift exists, normal Save:

- saves analyst text/status/confidence;
- preserves the old reviewed source fingerprint;
- leaves the synthesis in **Needs Re-review** state.

A new baseline is accepted only through the explicit re-review control:

1. review the changed-source checklist;
2. enter an analyst re-review memo;
3. tick the explicit confirmation checkbox;
4. click **Confirm Re-review & accept new baseline**.

The acceptance action preserves analyst synthesis text, workspace status and confidence. It updates only source-baseline/audit metadata and creates an immutable synthesis snapshot for the reviewed state.

## Consolidated report integration

`pages/04_Bao_cao_tong_hop.py` now calls the Phase 9K report renderer after the Phase 9I research handoff.

The report shows:

- Synthesis Status;
- Analyst Confidence;
- Source Freshness (`Current`, `Needs Re-review`, `No baseline`);
- Final Analyst Management Synthesis;
- Chapter 7/8/9 takeaways;
- Management Strengths;
- Management Concerns;
- Material Management Unknowns;
- Evidence That Would Change View;
- analyst notes and review timestamps.

If source drift exists, the report displays the changed-source checklist and clearly states that the report is read-only. The report never accepts a baseline on behalf of the analyst.

## Persistence and compatibility

The existing database remains:

`data_cache/deep_company_analysis_management_synthesis.db`

The SQL table design is unchanged. Phase 9K bumps payload schema to V2 and stores new audit fields inside `payload_json`:

- `last_re_review_at`;
- `last_re_review_note`;
- `last_re_review_sections`.

V71 payloads are normalized additively to V2 without losing analyst text or baseline data.

## Runtime log

Phase 9K uses the existing Chapter 9 JSONL diagnostic log for:

- synthesis saves;
- synthesis snapshots;
- explicit source re-review acceptance.

Log entries are operational audit records only and are not analytical conclusions.

## App UI rule

New long read-only tables use the shared:

`static_table_html() -> st.html()`

path so text wraps in cells and remains usable on-screen and when printed.

## Acceptance criteria

V72 must prove that:

- Q33–Q52 and Chapter 7 manager SSOT remain unchanged;
- ordinary Save cannot silently accept source drift;
- explicit re-review acceptance updates only baseline/audit metadata;
- analyst status/confidence/text remain unchanged by source drift and re-review acceptance;
- the consolidated report shows the saved analyst synthesis and freshness label;
- stale synthesis remains visible but is clearly marked `Needs Re-review`;
- snapshots do not silently re-baseline;
- V71 payloads migrate additively to schema V2;
- no management score, character classification or investment signal is created;
- MOS and investment Research Gate are unchanged.

## Next phase

**Phase 9L** should add cross-snapshot analyst-synthesis history/delta review and report version lineage so the analyst can see how the final management thesis itself changed over time, while still avoiding automatic management scoring or investment conclusions.
