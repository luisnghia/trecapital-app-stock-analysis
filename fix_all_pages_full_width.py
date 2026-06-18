from pathlib import Path
import re

repo = Path(".")
css_file = repo / "tre_full_width.py"

css_file.write_text(
'''from __future__ import annotations

import streamlit as st

def apply_full_width() -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            width: 100% !important;
            max-width: none !important;
        }

        .main .block-container,
        section.main > div,
        div[data-testid="stAppViewContainer"] .block-container {
            max-width: none !important;
            width: 100% !important;
            padding-left: 1.0rem !important;
            padding-right: 1.0rem !important;
            padding-top: 0.8rem !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"] {
            max-width: none !important;
            width: 100% !important;
        }

        iframe {
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
''',
encoding="utf-8",
)

target_files = [
    Path("module1_dashboard.py"),
    Path("module2_dashboard.py"),
    Path("report_exporter.py"),
]

pages_dir = Path("pages")
if pages_dir.exists():
    target_files.extend(sorted(pages_dir.glob("*.py")))

def insert_after_set_page_config(text: str) -> str:
    if "apply_full_width()" in text:
        return text

    idx = text.find("st.set_page_config(")
    if idx == -1:
        return text

    # tìm dấu đóng ngoặc của st.set_page_config(...)
    pos = idx + len("st.set_page_config(")
    depth = 1
    in_str = None
    escape = False

    while pos < len(text):
        ch = text[pos]

        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    pos += 1
                    # nếu sau đó có dấu phẩy hoặc xuống dòng thì giữ nguyên
                    break
        pos += 1

    insert = "\n\nfrom tre_full_width import apply_full_width\napply_full_width()\n"
    return text[:pos] + insert + text[pos:]

for p in target_files:
    if not p.exists():
        continue

    text = p.read_text(encoding="utf-8")

    original = text

    # Ép các max-width cũ thành full-width
    text = re.sub(r"max-width:\s*(1200|1300|1400|1500|1540|1600)px\s*!important;", 
                  "max-width: none !important; width: 100% !important;", text)
    text = re.sub(r"max-width:\s*(1200|1300|1400|1500|1540|1600)px;", 
                  "max-width: none; width: 100%;", text)

    # Thêm CSS sau st.set_page_config để không vi phạm thứ tự Streamlit
    text = insert_after_set_page_config(text)

    if text != original:
        p.write_text(text, encoding="utf-8")
        print(f"Updated: {p}")
    else:
        print(f"No change: {p}")

print("Done.")
