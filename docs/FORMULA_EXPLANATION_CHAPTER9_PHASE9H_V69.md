# Formula / Logic Explanation — Chapter 9 Phase 9H V69

## Scope

Phase 9H contains **no financial valuation formula**. It does not calculate intrinsic value, WACC, ROIC, MOS, management score, weighted score or investment recommendation. The logic below is set/history comparison logic only.

## 1. Question report logic

For each source-locked question `q ∈ {Q48,Q49,Q50,Q51,Q52}`, the consolidated report reads these analyst-owned values without transformation:

- `Research Status(q)`
- `Analyst Confidence(q)`
- `Analyst Assessment(q)`

It then joins the Phase 9G research-completion metadata for the same question:

- Source Dimensions
- Closed Dimensions
- Review Dimensions
- Open / Blocked Dimensions
- Completion Status

No arithmetic combination of those fields is used to rank or judge management quality.

## 2. Chapter summary counts

The report uses simple integer tallies:

`Answered = count(q where Research Status(q) = Answered)`

`Partial = count(q where Research Status(q) = Partial)`

`Unknown = count(q where Research Status(q) = Unknown)`

`Analyst Conclusions = count(q where Analyst Assessment(q) is neither blank nor Unknown)`

`Confidence Known = count(q where Analyst Confidence(q) is neither blank nor Unknown)`

Evidence rows and research gaps are also simple row counts. These tallies are research-completeness metadata, not scores.

## 3. Stable evidence identity

Preferred identity for promoted evidence:

`Evidence ID = Candidate ID`, when Candidate ID exists.

For manual evidence without Candidate ID, Phase 9H creates a deterministic SHA-1 identity from the concatenated normalized values:

`Question | Dimension Key | Manager ID | Source URL/File | Evidence Text/Reference | Observation/Claim`

The hash is only a technical row-matching key. It has no financial or qualitative meaning.

## 4. Research-gap identity

A research gap is matched across two snapshots using a deterministic SHA-1 identity from:

`Question | Dimension Key | Manager ID | Research Gap`

`Status` is intentionally excluded so a change from Open to Closed can be detected on the same logical gap.

Gap status transition labels are descriptive:

- open/non-closed → closed-like = `Closed`
- closed-like → open/non-closed = `Reopened`
- other different status = `Status changed`

A Closed gap can represent a documented Known Unknown. It does not imply positive or negative management evidence.

## 5. Behavior-event identity

A behavior event is matched by a deterministic identity from:

`Event Date | Manager ID | Context/Situation | Source`

If the same identity exists on both sides but other stored fields differ, the row is reported as `Changed`.

## 6. Set-delta logic

For each identity-keyed collection:

- key only in comparison state → `Added`
- key only in baseline state → `Removed`
- key in both but canonical row fingerprint differs → `Changed`
- key in both and fingerprint is identical → no delta row

This is standard set/history comparison. Added is not automatically good; Removed is not automatically bad.

## 7. Source-dimension closure delta

Phase 9H reuses the Phase 9G closure engine for both states using the same current **Chapter 7 manager master**.

For each of the 26 dimension keys:

- before not Closed, after Closed → `Newly closed`
- before Closed, after not Closed → `Reopened / no longer closed`
- any other status difference → `Closure status changed`

The count `Dimensions newly closed` is a process-completion tally only. It is not a Management Quality Score.

## 8. Immutability

The comparison engine deep-copies/normalizes its inputs and performs no SQLite write, snapshot creation, restore or Streamlit action. Both input payloads and the Chapter 7 payload remain unchanged.

## 9. Formatting rule

No financial-format rule applies because Phase 9H creates no new monetary, percentage or ratio calculation. New read-only report/delta tables are formatted through shared `static_table_html()` and rendered by actual `st.html(...)`, preserving wrapped long text for print/readability.
