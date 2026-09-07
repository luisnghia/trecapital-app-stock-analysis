# Chapter 10 Phase 10C / V76 — Canonical Data Bridge

## Scope

Phase 10C connects the Chapter 10 Q53-Q57 evidence schema to caller-supplied canonical company/financial payloads. It is deliberately a **read-only bridge**, not a new financial engine and not a research/analyst conclusion engine.

Source lock remains Michael Shearn, *The Investment Checklist*, Chapter 10, printed pages 281-303, Q53-Q57. The 34 Phase 10B evidence dimensions are unchanged.

## Contract

`modules/deep_company_analysis/chapter10_data_bridge.py`:

- reads existing canonical values through a small alias map;
- supports common canonical containers (`metrics`, `financials`, `canonical`, `canonical_metrics`, `derived_metrics`, `facts`, and root);
- maps dependency availability to the 34 Chapter 10 evidence dimensions;
- preserves source/as-of/container/key provenance;
- leaves qualitative dimensions `Unknown` until research/analyst evidence exists;
- never changes the analyst-owned Chapter 10 payload;
- creates no growth score, growth forecast, valuation conclusion, MOS change, Research Gate change, or BUY/HOLD/SELL signal.

## CCC boundary

Q57 names the cash-conversion cycle. V76 consumes `ccc` / `cash_conversion_cycle` only when that value already exists in the canonical SSOT. If DIO, DSO and DPO exist but canonical CCC does not, the bridge returns CCC as `Unknown` and records that Chapter 10 does not recompute it.

This is intentional. The bridge may expose canonical DIO/DSO/DPO as evidence/provenance, but `CCC = DIO + DSO - DPO` remains a financial-SSOT responsibility rather than a Chapter 10 formula implementation.

## Unknown-first behavior

Missing canonical values do not become negative evidence. A missing dependency is reported explicitly as a research/data gap. A dimension with no quantitative SSOT dependency remains `Unknown` and must be handled by later source research and analyst review.

## Deferred

Phase 10C adds no Streamlit UI, persistence/database, web research, AI research assistant, historical snapshot, or consolidated report integration. Those belong to later Chapter 10 phases.
