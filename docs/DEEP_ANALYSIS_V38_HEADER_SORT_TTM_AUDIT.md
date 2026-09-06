# Deep Company Analysis V38 — Header Sort Everywhere + TTM Latest Default

## Scope

V38 hardens the V37.2 table migration across Deep Company Analysis Chapters 1–7.

User contract:

1. Sorting is performed by clicking a column header directly.
2. The old `Sort theo cột / Thứ tự` UI and its legacy implementation are removed, not merely hidden.
3. The same behavior applies to read-only and editable tables.
4. When canonical data contains TTM, TTM is the default/latest period. If TTM is unavailable, the latest real period is used. TTM is never fabricated.

## V37.2 gap found during re-audit

V37.2 correctly migrated read-only tables to `st.dataframe`, but editable tables still passed through `num_rows="dynamic"` when callers requested dynamic rows.

The project is pinned to Streamlit 1.40.2. In that Streamlit behavior, dynamic-row `st.data_editor` disables column sorting. Therefore V37.2 did not fully satisfy the requirement for **all** tables even though the separate legacy sort selectors had been removed.

## V38 implementation

### Read-only tables

`render_static_table()` uses the native Streamlit dataframe grid. Clicking a header performs native ascending/descending sorting.

### Editable tables

`sortable_data_editor()` intercepts callers that request dynamic rows. The underlying Streamlit editor is always rendered with `num_rows="fixed"`, preserving native header sorting. Row management is preserved with explicit `➕ Thêm dòng` and `🗑 Xóa dòng đã chọn` controls managed by the shared wrapper.

This keeps one sorting interaction only: **the column header itself**.

### Legacy sort removal

The shared table layer no longer contains or exports:

- `interactive_sort_frame`
- `sort_frame`
- `ORIGINAL_ORDER_LABEL`
- `ASC_LABEL`
- `DESC_LABEL`
- the old `Sort theo cột / Thứ tự` selectors

### TTM contract

`prefer_ttm_latest()` places a real TTM row at the latest/default end of period tables while preserving the relative order of non-TTM rows.

`default_latest_period_index()` / `default_latest_period()` provide the same rule for period selectors:

- TTM present → default TTM;
- no TTM → default latest available real period;
- never create or calculate a synthetic TTM inside the table layer.

Canonical TTM remains upstream-owned through the Trecapital data layer / `append_ttm_row()`.

## QA result

Target workflow: **Deep Analysis V38 — Header Sort Everywhere + TTM Latest**  
Run ID: **34023498982**  
Result: **PASS**

Passed gates:

1. `QA 1 — Header-sort contract` — PASS.
2. `QA 2 — TTM coverage and no fabrication` — PASS.
3. `QA 3 — Full Deep Company Analysis regression` — PASS.
4. `Static audit — old sort implementation is gone` — PASS.
5. `Static audit — every Streamlit table goes through the shared renderer` — PASS.
6. `Audit possible HTML table renderers` — completed successfully.
7. `Audit period selectors` — completed successfully.
8. `Streamlit smoke` — PASS.

The workflow also uploaded the Streamlit smoke log artifact for traceability.

**Status: PASS — V38 verified on `feature/deep-company-analysis-sort-ttm-v38`.**
