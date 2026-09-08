# Formula / Data Explanation — Appendix C Phase B V97

Appendix C V97 introduces **no new financial formula** and no duplicate financial SSOT.

## Display logic

For each source-locked Qxx item, V97 reads only the matching owner chapter fields when available:

- Research status = owner payload `question_status[Qxx]`, otherwise `Unknown`.
- Confidence = owner payload `confidence[Qxx]`, otherwise `Unknown`.
- Analyst assessment = owner payload `analyst_assessment[Qxx]`, otherwise `Unknown`.

Section and whole-book summaries are simple integer counts by status (`Unknown`, `Partial`, `Answered`, `N/A`). They are deliberately **not converted to a weighted percentage or score** and carry no investment meaning.

## Formatting contract

Appendix C is a text/research navigation view, so no financial values are recalculated or reformatted. When a user follows a Qxx reference to its owner chapter, all tables, units, decimal precision, negative-number treatment, dates, financial periods, and chart formatting remain governed by the existing DCA/financial SSOT formatting rules in that owner workspace.

## Prohibited derivations

V97 does not derive management quality, growth quality, checklist score, valuation, intrinsic value, margin of safety, Research Gate, BUY/HOLD/SELL, or any other investment recommendation from research-completeness counts.
