# Interaction performance verification — 2026-10-06

Production comparison: previous source commit `ee4f44f701be00c3d3d3edc4795b343458a42c7d` versus this change, using installed Docker application sources, Streamlit 1.63.0, Python 3.12, one machine, and the same isolated synthetic SQLite dataset. Each result is the median of five warm runs. The cloud Docker build separately runs all QA on Python 3.11.

The dataset contains 160 authorized customer-work cases with multiline notes; QLKH and CBHT each own 80. Leader and Admin can see all 160. Counts and filtering still use the complete fresh dataset. Pagination renders at most 24 cards per page, preserves order and exposes all pages. Closed priority groups render their cards when expanded.

## Actual application and navigation timings

These are AppTest script/interaction wall times, including the click and requested reruns for navigation. They are not network or physical-device input latency.

| Role | Flow | Before (ms) | After (ms) | Speedup |
|---|---|---:|---:|---:|
| QLKH | Customer work | 231.46 | 44.96 | 5.15× |
| QLKH | Today / priority | 255.78 | 40.17 | 6.37× |
| QLKH | Click → Today | 272.76 | 47.06 | 5.80× |
| QLKH | Click → Customer work | 272.00 | 41.88 | 6.49× |
| QLKH | Weekly plan (empty fixture) | 51.40 | 48.23 | 1.07× |
| QLKH | Case detail | 35.39 | 33.60 | 1.05× |
| CBHT | Customer work | 231.84 | 40.05 | 5.79× |
| CBHT | Today / priority | 260.21 | 38.32 | 6.79× |
| CBHT | Click → Today | 261.37 | 37.99 | 6.88× |
| CBHT | Click → Customer work | 240.39 | 37.70 | 6.38× |
| CBHT | Weekly plan (empty fixture) | 53.97 | 46.82 | 1.15× |
| CBHT | Case detail | 37.66 | 32.24 | 1.17× |
| Leader | Customer work | 424.12 | 41.94 | 10.11× |
| Leader | Today / priority | 417.53 | 34.23 | 12.20× |
| Leader | Room dashboard | 484.14 | 48.66 | 9.95× |
| Leader | Click → Today | 466.66 | 36.76 | 12.69× |
| Leader | Click → Customer work | 434.57 | 37.17 | 11.69× |
| Leader | Weekly plan (empty fixture) | 45.03 | 39.74 | 1.13× |
| Leader | Case detail | 37.98 | 29.72 | 1.28× |
| Admin | Customer work | 453.43 | 37.13 | 12.21× |
| Admin | Today / priority | 471.27 | 38.91 | 12.11× |
| Admin | Room dashboard | 493.60 | 54.55 | 9.05× |
| Admin | Click → Today | 469.96 | 34.30 | 13.70× |
| Admin | Click → Customer work | 456.35 | 42.91 | 10.64× |
| Admin | Weekly plan (empty fixture) | 55.50 | 40.65 | 1.37× |
| Admin | Case detail | 34.47 | 34.62 | 1.00× |

Heavy lists, priority pages, room dashboards and tested navigation improve by 5.15–13.70×. Already-light weekly-plan and single-case pages improve by 1.00–1.37×; this change does not establish a universal 3× speedup for every operation. Database persistence, exports, network travel and physical iPhone/iPad keyboard paint time require separate measurements.

## Input behavior and business regression checks

- The instrumented Node DOM protocol test delivers 2,000 input events with **zero component-value or frame-height messages before Save**. It verifies phone leading zeros, all nine contact fields, local selection, retained drafts, immediate busy feedback and double-tap suppression. This is protocol verification, not a measured Safari frame-time result.
- Case-detail text drafts now remain in the browser component until their explicit action: stage update, issue creation/resolution, reschedule, cancellation and manager notes. No per-keystroke server handler or polling is added.
- The final installed runtime QA exercises actual saves for CBHT, QLKH, Leader and Admin, including persisted multiline text, exact due date/time, audit records, pending cancellation and no duplicate write on rerun. Existing contact, weekly-entry, operational-review, permission, Excel/PDF and notification tests remain build gates.
- Separate QA verifies that every paginated row remains reachable, ordering/filter resets, closed/open priority groups, stale-draft rejection and atomic notes/audit rollback.
- The card-key benchmark compares the original `inspect.stack()` implementation with frame walking at the same call site, checks identical keys and enforces a 3× minimum for that specific hot path. Whole-flow timing above is the relevant application comparison.

## Reproduction

Run `performance_flow_probe.py` against each installed revision in a separate process on the same machine. Use the same `--rounds` and `--cards`. It always creates a new temporary database, seeds synthetic users without usable login passwords, and reports all four roles. Run the Dockerfile installer/QA chain with `.streamlit/config.toml` at the working directory before measuring. Do not rerun the non-idempotent original installer chain on an already installed tree.
