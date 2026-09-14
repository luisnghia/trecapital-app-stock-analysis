"""Install KHDN performance patches into the built Streamlit image."""
from pathlib import Path
import re
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
        "from khdn_apps.catalog_input_fast_patch import patch_source as _catalog_input_fast_patch_source\n"
        "_source = _catalog_input_fast_patch_source(_source)\n"
    )
    old_variants = [
        (
            "from khdn_apps.performance_patch import patch_source as _performance_patch_source\n"
            "_source = _performance_patch_source(_source)\n"
            "from khdn_apps.input_batch_patch import patch_source as _input_batch_patch_source\n"
            "_source = _input_batch_patch_source(_source)\n"
        ),
        (
            "from khdn_apps.performance_patch import patch_source as _performance_patch_source\n"
            "_source = _performance_patch_source(_source)\n"
        ),
    ]
    if perf not in text:
        replaced=False
        for old_perf in old_variants:
            if old_perf in text:
                text=text.replace(old_perf,perf,1); replaced=True; break
        if not replaced:
            if exec_line not in text:
                raise RuntimeError("Performance installer cannot find loader exec marker")
            text=text.replace(exec_line,perf+exec_line,1)
    # inspect.getsource (used by Streamlit cache decorators) must see the final
    # transformed source, not the older readable snapshot at the same filename.
    source_cache = (
        "import linecache as _source_linecache\n"
        "_source_filename = str(_Path(__file__).resolve().parent / 'app_v223_source.py')\n"
        "_source_linecache.cache[_source_filename] = (len(_source), None, _source.splitlines(keepends=True), _source_filename)\n"
    )
    if source_cache not in text:
        if exec_line not in text:
            raise RuntimeError("Cannot register transformed source before execution")
        text=text.replace(exec_line,source_cache+exec_line,1)
    loader.write_text(text,encoding="utf-8")

    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    page = index.read_text(encoding="utf-8")

    # Remove any previously installed global typing-mode script/style. V2.14 had
    # no focus listeners or body-class toggles; the browser should be left alone
    # while a native widget is accepting keystrokes.
    page = re.sub(r'<style id="khdn-typing-fastpath-style">.*?</style>\s*<script id="khdn-typing-fastpath">.*?</script>', '', page, flags=re.S)

    # Keep the mobile 2-column correction only when an operational card grid
    # actually exists. Admin catalog pages therefore have zero MutationObservers.
    old = "  new MutationObserver(scheduleGrid).observe(document.documentElement,{childList:true,subtree:true});\n"
    new = '''  const OPS_GRID_SELECTOR='div[class*="st-key-ops_cards_support_view"],div[class*="st-key-ops_cards_qlkh_view"],div[class*="st-key-ops_cards_leader_view"],div[class*="st-key-ops_cards_admin_view"]';
  const hasOpsGrid=()=>!!document.querySelector(OPS_GRID_SELECTOR);
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
    if(mutationTouchesGrid(mutations)) scheduleGrid();
  });
  const syncGridObserver=()=>{
    const shouldWatch=mobile()&&hasOpsGrid();
    if(shouldWatch&&!gridWatching){
      gridObserver.observe(document.body||document.documentElement,{childList:true,subtree:true});
      gridWatching=true;
      scheduleGrid();
    }else if(!shouldWatch&&gridWatching){
      gridObserver.disconnect();
      gridWatching=false;
    }
  };
  syncGridObserver();
  window.addEventListener('resize',syncGridObserver,{passive:true});
  setTimeout(syncGridObserver,250);
  setTimeout(syncGridObserver,900);
'''
    if old in page:
        page=page.replace(old,new,1)
    elif "hasOpsGrid" not in page:
        # Replace the immediately previous observer implementation if present.
        page=re.sub(
            r"  const OPS_GRID_SELECTOR=.*?window\.addEventListener\('resize',syncGridObserver,\{passive:true\}\);\n",
            new,
            page,
            count=1,
            flags=re.S,
        )
        if "hasOpsGrid" not in page:
            raise RuntimeError("Performance installer cannot find mobile grid observer marker")

    # Do not keep the sidebar on a permanent compositor layer.
    page=page.replace(";will-change:transform,width","")
    page=page.replace("will-change:transform,width;","")

    index.write_text(page,encoding="utf-8")


if __name__ == "__main__":
    install()
