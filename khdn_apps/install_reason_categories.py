"""Install reason-category and task-note transformers into the compressed loader."""
from pathlib import Path


def install():
    app=Path(__file__).resolve().parent / "app.py"
    text=app.read_text(encoding="utf-8")
    lunch=(
        "from khdn_apps.lunch_break_patch import patch_source as _lunch_break_patch_source\n"
        "_source = _lunch_break_patch_source(_source)\n"
    )
    mobile=(
        "from khdn_apps.mobile_nav_patch import patch_source as _patch_source\n"
        "_source = _patch_source(_source)\n"
    )
    reason=(
        "from khdn_apps.reason_categories_patch import patch_source as _reason_categories_patch_source\n"
        "_source = _reason_categories_patch_source(_source)\n"
        "_source = _source.replace('(\"reasons\",\"🧩\",\"Nhóm nguyên nhân\")', '(\"reasons\",\"🏷️\",\"Nhóm nguyên nhân\")')\n"
    )
    note=(
        "from khdn_apps.task_note_visibility_patch import patch_source as _task_note_visibility_patch_source\n"
        "_source = _task_note_visibility_patch_source(_source)\n"
    )
    if mobile not in text:
        raise RuntimeError("Reason-category installer requires mobile patch marker")
    if lunch not in text:
        text=text.replace(mobile,lunch+mobile,1)
    old_reason=(
        "from khdn_apps.reason_categories_patch import patch_source as _reason_categories_patch_source\n"
        "_source = _reason_categories_patch_source(_source)\n"
    )
    if old_reason in text and reason not in text:
        text=text.replace(old_reason,reason,1)
    elif reason not in text:
        text=text.replace(mobile,mobile+reason,1)
    if note not in text:
        if reason not in text:
            raise RuntimeError("Task-note installer requires reason-category transformer marker")
        text=text.replace(reason,reason+note,1)
    app.write_text(text,encoding="utf-8")


if __name__ == "__main__":
    install()
