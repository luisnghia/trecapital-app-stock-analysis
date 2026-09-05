# Deep Company Analysis — Table & Numeric Display Format Lock V30

Scope: Chapters 1–6 unified Deep Company Analysis workspace.

- Amounts denominated in VND: **tỷ đồng, 0 decimals**.
- Percentages: **1 decimal**.
- Ratios: **1 decimal**.
- CCC/DSO/DIO/DPO: **1 decimal**.
- Negative signed performance/cash-flow values: red heat; positive signed performance/growth: emerald heat. Heat is not an investment-quality conclusion.
- Read-only/static tables: `st.html()` via `render_static_table()`.
- Editable analyst registers: `st.data_editor()`.
- CSS: `table-layout: fixed`, `white-space: normal`, `overflow-wrap: anywhere`.
- Missing values: `—`; no fabricated unit/value.

Audit: Chapter 1 already had no legacy `st.dataframe`; Chapters 2–5 static tables are migrated to the shared renderer. Chapter 5 `Nợ vay ròng (tỷ)` metric is corrected from 1 decimal to 0 decimals. Chapter 6 retains approved V29 formatting and follows the same contract.
