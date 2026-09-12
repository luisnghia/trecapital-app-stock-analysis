"""Install governance source transformers into the production loader."""
from pathlib import Path


def install():
    app = Path(__file__).resolve().parent / "app.py"
    text = app.read_text(encoding="utf-8")
    mobile = (
        "from khdn_apps.mobile_nav_patch import patch_source as _patch_source\n"
        "_source = _patch_source(_source)\n"
    )
    governance = (
        "from khdn_apps.governance_source_patch import patch_source as _governance_patch_source\n"
        "_source = _governance_patch_source(_source)\n"
    )
    reason_admin = (
        "from khdn_apps.reason_admin_ui_patch import patch_source as _reason_admin_patch_source\n"
        "_source = _reason_admin_patch_source(_source)\n"
    )

    if mobile not in text:
        raise RuntimeError("Governance loader requires the mobile source patch marker")
    if governance not in text:
        text = text.replace(mobile, mobile + governance, 1)
    if reason_admin not in text:
        text = text.replace(governance, governance + reason_admin, 1)

    app.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    install()
