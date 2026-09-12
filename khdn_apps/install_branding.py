"""Install web-clip metadata and production UI source patches during image build."""
from pathlib import Path
import re
import shutil
import streamlit


def install():
    app_dir = Path(__file__).resolve().parent
    static = Path(streamlit.__file__).resolve().parent / "static"
    assets = app_dir / "static"
    index = static / "index.html"

    # Patch the compressed loader before runtime. The large application engine
    # stays compressed in Git; only compact UI fragments are transformed before exec().
    loader = app_dir / "app.py"
    loader_text = loader.read_text(encoding="utf-8")
    patch_marker = (
        "from khdn_apps.mobile_nav_patch import patch_source as _patch_source\n"
        "_source = _patch_source(_source)\n"
    )
    exec_line = 'exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())\n'
    if patch_marker not in loader_text:
        if exec_line not in loader_text:
            raise RuntimeError("KHDN loader exec line not found; mobile navigation patch not installed")
        loader_text = loader_text.replace(exec_line, patch_marker + exec_line, 1)

    # V2.35+: the old runtime support/QLKH override recreated ops_action_cards()
    # after the patched source had been loaded. Remove it so CBHT/QLKH use the
    # exact same source renderer as leader_view.
    runtime_nav_start = "# Remove the separate workflow pill strip on the two operational pages."
    runtime_nav_end = "# Dark-mode readability + yellow Create actions."
    start_idx = loader_text.find(runtime_nav_start)
    if start_idx >= 0:
        end_idx = loader_text.find(runtime_nav_end, start_idx)
        if end_idx < 0:
            raise RuntimeError("KHDN runtime navigation override end marker not found")
        loader_text = (
            loader_text[:start_idx]
            + "# V2.35+: CBHT/QLKH use the same patched source navigation renderer as leader_view.\n"
            + loader_text[end_idx:]
        )
    loader.write_text(loader_text, encoding="utf-8")

    page = index.read_text(encoding="utf-8")
    if "</head>" not in page:
        raise RuntimeError("Streamlit index.html has no head; branding not installed")
    page = re.sub(r'<link\b[^>]*rel=["\'](?:shortcut icon|icon|apple-touch-icon|apple-touch-icon-precomposed|manifest)["\'][^>]*>', '', page)
    page = re.sub(r'<title>.*?</title>', '<title>KHDN Apps</title>', page)
    # Keep the build idempotent when an image is rebuilt from a cached layer.
    page = re.sub(r'<script id="khdn-mobile-swipe">.*?</script>', '', page, flags=re.S)
    page = re.sub(r'<style id="khdn-mobile-swipe-style">.*?</style>', '', page, flags=re.S)
    tags = '''
<link rel="apple-touch-icon" sizes="180x180" href="/app/static/bidv-icon-180.png?v=official-3">
<link rel="icon" type="image/png" href="/app/static/bidv-icon-192.png?v=official-3">
<link rel="manifest" href="/app/static/manifest.json?v=official-3">
<meta name="apple-mobile-web-app-title" content="KHDN Apps">
<meta name="theme-color" content="#006B68">
<style id="khdn-mobile-swipe-style">
section[data-testid="stSidebar"]{transition:transform .30s cubic-bezier(.22,.61,.36,1),width .30s cubic-bezier(.22,.61,.36,1),box-shadow .30s ease!important;will-change:transform,width}

/* Primary create actions live in the same card grid as workflow statuses. */
div[class*="st-key-ops_create_support_view_"] button,
div[class*="st-key-ops_create_qlkh_view_"] button{
  background:linear-gradient(135deg,#FFD65A,#F4B41A)!important;
  border:1.6px solid #D89A00!important;
  color:#2C250F!important;
  -webkit-text-fill-color:#2C250F!important;
  font-weight:950!important;
  box-shadow:0 8px 22px rgba(244,180,26,.28)!important;
}
div[class*="st-key-ops_create_support_view_"] button p,
div[class*="st-key-ops_create_qlkh_view_"] button p,
div[class*="st-key-ops_create_support_view_"] button span,
div[class*="st-key-ops_create_qlkh_view_"] button span{
  color:#2C250F!important;-webkit-text-fill-color:#2C250F!important;font-weight:950!important;
}
div[class*="st-key-ops_create_support_view_"] button:hover,
div[class*="st-key-ops_create_qlkh_view_"] button:hover{
  background:linear-gradient(135deg,#FFE486,#FFC62E)!important;
  border-color:#F4B41A!important;
  transform:translateY(-1px)!important;
  box-shadow:0 10px 24px rgba(244,180,26,.34)!important;
}

/* Admin buttons use exactly the same idle/hover colors as work-management cards. */
div[class*="st-key-admin_nav_card_"] button,
div[class*="st-key-admin_nav_card_"] button[kind="primary"],
div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg,#173A37,#15302E)!important;
  color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;
  border-color:rgba(164,232,219,.42)!important;
  box-shadow:0 6px 17px rgba(0,0,0,.24)!important;
}
div[class*="st-key-admin_nav_card_"] button *,
div[class*="st-key-admin_nav_card_"] button[kind="primary"] *{
  color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;
}
div[class*="st-key-admin_nav_card_"] button:hover,
div[class*="st-key-admin_nav_card_"] button[kind="primary"]:hover{
  background:linear-gradient(135deg,#20514B,#1A3D39)!important;
  color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
  border-color:#F4B41A!important;
}

/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */
@media(max-width:768px){
  div[class*="st-key-ops_cards_"] button{
    width:100%!important;min-height:70px!important;padding:7px 6px!important;border-radius:13px!important;
  }
  div[class*="st-key-ops_cards_"] button p{
    font-size:.69rem!important;line-height:1.12!important;white-space:pre-line!important;
  }
}
@media(max-width:430px){
  div[class*="st-key-ops_cards_"] button{min-height:66px!important;padding:6px 4px!important}
  div[class*="st-key-ops_cards_"] button p{font-size:.64rem!important}
}
</style>
<script id="khdn-mobile-swipe">
(()=>{
  const mobile=()=>window.matchMedia&&window.matchMedia('(max-width: 768px)').matches;
  const sidebar=()=>document.querySelector('section[data-testid="stSidebar"]');
  const expanded=()=>sidebar()?.getAttribute('aria-expanded')==='true';
  const toggle=()=>{
    const panel=sidebar();
    const button=expanded()
      ? panel?.querySelector('[data-testid="stSidebarCollapseButton"] button')
      : document.querySelector('[data-testid="stExpandSidebarButton"]');
    if(button) button.click();
  };

  /*
   * Streamlit currently inserts an extra wrapper around stColumn on some phone
   * breakpoints. Earlier CSS shrank that wrapper to 50%, which produced exactly
   * the symptom seen on iPhone: every card was half-width but still stacked in
   * one left-hand column. Resolve the real column parent after render and apply
   * the same two-column layout used by the working Leader work-management page.
   */
  const directChildUnder=(node,parent)=>{
    let cur=node;
    while(cur&&cur.parentElement&&cur.parentElement!==parent) cur=cur.parentElement;
    return cur;
  };
  const commonAncestor=(nodes,limit)=>{
    if(!nodes.length) return null;
    let p=nodes[0].parentElement;
    while(p&&p!==limit){
      if(nodes.every(n=>p.contains(n))) return p;
      p=p.parentElement;
    }
    return limit;
  };
  const forceTwoColumnCards=()=>{
    if(!mobile()) return;
    const roots=document.querySelectorAll(
      'div[class*="st-key-ops_cards_support_view"],div[class*="st-key-ops_cards_qlkh_view"],div[class*="st-key-ops_cards_leader_view"],div[class*="st-key-ops_cards_admin_view"]'
    );
    roots.forEach(root=>{
      const hb=root.querySelector('[data-testid="stHorizontalBlock"]')||root;
      const cols=[...hb.querySelectorAll('[data-testid="stColumn"],[data-testid="column"]')]
        .filter(c=>c.querySelector('button'));
      if(cols.length<2) return;

      let layout=commonAncestor(cols,hb)||hb;
      if(layout===hb){
        const parents=[...new Set(cols.map(c=>c.parentElement))];
        if(parents.length===1&&parents[0]) layout=parents[0];
      }

      /* Undo any old 50%-width rule applied to the outer Streamlit wrapper. */
      let outer=layout;
      while(outer&&outer!==hb){
        outer.style.setProperty('width','100%','important');
        outer.style.setProperty('max-width','100%','important');
        outer.style.setProperty('min-width','0','important');
        outer.style.setProperty('flex','1 1 100%','important');
        outer=outer.parentElement;
      }
      hb.style.setProperty('width','100%','important');
      hb.style.setProperty('max-width','100%','important');

      layout.style.setProperty('display','flex','important');
      layout.style.setProperty('flex-wrap','wrap','important');
      layout.style.setProperty('gap','7px','important');
      layout.style.setProperty('align-items','stretch','important');
      layout.style.setProperty('width','100%','important');
      layout.style.setProperty('max-width','100%','important');

      const items=[...new Set(cols.map(c=>directChildUnder(c,layout)).filter(Boolean))];
      items.forEach(item=>{
        item.style.setProperty('flex','0 0 calc(50% - 4px)','important');
        item.style.setProperty('width','calc(50% - 4px)','important');
        item.style.setProperty('max-width','calc(50% - 4px)','important');
        item.style.setProperty('min-width','0','important');
        item.style.setProperty('box-sizing','border-box','important');
        item.style.setProperty('margin','0','important');
      });
      cols.forEach(col=>{
        col.style.setProperty('width','100%','important');
        col.style.setProperty('max-width','100%','important');
        col.style.setProperty('min-width','0','important');
      });
    });
  };

  let raf=0;
  const scheduleGrid=()=>{
    if(raf) cancelAnimationFrame(raf);
    raf=requestAnimationFrame(()=>{raf=0;forceTwoColumnCards();});
  };
  new MutationObserver(scheduleGrid).observe(document.documentElement,{childList:true,subtree:true});
  window.addEventListener('resize',scheduleGrid,{passive:true});
  document.addEventListener('DOMContentLoaded',scheduleGrid,{once:true});
  setTimeout(scheduleGrid,250);
  setTimeout(scheduleGrid,900);

  let startX=0,startY=0,tracking=false,startedInPanel=false;
  document.addEventListener('touchstart',event=>{
    if(!mobile()||event.touches.length!==1) return;
    const touch=event.touches[0],panel=sidebar();
    startedInPanel=!!panel?.contains(event.target);
    const fromEdge=touch.clientX<=30;
    if((!expanded()&&fromEdge)||(expanded()&&startedInPanel)){
      startX=touch.clientX;startY=touch.clientY;tracking=true;
    }else tracking=false;
  },{passive:true});
  document.addEventListener('touchend',event=>{
    if(!tracking||!mobile()) return;
    tracking=false;
    const touch=event.changedTouches[0],dx=touch.clientX-startX,dy=touch.clientY-startY;
    if(Math.abs(dx)<58||Math.abs(dx)<=Math.abs(dy)*1.15) return;
    if((dx>0&&!expanded()&&startX<=30)||(dx<0&&expanded()&&startedInPanel)) toggle();
  },{passive:true});
  document.addEventListener('touchcancel',()=>{tracking=false},{passive:true});
})();
</script>
'''
    page = page.replace("</head>", tags + "</head>")
    index.write_text(page, encoding="utf-8")
    for name in ("apple-touch-icon.png", "apple-touch-icon-precomposed.png"):
        shutil.copyfile(assets / "bidv-icon-180.png", static / name)


if __name__ == "__main__":
    install()