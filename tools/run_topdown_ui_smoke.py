"""tools/run_ui_smoke_test.py — Chạy thử toàn bộ giao diện mà KHÔNG cần cài Streamlit.

Mục đích: bắt lỗi runtime của tầng giao diện (sai tên tham số, sai khóa session,
sai kiểu dữ liệu truyền vào bảng, lỗi khi dữ liệu rỗng) trong môi trường không có
mạng để cài streamlit.

Cách làm: dựng một module 'streamlit' giả lập đủ các API mà dashboard sử dụng, nạp
vào sys.modules trước khi import dashboard, rồi gọi render_dashboard() qua nhiều
kịch bản tương tác khác nhau.

Chạy: python tools/run_ui_smoke_test.py

LƯU Ý: bộ giả lập này KHÔNG thay thế được việc chạy thật trên Streamlit. Nó chỉ xác
nhận mã Python không ném lỗi và luồng dữ liệu thông suốt. Phần hiển thị trực quan
(CSS, biểu đồ, hành vi click đôi trong iframe) vẫn phải kiểm tra bằng mắt khi deploy.
"""

from __future__ import annotations

import random
import sys
import traceback
import types
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

# ======================================================================================
# 1. Bộ giả lập Streamlit
# ======================================================================================

GHI_NHAN: dict[str, int] = {}
HTML_COMPONENTS: list[str] = []


def _dem(ten: str) -> None:
    GHI_NHAN[ten] = GHI_NHAN.get(ten, 0) + 1


class _SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc

    def __setattr__(self, k, v):
        self[k] = v


class _Ctx:
    """Đối tượng vừa là container vừa là context manager, giống st.columns/tabs/expander."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(sys.modules["streamlit"], name)


class _StubStreamlit(types.ModuleType):
    session_state = _SessionState()

    # --- các hàm chỉ hiển thị, không trả giá trị ---
    def _noop(self, *a, **k):
        return None

    markdown = caption = write = divider = _noop
    header = subheader = title = text = code = json = _noop
    info = warning = error = success = _noop
    page_link = _noop
    metric = _noop
    dataframe = table = _noop
    plotly_chart = pyplot = _noop
    rerun = _noop
    set_page_config = _noop
    stop = _noop

    def bar_chart(self, data=None, **k):
        # Bắt lỗi thật: st.bar_chart yêu cầu dữ liệu số.
        if isinstance(data, pd.DataFrame):
            for c in data.columns:
                pd.to_numeric(data[c], errors="raise")
        _dem("bar_chart")

    line_chart = area_chart = bar_chart

    # --- layout ---
    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(n)]

    def tabs(self, labels):
        _dem("tabs")
        return [_Ctx() for _ in labels]

    def expander(self, label, expanded=False):
        return _Ctx()

    def container(self, **k):
        return _Ctx()

    def form(self, key, **k):
        return _Ctx()

    empty = container
    spinner = container

    # --- widget: trả về giá trị mặc định hoặc giá trị được kịch bản ép ---
    _ep: dict[str, object] = {}

    def _lay(self, key, mac_dinh):
        if key is not None and key in self._ep:
            return self._ep[key]
        return mac_dinh

    def selectbox(self, label, options, index=0, format_func=None, key=None, **k):
        opts = list(options)
        if not opts:
            return None
        if format_func:
            for o in opts:
                format_func(o)  # gọi thật để bắt lỗi trong lambda
        return self._lay(key, opts[min(index, len(opts) - 1)])

    def radio(self, label, options, index=0, horizontal=False, format_func=None, key=None, **k):
        return self.selectbox(label, options, index, format_func, key)

    def multiselect(self, label, options, default=None, key=None, **k):
        return self._lay(key, list(default) if default is not None else [])

    def select_slider(self, label, options, value=None, format_func=None, key=None, **k):
        opts = list(options)
        if format_func:
            for o in opts:
                format_func(o)
        return self._lay(key, value if value is not None else opts[0])

    def slider(self, label, min_value=0.0, max_value=1.0, value=None, step=None, key=None, **k):
        return self._lay(key, value if value is not None else min_value)

    def number_input(self, label, min_value=None, max_value=None, value=0.0, step=None, format=None, key=None, **k):
        return self._lay(key, value)

    def text_input(self, label, value="", key=None, **k):
        return self._lay(key, value)

    def checkbox(self, label, value=False, key=None, **k):
        return self._lay(key, value)

    def button(self, label, key=None, **k):
        return self._lay(key, False)

    def download_button(self, label, data, file_name=None, mime=None, key=None, **k):
        # Bắt lỗi thật: data phải serialize được.
        if not isinstance(data, (bytes, bytearray, str)):
            raise TypeError(f"download_button '{label}': dữ liệu phải là bytes hoặc str, nhận {type(data)}")
        _dem("download_button")
        return False

    def file_uploader(self, label, type=None, key=None, **k):
        return self._lay(key, None)

    def data_editor(self, data, key=None, **k):
        _dem("data_editor")
        return data.copy() if isinstance(data, pd.DataFrame) else data

    # --- sidebar ---
    @property
    def sidebar(self):
        return _Ctx()

    # --- column_config ---
    class column_config:  # noqa: N801
        @staticmethod
        def NumberColumn(*a, **k):  # noqa: N802
            return {"type": "number"}

        @staticmethod
        def SelectboxColumn(*a, **k):  # noqa: N802
            return {"type": "selectbox"}

        @staticmethod
        def TextColumn(*a, **k):  # noqa: N802
            return {"type": "text"}


stub = _StubStreamlit("streamlit")
sys.modules["streamlit"] = stub

_components_v1 = types.ModuleType("streamlit.components.v1")


def _html(html_doc, height=None, scrolling=False):
    HTML_COMPONENTS.append(html_doc)
    _dem("components_html")


_components_v1.html = _html
_components = types.ModuleType("streamlit.components")
_components.v1 = _components_v1
sys.modules["streamlit.components"] = _components
sys.modules["streamlit.components.v1"] = _components_v1

# ======================================================================================
# 2. Chạy các kịch bản
# ======================================================================================

loi: list[str] = []


def chay_kich_ban(ten: str, ep: dict | None = None, session: dict | None = None) -> None:
    stub._ep = dict(ep or {})
    stub.session_state.clear()
    stub.session_state.update(session or {})
    HTML_COMPONENTS.clear()
    try:
        import module_topdown_dashboard as D

        D.render_dashboard()
        print(f"  [OK]   {ten} — dựng {len(HTML_COMPONENTS)} bảng có ghi chú")
    except Exception as exc:  # noqa: BLE001
        print(f"  [LỖI]  {ten}: {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=6)
        loi.append(f"{ten}: {exc}")


print("\n=== 1. NẠP DASHBOARD ===")
try:
    import module_topdown_dashboard as D  # noqa: E402

    print("  [OK]   Import module_topdown_dashboard thành công")
except Exception as exc:  # noqa: BLE001
    print(f"  [LỖI]  Không import được dashboard: {exc}")
    traceback.print_exc()
    sys.exit(1)

import module_topdown_engine as E  # noqa: E402

driver_ids = [d["id"] for d in E.drivers_config().get("drivers", [])]
phase_ids = [p["id"] for p in E.cycle_config().get("pha_chu_ky", [])]

print("\n=== 2. KỊCH BẢN MẶC ĐỊNH ===")
chay_kich_ban("Mở app lần đầu, chưa chấm driver nào")

print("\n=== 3. KỊCH BẢN TƯƠNG TÁC SIDEBAR ===")
for pha in phase_ids:
    chay_kich_ban(
        f"Đổi pha chu kỳ sang '{pha}'",
        ep={"sb_pha": pha, **{f"drv_{d}": 1.0 for d in driver_ids[:8]}},
    )

for bm in [b["id"] for b in E.benchmark_config().get("benchmarks", [])]:
    chay_kich_ban(f"Đổi benchmark sang '{bm}'", ep={"sb_bm": bm})

print("\n=== 4. KỊCH BẢN CHẤM DRIVER CỰC TRỊ ===")
for muc in (-2.0, 2.0):
    chay_kich_ban(
        f"Mọi driver = {muc:+.0f}",
        ep={f"drv_{d}": muc for d in driver_ids},
    )

print("\n=== 5. KỊCH BẢN NGẪU NHIÊN ===")
random.seed(20260824)
for i in range(8):
    ep = {f"drv_{d}": float(random.choice([-2, -1, 0, 1, 2])) for d in driver_ids}
    ep["sb_pha"] = random.choice(phase_ids)
    ep["attr_0"] = True
    ep["attr_3"] = True
    chay_kich_ban(f"Ngẫu nhiên #{i + 1}", ep=ep)

print("\n=== 6. KỊCH BẢN DỮ LIỆU XẤU ===")
chay_kich_ban(
    "Benchmark tổng khác 100% (chỉ có 2 ngành)",
    session={"topdown_benchmark_weights": {"FIN": 30.0, "ITE": 20.0}},
)
chay_kich_ban(
    "Benchmark toàn số 0",
    session={"topdown_benchmark_weights": {c: 0.0 for c in E.sector_codes()}},
)
chay_kich_ban(
    "Trọng số bốn trục đều bằng 0",
    session={"topdown_trong_so": {"driver_kinh_te": 0.0, "driver_chinh_tri": 0.0, "driver_tam_ly": 0.0, "vi_the_chu_ky": 0.0}},
)
chay_kich_ban(
    "Bảng sàng lọc có dữ liệu thật",
    session={
        "topdown_bang_sang_loc": pd.DataFrame(
            [
                {"Mã CK": "AAA", "Tên doanh nghiệp": "DN A", "Mã ngành": "FIN", "Vốn hóa (tỷ đồng)": 20000,
                 "P/E (lần)": 9.0, "P/B (lần)": 1.2, "P/CF (lần)": 6.0, "P/S (lần)": 1.5,
                 "Nợ vay/Vốn chủ (lần)": 0.4, "GTGD bình quân 20 phiên (tỷ đồng)": 50},
                {"Mã CK": "BBB", "Tên doanh nghiệp": "DN B", "Mã ngành": "ITE", "Vốn hóa (tỷ đồng)": 300,
                 "P/E (lần)": -5.0, "P/B (lần)": 12.0, "P/CF (lần)": 40.0, "P/S (lần)": 20.0,
                 "Nợ vay/Vốn chủ (lần)": 3.0, "GTGD bình quân 20 phiên (tỷ đồng)": 0.5},
            ]
        )
    },
)
chay_kich_ban("Tìm thuật ngữ không tồn tại", ep={"": ""}, session={})

print("\n=== 7. KIỂM TRA NỘI DUNG BẢNG SINH RA ===")
stub._ep = {f"drv_{d}": 1.0 for d in driver_ids}
stub.session_state.clear()
HTML_COMPONENTS.clear()
D.render_dashboard()

kiem = []


def ktra(dk: bool, msg: str) -> None:
    print(f"  [{'OK' if dk else 'LỖI'}]   {msg}")
    if not dk:
        loi.append(msg)


ktra(len(HTML_COMPONENTS) >= 6, f"Sinh ra ít nhất 6 bảng có ghi chú (thực tế: {len(HTML_COMPONENTS)})")
tat_ca = "\n".join(HTML_COMPONENTS)
ktra("dblclick" in tat_ca, "Bảng có gắn sự kiện nhấp đôi (nguyên tắc số 6)")
ktra("data-note" in tat_ca, "Mỗi dòng bảng có mang dữ liệu ghi chú")
ktra("GLOSSARY" in tat_ca and "termtip" in tat_ca, "Bảng có tính năng quét chọn thuật ngữ (nguyên tắc số 9)")
ktra("heat-green" in tat_ca and "heat-red" in tat_ca, "Bảng có tô màu nhiệt (nguyên tắc số 8)")
ktra("rgba(239,68,68" in tat_ca or "rgba(16,185,129" in tat_ca, "Bảng có tô gradient âm đỏ / dương xanh (nguyên tắc số 5)")

# Kiểm tra định dạng số hiển thị trong HTML (nguyên tắc số 4).
import re  # noqa: E402

pct = re.findall(r">(\d[\d,]*\.\d)%<", tat_ca)
ktra(len(pct) > 0, f"Phần trăm hiển thị đúng 1 chữ số thập phân ({len(pct)} ô)")
pct_sai = re.findall(r">(\d[\d,]*\.\d{2,})%<", tat_ca)
ktra(not pct_sai, f"Không có ô phần trăm nhiều hơn 1 thập phân (sai: {pct_sai[:5]})")

# Kiểm tra kết quả đã đẩy sang session dùng chung (nguyên tắc số 7).
for k in [
    "topdown_ranking",
    "topdown_weights",
    "topdown_top_sector_code",
    "topdown_cycle_phase",
    "topdown_governed_snapshot_payload",
]:
    ktra(k in stub.session_state, f"Đã đẩy '{k}' sang session dùng chung")
ktra(
    stub.session_state.get("topdown_governed_snapshot_payload", {}).get("schema")
    == "trecapital-topdown-sector-context-v1",
    "Governed session payload dùng đúng Phase 8 schema",
)

print("\n=== 8. THỐNG KÊ WIDGET ĐÃ DỰNG ===")
for k, v in sorted(GHI_NHAN.items()):
    print(f"  {k}: {v} lần")

print("\n" + "=" * 72)
if loi:
    print(f"KẾT QUẢ: THẤT BẠI — {len(loi)} lỗi")
    for x in loi:
        print(f"  • {x}")
    sys.exit(1)
print("KẾT QUẢ: ĐẠT TOÀN BỘ — giao diện dựng được qua mọi kịch bản, 0 lỗi")
sys.exit(0)
