"""Build-time smoke check for the final transformed KHDN source.

Semantic transaction tests live in reason_categories_semantic_qa.py. This check focuses
on the exact UI source that will execute in Streamlit after all source transformers.
"""
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
from khdn_apps.input_batch_patch import patch_source as input_batch_patch
from khdn_apps.catalog_input_fast_patch import patch_source as catalog_fast_patch


def run():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    source=gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    source=catalog_fast_patch(input_batch_patch(performance_patch(reason_patch(mobile_patch(source)))))
    compile(source,"<khdn-final-streamlit-smoke>","exec")

    checks={
        "admin_reason_route": 'if admin_view == "reasons":\n        _render_reason_category_manager(u)' in source,
        "leader_reason_manager_absent": 'Quản lý nhóm nguyên nhân trả lại / hủy' not in source[source.find('def leader_page'):source.find('def dashboard_page')],
        "task_type_zero_keystroke": 'key="catalog_submit_only_task_type"' in source and 'st.text_input("Tên công việc mới")' not in source,
        "reason_zero_keystroke": 'catalog_submit_only_reason_' in source and 'st.text_input("Tên nhóm nguyên nhân mới")' not in source,
        "plain_catalog_table": 'class="khdn-catalog-table"' in source,
        "return_reason_required": 'Nhóm nguyên nhân trả lại *' in source and 'Lý do trả lại chi tiết *' in source,
        "cancel_reason_required": 'Nhóm nguyên nhân hủy *' in source and 'Lý do hủy chi tiết *' in source,
        "invalid_string_callback_absent": 'on_change="ignore"' not in source and "on_change='ignore'" not in source,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_FINAL_STREAMLIT_SMOKE",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN final Streamlit smoke failed: "+", ".join(failed))


if __name__=="__main__":
    run()
