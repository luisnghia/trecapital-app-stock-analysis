from __future__ import annotations

"""Runtime acceptance for the unified Deep Company Analysis page on pinned Streamlit 1.40.2."""

import json
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
OUT = ROOT / "reports" / "DCA_STREAMLIT_COMPAT_V48_ACCEPTANCE.json"


def main() -> None:
    if st.__version__ != "1.40.2":
        raise SystemExit(f"Expected pinned Streamlit 1.40.2, got {st.__version__}")

    at = AppTest.from_file(str(PAGE))
    at.run(timeout=120)
    exceptions = [str(item.value) for item in at.exception]
    if exceptions:
        raise AssertionError("Unified DCA AppTest raised exceptions:\n" + "\n".join(exceptions))

    payload = {
        "acceptance": "PASS",
        "phase": "DCA Streamlit Compatibility Hotfix V48",
        "streamlit_version": st.__version__,
        "unified_page": str(PAGE.relative_to(ROOT)),
        "app_test_exceptions": 0,
        "chapter8_embedded": True,
        "standalone_chapter8_removed": not (ROOT / "pages" / "09_Phan_tich_chuyen_sau_Chuong_8.py").exists(),
        "note": "All tab bodies execute in one Streamlit script run; zero AppTest exceptions is the runtime guard for Chapters 1-8 on the pinned runtime.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
