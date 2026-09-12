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
