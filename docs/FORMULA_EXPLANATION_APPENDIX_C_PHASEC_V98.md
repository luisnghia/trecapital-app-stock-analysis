# Formula / Data Explanation — Appendix C Phase C V98

Appendix C V98 adds **no investment formula**. Research completeness is represented only by raw counts of owner-chapter labels (`Unknown`, `Partial`, `Answered`, `N/A`). No percentage is converted into a score or investment signal.

The history fingerprint is deterministic SHA-256 over the normalized referential snapshot payload. It is an integrity/version-lineage identifier only; it has no financial meaning.

Delta is categorical only: equal values → `Unchanged`; blank→nonblank → `Added`; nonblank→blank → `Removed`; otherwise → `Changed`. Delta never means better/worse, bullish/bearish, or pass/fail.

All financial formulas, units, rounding, decimal precision, negative-number formatting, tables and chart conventions remain owned by the existing chapter/financial SSOT and are not recalculated or reformatted by Appendix C.
