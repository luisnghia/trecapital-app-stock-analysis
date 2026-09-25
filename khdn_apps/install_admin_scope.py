"""Install the final admin-scope transform into the compressed app loader."""
from pathlib import Path


def install():
    app_dir=Path(__file__).resolve().parent
    loader=app_dir/"app.py"
    text=loader.read_text(encoding="utf-8")
    patch=(
        "from khdn_apps.admin_scope_patch import patch_source as _admin_scope_patch_source\n"
        "_source = _admin_scope_patch_source(_source)\n"
    )
    if patch in text:
        return
    # performance installer registers linecache immediately before exec. Put the
    # admin transform before that registration so inspect.getsource sees exactly
    # the source that is executed.
    linecache_marker="import linecache as _source_linecache\n"
    exec_marker='exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())\n'
    if linecache_marker in text:
        text=text.replace(linecache_marker,patch+linecache_marker,1)
    elif exec_marker in text:
        text=text.replace(exec_marker,patch+exec_marker,1)
    else:
        raise RuntimeError("Admin-scope installer cannot find loader execution marker")
    loader.write_text(text,encoding="utf-8")


if __name__=="__main__":
    install()
