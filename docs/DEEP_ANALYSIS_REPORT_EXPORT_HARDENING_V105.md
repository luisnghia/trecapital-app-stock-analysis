# Deep Company Analysis — Report Export & DOCX Layout Hardening V105

## Purpose

V105 is a production-export hardening phase created after live V104 runs for VIP, SCS and THG exposed a concrete pagination defect: long table rows could split across Word pages. V105 fixes the DOCX presentation layer without changing financial semantics, checklist semantics, valuation, MOS, or analyst conclusions.

## Layout controls

V105 adds one shared, idempotent OOXML layout helper used by the V101 → V102 → V103 report composition chain:

1. Every table row receives `w:cantSplit`, so a row is moved intact to the next page when it fits there.
2. The first row of every table receives `w:tblHeader`, so Word/LibreOffice can repeat table headers on later pages.
3. `Title` and `Heading*` paragraphs receive `w:keepNext` and `w:keepLines`, reducing orphan headings and split heading text.
4. The helper is idempotent. V101, V102 and V103 may each call it as they append content without creating duplicate OOXML controls.

These controls apply to the checklist tables, the 10Y + TTM financial tables, cyclical-normalization/provenance tables, and the V103 event → question mapping table.

## Architecture boundaries retained

- Trecapital Data Layer remains the financial SSOT.
- V105 does not fetch, normalize, persist, or recalculate financial data.
- Module 2 remains the sole valuation/MOS owner.
- Appendix C remains the source lock for Q01–Q59 wording.
- AI remains `Research Assistant`; the analyst owns conclusions.
- No weighted management/growth/checklist score is added.
- No BUY/HOLD/SELL output is added.
- No automatic intrinsic-value/MOS or Research Gate change is added.

## Deterministic QA

V105 tests the actual DOCX OOXML package and verifies:

- all exported table rows contain `w:cantSplit`;
- every table first row contains `w:tblHeader`;
- all Title/Heading paragraphs contain `w:keepNext` + `w:keepLines`;
- applying hardening twice does not duplicate controls;
- Q01 and Q59 source wording remains unchanged;
- V102 chart media remains embedded;
- full DCA regression and Streamlit health remain green.

The dedicated acceptance script generates `reports/DGC_REPORT_EXPORT_HARDENING_V105_SAMPLE.docx` for render QA.
