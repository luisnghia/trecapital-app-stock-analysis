"""Build-time structural QA for KHDN V2.14 golden-input fast flow."""
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


def main():
    root=Path(__file__).resolve().parent
    payload="".join(p.read_text(encoding="ascii") for p in sorted((root/"_src").glob("*.txt")))
    baseline=reason_patch(mobile_patch(gzip.decompress(base64.b64decode(payload)).decode("utf-8")))
    source=input_batch_patch(performance_patch(baseline))
    compile(source,"<khdn-speed-preflight>","exec")

    get_conn_block=source[source.index("def get_conn") : source.index("def table_columns")]
    main_tail=source[source.index("def app()"):] if "def app()" in source else source[-25000:]
    search_anchor='placeholder="Nhập CIF hoặc tên khách hàng để tìm nhanh…"'
    reason_block=source[source.index("def _render_reason_category_manager") : source.index("def user_by_username")]
    type_start=source.index('    if admin_view == "types":')
    type_end=source.index('    if admin_view == "reasons":', type_start)
    type_block=source[type_start:type_end]
    component_py=(root/"fast_catalog_input.py").read_text(encoding="utf-8")
    component_html=(root/"fast_catalog_component"/"index.html").read_text(encoding="utf-8")
    checks={
        "wal_not_per_connection": "PRAGMA journal_mode=WAL" not in get_conn_block,
        "wal_still_initialized": 'c.execute("PRAGMA journal_mode=WAL")' in source,
        "user_validation_throttled": "_user_last_validated_mono" in main_tail and ">= 10.0" in main_tail,
        "realtime_page_scoped": 'if page in {"support", "qlkh", "leader", "dashboard"}' in main_tail,
        "admin_route_before_poll": main_tail.find("page = sidebar_navigation(u)") < main_tail.find("realtime_refresh_watch(u)"),
        "invalid_string_callbacks_absent": 'on_change="ignore"' not in source and "on_change='ignore'" not in source,
        "task_type_zero_keystroke_component": 'fast_catalog_input("Tên công việc mới"' in type_block and 'st.text_input("Tên công việc mới")' not in type_block,
        "task_type_table_and_edit_same_page": type_block.find('st.dataframe(types') < type_block.find('fast_catalog_input("Tên công việc mới"') and 'Chọn loại công việc để sửa' in type_block and 'Cập nhật loại công việc' in type_block,
        "task_type_no_extra_mode": 'task_type_catalog_mode_fast' not in type_block and 'Danh sách / trạng thái' not in type_block,
        "reason_route_preserved": '    if admin_view == "reasons":\n        _render_reason_category_manager(u)\n' in source,
        "reason_zero_keystroke_component": 'fast_catalog_input("Tên nhóm nguyên nhân mới"' in reason_block and 'st.text_input("Tên nhóm nguyên nhân mới")' not in reason_block,
        "reason_single_kind_only": 'key="reason_catalog_kind_v214"' in reason_block and 'st.tabs(' not in reason_block,
        "reason_table_and_edit_same_page": 'df=qdf("SELECT id,name,active,created_at,updated_at FROM reason_categories WHERE reason_type=? ORDER BY id"' in reason_block and 'with st.form(f"reason_edit_form_{kind}_{int(xid)}"):' in reason_block,
        "reason_no_extra_mode": 'reason_catalog_mode_' not in reason_block and 'Danh sách / chỉnh sửa' not in reason_block,
        "qlkh_create_payload_batched": 'with st.form("qlkh_create_payload_form", clear_on_submit=False, enter_to_submit=False):' in source and 'st.form_submit_button("Giao hồ sơ cho Cán bộ hỗ trợ"' in source,
        "support_create_payload_batched": 'with st.form("support_create_payload_form", clear_on_submit=False, enter_to_submit=False):' in source and 'st.form_submit_button("Tạo tác nghiệp"' in source,
        "qlkh_note_same_native_widget": 'st.text_area("Ghi chú / yêu cầu xử lý (không bắt buộc)",key="ql_new_note")' in source,
        "customer_search_stays_live_outside_form": source.find('cust=customer_selector("ql_new_cust"') < source.find('with st.form("qlkh_create_payload_form"') and search_anchor in source,
        "component_does_not_emit_on_input": "inputEl.addEventListener('input'" not in component_html and "streamlit:setComponentValue" in component_html,
        "component_emits_only_on_submit": "function submit()" in component_html and "buttonEl.addEventListener('click',submit)" in component_html and "event.key==='Enter'" in component_html,
        "component_bridge_dedupes_submit": "_khdn_fast_catalog_seen_" in component_py,
        "source_compiles": True,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_V214_GOLDEN_PREFLIGHT",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN V2.14 golden-input preflight failed: "+", ".join(failed))


if __name__=="__main__":
    main()
