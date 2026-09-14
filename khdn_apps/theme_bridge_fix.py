"""Install a reliable client-side Light/Dark bridge for KHDN Ops.

Streamlit persists the user's theme choice in localStorage under
``stActiveTheme-${window.location.pathname}-v2`` with one of the selections
``System``, ``Light`` or ``Dark``. The previous bridge depended primarily on a
custom-component theme message; on some browsers that message is not emitted when
only the theme changes, leaving the KHDN root class stuck on Dark even while native
Streamlit widgets already switch to Light.

This patch makes the persisted Streamlit selection authoritative, keeps the probe as
fallback, and does not touch application data or the established Dark CSS.
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

  const apply=(base)=>{
    const normalized=String(base||'').toLowerCase();
    if(normalized!=='light' && normalized!=='dark') return false;
    const light=normalized==='light';
    /* Streamlit may reconcile <html class> during a rerun.  Do not return early
       solely because the cached theme value is unchanged: re-assert the custom
       class whenever it was removed by the host shell. */
    if(lastApplied===normalized && root.dataset.khdnTheme===normalized &&
       root.classList.contains(light?'khdn-light':'khdn-dark') &&
       !root.classList.contains(light?'khdn-dark':'khdn-light')) return true;
    root.classList.toggle('khdn-light',light);
    root.classList.toggle('khdn-dark',!light);
    root.dataset.khdnTheme=normalized;
    lastApplied=normalized;
    return true;
  };

  const systemBase=()=>systemQuery && systemQuery.matches ? 'dark' : 'light';

  const cachedBase=()=>{
    try{
      const raw=window.localStorage.getItem(cacheKey());
      if(raw===null) return '';
      const selection=JSON.parse(raw);
      if(selection==='Light') return 'light';
      if(selection==='Dark') return 'dark';
      if(selection==='System') return systemBase();
    }catch(_err){}
    return '';
  };

  const queryBase=()=>{
    try{
      const params=new URLSearchParams(window.location.search);
      const direct=String(params.get('theme')||'').toLowerCase();
      if(direct==='light' || direct==='dark') return direct;
    }catch(_err){}
    return '';
  };

  const syncFromStreamlitPreference=()=>{
    const base=queryBase() || cachedBase();
    return base ? apply(base) : false;
  };

  /* Apply the persisted selection immediately, before the app finishes mounting.
     Dark remains the deterministic fallback when Streamlit has no saved choice. */
  if(!syncFromStreamlitPreference()) apply('dark');

  /* Same-window localStorage writes do not emit a storage event in that same window.
     A tiny 250ms key read is therefore the most reliable cross-browser way to notice
     Streamlit's Settings -> Theme choice without causing reruns or DOM churn. */
  window.setInterval(syncFromStreamlitPreference,250);

  /* Other-tab changes are immediate. */
  window.addEventListener('storage',event=>{
    if(event.key===cacheKey()) syncFromStreamlitPreference();
  });

  /* System theme changes only matter when Streamlit's saved selection is System. */
  if(systemQuery){
    const onSystemChange=()=>{
      try{
        const raw=window.localStorage.getItem(cacheKey());
        if(raw!==null && JSON.parse(raw)==='System') apply(systemBase());
      }catch(_err){}
    };
    if(typeof systemQuery.addEventListener==='function') systemQuery.addEventListener('change',onSystemChange);
    else if(typeof systemQuery.addListener==='function') systemQuery.addListener(onSystemChange);
  }

  /* Keep the custom component message as a fallback for query/host theme cases where
     Streamlit intentionally does not persist a localStorage preference. */
  window.addEventListener('message',event=>{
    const data=event.data;
    if(!data || data.type!=='khdn-theme-sync') return;
    if(syncFromStreamlitPreference()) return;
    const base=String(data.base||'').toLowerCase();
    if(base==='light' || base==='dark') apply(base);
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
