"""Event-driven Light/Dark bridge for KHDN Apps.

No recurring timer is allowed on the mobile typing hot path. Native Streamlit theme
render messages, storage events, focus/visibility changes and OS theme changes are
sufficient to keep the custom class synchronized without 250ms/1500ms polling.
"""
from __future__ import annotations

from pathlib import Path
import re
import streamlit


def install() -> None:
    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    page = index.read_text(encoding="utf-8")
    bridge = r'''
<script id="khdn-live-theme-class">
(()=>{
  const root=document.documentElement;
  const systemQuery=window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const cacheKey=()=>`stActiveTheme-${window.location.pathname}-v2`;
  let lastApplied='';
  try{
    const saved=window.localStorage.getItem(cacheKey());
    let selection=null; try{selection=JSON.parse(saved);}catch(_err){}
    if(!['Light','Dark','System'].includes(selection)) window.localStorage.setItem(cacheKey(),JSON.stringify('Dark'));
  }catch(_err){}
  const apply=(base)=>{
    const normalized=String(base||'').toLowerCase();
    if(normalized!=='light'&&normalized!=='dark')return false;
    const light=normalized==='light';
    if(lastApplied===normalized&&root.dataset.khdnTheme===normalized&&root.classList.contains(light?'khdn-light':'khdn-dark')&&!root.classList.contains(light?'khdn-dark':'khdn-light'))return true;
    root.classList.toggle('khdn-light',light);root.classList.toggle('khdn-dark',!light);root.dataset.khdnTheme=normalized;lastApplied=normalized;return true;
  };
  const systemBase=()=>systemQuery&&systemQuery.matches?'dark':'light';
  const cachedBase=()=>{
    try{
      const raw=window.localStorage.getItem(cacheKey());if(raw===null)return '';
      const selection=JSON.parse(raw);if(selection==='Light')return 'light';if(selection==='Dark')return 'dark';if(selection==='System')return systemBase();
    }catch(_err){} return '';
  };
  const queryBase=()=>{try{const p=new URLSearchParams(window.location.search),v=String(p.get('theme')||'').toLowerCase();return(v==='light'||v==='dark')?v:'';}catch(_err){return '';}};
  const sync=()=>{const base=queryBase()||cachedBase();return base?apply(base):false;};
  if(!sync())apply('dark');
  window.addEventListener('storage',event=>{if(event.key===cacheKey())sync();});
  window.addEventListener('focus',sync,{passive:true});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)sync();},{passive:true});
  document.addEventListener('focusout',()=>window.requestAnimationFrame(sync),{passive:true});
  if(systemQuery){
    const onSystemChange=()=>{try{const raw=window.localStorage.getItem(cacheKey());if(raw!==null&&JSON.parse(raw)==='System')apply(systemBase());}catch(_err){}};
    if(typeof systemQuery.addEventListener==='function')systemQuery.addEventListener('change',onSystemChange);else if(typeof systemQuery.addListener==='function')systemQuery.addListener(onSystemChange);
  }
  window.addEventListener('message',event=>{
    const data=event.data;if(!data||data.type!=='khdn-theme-sync')return;
    if(sync())return;const base=String(data.base||'').toLowerCase();if(base==='light'||base==='dark')apply(base);
  });
})();
</script>
'''
    pattern = r'<script id="khdn-live-theme-class">.*?</script>'
    if not re.search(pattern, page, flags=re.S):
        raise RuntimeError("Reliable theme bridge cannot find existing KHDN theme script")
    page = re.sub(pattern, bridge.strip(), page, count=1, flags=re.S)
    index.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    install()
