# DGC — Chapter 1 trial & Trecapital auto-data audit

As-of trial: **28/08/2026**. Purpose: validate the Chapter 1 workflow; not an investment recommendation.

## 1. DGC trial result

- Ticker: DGC — CTCP Tập đoàn Hóa chất Đức Giang
- Opportunity signal: price 43,000 VND/share; 52-week high 103,000; trial drawdown 58.3%
- Quality Filter: 5/10
- Unknown: 2/10
- Research Gate: 🟡 Watch
- Target Price / MOS: intentionally blank until canonical Module 2 valuation is bridged into this page

### Table 1.1 trial

| Criterion | Analyst | Confidence | Trial rationale |
|---|---|---|---|
| Recurring Revenue | X Không | Trung bình | Revenue is product/volume/price driven; recurring-contract evidence is insufficient |
| Long Runway | ✓ Có | Trung bình | Phosphorus downstream products and Nghi Son create runway, subject to feedstock/project risks |
| Proven Management | — Chưa biết | Thấp | Historical operating track record is offset by 2026 governance/legal uncertainty |
| Franchise / Moat | ✓ Có | Trung bình | Historical technology/scale/feedstock advantages, but captive apatite disruption tests durability |
| Strong Financials | ✓ Có | Trung bình | Historically strong; H1 2026 profitability and cash conversion weakened materially |
| High ROIC | ✓ Có | Cao | Historical/canonical data support high returns on invested capital; bridge should use Trecapital field |
| Limited Competition | X Không | Trung bình | Strong domestic position does not eliminate global commodity/chemical competition |
| Low Capital Expenditures | X Không | Cao | Chemical production is capital intensive and Nghi Son is a major expansion project |
| Diversified Customer Base | — Chưa biết | Thấp | Export breadth is visible but customer concentration data is not sufficient |
| Strong Balance Sheet | ✓ Có | Cao | Cash/liquid investments and low leverage support a strong balance sheet; audit qualification remains a research item |

## 2. What Trecapital can already automate

The existing `trecapital_bridge.py` and Module 1/2 canonical data can already resolve or derive:

### Valuation / Table 1.2

- Current price
- Shares outstanding
- Market capitalization
- Cash + short-term investments
- Interest-bearing debt
- Net debt
- TEV
- EBIT
- EBITDA
- Pretax profit / normalized earnings proxy
- Interest expense
- CFO
- Capex
- FCF
- FCF Yield
- Dividend/share and Dividend Yield
- TEV/EBIT
- TEV/EBITDA
- TEV/Normalized Earnings
- Pre-Tax Earnings Yield
- Debt/EBITDA
- EBIT/Interest
- FCF estimate/share
- CCC
- Module 2 weighted Target Price when valuation is available
- MOS and Price/Target
- 10-year + TTM proxy history for the above fields where source history exists

### Table 1.1 — strong quantitative auto-suggestion candidates

- Strong Financials
- High ROIC
- Low Capital Expenditures
- Strong Balance Sheet

These should be **AI/Data Suggested**, not final analyst assessments.

## 3. Can be automated with a small extension to existing Trecapital data

- Historical valuation percentile: calculate from 10Y+TTM valuation history already produced by the bridge
- Price vs earnings/cash-flow divergence: compare normalized price history with EBIT/EPS/FCF history
- Numerical monitoring triggers: price, MOS, FCF yield, Debt/EBITDA, ROIC, margin, CCC, etc.
- Company name / industry classification from overview

## 4. Not currently available as reliable canonical fields

These require a new source layer, document evidence, AI research or analyst input:

- Exact rolling 52-week high/low and drawdown (current canonical financial bridge does not expose a 52-week field)
- Forced selling / index removal / event classification
- Why the market may be wrong
- Initial investment thesis
- Research Gate and Reason for Gate
- Recurring Revenue quality
- Long Runway final judgement
- Proven Management
- Franchise/Moat final judgement
- Limited Competition final judgement
- Customer concentration / Diversified Customer Base
- Legal/governance qualitative risk
- Critical Research Gaps

## 5. Design rule

Trecapital financial data remains the Single Source of Truth. Chapter 1 must not create a parallel financial data engine. Qualitative sources may produce evidence/suggestions, but the analyst controls Table 1.1 assessment and Research Gate.
