from pathlib import Path
import re

repo = Path(".")
utf8 = "utf-8"

FULL_WIDTH_CODE = '''from __future__ import annotations

import streamlit as st

def apply_full_width() -> None:
    st.markdown(
        """
        <style>
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer,
        [class*="stMainBlockContainer"],
        section.main,
        section.main > div {
            width: 100% !important;
            max-width: none !important;
        }

        .main .block-container,
        section.main > div,
        div[data-testid="stAppViewContainer"] .block-container,
        div[data-testid="stMainBlockContainer"],
        .block-container,
        [class*="block-container"] {
            max-width: none !important;
            width: 100% !important;
            padding-left: 1.0rem !important;
            padding-right: 1.0rem !important;
            padding-top: 0.8rem !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="column"],
        div[data-testid="stElementContainer"],
        [class*="stVerticalBlock"],
        [class*="stHorizontalBlock"],
        [class*="stElementContainer"] {
            max-width: none !important;
        }

        .page-brand-shell,
        .page-hero-card,
        .hero-card,
        .workflow-card,
        .source-card,
        .note-card,
        .ok-card,
        .warn-card,
        .big-warning-card,
        .tre-card,
        .tre-section,
        .tre-container {
            max-width: none !important;
            width: 100% !important;
        }

        .hero-card p,
        .page-hero-card p {
            max-width: none !important;
        }

        iframe {
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
'''

# 1) Ghi file CSS chung
(repo / "tre_full_width.py").write_text(FULL_WIDTH_CODE, encoding=utf8)

# 2) Sửa config.toml không BOM và tắt watcher
streamlit_dir = repo / ".streamlit"
streamlit_dir.mkdir(exist_ok=True)

config = '''[theme]
base = "light"
primaryColor = "#0F766E"
backgroundColor = "#F8FAFC"
secondaryBackgroundColor = "#ECFDF5"
textColor = "#0F172A"

[server]
headless = true
enableCORS = false
enableXsrfProtection = false
fileWatcherType = "none"
runOnSave = false
'''
(streamlit_dir / "config.toml").write_text(config, encoding=utf8)

# 3) app.py chỉ gọi module1 và apply CSS sau render
app_py = repo / "app.py"
app_py.write_text(
'''from __future__ import annotations

from module1_dashboard import render_dashboard
from tre_full_width import apply_full_width

render_dashboard()
apply_full_width()
''',
encoding=utf8
)

# Helper
def ensure_import(text: str) -> str:
    if "from tre_full_width import apply_full_width" in text:
        return text

    lines = text.splitlines()
    insert_at = 0

    # Sau from __future__ nếu có
    for i, line in enumerate(lines):
        if line.startswith("from __future__"):
            insert_at = i + 1

    # Sau import streamlit nếu có
    for i, line in enumerate(lines):
        if line.strip() == "import streamlit as st":
            insert_at = max(insert_at, i + 1)

    lines.insert(insert_at, "from tre_full_width import apply_full_width")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

def replace_max_width(text: str) -> str:
    # Xóa các max-width cố định có !important
    text = re.sub(
        r"max-width\s*:\s*(?:900|960|1000|1100|1200|1280|1300|1400|1450|1480|1500|1540|1600|1700|1800)px\s*!important\s*;",
        "max-width: none !important; width: 100% !important;",
        text,
        flags=re.IGNORECASE,
    )

    # Xóa các max-width cố định không có !important
    text = re.sub(
        r"max-width\s*:\s*(?:900|960|1000|1100|1200|1280|1300|1400|1450|1480|1500|1540|1600|1700|1800)px\s*;",
        "max-width: none; width: 100%;",
        text,
        flags=re.IGNORECASE,
    )

    return text

def add_apply_after_calls(text: str) -> str:
    text = ensure_import(text)

    # Thêm apply_full_width() ngay sau các hàm inject CSS/theme để CSS full-width thắng sau cùng
    target_calls = [
        "_inject_runtime_ui_css()",
        "inject_oaktree_theme()",
        "apply_oaktree_theme()",
        "inject_theme()",
    ]

    lines = text.splitlines()
    out = []

    for idx, line in enumerate(lines):
        out.append(line)
        stripped = line.strip()

        if stripped in target_calls:
            indent = line[:len(line) - len(line.lstrip())]
            next_line = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if next_line != "apply_full_width()":
                out.append(indent + "apply_full_width()")

    return "\n".join(out) + ("\n" if text.endswith("\n") else "")

# 4) Sửa module1/module2/ui theme
for file_name in ["module1_dashboard.py", "module2_dashboard.py", "ui_oaktree_theme.py"]:
    p = repo / file_name
    if not p.exists():
        print(f"Skip missing {file_name}")
        continue

    text = p.read_text(encoding=utf8)
    original = text

    text = replace_max_width(text)

    if file_name in ["module1_dashboard.py", "module2_dashboard.py"]:
        text = add_apply_after_calls(text)
    elif file_name == "ui_oaktree_theme.py":
        # Theme không nhất thiết cần gọi apply, nhưng phải bỏ max-width cố định.
        pass

    if text != original:
        p.write_text(text, encoding=utf8)
        print(f"Updated {file_name}")
    else:
        print(f"No change {file_name}")

# 5) Sửa tất cả pages/*.py: import apply_full_width và gọi cuối file
pages_dir = repo / "pages"
if pages_dir.exists():
    for p in sorted(pages_dir.glob("*.py")):
        text = p.read_text(encoding=utf8)
        original = text

        text = replace_max_width(text)
        text = ensure_import(text)

        if not re.search(r"(?m)^\s*apply_full_width\(\)\s*$", text):
            text = text.rstrip() + "\n\napply_full_width()\n"

        if text != original:
            p.write_text(text, encoding=utf8)
            print(f"Updated {p}")
        else:
            print(f"No change {p}")

# 6) Kiểm tra còn max-width cố định nguy hiểm không
bad = []
for p in list(repo.glob("*.py")) + list((repo / "pages").glob("*.py") if pages_dir.exists() else []):
    txt = p.read_text(encoding=utf8, errors="ignore")
    for m in re.finditer(r"max-width\s*:\s*(?:900|960|1000|1100|1200|1280|1300|1400|1450|1480|1500|1540|1600|1700|1800)px", txt, re.I):
        line_no = txt[:m.start()].count("\n") + 1
        bad.append(f"{p}:{line_no}: {m.group(0)}")

if bad:
    print("\nWARNING: Vẫn còn max-width cố định:")
    for x in bad:
        print(x)
else:
    print("\nOK: Không còn max-width cố định phổ biến.")

print("DONE")
