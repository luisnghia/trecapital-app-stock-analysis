"""Install small PWA metadata additions required by the notification release."""
from __future__ import annotations

from pathlib import Path
import re
import streamlit


def install() -> None:
    static = Path(streamlit.__file__).resolve().parent / "static"
    index = static / "index.html"
    text = index.read_text(encoding="utf-8")
    if "</head>" not in text:
        raise RuntimeError("Streamlit index.html has no </head>")
    marker = "khdn-push-pwa-meta"
    text = re.sub(r'<!-- khdn-push-pwa-meta -->.*?<!-- /khdn-push-pwa-meta -->', '', text, flags=re.S)
    tags = '''<!-- khdn-push-pwa-meta -->
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="KHDN Apps">
<meta name="application-name" content="KHDN Apps">
<!-- /khdn-push-pwa-meta -->
'''
    text = text.replace("</head>", tags + "</head>", 1)
    index.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    install()
