from __future__ import annotations

from pathlib import Path


def patch_file(path: str, replacements: list[tuple[str, str]]) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements:
        if new in text:
            continue
        if old not in text:
            raise SystemExit(f"V6 patch anchor not found in {path}:\n{old[:500]}")
        text = text.replace(old, new, 1)
        changed = True
    if changed:
        target.write_text(text, encoding="utf-8")
        print(f"Patched {path} to Chapter 1 V6 structured triggers")
    else:
        print(f"{path} already contains V6 structured triggers")


patch_file(
    "modules/deep_company_analysis/monitoring.py",
    [
        (
'''class TriggerRule:
    kind: str
    metric: str = ""
    operator: str = ""
    threshold: Optional[float] = None
    label: str = ""
''',
'''class TriggerRule:
    kind: str
    metric: str = ""
    operator: str = ""
    threshold: Optional[float] = None
    label: str = ""
    target_period: str = ""
''',
        ),
        (
'''    "event_new": "Cao",
    "statement_new": "Trung bình",
''',
'''    "event_new": "Cao",
    "statement_new": "Trung bình",
    "statement_period": "Trung bình",
''',
        ),
        (
'''def parse_trigger(text: str) -> TriggerRule:
    original = str(text or "").strip()
    normalized = _norm(original)
    if not normalized:
        return TriggerRule("unsupported", label=original)

    if re.search(r"\\bbctc\\s*moi\\b|bao cao tai chinh moi|co bctc moi|sau bctc", normalized):
        return TriggerRule("statement_new", label="BCTC mới")
''',
'''def _specific_statement_period(normalized: str) -> str:
    patterns = (
        r"(?:bctc|bao cao tai chinh).*?q([1-4])\\s*[/\\-]\\s*(20\\d{2})",
        r"(?:bctc|bao cao tai chinh).*?(20\\d{2})\\s*[/\\-]\\s*q([1-4])",
        r"(?:sau|co).*?q([1-4])\\s*[/\\-]\\s*(20\\d{2})",
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, normalized)
        if not match:
            continue
        if index == 1:
            year, quarter = int(match.group(1)), int(match.group(2))
        else:
            quarter, year = int(match.group(1)), int(match.group(2))
        return f"{year:04d}-Q{quarter}"
    return ""


def _period_rank(value: Any) -> Optional[int]:
    normalized = _norm(value)
    if not normalized:
        return None
    qy = re.search(r"q([1-4])\\s*[/\\-]?\\s*(20\\d{2})", normalized)
    if qy:
        quarter, year = int(qy.group(1)), int(qy.group(2))
        return year * 4 + quarter
    yq = re.search(r"(20\\d{2})\\s*[/\\-]?\\s*q([1-4])", normalized)
    if yq:
        year, quarter = int(yq.group(1)), int(yq.group(2))
        return year * 4 + quarter
    year_only = re.fullmatch(r"(20\\d{2})", normalized)
    if year_only:
        return int(year_only.group(1)) * 4 + 4
    return None


def parse_trigger(text: str) -> TriggerRule:
    original = str(text or "").strip()
    normalized = _norm(original)
    if not normalized:
        return TriggerRule("unsupported", label=original)

    target_period = _specific_statement_period(normalized)
    if target_period:
        return TriggerRule("statement_period", metric="statement_period", label=f"BCTC {target_period}", target_period=target_period)
    if re.search(r"\\bbctc\\s*moi\\b|bao cao tai chinh moi|co bctc moi|sau bctc", normalized):
        return TriggerRule("statement_new", label="BCTC mới")
''',
        ),
        (
'''        "baseline": _baseline(previous_state),
    }

    if rule.kind == "numeric":
''',
'''        "baseline": _baseline(previous_state),
        "target_period": rule.target_period,
    }

    if rule.kind == "numeric":
''',
        ),
        (
'''    if rule.kind == "statement_new":
        baseline = result["baseline"]
''',
'''    if rule.kind == "statement_period":
        current_rank = _period_rank(data_as_of)
        target_rank = _period_rank(rule.target_period)
        if current_rank is None:
            result.update(status="missing_data", evidence=f"Chưa đọc được kỳ BCTC canonical hiện tại để so với {rule.target_period}.")
            return result
        if target_rank is None:
            result.update(status="unsupported", evidence=f"Không đọc được kỳ BCTC mục tiêu: {rule.target_period}.")
            return result
        hit = current_rank >= target_rank
        result.update(
            triggered=hit,
            status="triggered" if hit else "armed",
            observed_value=data_as_of,
            evidence=(
                f"Kỳ canonical hiện tại {data_as_of} đã đạt/vượt mốc {rule.target_period}."
                if hit
                else f"Kỳ canonical hiện tại {data_as_of} chưa đạt mốc {rule.target_period}."
            ),
        )
        return result

    if rule.kind == "statement_new":
        baseline = result["baseline"]
''',
        ),
    ],
)


patch_file(
    "modules/deep_company_analysis/chapter1.py",
    [
        (
'''from modules.deep_company_analysis.monitoring import evaluate_and_persist, render_monitoring_panel

APP_ROOT = Path(__file__).resolve().parents[2]
''',
'''from modules.deep_company_analysis.monitoring import evaluate_and_persist, render_monitoring_panel
from modules.deep_company_analysis.structured_triggers import render_structured_trigger_builder

APP_ROOT = Path(__file__).resolve().parents[2]
''',
        ),
        (
'''    trigger_text = st.text_area(
        "Monitoring triggers — mỗi dòng một trigger",
        value="\\n".join(record.get("triggers", [])),
        height=100,
        placeholder="Ví dụ: Review khi MOS > 25%\\nReview sau BCTC Q3/2026",
        key=f"dca_triggers_{ticker}",
    )
    st.warning(
''',
'''    configured_triggers = render_structured_trigger_builder(ticker, list(record.get("triggers", [])))
    st.warning(
''',
        ),
        (
'''                "next_review": next_review,
                "triggers": [line.strip() for line in trigger_text.splitlines() if line.strip()],
            }
''',
'''                "next_review": next_review,
                "triggers": configured_triggers,
            }
''',
        ),
    ],
)
