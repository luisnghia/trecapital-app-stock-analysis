# Chapter 7 V37.1 — Management Discovery Hotfix Audit

Status: PASS

- Empty Management Profile triggers candidate-manager discovery from company/IR sources.
- Candidate identity filtering rejects organization, navigation, document-heading and place fragments before they enter the manager dataset.
- Related-person wording is recognized only when the relationship label immediately follows the name, so a later manager name cannot create a false relation match.
- Related-person wording does not borrow a nearby board/executive role.
- Research-target selection is candidate-only and explicitly covers strongest available Chairman and CEO candidates before filling the remaining top-five queue.
- Official table rows without Ông/Bà remain accepted only when a recognized management role is locally supported.
- Signed official disclosures where a role precedes the manager name remain supported.
- Compound titles remain specificity-first: Deputy CEO/Vice Chairman/Independent Director do not collapse into generic embedded titles.
- Management-related official PDFs remain prioritized ahead of generic IR category pages.
- Future tenure-end years are capped for ranking and are not treated as future source dates.
- Discovered identities remain analyst-verification candidates and never overwrite Management Profile.
- No automatic OO/LT/HH, Lion/Hyena, Management Quality, insider Buy/Sell, MOS or Research Gate conclusion.
- DGC Round 5H strict production-path live acceptance passed with no noise identity in the manager dataset or research-target queue.
- Unified Streamlit smoke passed.
