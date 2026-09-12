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

    # V2.35: the old runtime support/QLKH override recreated ops_action_cards()
    # after the patched source had been loaded. That gave CBHT/QLKH a different
    # DOM path from leader_view and defeated the proven mobile 2-column layout.
    # Remove that override at image-build time so all three workflow pages use
    # the exact same source ops_action_cards() renderer.
    runtime_nav_start = "# Remove the separate workflow pill strip on the two operational pages."
    runtime_nav_end = "# Dark-mode readability + yellow Create actions."
    start_idx = loader_text.find(runtime_nav_start)
    if start_idx >= 0:
        end_idx = loader_text.find(runtime_nav_end, start_idx)
        if end_idx < 0:
            raise RuntimeError("KHDN runtime navigation override end marker not found")
        loader_text = (
            loader_text[:start_idx]
            + "# V2.35: CBHT/QLKH use the same patched source navigation renderer as leader_view.\n"
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

/* Mobile fallback: every ops_cards_* group is two columns, same DOM path as leader_view. */
@media(max-width:768px){
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"]{
    display:flex!important;flex-wrap:wrap!important;gap:.44rem!important;align-items:stretch!important;
  }
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"] > [data-testid="column"],
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"] > div{
    flex:0 0 calc(50% - .22rem)!important;
    width:calc(50% - .22rem)!important;
    min-width:0!important;max-width:calc(50% - .22rem)!important;
    box-sizing:border-box!important;margin:0!important;padding:0!important;
  }
  div[class*="st-key-ops_cards_"] button{
    width:100%!important;min-height:70px!important;padding:7px 6px!important;border-radius:13px!important;
  }
  div[class*="st-key-ops_cards_"] button p{
    font-size:.69rem!important;line-height:1.12!important;white-space:pre-line!important;
  }
}
@media(max-width:430px){
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"] > [data-testid="column"],
  div[class*="st-key-ops_cards_"] div[data-testid="stHorizontalBlock"] > div{
    flex:0 0 calc(50% - .22rem)!important;
    width:calc(50% - .22rem)!important;min-width:0!important;max-width:calc(50% - .22rem)!important;
  }
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
