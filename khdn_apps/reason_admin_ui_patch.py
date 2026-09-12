"""V2.41 UI patch for reason-category governance.

Fixes V2.40 regressions:
- Never guards/returns from the whole admin_page function.
- Removes the reason-category expander from Leader work management.
- Adds Reason categories as a normal Admin navigation card.
- Shows the existing Admin reason-category editor only when that card is active.
- Reason-category create/edit UI asks for name only; DB description stays for compatibility.
"""
import re


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _function_bounds(source: str, name: str):
    marker = f"\ndef {name}("
    start = source.find(marker)
    if start < 0 and source.startswith(f"def {name}("):
        start = -1
    if start < -1:
        raise RuntimeError(f"V2.41 cannot find function {name}")
    start += 1
    end = source.find("\ndef ", start + 1)
    if end < 0:
        end = len(source)
    return start, end


def _remove_named_expander(block: str, phrases) -> str:
    """Remove exactly one with st.expander(...) block matching any phrase."""
    lines = block.splitlines(True)
    for i, line in enumerate(lines):
        if "st.expander(" not in line or not any(p in line for p in phrases):
            continue
        base_indent = _indent_of(line)
        j = i + 1
        while j < len(lines):
            raw = lines[j]
            if raw.strip() and _indent_of(raw) <= base_indent:
                break
            j += 1
        return "".join(lines[:i] + lines[j:])
    return block


def _convert_admin_expander(block: str) -> str:
    """Make the Admin reason editor a direct section visible only in reasons view."""
    lines = block.splitlines(True)
    phrases = (
        "Danh mục nhóm nguyên nhân trả lại / hủy",
        "Quản lý nhóm nguyên nhân trả lại / hủy",
    )
    target = None
    for i, line in enumerate(lines):
        if "st.expander(" in line and any(p in line for p in phrases):
            target = i
            break
    if target is None:
        raise RuntimeError("V2.41 cannot find Admin reason-category expander")

    base_indent = _indent_of(lines[target])
    newline = "\n" if lines[target].endswith("\n") else ""
    # Use session_state because governance V2.39 placed this block above the
    # Admin navigation assignment. This avoids NameError and keeps other Admin
    # tabs fully visible.
    lines[target] = (
        " " * base_indent
        + 'if st.session_state.get("admin_view", "users") == "reasons":'
        + newline
    )

    # Keep the original body indentation. Replace only the UI description inputs;
    # stored description columns remain untouched for backward compatibility.
    j = target + 1
    while j < len(lines):
        raw = lines[j]
        if raw.strip() and _indent_of(raw) <= base_indent:
            break
        if "Mô tả" in raw and ("text_input(" in raw or "text_area(" in raw):
            m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=", raw)
            if m:
                lines[j] = f'{m.group(1)}{m.group(2)} = ""\n'
        j += 1
    return "".join(lines)


def patch_source(source: str) -> str:
    # 1) Admin navigation: add Reason categories at the same level/style as Task types.
    old_options = '    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n'
    new_options = '    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("reasons","🧩","Nhóm nguyên nhân"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n'
    if new_options not in source:
        if old_options not in source:
            raise RuntimeError("V2.41 cannot find Admin navigation options")
        source = source.replace(old_options, new_options, 1)

    source = source.replace(
        'page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, audit và sao lưu dữ liệu.")',
        'page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân, audit và sao lưu dữ liệu.")',
        1,
    )

    # 2) Remove reason-category management from Leader work-management only.
    ls, le = _function_bounds(source, "leader_page")
    leader = source[ls:le]
    leader2 = _remove_named_expander(
        leader,
        (
            "Quản lý nhóm nguyên nhân trả lại / hủy",
            "Danh mục nhóm nguyên nhân trả lại / hủy",
        ),
    )
    # The screenshot regression proves this block existed. Fail loudly if it is
    # still present after the targeted removal.
    if "nhóm nguyên nhân trả lại / hủy" in leader2.lower():
        raise RuntimeError("V2.41 Leader reason-category UI was not fully removed")
    source = source[:ls] + leader2 + source[le:]

    # 3) Convert only the inline Admin reason expander; do NOT alter/guard admin_page.
    ads, ade = _function_bounds(source, "admin_page")
    admin = source[ads:ade]
    # Remove the V2.40 function-level guard if a cached/source variant contains it.
    admin = admin.replace(
        '    if st.session_state.get("main_page") != "admin" or st.session_state.get("admin_view") != "reasons":\n        return\n',
        '',
        1,
    )
    admin = _convert_admin_expander(admin)
    source = source[:ads] + admin + source[ade:]

    # 4) Regression assertions before image build.
    ads, ade = _function_bounds(source, "admin_page")
    admin_final = source[ads:ade]
    if 'st.session_state.get("main_page") != "admin"' in admin_final:
        raise RuntimeError("V2.41 found forbidden whole-admin guard")
    if 'st.session_state.get("admin_view", "users") == "reasons"' not in admin_final:
        raise RuntimeError("V2.41 Admin reasons section is not scoped to reasons view")
    if '("reasons","🧩","Nhóm nguyên nhân")' not in source:
        raise RuntimeError("V2.41 Admin reasons navigation card missing")

    compile(source, "<khdn-v241-reason-admin-ui>", "exec")
    return source
