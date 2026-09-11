# V105 Formula / Semantics Impact Note

V105 changes **no financial formula** and introduces **no valuation formula**.

The only new logic is presentation-only OOXML pagination metadata:

- `w:cantSplit` = keep one table row on one page where possible;
- `w:tblHeader` = repeat the first table row as a page header;
- `w:keepNext` = keep a heading with the next paragraph/table;
- `w:keepLines` = keep the heading paragraph's own lines together.

Therefore Revenue, margins, CFO, Capex, FCF, ROIC/ROCE, working-capital metrics, cyclical normalization, Module 2 valuation/MOS, and Q01–Q59 evidence/status calculations are unchanged from their owning modules. V105 only affects DOCX pagination and readability.
