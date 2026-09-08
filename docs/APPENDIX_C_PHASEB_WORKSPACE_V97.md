# Appendix C — Phase B / V97

## Scope

V97 operationalizes Michael Shearn's **Appendix C — Your Investment Checklist** as a consolidated, read-only research workspace over the existing Q01–Q59 owner chapter SSOT.

Source lock: printed pages 335–338, ten source sections, Q01–Q59 in book order. Appendix C adds no new question wording, score, ranking, valuation rule, or investment recommendation.

## Architecture

- `appendix_c.py` remains the canonical Appendix C source-lock/index contract.
- `appendix_c_workspace.py` dynamically reads the existing `chapterN_store.load_record(...)` payloads where available.
- The workspace extracts only `question_status`, `confidence`, and `analyst_assessment` for the matching Qxx reference.
- Owner chapter, section, exact Qxx reference, and research target are rendered for navigation.
- Missing owner state remains `Unknown`; V97 never infers or fills missing research.
- No Appendix C answer/evidence database is created.

## UI

`pages/12_Appendix_C_Investment_Checklist.py` provides:

1. neutral counts of Unknown / Partial / Answered / N/A;
2. source-section overview;
3. Q01–Q59 consolidated table with source-locked wording and live owner status;
4. section/status filtering; and
5. explicit owner chapter/Qxx research-target guidance.

The counts are research-completeness counts only. They are not percentages, weights, quality scores, Research Gate outputs, or investment signals.

## Boundaries

AI remains **Research Assistant** and the analyst owns all interpretations and conclusions. V97 does not create weighted management/growth/checklist scores, BUY/HOLD/SELL, intrinsic-value or MOS changes, Investment Research Gate changes, duplicate financial SSOT, duplicate question SSOT, or an Appendix C answer store.
