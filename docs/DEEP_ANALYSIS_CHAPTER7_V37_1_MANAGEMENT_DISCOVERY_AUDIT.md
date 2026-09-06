# Chapter 7 V37.1 — Management Discovery Hotfix Audit

Status: PASS

- Empty Management Profile triggers candidate-manager discovery from company/IR sources.
- Person parsing excludes action phrases such as “giữ chức vụ”.
- Heading/navigation strings such as CBTT, BIÊN BẢN, GIẤY ĐỀ CỬ, Tiếng Việt and BOARD OF MANAGEMENT cannot enter manager research targets.
- Official table rows without Ông/Bà are accepted only when a recognized management role is local to the same/adjacent layout line.
- Signed official disclosures where a role precedes the manager name are supported with a narrow local parser.
- Role phrases act as deterministic delimiters between manager names and titles even when PDF layout spacing collapses.
- Flattened HTML with multiple Ông/Bà manager rows is segmented per person before role resolution.
- Role extraction is row-local so adjacent manager rows cannot leak titles into each other.
- Compound titles use specificity-first matching: Deputy CEO/Vice Chairman/Independent Director do not collapse into generic embedded titles.
- Management-related official PDFs are prioritized ahead of generic IR category pages.
- Chairman/CEO/other senior-role abbreviations are normalized without changing analyst-owned conclusions.
- Current official governance, financial, annual-report and personnel disclosures are prioritized.
- URL fragments are de-duplicated before crawl scheduling.
- Discovered identities remain analyst-verification candidates and never overwrite Management Profile.
- No automatic OO/LT/HH, Lion/Hyena, Management Quality, insider Buy/Sell, MOS or Research Gate conclusion.
- DGC Round 5F production-path live acceptance passed.
- Unified Streamlit smoke passed.
