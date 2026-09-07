# Formula / Logic Explanation — Chapter 9 Phase 9G V68

Phase 9G contains **no financial valuation formula** and intentionally adds no weighted score. The only calculations are transparent research-completeness tallies.

## 1. Dimension-level closure

For every one of the 26 source-locked dimensions, V68 reads:

- Chapter 7 manager scope;
- Chapter 9 evidence rows matching the exact `Question` + `Dimension Key`;
- evidence verification status;
- source lineage (source URL/file + evidence/reference);
- research-gap rows matching the exact `Question` + `Dimension Key`;
- analyst-controlled gap status.

Priority order:

`Manager scope blocker → verified evidence with source lineage → verified evidence missing lineage → unverified evidence → open gap → analyst-closed known unknown → no coverage`

This priority is deterministic so a missing manager identity cannot be hidden by an unrelated evidence row.

## 2. Counts

For each dimension:

- `Evidence Rows = count(exact dimension-linked evidence)`
- `Verified Evidence = count(evidence whose Status begins with promoted / verified / confirmed / accepted / closed)`
- `Source-Lineage Rows = count(evidence having both source and reference/claim/title)`
- `Open Gaps = count(dimension gaps not explicitly closed/resolved)`
- `Closed Gaps = count(dimension gaps explicitly closed/resolved/completed/N/A)`

These are **counts only**, not scores and not weights.

## 3. Question-level completion

For each Q48–Q52:

- `Source Dimensions = number of source-contract dimensions for that question`
- `Closed Dimensions = count(Closure Status starts with Closed)`
- `Review Dimensions = count(Closure Status starts with Review)`
- `Open / Blocked Dimensions = count(Closure Status starts with Open or Blocked)`

Question completion is:

- `Blocked — research incomplete` if any dimension is Open or Blocked;
- else `Review — evidence/source verification required` if any dimension is Review;
- else Review if analyst Research Status is not Answered/N/A;
- else Review if Analyst Confidence is Unknown;
- else Review if Analyst Assessment is blank/Unknown;
- otherwise `Ready — research closure complete`.

The engine does **not** write any of the analyst-owned fields.

## 4. Chapter-level Research Completion Gate

- if any question is Blocked → `Blocked — research incomplete`;
- else if any question is Review → `Review — analyst closure required`;
- else → `Ready — research closure complete`.

This is a workflow gate only. It is distinct from any investment Research Gate elsewhere in Trecapital.

## 5. No automatic inference from absence

`No evidence found` never means a negative management trait and never means a dimension is closed. The analyst can keep it Open, continue research, or explicitly close the documented gap as a **known unknown**.

## 6. Q48 / Q52 CEO rule

Q48 and Q52 cannot become research-complete without an explicit CEO/Tổng Giám đốc scope supplied by Chapter 7. Deputy/vice CEO roles are not silently upgraded to CEO.

## 7. Source lineage rule

Verified evidence is not considered sufficient for closure if the audit trail is incomplete. At minimum the row needs:

- a source URL/file (or equivalent source field); and
- an evidence/reference, observation/claim, or source title.

This is an auditability rule, not a source-quality score.

## 8. Display and diagnostic rules

- Phase 9G read-only tables are rendered through `st.html()` using the shared wrapped-cell formatter.
- Workflow urgency uses red / amber / emerald for Blocked / Review / Ready.
- Diagnostic actions append JSONL to `data_cache/logs/deep_company_analysis_chapter9.log`.
- No financial amount, percentage, or ratio is produced by Phase 9G; therefore the financial number-format rules do not apply here.
