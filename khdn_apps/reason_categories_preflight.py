"""Build-time QA for reason-category workflow on the exact V2.38 compressed source."""
from pathlib import Path
import base64, gzip, sys

# Docker executes this file directly before the runtime ENV PYTHONPATH is applied.
# Add /app explicitly so the preflight imports the same package copied into the image.
_app_root=str(Path(__file__).resolve().parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0,_app_root)

from khdn_apps.mobile_nav_patch import patch_source as mobile_patch
from khdn_apps.reason_categories_patch import patch_source as reason_patch


def main():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    source=gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    source=mobile_patch(source)
    source=reason_patch(source)
    compile(source,"<khdn-reason-preflight>","exec")
    leader=source[source.index("def leader_page(u):"):source.index("def make_excel_report")]
    admin=source[source.index("def admin_page(u):"):]
    checks={
        "leader_has_no_reason_manager": "Nhóm nguyên nhân" not in leader and "_render_reason_category_manager" not in leader,
        "admin_has_reason_button": '("reasons","🧩","Nhóm nguyên nhân")' in admin,
        "return_selectors": source.count('reason_category_selectbox("RETURN"')==2,
        "cancel_selectors": source.count('reason_category_selectbox("CANCEL"')==2,
        "reason_table": "CREATE TABLE IF NOT EXISTS reason_categories" in source,
        "reason_events": "CREATE TABLE IF NOT EXISTS task_reason_events" in source,
        "atomic_transition": "def _reasoned_task_transition" in source,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_REASON_PREFLIGHT",checks,flush=True)
    if failed:
        raise RuntimeError("Reason-category preflight failed: "+", ".join(failed))


if __name__ == "__main__":
    main()
