# Formula / Logic Explanation — Appendix A Phase B V91

Appendix A V91 adds **no investment, valuation, credibility, source-quality or weighted scoring formula**.

The only deterministic calculations are record identity and validation utilities:

- `Source ID = SRC- + SHA256(normalized source name | source type | organization/context)[0:16]`
- `Interview ID = INT- + SHA256(source id | interview date | prompt | source response/observation)[0:16]`
- `Gap ID = GAP- + SHA256(unanswered question/assumption | normalized Q01–Q59 references)[0:16]`

These hashes exist solely for stable persistence and duplicate prevention. They do not express source quality or confidence.

Question references are validated against the closed set `Q01..Q59`. A reference does not import chapter state and cannot modify Research Status, Confidence, Research Gate, MOS, intrinsic value, BUY/HOLD/SELL or any financial SSOT.

## No new financial formulas

V91 adds no new financial formulas and no duplicate financial/company SSOT. All financial and valuation facts remain owned by the existing canonical systems.
