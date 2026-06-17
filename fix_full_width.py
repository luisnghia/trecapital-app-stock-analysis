from pathlib import Path
import re

files = [
    Path("module1_dashboard.py"),
    Path("module2_dashboard.py"),
    Path("ui_oaktree_theme.py"),
]

patterns = [
    (r"max-width:\s*1500px\s*!important;", "max-width: none !important; width: 100% !important;"),
    (r"max-width:\s*1540px\s*!important;", "max-width: none !important; width: 100% !important;"),
    (r"max-width:\s*1200px\s*!important;", "max-width: none !important; width: 100% !important;"),
    (r"max-width:\s*1500px;", "max-width: none; width: 100%;"),
    (r"max-width:\s*1540px;", "max-width: none; width: 100%;"),
    (r"max-width:\s*1200px;", "max-width: none; width: 100%;"),
]

for p in files:
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    original = text
    for pat, repl in patterns:
        text = re.sub(pat, repl, text)
    if text != original:
        p.write_text(text, encoding="utf-8")
        print(f"Updated {p}")
    else:
        print(f"No max-width pattern found in {p}")
