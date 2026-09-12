"""V2.40 UI patch for reason-category governance.

- Reason categories are a normal Admin navigation button, like Task types.
- The manager renders only inside Quản trị hệ thống > Nhóm nguyên nhân.
- It is hidden from the Leader work-management page.
- Category maintenance asks only for the category name; description is no longer an input.
"""
import re


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unwrap_reason_expander(block: str) -> str:
    """Turn the old expander into a direct admin section."""
    lines = block.splitlines(True)
    target = None
    for i, line in enumerate(lines):
        if "Danh mục nhóm nguyên nhân trả lại / hủy" in line and "expander" in line:
            target = i
            break
    if target is None:
        return block

    with_indent = _indent_of(lines[target])
    newline = "\n" if lines[target].endswith("\n") else ""
    lines[target] = " " * with_indent + 'st.subheader("Danh mục nhóm nguyên nhân trả lại / hủy")' + newline

    # Dedent only the former expander body. Stop if another statement returns to
    # the expander's indentation level.
    j = target + 1
    while j < len(lines):
        raw = lines[j]
        if raw.strip():
            indent = _indent_of(raw)
            if indent <= with_indent:
                break
            if raw.startswith(" " * (with_indent + 4)):
                lines[j] = raw[4:]
        j += 1
    return "".join(lines)


def _remove_description_inputs(block: str) -> str:
    """Keep DB compatibility but remove description fields from the UI."""
    out = []
    for line in block.splitlines(True):
        if "Mô tả" in line and ("text_input(" in line or "text_area(" in line):
            m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if m:
                out.append(f'{m.group(1)}{m.group(2)} = ""\n')
                continue
        out.append(line)
    return "".join(out)


def patch_source(source: str) -> str:
    # 1) Add a sixth Admin button, using exactly the same renderer/style/layout
    # path as Người dùng / Khách hàng CIF / Loại công việc / Audit / Sao lưu.
    old_options = '    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n'
    new_options = '    _admin_options=[("users","👥","Người dùng"),("customers","🏢","Khách hàng CIF"),("types","🧩","Loại công việc"),("reasons","🧩","Nhóm nguyên nhân"),("audit","🧾","Audit"),("backup","💾","Sao lưu")]\n'
    if new_options not in source:
        if old_options not in source:
            raise RuntimeError("V2.40 cannot find Admin navigation options")
        source = source.replace(old_options, new_options, 1)

    # Keep the page caption in sync with the new Admin function.
    source = source.replace(
        'page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, audit và sao lưu dữ liệu.")',
        'page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân, audit và sao lưu dữ liệu.")',
        1,
    )

    # 2) Locate the governance manager by its visible title, regardless of the
    # helper function name chosen in V2.39.
    marker = "Danh mục nhóm nguyên nhân trả lại / hủy"
    marker_pos = source.find(marker)
    if marker_pos < 0:
        raise RuntimeError("V2.40 cannot find reason-category manager")
    func_start = source.rfind("\ndef ", 0, marker_pos)
    if func_start < 0:
        if source.startswith("def "):
            func_start = -1
        else:
            raise RuntimeError("V2.40 cannot locate reason-category function start")
    func_start += 1
    func_end = source.find("\ndef ", marker_pos)
    if func_end < 0:
        func_end = len(source)
    block = source[func_start:func_end]

    # 3) The manager may still be called from Leader/Admin pages, but it becomes
    # a no-op everywhere except the dedicated Admin > Nhóm nguyên nhân view.
    first_nl = block.find("\n")
    if first_nl < 0:
        raise RuntimeError("V2.40 malformed reason-category function")
    guard = (
        '    if st.session_state.get("main_page") != "admin" or st.session_state.get("admin_view") != "reasons":\n'
        '        return\n'
    )
    if 'st.session_state.get("admin_view") != "reasons"' not in block:
        block = block[:first_nl + 1] + guard + block[first_nl + 1:]

    # 4) Display the manager directly like the Loại công việc page, not as the
    # large grey expander shown above the Admin action buttons.
    block = _unwrap_reason_expander(block)

    # 5) A reason category needs only its name. Existing description columns are
    # retained in SQLite for backward compatibility but new/edit UI writes blank.
    block = _remove_description_inputs(block)

    source = source[:func_start] + block + source[func_end:]
    compile(source, "<khdn-v240-reason-admin-ui>", "exec")
    return source
