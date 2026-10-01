"""Scoped layout polish for the zero-keystroke Customer Work create form.

This adapter changes presentation only:
- keep the blank priority prompt first and move "Không thuộc công việc trọng tâm"
  to the bottom of the priority dropdown;
- use a four-track desktop grid for the Customer Work create component;
- give contact name more room (2/4) and phone/role 1/4 each;
- render due-date/stage and owner/controller as balanced 50/50 rows.

Business values, validation, submit-only behavior and database writes remain owned
by global_zero_keystroke_patch and are not changed here.
"""
from __future__ import annotations

from khdn_apps.legacy_fast_form import legacy_fast_form as _base_legacy_fast_form
from khdn_apps import global_zero_keystroke_patch as zero

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_WORK_FORM_LAYOUT_VERSION"
_PREFIX = "p17_customer_work_create_"


def _ordered_priority_options(options):
    values = list(options or [])
    blank = [x for x in values if str((x or {}).get("value", "")) == ""]
    none = [x for x in values if str((x or {}).get("value", "")) == "NONE"]
    normal = [
        x for x in values
        if str((x or {}).get("value", "")) not in {"", "NONE"}
    ]
    return blank + normal + none


def _layout_fields(fields):
    out = []
    for raw in fields or []:
        field = dict(raw or {})
        name = str(field.get("name") or "")

        if name == "focus":
            field["options"] = _ordered_priority_options(field.get("options"))

        if name.startswith("contact_") and name.endswith("_name"):
            field.pop("full", None)
            field["span"] = 2
        elif name.startswith("contact_") and (
            name.endswith("_phone") or name.endswith("_role")
        ):
            field.pop("full", None)
            field["span"] = 1
        elif name in {"due_date", "stage", "owner", "controller"}:
            field.pop("full", None)
            field["span"] = 2

        out.append(field)
    return out


def _customer_work_fast_form(
    fields,
    button_label,
    key,
    *,
    reset_token="",
    title="",
    help_text="",
    columns=1,
):
    if str(key).startswith(_PREFIX):
        return _base_legacy_fast_form(
            _layout_fields(fields),
            button_label,
            key,
            reset_token=reset_token,
            title=title,
            help_text=help_text,
            columns=4,
        )
    return _base_legacy_fast_form(
        fields,
        button_label,
        key,
        reset_token=reset_token,
        title=title,
        help_text=help_text,
        columns=columns,
    )


def _self_check():
    sample = [
        {"name": "focus", "options": [
            {"value": "", "label": "— Chọn công việc trọng tâm —"},
            {"value": "NONE", "label": "Không thuộc công việc trọng tâm"},
            {"value": "11", "label": "TT01 · Huy động vốn"},
            {"value": "12", "label": "TT02 · Tín dụng"},
        ], "full": True},
        {"name": "contact_1_name"},
        {"name": "contact_1_phone"},
        {"name": "contact_1_role"},
        {"name": "due_date"},
        {"name": "stage", "span": 2},
        {"name": "owner"},
        {"name": "controller", "span": 2},
    ]
    laid = _layout_fields(sample)
    by_name = {x.get("name"): x for x in laid}
    opts = by_name["focus"]["options"]
    assert [str(x.get("value")) for x in opts] == ["", "11", "12", "NONE"]
    assert sum(int(by_name[f"contact_1_{x}"].get("span", 1)) for x in ("name", "phone", "role")) == 4
    assert int(by_name["due_date"]["span"]) + int(by_name["stage"]["span"]) == 4
    assert int(by_name["owner"]["span"]) + int(by_name["controller"]["span"]) == 4
    return True


def install(app_ns=None, logger=None):
    _self_check()
    # Rebind the module-global function used by _customer_create_fast. This does
    # not alter the generic legacy component for any other form.
    zero.legacy_fast_form = _customer_work_fast_form
    if isinstance(app_ns, dict):
        app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "CUSTOMER_WORK_FORM_LAYOUT_PATCH_INSTALLED priority_none_last=1 grid4=1 contact_2_1_1=1 pair_2_2=1 zero_keystroke_preserved=1 data_migration=0"
        )
