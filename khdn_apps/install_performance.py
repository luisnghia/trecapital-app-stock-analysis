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
    )
    if perf not in text:
        if exec_line not in text:
            raise RuntimeError("Performance installer cannot find loader exec marker")
        text = text.replace(exec_line, perf + exec_line, 1)
    loader.write_text(text, encoding="utf-8")

    # The previous mobile grid observer watched the entire document and ran a
    # document-wide query after every Streamlit DOM mutation. Limit work to DOM
    # changes that can actually affect the operational-card grids.
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
  const gridObserver=new MutationObserver(mutations=>{
    if(document.body?.classList.contains('khdn-typing-mode')) return;
    if(mutationTouchesGrid(mutations)) scheduleGrid();
  });
  gridObserver.observe(document.body||document.documentElement,{childList:true,subtree:true});
'''
    if old not in page:
        raise RuntimeError("Performance installer cannot find mobile MutationObserver marker")
    page = page.replace(old, new, 1)

    # Older/mobile GPUs can spend a surprising amount of time continuously
    # compositing the pulsing alert cards while the software keyboard is active.
    # Pause non-essential animation/transition work only while a text editor has
    # focus. This keeps all alert animation intact as soon as the user leaves the
    # field, while prioritising keystroke paint latency during typing.
    typing_fastpath = '''
<style id="khdn-typing-fastpath-style">
@media(max-width:768px){
  body.khdn-typing-mode div[class*="st-key-ops_alert_hot_"] button,
  body.khdn-typing-mode div[class*="st-key-ops_alert_danger_"] button,
  body.khdn-typing-mode div[class*="st-key-ops_alert_hot_"] button::before,
  body.khdn-typing-mode div[class*="st-key-ops_alert_danger_"] button::before{
    animation:none!important;transform:none!important;
  }
  body.khdn-typing-mode section[data-testid="stSidebar"]{
    transition:none!important;will-change:auto!important;
  }
}
</style>
<script id="khdn-typing-fastpath">
(()=>{
  const isEditor=(el)=>!!el&&el.nodeType===1&&el.matches?.('input,textarea,[contenteditable="true"]');
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

    index.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    install()
