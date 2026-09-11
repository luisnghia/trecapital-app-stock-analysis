# V105 — Deep Company Analysis Report Export Hardening

## Added / fixed

- Fixed live DOCX pagination defect observed after VIP/SCS/THG V104 report runs.
- Prevent table rows from splitting across pages (`w:cantSplit`).
- Repeat table header rows on subsequent pages (`w:tblHeader`).
- Keep report headings with following content (`w:keepNext`, `w:keepLines`).
- Shared idempotent layout hardening across V101, V102 and V103 report composition.
- Deterministic structural tests and V105 acceptance sample.
- Dedicated V105 GitHub Actions workflow, full DCA regression, Streamlit health, DOCX render smoke and offline ZIP artifact.

## No semantic changes

- No financial SSOT change.
- No Module 2 valuation/MOS change.
- No Q01–Q59 source wording/status rule change.
- No weighted score, BUY/HOLD/SELL, or Research Gate automation.
