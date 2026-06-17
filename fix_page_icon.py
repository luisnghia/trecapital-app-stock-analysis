from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")
text = text.replace('page_icon="??",', 'page_icon=":bar_chart:",')
p.write_text(text, encoding="utf-8")
print("Fixed page_icon safely")
