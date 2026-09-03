# Trecapital — Chapter 4 Phase 4B Quantitative Bridge

## Status

Implementation phase following the approved Chapter 4 Source-Locked Core.

Branch: `feature/deep-company-analysis-checklist`

## Objective

Connect canonical Trecapital financial data to Q16/Q17/Q19/Q20 without creating any automatic qualitative conclusion.

**AI/Data = Research Assistant; User = Investment Analyst.**

Phase 4B is intentionally data-first and read-mostly. It must not infer:
- sustainable competitive advantage;
- pricing power;
- good/bad industry;
- competition intensity;
- supplier quality/relationship;
- BUY/HOLD/SELL;
- Research Gate changes.

## Quantitative bridges

### Q16 — Pricing Power context
Shows up to 10 annual observations of:
- revenue growth;
- gross margin;
- EBIT/core operating margin;
- FCF margin.

No price increase is inferred from margin movement. Explicit pricing/volume/customer evidence remains necessary for a Pricing Event record.

### Q17 — Industry economics / ROIC distribution
Analyst supplies a peer ticker set. The target ticker is always included. Only peers with local/current canonical Trecapital bundles are used.

For each company:
- latest ROIC;
- 5Y ROIC median;
- 10Y ROIC median;
- 10Y min/max;
- gross margin;
- EBIT margin;
- FCF margin;
- CCC;
- inventory turnover;
- data period and provenance.

Industry distribution:
- peer count with valid ROIC;
- median;
- P25/P75;
- min/max;
- spread;
- % positive ROIC.

No Good/Mixed/Bad classification is generated.

A button may copy canonical numeric peer values into the existing Q17 peer table. It preserves the analyst Comment field and does not touch the Q17 qualitative conclusion.

### Q19 — Table 4.2 quantitative benchmark
Shows, by metric:
- target;
- peer median;
- peer min;
- peer max.

Min/max are descriptive and deliberately not called `Best` or `Ideal`. The analyst must choose the Ideal Business source and explain why.

### Q20 — Supply-chain operating context
Shows annual history of:
- inventory turnover;
- CCC;
- DSO;
- DIO;
- DPO.

These are operating metrics only. DPO increase does not imply a better supplier relationship; inventory turnover does not imply supplier quality.

## Peer-set behavior

- Peer tickers are entered explicitly by the analyst.
- App does not guess peers from an industry label.
- Target is automatically included.
- Up to 12 tickers are retained for the UI bridge.
- A peer without canonical cache is displayed as missing and excluded from quantitative statistics.
- No unrelated ticker data is substituted.

## Provenance

Each company snapshot carries:
- source label;
- source module;
- data origin;
- data period.

Financial data remains sourced from Trecapital Module 1 normalized data. Chapter 4 does not create a parallel parser/source.

## Guardrails

The quantitative snapshot explicitly carries false flags for:
- `auto_moat_conclusion`
- `auto_pricing_power_conclusion`
- `auto_industry_quality_conclusion`
- `auto_competition_intensity_conclusion`
- `auto_supplier_quality_conclusion`

Tests assert these stay false.

## Acceptance tests

Phase 4B tests cover:
1. annual-vs-TTM treatment for latest vs historical medians;
2. 5Y/10Y ROIC medians;
3. descriptive peer distribution only;
4. no Ideal Company auto-selection;
5. margin history never becomes pricing-event inference;
6. supply-chain metrics never become supplier judgement;
7. missing ROIC stays missing rather than fabricated.

## Formula documentation

See:

`docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER4_FORMULAS.md`

## Next phase

Phase 4C — Research Assistant evidence bridge:
- moat supporting + counter-evidence;
- explicit pricing evidence;
- industry evolution/regulation;
- competitor/substitute/failure evidence;
- supplier/commodity evidence;
- no overwrite of analyst fields.
