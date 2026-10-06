"""Install an event-driven iOS input performance guard into Streamlit shell.

Both submit-only KHDN components and ordinary Streamlit inputs activate the same
keyboard-time guard.  While an editable field is focused, expensive page effects
are suspended and large static tables are paint/layout-contained.  No polling,
timers, keystroke bridge messages or backend calls are introduced.
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
/* Static catalog tables stay visible but do not force whole-page paint/layout. */
.cw-table-wrap,.khdn-fast-admin-table,.khdn-catalog-table-wrap,
[class*="khdn-fast-task-type-table"]{
  contain:layout paint style!important;
  content-visibility:auto;
  contain-intrinsic-size:auto 360px;
}
html.khdn-fast-input-active .stApp *,
html.khdn-fast-input-active .stApp *::before,
html.khdn-fast-input-active .stApp *::after{
  animation:none!important;
  transition:none!important;
  scroll-behavior:auto!important;
  filter:none!important;
  backdrop-filter:none!important;
  -webkit-backdrop-filter:none!important;
  box-shadow:none!important;
  text-shadow:none!important;
}
/* Long card lists are independent paint regions, including outside the keyboard. */
div[class*="st-key-cwux_card_"]{
  contain:layout paint style;
  content-visibility:auto;
  contain-intrinsic-size:auto 220px;
}
html.khdn-fast-input-active .stApp,
html.khdn-fast-input-active [data-testid="stAppViewContainer"],
html.khdn-fast-input-active [data-testid="stMain"],
html.khdn-fast-input-active section[data-testid="stSidebar"]{
  filter:none!important;
  backdrop-filter:none!important;
  box-shadow:none!important;
}
@media(max-width:768px){
  /* 16px prevents Safari keyboard focus zoom/reflow on native Streamlit fields. */
  .stApp input:not([type="checkbox"]):not([type="radio"]),
  .stApp textarea,.stApp select,.stApp [contenteditable="true"]{
    font-size:16px!important;
    -webkit-text-size-adjust:100%!important;
  }
}
</style>
<script id="khdn-fast-input-perf-js">
(()=>{
  const root=document.documentElement;
  const setActive=active=>root.classList.toggle('khdn-fast-input-active',!!active);
  const clear=()=>setActive(false);
  const editable=el=>!!(el&&el.matches&&el.matches(
    'input:not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"]),textarea,select,[contenteditable="true"]'
  ));

  /* Messages are focus enter/leave only; custom components never report keys. */
  window.addEventListener('message',event=>{
    if(event.origin!==window.location.origin) return;
    const data=event.data||{};
    if(data.type!=='khdn-fast-input-focus') return;
    setActive(!!data.active);
  });

  /* Native Streamlit controls use the same guard. Capture phase catches BaseWeb. */
  document.addEventListener('focusin',event=>{
    if(editable(event.target)){
      // Configure once on focus. No input/keydown handlers or DOM scans while typing.
      event.target.setAttribute('spellcheck','false');
      event.target.setAttribute('autocorrect','off');
      setActive(true);
    }
  },true);
  document.addEventListener('focusout',event=>{
    if(!editable(event.target)) return;
    queueMicrotask(()=>{if(!editable(document.activeElement)) clear();});
  },true);

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
