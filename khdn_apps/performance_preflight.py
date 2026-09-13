"""Build-time structural QA for KHDN speed v1."""
from pathlib import Path
import base64
import gzip
import sys

_app_root=str(Path(__file__).resolve().parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0,_app_root)

from khdn_apps.mobile_nav_patch import patch_source as mobile_patch
from khdn_apps.reason_categories_patch import patch_source as reason_patch
from khdn_apps.performance_patch import patch_source as performance_patch


def main():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    baseline=reason_patch(mobile_patch(gzip.decompress(base64.b64decode(payload)).decode("utf-8")))
    source=performance_patch(baseline)
    compile(source,"<khdn-speed-preflight>","exec")

    get_conn_block=source[source.index("def get_conn") : source.index("def table_columns")]
    main_tail=source[source.index("def app()"):] if "def app()" in source else source[-25000:]
    checks={
        "wal_not_per_connection": "PRAGMA journal_mode=WAL" not in get_conn_block,
        "wal_still_initialized": 'c.execute("PRAGMA journal_mode=WAL")' in source,
        "user_validation_throttled": "_user_last_validated_mono" in main_tail and ">= 10.0" in main_tail,
        "realtime_page_scoped": 'if page in {"support", "qlkh", "leader", "dashboard"}' in main_tail,
        "admin_route_before_poll": main_tail.find("page = sidebar_navigation(u)") < main_tail.find("realtime_refresh_watch(u)"),
        "source_compiles": True,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_SPEED_PREFLIGHT",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN speed preflight failed: "+", ".join(failed))


if __name__=="__main__":
    main()
