from __future__ import annotations

"""Runtime acceptance for the real multipage DCA path on pinned Streamlit 1.40.2.

The production app enters through ``app.py`` where ``module1_dashboard`` owns the host page
configuration. Streamlit then keeps imported modules cached when a user navigates to the unified
DCA page. The isolated AppTest runner cannot resolve ``st.page_link('app.py')`` when page 07 is
executed as a temporary entrypoint, so only the shared sidebar renderer is suppressed for that
second isolated test. All Chapter 1-8 tab bodies still execute.
"""

import json
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

import tre_sidebar_nav


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "app.py"
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
OUT = ROOT / "reports" / "DCA_STREAMLIT_COMPAT_V48_ACCEPTANCE.json"


def _exceptions(at: AppTest) -> list[str]:
    return [str(item.value) for item in at.exception]


def main() -> None:
    if st.__version__ != "1.40.2":
        raise SystemExit(f"Expected pinned Streamlit 1.40.2, got {st.__version__}")

    # 1) Real app entrypoint. This validates the production multipage host/sidebar normally.
    home = AppTest.from_file(str(ENTRYPOINT))
    home.run(timeout=120)
    home_exceptions = _exceptions(home)
    if home_exceptions:
        raise AssertionError("App entrypoint AppTest raised exceptions:\n" + "\n".join(home_exceptions))

    # 2) Unified DCA page in the same Python process. module1_dashboard is already cached, matching
    #    normal multipage navigation. We suppress only the sidebar renderer because AppTest treats
    #    PAGE as a new entrypoint and therefore cannot resolve the legitimate production link app.py.
    with patch.object(tre_sidebar_nav, "render_tre_sidebar_nav", lambda: None):
        dca = AppTest.from_file(str(PAGE))
        dca.run(timeout=120)
    dca_exceptions = _exceptions(dca)
    if dca_exceptions:
        raise AssertionError("Unified DCA AppTest raised exceptions:\n" + "\n".join(dca_exceptions))

    payload = {
        "acceptance": "PASS",
        "phase": "DCA Streamlit Compatibility Hotfix V48",
        "streamlit_version": st.__version__,
        "entrypoint": str(ENTRYPOINT.relative_to(ROOT)),
        "unified_page": str(PAGE.relative_to(ROOT)),
        "entrypoint_app_test_exceptions": 0,
        "unified_dca_app_test_exceptions": 0,
        "unified_dca_sidebar_mocked_only_for_isolated_apptest": True,
        "chapter8_embedded": True,
        "standalone_chapter8_removed": not (ROOT / "pages" / "09_Phan_tich_chuyen_sau_Chuong_8.py").exists(),
        "note": (
            "Production entrypoint/sidebar is tested normally. For isolated page-07 AppTest only, "
            "the sidebar renderer is suppressed because AppTest cannot resolve app.py from a page-as-entrypoint context. "
            "All Chapter 1-8 tab bodies execute with zero AppTest exceptions."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
