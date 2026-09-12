"""Install web-clip metadata into Streamlit's initial HTML during image build."""
from pathlib import Path
import re
import shutil
import streamlit


def install():
    static = Path(streamlit.__file__).resolve().parent / "static"
    assets = Path(__file__).resolve().parent / "static"
    index = static / "index.html"
    page = index.read_text(encoding="utf-8")
    if "</head>" not in page:
        raise RuntimeError("Streamlit index.html has no head; branding not installed")
    page = re.sub(r'<link\b[^>]*rel=["\'](?:shortcut icon|icon|apple-touch-icon|manifest)["\'][^>]*>', '', page)
    page = re.sub(r'<title>.*?</title>', '<title>KHDN Apps</title>', page)
    tags = '''
<link rel="apple-touch-icon" sizes="180x180" href="/app/static/bidv-icon-180.png?v=official-3">
<link rel="icon" type="image/png" href="/app/static/bidv-icon-192.png?v=official-3">
<link rel="manifest" href="/app/static/manifest.json?v=official-3">
<meta name="apple-mobile-web-app-title" content="KHDN Apps">
<meta name="theme-color" content="#006B68">
'''
    page = page.replace("</head>", tags + "</head>")
    index.write_text(page, encoding="utf-8")
    for name in ("apple-touch-icon.png", "apple-touch-icon-precomposed.png"):
        shutil.copyfile(assets / "bidv-icon-180.png", static / name)


if __name__ == "__main__":
    install()
