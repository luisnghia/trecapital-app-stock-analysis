"""Install a tiny event-driven iOS input performance guard into Streamlit shell.

The fast client form reports only focus enter/leave (never keystrokes).  While a
field is focused we suspend parent-page animation/filter/shadow work that otherwise
gets repainted repeatedly when iOS changes the visual viewport for its keyboard.
No polling, timers or backend messages are introduced.
"""
from __future__ import annotations

from pathlib import Path
import re
import streamlit

MARKER = "khdn-fast-input-perf"


def install() -> None:
    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    text = index.read_text(encoding="utf-8")
    text = re.sub(
        rf'<style id="{MARKER}">.*?</style>\s*<script id="{MARKER}-js">.*?</script>',
        "",
        text,
        flags=re.S,
    )
    block = r'''
<style id="khdn-fast-input-perf">
html.khdn-fast-input-active .stApp *,
html.khdn-fast-input-active .stApp *::before,
html.khdn-fast-input-active .stApp *::after{
  animation:none!important;
  transition:none!important;
  scroll-behavior:auto!important;
}
html.khdn-fast-input-active .stApp,
html.khdn-fast-input-active [data-testid="stAppViewContainer"],
html.khdn-fast-input-active [data-testid="stMain"],
html.khdn-fast-input-active section[data-testid="stSidebar"]{
  filter:none!important;
  backdrop-filter:none!important;
  box-shadow:none!important;
}
</style>
<script id="khdn-fast-input-perf-js">
(()=>{
  const root=document.documentElement;
  const clear=()=>root.classList.remove('khdn-fast-input-active');
  window.addEventListener('message',event=>{
    if(event.origin!==window.location.origin) return;
    const data=event.data||{};
    if(data.type!=='khdn-fast-input-focus') return;
    root.classList.toggle('khdn-fast-input-active',!!data.active);
  });
  window.addEventListener('pagehide',clear,{passive:true});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clear();},{passive:true});
})();
</script>
'''
    if "</head>" not in text:
        raise RuntimeError("Streamlit shell has no </head> for mobile input guard")
    text = text.replace("</head>", block + "\n</head>", 1)
    index.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    install()
