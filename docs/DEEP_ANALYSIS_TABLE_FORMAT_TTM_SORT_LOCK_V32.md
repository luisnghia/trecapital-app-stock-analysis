# Deep Company Analysis — Format + TTM + Sort Lock V32

Scope: unified Chapters 1–6 Deep Company Analysis workspace.

## Format
- VND amounts explicitly labelled `(tỷ)`: 0 decimals.
- Percentages: 1 decimal.
- Ratios: 1 decimal.
- DSO/DIO/DPO/CCC days: 1 decimal.
- Signed performance/cash-flow heat: negative red, positive emerald; heat is not a quality conclusion.
- Static financial tables: `st.html()` with fixed layout and wrapped text.
- Editable tables: explicit numeric `NumberColumn` formatting.

## TTM
- Canonical quantitative history tables display the valid appended TTM row when the canonical quarterly bundle can construct it.
- Chapter 4 history ends at TTM while historical medians remain annual-only.
- Chapter 5 Q22/Q25/Q26 display current TTM; reinvestment shows a TTM terminal row but refuses an FY-vs-TTM incremental-return calculation.
- Chapter 6 Q27/Q28/Q29/Q31/Q32 already use valid TTM; Q30 shows TTM as current context but DOL is N/A unless a comparable prior TTM exists.
- Analyst registers, evidence inventories, peer lists and snapshots are not time-series financial statements; TTM is not fabricated for them.
- Beneish/Jones/REM remain annual-statement diagnostics and show a TTM applicability N/A row in Phase 6C.

## Sortability
- Every shared read-only table exposes `Sort theo cột` + `Tăng dần/Giảm dần` controls.
- Every editable `st.data_editor` in Chapters 2–6 is routed through `sortable_data_editor`, which exposes the same explicit sort selector.
- Chapter 1 custom Opportunity Inventory sorts raw values through `interactive_sort_frame` before display formatting.
- Sorting is view/order behavior only; it does not alter calculations or analyst conclusions.
