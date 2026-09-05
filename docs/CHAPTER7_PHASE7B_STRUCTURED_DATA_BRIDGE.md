# Chapter 7 Phase 7B — Structured Management Data Bridge (V35)

## Scope lock

Phase 7B converts the Phase 7A manual Chapter 7 workspace into a structured management-data pipeline while preserving analyst ownership of all conclusions.

Pipeline:

`Official/primary source -> Raw -> Normalized Candidate -> Analyst Review -> Apply to Chapter 7`

The bridge does **not** auto-classify OO1/OO2/OO3/LT1/LT2/HH1/HH2, Lion/Hyena, management quality, MOS, Research Gate or BUY/HOLD/SELL.

## Source priority

1. Annual report / governance report / financial-statement note.
2. AGM / Board documents and appointment/resignation disclosures.
3. Exchange / regulator / insider disclosures.
4. Official IR pages, official management biographies and company press releases.
5. Structured secondary sources only as fallback/cross-check.

Each source retains title, type, URL/file, grade, publication date, effective date, as-of date, page/section, parser status and refresh timestamp.

## Structured-only Phase 7B boundary

Phase 7B parses only structured JSON, CSV and HTML tables. PDF/unstructured text is retained as provenance but values are not guessed. Deep extraction/research from PDF/web text belongs to Phase 7C.

## Management identity

- Exact accent/case-normalized names receive a deterministic `manager_id`.
- Similar but non-identical names generate a **possible identity match** requiring analyst review.
- The engine never auto-merges two identities based on fuzzy similarity alone.

## Role normalization

Raw titles are retained in the bridge provenance/role history while a normalized role is derived for structured comparison. Specific titles are matched before broad substrings (e.g. `Phó Tổng Giám đốc` must not collapse into `CEO`).

## Dates

Chapter 7 is event/as-of based. Publication date, effective date and as-of date remain separate concepts. Year-only disclosures remain year-only; Phase 7B never invents month/day precision and never fabricates TTM management data.

## Q36 career chronology

Structured career records preserve date precision. Potential chronology gaps may be surfaced later, but a missing period never receives an invented reason such as resignation/firing/unemployment.

## Q37 compensation and ownership

- Aggregate board compensation is retained as aggregate and never allocated to individuals.
- Data-quality flags may include `aggregate_only`, `individual_amount_missing`, `equity_component_unknown`, `vesting_terms_missing`, and `metric_not_disclosed`.
- Actual shares, options, RSU/restricted shares and unvested/ESOP awards remain separate.

## Q38 insider transactions

Registered shares and executed shares are separate fields. The executed amount is the transaction actually completed. Transaction type is normalized separately from Buy/Sell direction. `% of Existing Ownership` is descriptive only and never becomes a conviction/BUY/SELL signal.

## Conflicts and chronology

Same canonical record key with materially different normalized values creates a conflict item instead of a silent overwrite. Newer role/event episodes can coexist chronologically. Conflicts remain open until analyst review.

## Management review queue

Structured management events map to Chapter 7 questions requiring review, for example:

- CEO appointed/resigned -> Q33, Q34, Q36.
- CFO/COO change -> Q33, Q36.
- Compensation plan / ESOP -> Q37.
- Large insider transaction -> Q38.

Creating/closing a review item never changes Q33-Q38 answers automatically.

## Persistence

Phase 7B adds these tables to the Chapter 7 SQLite database:

- `chapter7_source_documents`
- `chapter7_raw_management_records`
- `chapter7_candidate_records`
- `chapter7_role_history`
- `chapter7_data_conflicts`
- `chapter7_data_refresh_runs`
- `chapter7_review_queue`

## Acceptance boundary

A candidate may populate roster, career, compensation, ownership, insider or management-event tables only after analyst selection. Apply must preserve question status, Q33-Q38 analyst fields, final management classification and analyst summary.

Phase 7B intentionally does not add the Chapter 7 Completion Gate. Final source closure remains Phase 7D after Phase 7C evidence/research assistant work.
