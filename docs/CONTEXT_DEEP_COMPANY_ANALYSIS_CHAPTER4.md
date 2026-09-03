# Trecapital — Deep Company Analysis — Chapter 4 Context (APPROVED)

## Status

Approved by user after final design review. Implementation target: `feature/deep-company-analysis-checklist`.

Chapter title from Michael Shearn, *The Investment Checklist*:

**Chapter 4 — Evaluating the Strengths and Weaknesses of a Business and Industry**

Questions:
- Q15 — Does the business have a sustainable competitive advantage and what is its source?
- Q16 — Does the business possess the ability to raise prices without losing customers?
- Q17 — Does the business operate in a good or bad industry?
- Q18 — How has the industry evolved over time?
- Q19 — What is the competitive landscape, and how intense is the competition?
- Q20 — What type of relationship does the business have with its suppliers?

## Core principle

**AI/Data = Research Assistant; User = Investment Analyst.**

Chapter 4 is not a scoring model. Do not create Moat Score, Chapter Score, BUY/HOLD/SELL or automatic Research Gate changes. Research completeness is separate from investment quality.

Every analytical object should follow:

`Source/Factor → Specific Object → Economic Mechanism → Supporting Evidence → Counter-Evidence → Current Assessment → Trend → What Could Change It? → Confidence → Analyst Conclusion → Review History`

AI/data updates must never overwrite saved analyst Assessment, Trend, Confidence or Conclusion.

---

# Q15 — Sustainable Competitive Advantage

## Approved source structure

Six Shearn sources plus one clearly labeled analyst extension:
1. Network Economics — Shearn
2. Brand Loyalty — Shearn
3. Patents — Shearn
4. Regulatory Licenses — Shearn
5. Switching Costs — Shearn
6. Cost Advantages from Scale / Location / Unique Asset — Shearn
7. Other Source — Analyst-defined

Each source may contain multiple **Specific Advantages**.

Each specific advantage records:
- Specific Advantage
- Economic Mechanism
- Supporting Evidence
- Counter-Evidence
- Competitor Comparison
- Copyability
- Time to Copy/Replace
- Structural Character
- Current Strength
- Trend: Expanding / Stable / Deteriorating / Mixed / Unknown
- Why Trend?
- Primary Erosion Threat
- Reinvestment Inside Advantage
- Confidence
- Analyst Conclusion

Q15 must distinguish competitive strength from sustainable competitive advantage. The app must force a copy/replace and durability test rather than label a brand, patent, customer service, scale or resource access as a moat automatically.

### Source-specific logic

**Network Economics:** utility as participants increase, participant quality, critical mass, multi-homing, user/node retention, network strengthening vs weakening.

**Brand Loyalty:** what the brand means to customers, loyalty vs awareness, premium willingness, repeat purchase, discount dependence, brand investment and deterioration.

**Patents:** commercial value, product/revenue/profit relevance only if explicitly disclosed, expiry, bypass/technology obsolescence and post-expiry economics.

**Regulatory Licenses:** regulator, scarcity of licenses, time/cost to obtain, price/capacity controls, legislation threats and whether regulation protects market access or economic returns.

**Switching Costs:** cash cost, retraining, migration/integration, operational risk, product embeddedness, time-to-switch, retention/churn evidence and technology that makes switching easier.

**Cost Advantages:** organize evidence around scale, industry consolidation, location and unique-asset access. Do not infer cost moat only from high gross margin. Compare actual cost position and ask whether peers can replicate it and how long that would take.

**Analyst-defined:** permitted, but must be explicitly labeled and pass the same mechanism/copyability/durability/counter-evidence tests.

### Q15 overall fields
- Sustainable Competitive Advantage Exists: Yes / Partial / No / Unknown
- Primary Source(s)
- Strongest Advantage
- Advantage Expanding Most
- Advantage Deteriorating Most
- Overall Moat Trend
- Copy/Replace Threat
- Technology Threat
- Regulatory Threat
- Right Place / Right Time Risk
- Strongest Counter-Evidence
- Reinvestment Runway Inside the Moat
- Analyst Confidence
- Analyst Conclusion

---

# Q16 — Pricing Power

Question: can the business raise price without losing customers?

Approved structure:

## Four common characteristics examined in the book
1. High Customer Retention
2. Low Price Sensitivity
3. Profitable Customer Business Models
4. High-Quality Products/Services where quality matters more than price

Plus a dedicated **Technology / Price Transparency Threat** section.

## Pricing Event Timeline
Every explicit price increase is a separate record:
- Period
- Product / Segment
- Price Increase %
- Volume Change %
- Retention / Churn Change
- Cost Inflation %
- Gross Margin %
- EBIT Margin %
- Competitor Price Change
- Nature
- Evidence
- Analyst Interpretation

Nature must distinguish:
- True Pricing Power
- Cost Pass-through
- Commodity / Shortage Pricing
- Promotional / Mix Effect
- Unknown

Never infer price increases from margin changes alone.

## Pricing scope by segment/product
- Segment / Product
- Revenue Relevance — only if disclosure/canonical data supports it
- Profit Relevance — only if disclosure supports it
- Pricing Power — analyst
- Trend — analyst
- Evidence

Overall:
- Pricing Power: Strong / Moderate / Weak / None / Unknown
- Nature: Structural / Temporary / Cost-pass-through / Commodity-Shortage / Mixed / Unknown
- Scope: Company-wide / Segment-specific / Unknown
- Trend: Expanding / Stable / Deteriorating / Mixed / Unknown
- Best Evidence
- Strongest Counter-Evidence
- Main Erosion Threat
- Confidence
- Conclusion

---

# Q17 — Good or Bad Industry

Central question: **How easy is it for businesses in this industry to make money?**

Do not infer industry quality from target-company ROIC alone.

## Industry ROIC distribution
Use canonical peer data in later phases to compare:
- latest ROIC
- 5Y median
- 10Y median
- min/max
- industry median / P25 / P75 / spread
- best/worst
- target vs industry

No automatic Good/Bad conclusion.

## Industry economics factors
Maintain the Shearn/Lister-style research groups disclosed in the book:
- What drives the industry?
- How do companies compete within the industry?
- What is the larger macro picture?
- What are the industry trends?
- Average Cash Conversion Cycle
- Exposure to cyclical markets
- Ability to pass on price increases
- Volatility of customer demand

Analyst-defined industry factors may be added but must be labeled.

## Best vs Worst
Compare why the best company makes money and the worst does not. Analyst must answer whether target performance comes from industry economics or company-specific advantage.

Overall:
- Industry Economics: Good / Mixed / Bad / Unknown
- Ease of Making Money
- ROIC Structure
- Demand Quality
- Pricing Environment
- Barriers
- Capital Intensity
- Cyclicality
- Trend
- Structural vs Temporary Drivers
- Main Positive / Main Negative
- Target good because industry good vs company-specific excellence
- Confidence
- Conclusion

---

# Q18 — Industry Evolution

Research horizon should generally be **more than 10 years** when evidence is available.

## Industry Evolution Timeline
Each major event/force records:
- Period
- Event / Force
- Category
- Origin
- Industry Before
- What Changed
- Industry After
- Impact on Demand
- Impact on Supply
- Impact on Pricing
- Impact on Margin
- Impact on ROIC
- Impact on Competition
- Winners / Losers
- Structural / Temporary
- Evidence
- Analyst Interpretation

Trecapital organization categories (not Shearn taxonomy): Technology, Regulation, Capacity, Consolidation, Customer Behavior, Distribution, Globalization, Substitute, Cost, Other.

## Then vs Now
Compare customer choice, pricing model, distribution, supply, competition, margin structure, capital requirements and profitability.

## Management Claim vs Industry History
Use history to test management claims; do not accept synergy/consolidation/scale narratives without historical support.

## Current Regime
- Current Industry Regime
- Regime Start
- Force that created current regime
- Previous regime
- What broke previous economics
- Next potential inflection point
- Early evidence regime is changing

Overall Q18: Improving / Stable / Deteriorating / Structural Transition / Unknown. Q18 describes evolution; Q17 decides Good/Bad economics.

---

# Q19 — Competitive Landscape

Preserve the eight research directions used by Shearn:
1. Does the business have limited competition?
2. Does the industry change often?
3. How do competitors compete, and how could that change?
4. How fiercely do businesses compete?
5. Substitute products
6. Low-cost country competition
7. Which competitor sets the industry standard? / ideal business
8. Why have competitors failed?

## Competitor Master Table
- Competitor
- Type: Direct / Indirect / Substitute / Foreign / New Entrant
- Segment
- Geography
- Market Share
- Customer Overlap
- Key Strength / Weakness
- Status
- Trend
- Evidence

## Competition modes
Four Shearn modes:
- Capital
- Service
- Price
- Copying

Plus Other — Analyst-defined.

Each mode records current importance, target position, best competitor, supporting/counter-evidence, trend, what could change it and analyst conclusion.

## Fierceness
Track number/size of meaningful competitors, industry maturity, capacity, price wars, below-economic pricing, acquisition/retention costs and irrational market-share pursuit.

## Substitutes
Each substitute is separate, with function replaced, price/performance/convenience advantage, adoption level/trend, time to threat, target response and analyst threat assessment.

## Low-cost country competition
Compare labor/input/energy/freight/tariff/quality/lead-time/delivered-cost economics. Analyst determines threat and trend.

## Industry Standard / Ideal Business — Table 4.2 implementation
Use peer operating/financial metrics in later phases, then allow analyst to combine the best characteristics into an Ideal Business. AI may suggest; analyst selects the ideal source and interprets the gap.

## Competitor Failures
Study failed competitors, root causes, early warnings, strategy/operating mistakes, financial consequences, whether target shares the risk and analyst lesson.

Overall:
- Competition Intensity: Limited / Moderate / Intense / Extreme / Unknown
- Trend: Easing / Stable / Intensifying / Mixed
- Dominant Competition Mode
- Industry Leader
- Target vs Ideal Business
- Biggest Direct Threat
- Biggest Substitute Threat
- Foreign Competition Threat
- Irrational Competition Risk
- Most Important Failure Lesson
- Confidence
- Conclusion

---

# Q20 — Supplier Relationships

Do not equate squeezing suppliers with good supplier economics. Analyze relationship quality, reliability, innovation, concentration and commodity/resource dependence.

## Reliable sources of supply
Supplier Map:
- Supplier / Group
- Input
- % Supply if Disclosed
- Criticality
- Alternative
- Switching Time
- Geography
- Reliability
- Relationship
- Trend
- Capacity Risk
- Financial Health
- Disruption History
- Evidence

If supplier concentration is not disclosed, keep Unknown; do not infer diversified suppliers.

## Supply Chain Management
Later Phase 4B links canonical inventory turnover and peer/trend comparison. Inventory turnover alone does not determine supplier quality.

## Supplier Innovation
Track joint innovation, customer feedback shared, result, competitive benefit, trend and evidence.

## Supplier Concentration
Assess material suppliers, alternatives, qualification/switching time, capacity and financial risk.

## Commodity Resource Dependence
Each commodity:
- Business Use
- % COGS if disclosed
- Historical Volatility
- Current Price Trend
- Pass-through Ability
- Lag to Pass Through
- Hedge / Hedge Duration
- Alternatives
- Earnings Sensitivity
- Analyst Assessment
- Evidence

Cross-check Q20 commodity exposure with Q16 pass-through/pricing power.

Overall:
- Supplier Relationship: Collaborative / Balanced / Transactional / Adversarial / Unknown
- Supply Reliability
- Supplier Concentration
- Commodity Dependence
- Supply-chain efficiency
- Supplier innovation
- Trend
- Biggest Supply Risk
- Biggest Supplier Strength
- Confidence
- Conclusion

---

# Cross-Question Consistency Engine

Trecapital implementation layer, not a new Shearn question. It only raises review warnings; it never changes analyst conclusions or Research Gate.

Examples:
- Q15 brand/advantage strong but Q16 pricing/retention evidence conflicts
- Q16 pricing power high while price changes are only pass-through/commodity shortage
- Q17 industry Good while Q18 regime is deteriorating/structural transition
- Q15 cost advantage threatened by Q19 foreign delivered-cost economics
- Q19 limited direct competition while substitutes are material
- Q20 supply reliability strong while supplier concentration is high
- Q20 commodity dependence high + Q16 pricing power weak → margin vulnerability
- analyst Moat Trend stable while specific advantages are deteriorating

---

# Evidence Architecture

Evidence rows should support:
- Question
- Claim
- Evidence Type
- Source Title
- Source URL/File
- Source Date
- Period represented
- Evidence Text
- Direction: Supporting / Contradicting / Neutral
- Status: Candidate / Verified
- Data Origin
- Analyst Note

Counter-evidence should be visible beside supporting evidence, especially for moat, pricing power and competitive intensity.

---

# Persistence — Phase 4A

Local/offline database:

`data_cache/deep_company_analysis_chapter4.db`

Master:
- `chapter4_current`
- `chapter4_snapshots`

Analytical child tables:
- `chapter4_advantages`
- `chapter4_advantage_history`
- `chapter4_pricing_events`
- `chapter4_pricing_segments`
- `chapter4_industry_peers`
- `chapter4_industry_factors`
- `chapter4_industry_events`
- `chapter4_competitors`
- `chapter4_competition_modes`
- `chapter4_substitutes`
- `chapter4_ideal_business`
- `chapter4_competitor_failures`
- `chapter4_suppliers`
- `chapter4_commodity_exposure`
- `chapter4_evidence`
- `chapter4_research_gaps`

Financial/source-of-truth data must remain canonical Trecapital data; SQLite stores analyst/research state and snapshots, not a parallel financial data source.

---

# Phase plan

## Phase 4A — Source-Locked Core
- Q15–Q20 analyst workspace
- six Q15 Shearn sources + analyst-defined source
- Table 4.1 Moat Copyability skeleton
- Q16 pricing event/segment skeleton
- Q17 industry factor/peer skeleton
- Q18 >10Y timeline skeleton
- Q19 8-subquestion structure + Table 4.2 Ideal Business skeleton
- Q20 supplier/commodity skeleton
- evidence/counter-evidence matrix
- research gaps
- consistency warnings
- persistence + append-only snapshots
- no AI/data conclusions

## Phase 4B — Quantitative Bridge
- canonical historical margins
- peer ROIC distribution
- CCC / inventory turnover where appropriate
- pricing analytics only from valid fields/disclosures
- peer/ideal-company quantitative bridge
- provenance

## Phase 4C — Research Assistant
- moat evidence + counter-evidence
- explicit pricing evidence
- industry history/regulatory/competitive evidence
- competitor failures
- supplier evidence
- no analyst overwrite

## Phase 4D — DGC End-to-End Lock
- DGC live acceptance
- no-fabrication guardrails
- evidence-quality audit
- Chapters 1–4 regression
- unified-page smoke test
- lock Chapter 4 only after acceptance passes

---

# Non-negotiable guardrails

- Brand mentioned ≠ moat.
- Patent exists ≠ moat.
- Gross margin rises ≠ pricing power.
- Commodity price/shortage pricing ≠ sustainable pricing power.
- Target ROIC high ≠ good industry.
- One exceptional peer ≠ industry economics.
- Export share ≠ competitor or supplier concentration.
- Supplier name ≠ purchase concentration.
- DPO increase ≠ good supplier relationship.
- Missing disclosure = Unknown, not inferred.
- AI/data refresh never overwrites analyst judgement.
- Conflicting evidence is surfaced, not silently resolved.
- Consistency warnings do not change Research Gate.
- No BUY/HOLD/SELL in Chapter 4.
