from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"


def main() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    old = '''        for manager, (role_raw, role_norm, priority), context in _board_signature_candidates(raw_text):\n            rows.append({\n'''
    new = '''        for manager, (role_raw, role_norm, priority), context in _board_signature_candidates(raw_text):\n            as_of = _candidate_as_of(manager, context, raw_source_title, source_url)\n            rows.append({\n'''
    if new not in text:
        if old not in text:
            raise RuntimeError("V37.1 Round 5Y signature as-of marker not found")
        text = text.replace(old, new, 1)
    DISCOVERY.write_text(text, encoding="utf-8")
    print("Chapter 7 V37.1 Round 5Y signature candidate as-of derivation applied")


if __name__ == "__main__":
    main()
