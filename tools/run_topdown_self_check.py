"""tools/run_topdown_self_check.py — Tự kiểm tra module Top-Down mà không cần Streamlit.

Chạy: python tools/run_topdown_self_check.py

Kiểm tra:
    1. Tất cả file cấu hình JSON nạp được và đủ khóa bắt buộc.
    2. Ma trận độ nhạy phủ đủ 11 ngành × toàn bộ driver, giá trị nằm trong [-3; 3].
    3. Bảng chu kỳ phủ đủ 11 ngành × 5 pha, giá trị nằm trong [-3; 3].
    4. Điểm ngành luôn nằm trong [0; 100] với nhiều kịch bản triển vọng khác nhau.
    5. Tổng tỷ trọng đề xuất luôn xấp xỉ 100% và độ lệch không vượt giới hạn.
    6. Định dạng số tuân thủ nguyên tắc số 4.
    7. Mọi thuật ngữ trong glossary đều có diễn giải khác rỗng.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import module_topdown_engine as E  # noqa: E402

loi: list[str] = []
canh_bao: list[str] = []


def kiem_tra(dieu_kien: bool, thong_diep: str, la_loi: bool = True) -> None:
    if dieu_kien:
        print(f"  [OK]   {thong_diep}")
    else:
        print(f"  [{'LỖI' if la_loi else 'CẢNH BÁO'}] {thong_diep}")
        (loi if la_loi else canh_bao).append(thong_diep)


print("\n=== 1. NẠP CẤU HÌNH ===")
for ten, fn, khoa in [
    ("sector_taxonomy_gics.json", E.taxonomy, "sectors"),
    ("sector_drivers_fisher.json", E.drivers_config, "drivers"),
    ("cycle_playbook_fisher.json", E.cycle_config, "pha_chu_ky"),
    ("scoring_rules_topdown.json", E.scoring_config, "nguong_xep_hang_nganh"),
    ("benchmark_weights.json", E.benchmark_config, "benchmarks"),
]:
    data = fn()
    kiem_tra(bool(data) and khoa in data, f"{ten}: nạp được và có khóa '{khoa}'")

print("\n=== 2. MA TRẬN ĐỘ NHẠY ===")
codes = E.sector_codes()
driver_ids = [d["id"] for d in E.drivers_config().get("drivers", [])]
kiem_tra(len(codes) == 11, f"Có đúng 11 ngành (hiện tại: {len(codes)})")
kiem_tra(len(driver_ids) >= 20, f"Có ít nhất 20 driver (hiện tại: {len(driver_ids)})")

sens = E.drivers_config().get("do_nhay_theo_nganh", {})
for c in codes:
    thieu = [d for d in driver_ids if d not in sens.get(c, {})]
    kiem_tra(not thieu, f"Ngành {c} phủ đủ {len(driver_ids)} driver" + (f" — thiếu: {thieu}" if thieu else ""))
    ngoai = [d for d, v in sens.get(c, {}).items() if not -3 <= float(v) <= 3]
    kiem_tra(not ngoai, f"Ngành {c}: mọi độ nhạy nằm trong [-3; 3]" + (f" — sai: {ngoai}" if ngoai else ""))

print("\n=== 3. BẢNG CHU KỲ ===")
phases = E.cycle_config().get("pha_chu_ky", [])
kiem_tra(len(phases) == 5, f"Có đúng 5 pha chu kỳ (hiện tại: {len(phases)})")
for p in phases:
    thieu = [c for c in codes if c not in p.get("diem_theo_nganh", {})]
    kiem_tra(not thieu, f"Pha '{p['ten_vi']}' phủ đủ 11 ngành" + (f" — thiếu: {thieu}" if thieu else ""))
    ngoai = [c for c, v in p.get("diem_theo_nganh", {}).items() if not -3 <= float(v) <= 3]
    kiem_tra(not ngoai, f"Pha '{p['ten_vi']}': mọi điểm nằm trong [-3; 3]")

print("\n=== 4. ĐIỂM NGÀNH QUA NHIỀU KỊCH BẢN ===")
random.seed(20260823)
ngoai_khoang = 0
so_kich_ban = 60
for i in range(so_kich_ban):
    inp = E.default_input()
    inp.pha_chu_ky = random.choice([p["id"] for p in phases])
    inp.trien_vong_driver = {d: float(random.choice([-2, -1, 0, 1, 2])) for d in driver_ids}
    df = E.cham_diem_tat_ca_nganh(inp)
    if df["Điểm tổng hợp"].min() < 0 or df["Điểm tổng hợp"].max() > 100:
        ngoai_khoang += 1
kiem_tra(ngoai_khoang == 0, f"Điểm tổng hợp luôn nằm trong [0; 100] qua {so_kich_ban} kịch bản ngẫu nhiên")

# Kịch bản biên: toàn bộ driver ở mức cực trị.
for cuc_tri in (-2.0, 2.0):
    inp = E.default_input()
    inp.trien_vong_driver = {d: cuc_tri for d in driver_ids}
    df = E.cham_diem_tat_ca_nganh(inp)
    kiem_tra(
        0 <= df["Điểm tổng hợp"].min() and df["Điểm tổng hợp"].max() <= 100,
        f"Kịch bản biên (mọi driver = {cuc_tri:+.0f}): điểm vẫn trong [0; 100]",
    )

print("\n=== 5. TỶ TRỌNG ĐỀ XUẤT ===")
sai_tong, sai_lech = 0, 0
for i in range(so_kich_ban):
    inp = E.default_input()
    inp.pha_chu_ky = random.choice([p["id"] for p in phases])
    inp.trien_vong_driver = {d: float(random.choice([-2, -1, 0, 1, 2])) for d in driver_ids}
    inp.lech_toi_da = random.choice([3.0, 5.0, 8.0, 12.0])
    df = E.cham_diem_tat_ca_nganh(inp)
    tt = E.bang_ty_trong_de_xuat(df, inp)
    if abs(float(tt["Tỷ trọng đề xuất %"].sum()) - 100.0) > 0.5:
        sai_tong += 1
    # Sau chuẩn hóa lại ở bước cuối, độ lệch có thể nhích nhẹ; cho phép biên 1.0 điểm %.
    if float(tt["Độ lệch điểm %"].abs().max()) > inp.lech_toi_da + 1.0:
        sai_lech += 1
kiem_tra(sai_tong == 0, f"Tổng tỷ trọng đề xuất luôn ≈ 100.0% qua {so_kich_ban} kịch bản")
kiem_tra(sai_lech == 0, f"Độ lệch luôn nằm trong giới hạn qua {so_kich_ban} kịch bản")

print("\n=== 6. ĐỊNH DẠNG SỐ (NGUYÊN TẮC SỐ 4) ===")
kiem_tra(E.fmt_ty(1234567.89) == "1,234,568", f"Tỷ đồng không có thập phân: {E.fmt_ty(1234567.89)}")
kiem_tra(E.fmt_pct(12.345) == "12.3%", f"Phần trăm 1 thập phân: {E.fmt_pct(12.345)}")
kiem_tra(E.fmt_ratio(2.567) == "2.6", f"Hệ số 1 thập phân: {E.fmt_ratio(2.567)}")
kiem_tra(E.fmt_ty(None) == "N/A" and E.fmt_pct(None) == "N/A", "Giá trị rỗng hiển thị N/A")

print("\n=== 7. GHI CHÚ GIẢI THÍCH ===")
inp = E.default_input()
inp.trien_vong_driver = {d: float(random.choice([-2, -1, 0, 1, 2])) for d in driver_ids}
df = E.cham_diem_tat_ca_nganh(inp)
tt = E.bang_ty_trong_de_xuat(df, inp)
for _, r in df.iterrows():
    n = E.note_xep_hang_nganh(r.to_dict(), inp)
    if len(n) < 400:
        loi.append(f"Ghi chú xếp hạng ngành {r['Mã ngành']} quá ngắn")
kiem_tra(all(len(E.note_xep_hang_nganh(r.to_dict(), inp)) >= 400 for _, r in df.iterrows()), "Mọi ghi chú xếp hạng ngành đủ chi tiết")
kiem_tra(all(len(E.note_ty_trong(r.to_dict(), inp)) >= 300 for _, r in tt.iterrows()), "Mọi ghi chú tỷ trọng đủ chi tiết")
kiem_tra(all(len(E.note_driver(d, inp)) >= 200 for d in driver_ids), "Mọi ghi chú driver đủ chi tiết")

print("\n=== 8. THUẬT NGỮ ===")
terms = E.glossary_terms()
rong = [k for k, v in terms.items() if not str(v).strip()]
kiem_tra(len(terms) >= 40, f"Có ít nhất 40 thuật ngữ (hiện tại: {len(terms)})")
kiem_tra(not rong, "Mọi thuật ngữ đều có diễn giải" + (f" — rỗng: {rong}" if rong else ""))

print("\n=== 9. SÀNG LỌC ĐỊNH LƯỢNG ===")
import pandas as pd  # noqa: E402

mau = pd.DataFrame(
    [
        {"Mã CK": "AAA", "Tên doanh nghiệp": "DN A", "Mã ngành": "FIN", "Vốn hóa (tỷ đồng)": 20000,
         "P/E (lần)": 9.0, "P/B (lần)": 1.2, "P/CF (lần)": 6.0, "P/S (lần)": 1.5,
         "Nợ vay/Vốn chủ (lần)": 0.4, "GTGD bình quân 20 phiên (tỷ đồng)": 50},
        {"Mã CK": "BBB", "Tên doanh nghiệp": "DN B", "Mã ngành": "ITE", "Vốn hóa (tỷ đồng)": 300,
         "P/E (lần)": 45.0, "P/B (lần)": 12.0, "P/CF (lần)": 40.0, "P/S (lần)": 20.0,
         "Nợ vay/Vốn chủ (lần)": 3.0, "GTGD bình quân 20 phiên (tỷ đồng)": 0.5},
        {"Mã CK": "", "Tên doanh nghiệp": "", "Mã ngành": "MAT", "Vốn hóa (tỷ đồng)": None,
         "P/E (lần)": None, "P/B (lần)": None, "P/CF (lần)": None, "P/S (lần)": None,
         "Nợ vay/Vốn chủ (lần)": None, "GTGD bình quân 20 phiên (tỷ đồng)": None},
    ]
)
tc = E.scoring_config()["sang_loc_dinh_luong_mac_dinh"]["chat_che"]
kq = E.chay_sang_loc(mau, tc)
kiem_tra(list(kq["Kết quả"]) == ["Đạt", "Không đạt", "Chưa nhập"], f"Sàng lọc phân loại đúng: {list(kq['Kết quả'])}")
kiem_tra(len(str(kq.iloc[1]["Lý do loại"])) > 30, "Mã không đạt có lý do loại chi tiết")

print("\n=== 10. TỰ KIỂM TRA ĐỒNG BỘ ===")
kt = E.kiem_tra_dong_bo(inp, df, tt)
kiem_tra(len(kt) >= 6, f"Bảng kiểm tra có ít nhất 6 hạng mục (hiện tại: {len(kt)})")

print("\n" + "=" * 72)
if loi:
    print(f"KẾT QUẢ: THẤT BẠI — {len(loi)} lỗi, {len(canh_bao)} cảnh báo")
    for x in loi:
        print(f"  • {x}")
    sys.exit(1)
print(f"KẾT QUẢ: ĐẠT TOÀN BỘ — 0 lỗi, {len(canh_bao)} cảnh báo")
for x in canh_bao:
    print(f"  • {x}")
sys.exit(0)
