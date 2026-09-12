"""Install the V2.38 reason-category transformer into the compressed production loader."""
from pathlib import Path


def install():
    app=Path(__file__).resolve().parent / "app.py"
    text=app.read_text(encoding="utf-8")
    mobile=(
        "from khdn_apps.mobile_nav_patch import patch_source as _patch_source\n"
        "_source = _patch_source(_source)\n"
    )
    reason=(
        "from khdn_apps.reason_categories_patch import patch_source as _reason_categories_patch_source\n"
        "_source = _reason_categories_patch_source(_source)\n"
    )
    if mobile not in text:
        raise RuntimeError("Reason-category installer requires mobile patch marker")
    if reason not in text:
        text=text.replace(mobile,mobile+reason,1)
    app.write_text(text,encoding="utf-8")


if __name__ == "__main__":
    install()
