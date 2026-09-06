from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from modules.deep_company_analysis.chapter7_management_discovery import choose_research_targets
from modules.deep_company_analysis.chapter7_research import Chapter7ResearchAgent, evidence_quality_summary


def main() -> None:
    Path("reports").mkdir(parents=True, exist_ok=True)
    cache = Path("data_cache/ch7_hotfix_dgc")
    cache.mkdir(parents=True, exist_ok=True)

    ticker = "DGC"
    company_name = "Tập đoàn Hóa chất Đức Giang"
    research = Chapter7ResearchAgent(cache).search(
        ticker,
        company_name,
        managers=[],
        max_results_per_query=2,
    )

    managers = (
        research.manager_candidates.copy()
        if isinstance(research.manager_candidates, pd.DataFrame)
        else pd.DataFrame()
    )
    candidates = research.candidates.copy()
    quality = evidence_quality_summary(candidates)
    research_targets = choose_research_targets(managers, max_targets=5)

    if candidates.empty:
        extracted = pd.DataFrame()
        manager_scoped = pd.DataFrame()
    else:
        extracted = candidates[
            candidates["Explicitness"].astype(str).str.contains(
                "Extracted official source text", na=False
            )
        ]
        manager_scoped = candidates[
            candidates["Manager"].astype(str).str.strip().ne("")
        ]

    roles = set(
        managers.get("Role Normalized", pd.Series(dtype="object")).astype(str)
    )
    names = set(managers.get("Manager", pd.Series(dtype="object")).astype(str))
    unique_names = {name.strip() for name in names if name.strip()}

    questions_with_official = sorted(
        set(
            extracted.get("Question", pd.Series(dtype="object")).astype(str)
        )
    )

    report: dict[str, object] = {
        "ticker": ticker,
        "research_note": research.note,
        "manager_candidate_rows": int(len(managers)),
        "unique_manager_names": sorted(unique_names),
        "research_targets": research_targets,
        "roles": sorted(roles),
        "research_candidate_rows": int(len(candidates)),
        "official_extracted_rows": int(len(extracted)),
        "manager_scoped_rows": int(len(manager_scoped)),
        "questions_with_official_extracted": questions_with_official,
        "quality": quality.to_dict("records"),
        "critical_errors": [],
        "warnings": [],
    }

    critical = report["critical_errors"]
    warnings = report["warnings"]
    assert isinstance(critical, list)
    assert isinstance(warnings, list)

    if len(unique_names) < 3:
        critical.append(
            f"Expected >=3 unique discovered managers, got {len(unique_names)}."
        )
    if "Chairman" not in roles:
        critical.append(
            "Chairman role was not discovered from DGC official/company sources."
        )
    if "CEO" not in roles:
        critical.append(
            "CEO role was not discovered from DGC official/company sources."
        )

    noisy = {
        "báo", "thay", "đổi", "nhân", "sự", "qua", "bầu", "nghị",
        "quyết", "thông", "tin", "công", "bố", "xem", "thêm", "giữ",
        "chức", "vụ", "được", "đảm",
    }
    for name in unique_names:
        if any(token.casefold() in noisy for token in str(name).split()):
            critical.append(
                f"Noise/action heading was misidentified as a manager: {name}"
            )

    if len(extracted) < 3:
        critical.append(
            f"Expected >=3 extracted official evidence candidates, got {len(extracted)}."
        )
    if len(manager_scoped) < 2:
        critical.append(
            f"Expected >=2 manager-scoped research candidates, got {len(manager_scoped)}."
        )
    if "Q33" not in set(questions_with_official):
        critical.append(
            "No extracted official Q33 management identity/background evidence."
        )

    if "Q36" not in set(questions_with_official):
        warnings.append(
            "No extracted official Q36 career/chronology evidence in this crawl."
        )
    if "Q37" not in set(questions_with_official):
        warnings.append(
            "No extracted official Q37 compensation/ownership evidence in this crawl; analyst gap remains open."
        )
    if "Q38" not in set(questions_with_official):
        warnings.append(
            "No extracted official Q38 insider-transaction evidence in this crawl; no transaction is inferred."
        )

    managers.to_csv(
        "reports/DGC_V37_1_discovered_managers.csv",
        index=False,
        encoding="utf-8-sig",
    )
    candidates.to_csv(
        "reports/DGC_V37_1_research_candidates.csv",
        index=False,
        encoding="utf-8-sig",
    )
    quality.to_csv(
        "reports/DGC_V37_1_quality.csv",
        index=False,
        encoding="utf-8-sig",
    )
    Path("reports/DGC_V37_1_ROUND3.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("reports/DGC_V37_1_ROUND3.md").write_text(
        "# DGC V37.1 Round 3\n\n"
        f"- Unique managers: {len(unique_names)}\n"
        f"- Manager candidate rows: {len(managers)}\n"
        f"- Research targets: {research_targets}\n"
        f"- Roles: {sorted(roles)}\n"
        f"- Research candidates: {len(candidates)}\n"
        f"- Extracted official candidates: {len(extracted)}\n"
        f"- Manager-scoped candidates: {len(manager_scoped)}\n"
        f"- Warnings: {warnings}\n"
        f"- Critical errors: {critical}\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if critical:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
