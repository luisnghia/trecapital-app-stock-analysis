# Appendix A — Phase B / V91

## Scope

Source lock: **Michael Shearn — The Investment Checklist — Appendix A, Building a Human Intelligence Network (print pages 323–330)**.

V91 turns the V90 source-lock contract into an analyst-owned human-intelligence workspace. It implements the book's practical direction to preserve interview details for future reference, keep source responses separate from analyst interpretation, record uncertainty rather than rationalizing ambiguous answers, and use human sources to investigate unanswered questions.

## Implemented workflow

- Human source records with source class (`Primary`, `Secondary`, `Unknown`) and source type from the V90 source universe.
- Interview database with stable IDs, interview date, prompt, verbatim/observational source response, statement type, uncertainty note, DCA question references and separate analyst commentary.
- Research-gap records linked by reference to **Q01–Q59**.
- SQLite persistence for the normalized Appendix A payload.
- Streamlit page `pages/10_Mang_nguon_tin.py` plus shared navigation entry.
- Unknown-first section status for all four Appendix A sections.

## Architecture boundary

Q01–Q59 links are references only. V91 does **not** read, clone or write the underlying chapter Research Gate, financial data, valuation data, MOS, intrinsic value, or analyst conclusions. It creates no human-source score, credibility score, weighted research score, BUY/HOLD/SELL signal, or automatic investment conclusion. It performs no automated outreach.

AI remains a **Research Assistant**. The analyst owns source classification, notes, interpretation, research-gap status and synthesis.
