from __future__ import annotations

"""DGC diagnostic for Chapter 5 Phase 5A Source-Locked Core.

Phase 5A intentionally does not fetch or infer canonical financial conclusions.  This diagnostic
validates source-locked structure, Shearn Q23 defaults, no-Confidence policy and analyst guardrails.
"""

from modules.deep_company_analysis.chapter5 import (
    QUESTION_KEYS,
    SHEARN_Q23_RISKS,
    cross_question_checks,
    empty_payload,
    guardrails,
)


def _has_confidence(value) -> bool:
    if isinstance(value, dict):
        return any("confidence" in str(k).casefold() or _has_confidence(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_has_confidence(x) for x in value)
    return False


def main() -> None:
    record = empty_payload("DGC", "CTCP Tập đoàn Hóa chất Đức Giang")
    print("=== DGC CHAPTER 5 PHASE 5A SOURCE-LOCKED DIAGNOSTIC ===")
    print("Questions:", ", ".join(QUESTION_KEYS))
    print("Confidence fields present:", _has_confidence(record))
    print("Shearn Q23 default risks:", len(record["q23_risks"]))
    for idx, row in enumerate(record["q23_risks"], 1):
        print(f"{idx:02d}. {row['Risk']} | {row['Risk (VI)']} | {row['Origin']} | F={row['Frequency']} | S={row['Severity']}")

    assert tuple(row["Risk"] for row in record["q23_risks"]) == tuple(name for name, _ in SHEARN_Q23_RISKS)
    assert len(record["q23_risks"]) == 17
    assert not _has_confidence(record)

    # Demonstrate the unknown-risk guardrail without turning it into an automatic risk rating.
    record["q23_risks"][0]["Severity"] = "Catastrophic"
    checks = cross_question_checks(record)
    print("\nConsistency / research-gap example:")
    for item in checks:
        print("-", item)
    assert any("Critical Research Gap" in item for item in checks)

    flags = guardrails()
    print("\nGuardrails:")
    for key, value in flags.items():
        print(f"- {key}={value}")
    assert all(value is False for value in flags.values())
    print("PASS: Phase 5A is analyst-owned; no automatic investment conclusion generated.")


if __name__ == "__main__":
    main()
