# Deep Analysis V37.2 — Native Header Sort + TTM Latest

Status: PASS

- Removed the visible `Sort theo cột / Thứ tự` controls from the shared table layer.
- Read-only tables use Streamlit native dataframe grids; users sort by clicking the column header.
- Editable tables no longer receive a separate sort widget; they use the native Streamlit editor behavior.
- Chapter 1 Opportunity Inventory, Gate History, and Monitoring Review Queue migrated from custom static HTML to the shared native grid.
- TTM, when already present in canonical data, is kept as the latest/default displayed period.
- No TTM row is fabricated when canonical TTM is unavailable.
- Existing numeric units/precision and positive/negative heat rules remain in the shared table layer.
- Full Deep Company Analysis regression and Streamlit smoke passed.
