"""Install KHDN performance patches into the built Streamlit image."""
from pathlib import Path
import streamlit


def install():
    app_dir = Path(__file__).resolve().parent
    loader = app_dir / "app.py"
    text = loader.read_text(encoding="utf-8")
    exec_line = 'exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())\n'
    perf = (
        "from khdn_apps.performance_patch import patch_source as _performance_patch_source\n"
        "_source = _performance_patch_source(_source)\n"
        "from khdn_apps.input_batch_patch import patch_source as _input_batch_patch_source\n"
        "_source = _input_batch_patch_source(_source)\n"
    )
    if perf not in text:
        if exec_line not in text:
            raise RuntimeError("Performance installer cannot find loader exec marker")
        old_perf = (
            "from khdn_apps.performance_patch import patch_source as _performance_patch_source\n"
            "_source = _performance_patch_source(_source)\n"
        )
        if old_perf in text:
            text = text.replace(old_perf, perf, 1)
        else:
            text = text.replace(exec_line, perf + exec_line, 1)
    loader.write_text(text, encoding="utf-8")

    # V2.14 had no document-wide DOM observer. Keep the mobile two-column fix,
    # but never attach its MutationObserver on desktop and suspend it completely
    # while the user is editing an input. This makes desktop form entry follow
    # the same simple browser-local path as V2.14.
    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    page = index.read_text(encoding="utf-8")
    old = "  new MutationObserver(scheduleGrid).observe(document.documentElement,{childList:true,subtree:true});\n"
    new = '''  const OPS_GRID_SELECTOR='div[class*="st-key-ops_cards_support_view"],div[class*="st-key-ops_cards_qlkh_view"],div[class*="st-key-ops_cards_leader_view"],div[class*="st-key-ops_cards_admin_view"]';
  const mutationTouchesGrid=(mutations)=>{
    for(const m of mutations){
      const target=m.target&&m.target.nodeType===1?m.target:null;
      if(target&&(target.matches?.(OPS_GRID_SELECTOR)||target.closest?.(OPS_GRID_SELECTOR))) return true;
      for(const node of m.addedNodes||[]){
        if(node.nodeType!==1) continue;
        if(node.matches?.(OPS_GRID_SELECTOR)||node.querySelector?.(OPS_GRID_SELECTOR)) return true;
      }
    }
    return false;
  };
  let gridWatching=false;
  const gridObserver=new MutationObserver(mutations=>{
    if(document.body?.classList.contains('khdn-typing-mode')) return;
    if(mutationTouchesGrid(mutations)) scheduleGrid();
  });
  const syncGridObserver=()=>{
    if(mobile()&&!gridWatching){
      gridObserver.observe(document.body||document.documentElement,{childList:true,subtree:true});
      gridWatching=true;
      scheduleGrid();
    }else if(!mobile()&&gridWatching){
      gridObserver.disconnect();
      gridWatching=false;
    }
  };
  syncGridObserver();
  window.addEventListener('resize',syncGridObserver,{passive:true});
'''
    if old in page:
        page = page.replace(old, new, 1)
    elif "syncGridObserver" not in page:
        raise RuntimeError("Performance installer cannot find mobile MutationObserver marker")

    # Avoid permanent compositor layers. V2.14 did not keep the sidebar on a
    # will-change layer; doing so is unnecessary when the user is typing.
    page = page.replace(";will-change:transform,width", "")

    # V2.14-style editor focus mode: while an input/select/textarea is active,
    # all KHDN-added animations/transitions/shadows are paused on every screen
    # size, not only phones. Streamlit's native widget remains untouched.
    typing_fastpath = '''
<style id="khdn-typing-fastpath-style">
body.khdn-typing-mode div[class*="st-key-ops_alert_hot_"] button,
body.khdn-typing-mode div[class*="st-key-ops_alert_danger_"] button,
body.khdn-typing-mode div[class*="st-key-ops_alert_idle_"] button,
body.khdn-typing-mode div[class*="st-key-ops_create_"] button,
body.khdn-typing-mode div[class*="st-key-admin_nav_card_"] button,
body.khdn-typing-mode div[class*="st-key-ops_alert_hot_"] button::before,
body.khdn-typing-mode div[class*="st-key-ops_alert_danger_"] button::before{
  animation:none!important;
  transition:none!important;
  transform:none!important;
  box-shadow:none!important;
}
body.khdn-typing-mode section[data-testid="stSidebar"]{
  transition:none!important;
  will-change:auto!important;
}
body.khdn-typing-mode [data-testid="stTextInput"] *,
body.khdn-typing-mode [data-testid="stTextArea"] *,
body.khdn-typing-mode [data-testid="stNumberInput"] *,
body.khdn-typing-mode [data-baseweb="select"] *{
  transition:none!important;
  animation:none!important;
}
</style>
<script id="khdn-typing-fastpath">
(()=>{
  const isEditor=(el)=>!!el&&el.nodeType===1&&(
    el.matches?.('input,textarea,[contenteditable="true"]')||
    !!el.closest?.('[data-testid="stTextInput"],[data-testid="stTextArea"],[data-testid="stNumberInput"],[data-baseweb="select"]')
  );
  const syncTypingMode=()=>{
    const active=document.activeElement;
    document.body?.classList.toggle('khdn-typing-mode',isEditor(active));
  };
  document.addEventListener('focusin',event=>{
    if(isEditor(event.target)) document.body?.classList.add('khdn-typing-mode');
  },true);
  document.addEventListener('focusout',()=>setTimeout(syncTypingMode,0),true);
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden) document.body?.classList.remove('khdn-typing-mode');
    else syncTypingMode();
  },{passive:true});
})();
</script>
'''
    if 'id="khdn-typing-fastpath"' not in page:
        if "</head>" not in page:
            raise RuntimeError("Performance installer cannot find </head> for typing fast path")
        page = page.replace("</head>", typing_fastpath + "</head>", 1)
    else:
        # Replace an older installed fastpath when a cached build layer already
        # contains one. This keeps the installer idempotent.
        import re
        page = re.sub(r'<style id="khdn-typing-fastpath-style">.*?</style>\s*<script id="khdn-typing-fastpath">.*?</script>', typing_fastpath.strip(), page, count=1, flags=re.S)

    index.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    install()
