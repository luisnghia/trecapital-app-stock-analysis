# Chapter 11 — Phase 11C / V84 — Canonical Data Bridge

## Scope

Phase 11C extends the Chapter 11 source-locked research contract for Michael Shearn's *The Investment Checklist*, Chapter 11 — **Evaluating Mergers & Acquisitions**. The source range remains exactly Q58-Q59 and the 15 evidence dimensions defined in V83.

- Q58: How does management make M&A decisions?
- Q59: Have past acquisitions been successful?

## Purpose

V84 connects quantitative/data-dependent Chapter 11 evidence dimensions to the application's existing canonical data/financial SSOT using a read-only bridge. It does not create a second financial engine and does not fetch external data.

The bridge can surface canonical availability for dependencies such as segment revenue, revenue, operating expenses/margin, debt, interest expense, customer retention, employee count/turnover, acquisition consideration, EBIT, EBITDA, free cash flow, book value, cash, debt coverage, equity issuance and shares outstanding.

## Neutral evidence behavior

A dimension with no canonical dependency remains `Unknown` and requires analyst/research evidence. A dimension with one or more canonical facts available becomes `Evidence found`, but its evidence direction remains `Unknown`. Partial availability is explicitly reported; it is never interpreted as favorable or unfavorable.

## SSOT boundary

Chapter 11 does **not** calculate or reconstruct:

- EV/EBIT
- EV/EBITDA
- EV/FCF
- book-value premium
- leverage
- debt coverage
- equity dilution
- acquisition returns
- synergy realization

These calculations, if available in the application, remain upstream canonical SSOT responsibilities. Chapter 11 consumes existing values/facts only.

## Analyst ownership

The bridge preserves the supplied analyst payload and does not automatically change question status, confidence, analyst assessment, dimension status or evidence. It does not create an M&A score, acquisition-success conclusion, synergy forecast, BUY/HOLD/SELL signal, intrinsic value, MOS adjustment or Investment Research Gate change.

## Deliverables

- `modules/deep_company_analysis/chapter11_data_bridge.py`
- `modules/deep_company_analysis/test_chapter11_phase11c.py`
- `scripts/qa_chapter11_data_bridge_v84.py`
- `docs/FORMULA_EXPLANATION_CHAPTER11_PHASE11C_V84.md`
- `.github/workflows/chapter11-phase11c-data-bridge-v84.yml`

## Next phase

The next logical phase is Chapter 11 Phase 11D: source research / Research Assistant bridge for qualitative dimensions and remaining Unknown data gaps, while preserving analyst ownership of every qualitative conclusion.
