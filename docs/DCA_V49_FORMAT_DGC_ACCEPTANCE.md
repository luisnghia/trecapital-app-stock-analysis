# Deep Company Analysis V49 — Numeric Format + DGC Ch1–Ch8 Acceptance

V49 locks the Vietnamese numeric display contract for Deep Company Analysis tables and validates the unified Chapter 1–8 workspace with a live DGC canonical refresh.

Display contract:
- VND billions: 0 decimals.
- Percentages: 1 decimal.
- Ratios and days: 1 decimal.
- Thousands separator: `.`.
- Decimal separator: `,`.
- Negative financial values: red heat styling.
- Positive/growth financial values: emerald heat styling.
- Text wraps inside tables; numeric cells remain numeric underneath so header sorting still works.

Live acceptance refreshes DGC through the Trecapital canonical pipeline, binds the resulting overview/annual/quarterly files to the unified Deep Company Analysis page, and executes all eight Streamlit tab bodies in one run. The acceptance does not substitute DCM sample data for DGC.
