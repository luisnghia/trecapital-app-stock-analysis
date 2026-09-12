"""Final browser-layer color fix for Admin navigation buttons.

This runs after install_branding.py and injects a highly-specific CSS/DOM patch
so Streamlit's primary-button state cannot recolor the selected Admin button.
The palette intentionally matches idle work-management cards.
"""
from pathlib import Path
import streamlit


def install():
    static = Path(streamlit.__file__).resolve().parent / "static"
    index = static / "index.html"
    page = index.read_text(encoding="utf-8")
    marker = '<style id="khdn-admin-color-fix">'
    if marker in page:
        return

    patch = r'''
<style id="khdn-admin-color-fix">
/* V2.37: Admin navigation must look exactly like idle Work Management cards,
   including the currently selected button. */
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button,
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button[kind="primary"],
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"],
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button[kind="secondary"],
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-secondary"]{
  background:linear-gradient(135deg,#173A37,#15302E)!important;
  color:#F4FFFC!important;
  -webkit-text-fill-color:#F4FFFC!important;
  border:1.4px solid rgba(164,232,219,.42)!important;
  box-shadow:0 6px 17px rgba(0,0,0,.24)!important;
  font-weight:850!important;
}
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button *,
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button[kind="primary"] *{
  color:#F4FFFC!important;
  -webkit-text-fill-color:#F4FFFC!important;
}
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button:hover,
html body div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button[kind="primary"]:hover{
  background:linear-gradient(135deg,#20514B,#1A3D39)!important;
  color:#FFFFFF!important;
  -webkit-text-fill-color:#FFFFFF!important;
  border-color:#0B7F75!important;
  box-shadow:0 10px 22px rgba(11,127,117,.14)!important;
  transform:translateY(-1px)!important;
}
</style>
<script id="khdn-admin-color-fix-script">
(()=>{
  const paint=()=>{
    document.querySelectorAll('div[class*="st-key-ops_cards_admin_view"] div[class*="st-key-admin_nav_card_"] button').forEach(btn=>{
      btn.style.setProperty('background','linear-gradient(135deg,#173A37,#15302E)','important');
      btn.style.setProperty('color','#F4FFFC','important');
      btn.style.setProperty('-webkit-text-fill-color','#F4FFFC','important');
      btn.style.setProperty('border','1.4px solid rgba(164,232,219,.42)','important');
      btn.style.setProperty('box-shadow','0 6px 17px rgba(0,0,0,.24)','important');
      btn.querySelectorAll('*').forEach(el=>{
        el.style.setProperty('color','#F4FFFC','important');
        el.style.setProperty('-webkit-text-fill-color','#F4FFFC','important');
      });
    });
  };
  const start=()=>{
    paint();
    new MutationObserver(paint).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['kind','data-testid','class']});
  };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
</script>
'''
    if "</head>" not in page:
        raise RuntimeError("Streamlit index.html has no </head> for admin color fix")
    index.write_text(page.replace("</head>", patch + "</head>"), encoding="utf-8")


if __name__ == "__main__":
    install()
