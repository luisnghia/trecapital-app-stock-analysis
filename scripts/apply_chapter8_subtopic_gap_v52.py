from __future__ import annotations

"""Wire the V52 Chapter 8 research wrapper into the existing analyst UI.

This script performs one narrow, idempotent source edit. It does not alter storage, analyst
assessments, canonical financial data, or Chapter 7 manager identities.
"""

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter8_page_support.py")
OLD = "from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS, Chapter8ResearchAgent"
NEW = "from modules.deep_company_analysis.chapter8_research_v52 import CANDIDATE_COLUMNS, Chapter8ResearchAgent"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if NEW in text:
        print("V52 Chapter 8 research wrapper already wired; no change needed.")
        return
    if OLD not in text:
        raise SystemExit("Expected Chapter 8 research import not found; refusing unsafe broad edit.")
    updated = text.replace(OLD, NEW, 1)
    PATH.write_text(updated, encoding="utf-8")
    print("Wired Chapter 8 UI to chapter8_research_v52.Chapter8ResearchAgent.")


if __name__ == "__main__":
    main()
