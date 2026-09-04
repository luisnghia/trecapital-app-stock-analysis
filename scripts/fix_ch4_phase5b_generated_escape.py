from pathlib import Path

path = Path(__file__).resolve().parents[1] / "modules" / "deep_company_analysis" / "chapter4_page_support.py"
text = path.read_text(encoding="utf-8")
broken = 'st.write("\n".join(f"- {x}" for x in notes))'
fixed = 'st.write(chr(10).join(f"- {x}" for x in notes))'
if broken in text:
    text = text.replace(broken, fixed)
elif fixed not in text:
    raise SystemExit("Expected generated peer-note join was not found")
path.write_text(text, encoding="utf-8")
print("Fixed generated Chapter 4 peer-note newline escaping")
