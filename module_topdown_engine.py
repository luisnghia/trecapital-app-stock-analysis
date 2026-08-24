"""module_topdown_engine.py — Bộ máy tính toán của module Phân tích Top-Down theo ngành.

Toàn bộ công thức trong file này được diễn giải chi tiết tại:
    docs/FORMULA_EXPLANATION_TOPDOWN.md
và ánh xạ về tài liệu nguồn tại:
    docs/SOURCE_MAPPING_FISHER.md

Nguyên tắc đơn vị (nguyên tắc xây dựng app số 4):
    - Giá trị tiền: tỷ đồng, không có số thập phân.
    - Phần trăm: 1 số thập phân.
    - Hệ số/lần: 1 số thập phân.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

from tre_log import log_event, traced

APP_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = APP_ROOT / "configs"

APP_VERSION = "V1.1_TOPDOWN_SECTOR"
APP_NAME = "Trecapital — Phân tích Top-Down theo ngành"

NHOM_KT = "Kinh tế"
NHOM_CT = "Chính trị"
NHOM_TL = "Tâm lý"


# ======================================================================================
# 1. Nạp cấu hình
# ======================================================================================


@lru_cache(maxsize=None)
def _load_json(name: str) -> dict:
    path = CONFIG_DIR / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        log_event("INFO", "config", f"Nạp cấu hình {name} thành công ({path.stat().st_size} bytes).")
        return data
    except Exception as exc:  # noqa: BLE001
        log_event("ERROR", "config", f"Không nạp được {name}: {exc}")
        return {}


def taxonomy() -> dict:
    return _load_json("sector_taxonomy_gics.json")


def drivers_config() -> dict:
    return _load_json("sector_drivers_fisher.json")


def cycle_config() -> dict:
    return _load_json("cycle_playbook_fisher.json")


def scoring_config() -> dict:
    return _load_json("scoring_rules_topdown.json")


def benchmark_config() -> dict:
    return _load_json("benchmark_weights.json")


def glossary_terms() -> dict:
    return _load_json("glossary_topdown.json").get("terms", {})


def sector_list() -> list[dict]:
    return taxonomy().get("sectors", [])


def sector_codes() -> list[str]:
    return [s["code"] for s in sector_list()]


def sector_name_map() -> dict[str, str]:
    return {s["code"]: s["ten_vi"] for s in sector_list()}


def sector_by_code(code: str) -> dict:
    for s in sector_list():
        if s["code"] == code:
            return s
    return {}


# ======================================================================================
# 2. Định dạng số liệu theo nguyên tắc số 4
# ======================================================================================


def _is_nan(value) -> bool:
    try:
        return value is None or (isinstance(value, float) and math.isnan(value))
    except Exception:
        return True


def fmt_ty(value) -> str:
    """Tỷ đồng: không có số thập phân."""
    if _is_nan(value):
        return "N/A"
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return "N/A"


def fmt_pct(value) -> str:
    """Phần trăm: 1 số thập phân."""
    if _is_nan(value):
        return "N/A"
    try:
        return f"{float(value):,.1f}%"
    except Exception:
        return "N/A"


def fmt_ratio(value) -> str:
    """Hệ số/lần: 1 số thập phân."""
    if _is_nan(value):
        return "N/A"
    try:
        return f"{float(value):,.1f}"
    except Exception:
        return "N/A"


def round_pct(value) -> float:
    try:
        return round(float(value), 1)
    except Exception:
        return float("nan")


def round_ratio(value) -> float:
    try:
        return round(float(value), 1)
    except Exception:
        return float("nan")


def round_ty(value) -> float:
    try:
        return float(round(float(value), 0))
    except Exception:
        return float("nan")


# ======================================================================================
# 3. Cấu trúc đầu vào
# ======================================================================================


@dataclass
class TopDownInput:
    """Toàn bộ input do người dùng nhập ở Bước 1 và Bước 2."""

    trien_vong_driver: dict[str, float] = field(default_factory=dict)
    pha_chu_ky: str = "mid"
    benchmark_id: str = "vnindex_khoi_tao"
    benchmark_weights: dict[str, float] = field(default_factory=dict)
    lech_toi_da: float = 8.0
    trong_so: dict[str, float] = field(default_factory=dict)


def default_input() -> TopDownInput:
    cfg = scoring_config()
    bms = benchmark_config().get("benchmarks", [])
    bm0 = next((b for b in bms if b["id"] == "vnindex_khoi_tao"), bms[0] if bms else {"id": "", "ty_trong": {}})
    ts = {k: float(v) for k, v in cfg.get("trong_so_diem_nganh", {}).items() if isinstance(v, (int, float))}
    return TopDownInput(
        trien_vong_driver={d["id"]: 0.0 for d in drivers_config().get("drivers", [])},
        pha_chu_ky="mid",
        benchmark_id=bm0.get("id", ""),
        benchmark_weights=dict(bm0.get("ty_trong", {})),
        lech_toi_da=float(cfg.get("gioi_han_lech_benchmark", {}).get("lech_toi_da_diem_phan_tram", 8.0)),
        trong_so=ts,
    )


# ======================================================================================
# 4. Công thức lõi — chấm điểm ngành
# ======================================================================================

DO_NHAY_MAX = 3.0
TRIEN_VONG_MAX = 2.0


def _drivers_by_group() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {NHOM_KT: [], NHOM_CT: [], NHOM_TL: []}
    for d in drivers_config().get("drivers", []):
        out.setdefault(d.get("nhom", NHOM_KT), []).append(d)
    return out


@traced("engine")
def diem_truc_driver(code: str, nhom: str, trien_vong: dict[str, float]) -> tuple[float, list[dict]]:
    """Điểm 0–100 của một ngành trên một trục driver (Kinh tế / Chính trị / Tâm lý).

    Công thức:
        đóng_góp_i  = độ_nhạy(ngành, driver_i) × triển_vọng(driver_i)
        điểm_thô    = Σ đóng_góp_i
        mẫu_số      = Σ |độ_nhạy_i| × TRIEN_VONG_MAX
        điểm_chuẩn  = 50 + 50 × điểm_thô / mẫu_số      (khóa trong [0; 100])

    Ý nghĩa: 50.0 là trung tính. Trên 50 nghĩa là tập hợp driver đang có lợi cho
    ngành; dưới 50 nghĩa là đang bất lợi. Chuẩn hóa theo tổng trị tuyệt đối độ nhạy
    để một ngành có nhiều driver mạnh không bị thổi phồng điểm một cách cơ học.
    """
    do_nhay_all = drivers_config().get("do_nhay_theo_nganh", {}).get(code, {})
    chi_tiet: list[dict] = []
    diem_tho = 0.0
    mau_so = 0.0
    for d in _drivers_by_group().get(nhom, []):
        did = d["id"]
        sens = float(do_nhay_all.get(did, 0))
        outlook = float(trien_vong.get(did, 0.0))
        dong_gop = sens * outlook
        diem_tho += dong_gop
        mau_so += abs(sens) * TRIEN_VONG_MAX
        if sens != 0:
            chi_tiet.append(
                {
                    "Driver": d["ten_vi"],
                    "driver_id": did,
                    "Độ nhạy": round_ratio(sens),
                    "Triển vọng": round_ratio(outlook),
                    "Đóng góp": round_ratio(dong_gop),
                }
            )
    if mau_so <= 0:
        return 50.0, chi_tiet
    diem = 50.0 + 50.0 * (diem_tho / mau_so)
    return max(0.0, min(100.0, round(diem, 1))), chi_tiet


@traced("engine")
def diem_chu_ky(code: str, pha: str) -> float:
    """Điểm 0–100 của vị thế ngành trong pha chu kỳ đang chọn.

    Công thức: điểm = 50 + 50 × điểm_pha / 3, với điểm_pha nằm trong [-3; +3].
    """
    for p in cycle_config().get("pha_chu_ky", []):
        if p["id"] == pha:
            raw = float(p.get("diem_theo_nganh", {}).get(code, 0))
            return max(0.0, min(100.0, round(50.0 + 50.0 * raw / 3.0, 1)))
    return 50.0


def _trong_so(inp: TopDownInput) -> tuple[float, float, float, float, float]:
    ts = inp.trong_so or scoring_config().get("trong_so_diem_nganh", {})
    w_kt = float(ts.get("driver_kinh_te", 40.0))
    w_ct = float(ts.get("driver_chinh_tri", 20.0))
    w_tl = float(ts.get("driver_tam_ly", 20.0))
    w_ck = float(ts.get("vi_the_chu_ky", 20.0))
    return w_kt, w_ct, w_tl, w_ck, max(w_kt + w_ct + w_tl + w_ck, 1e-9)


@traced("engine")
def diem_mot_nganh(code: str, inp: TopDownInput) -> dict:
    w_kt, w_ct, w_tl, w_ck, tong_w = _trong_so(inp)
    d_kt, _ = diem_truc_driver(code, NHOM_KT, inp.trien_vong_driver)
    d_ct, _ = diem_truc_driver(code, NHOM_CT, inp.trien_vong_driver)
    d_tl, _ = diem_truc_driver(code, NHOM_TL, inp.trien_vong_driver)
    d_ck = diem_chu_ky(code, inp.pha_chu_ky)
    tong = (w_kt * d_kt + w_ct * d_ct + w_tl * d_tl + w_ck * d_ck) / tong_w
    return {"kt": d_kt, "ct": d_ct, "tl": d_tl, "ck": d_ck, "tong": round_pct(tong)}


@traced("engine")
def cham_diem_tat_ca_nganh(inp: TopDownInput) -> pd.DataFrame:
    """Bảng xếp hạng ngành — đầu ra chính của Bước 3."""
    rows = []
    for s in sector_list():
        code = s["code"]
        d = diem_mot_nganh(code, inp)
        rows.append(
            {
                "Mã ngành": code,
                "Ngành": s["ten_vi"],
                "Tính chất": s.get("tinh_chat", ""),
                "Điểm kinh tế": round_pct(d["kt"]),
                "Điểm chính trị": round_pct(d["ct"]),
                "Điểm tâm lý": round_pct(d["tl"]),
                "Điểm chu kỳ": round_pct(d["ck"]),
                "Điểm tổng hợp": round_pct(d["tong"]),
            }
        )
    df = pd.DataFrame(rows).sort_values("Điểm tổng hợp", ascending=False).reset_index(drop=True)
    df.insert(0, "Xếp hạng", range(1, len(df) + 1))
    log_event("INFO", "engine", f"Chấm điểm xong {len(df)} ngành, pha chu kỳ = {inp.pha_chu_ky}.")
    return df


# ======================================================================================
# 5. Chuyển điểm thành quyết định tỷ trọng
# ======================================================================================


def nguong_cho_diem(diem: float) -> dict:
    for ng in scoring_config().get("nguong_xep_hang_nganh", []):
        if float(ng["tu"]) <= float(diem) <= float(ng["den"]):
            return ng
    return {"tu": 45.0, "den": 64.9, "nhan": "Trung lập theo benchmark", "ma_tin_hieu": "heat-yellow", "he_so_tilt": 1.0}


def _phan_bo_trong_gioi_han(
    tho: list[float], benchmark: list[float], lech_max: float, tong_muc_tieu: float = 100.0
) -> list[float]:
    """Đưa tỷ trọng thô về tổng 100% mà KHÔNG phá vỡ giới hạn độ lệch.

    Vấn đề: nếu chỉ khóa độ lệch rồi chuẩn hóa lại một lần, phép chuẩn hóa sẽ đẩy một
    số ngành vượt lại ra ngoài giới hạn. Hàm này giải bài toán bằng cách phân bổ lặp:

        cận dưới_i = max(0; benchmark_i − lệch_tối_đa)
        cận trên_i = benchmark_i + lệch_tối_đa
        Lặp: khóa về [cận dưới; cận trên] → tính phần dư so với 100% →
             chia phần dư cho các ngành CÒN dư địa, tỷ lệ thuận với dư địa còn lại.

    Bài toán luôn có nghiệm vì Σ benchmark = 100, nên Σ cận dưới ≤ 100 ≤ Σ cận trên.
    """
    n = len(tho)
    if n == 0:
        return []
    lb = [max(0.0, float(b) - lech_max) for b in benchmark]
    ub = [float(b) + lech_max for b in benchmark]
    w = [float(x) for x in tho]

    for _ in range(200):
        w = [min(max(w[i], lb[i]), ub[i]) for i in range(n)]
        du = tong_muc_tieu - sum(w)
        if abs(du) < 1e-9:
            break
        if du > 0:
            du_dia = [ub[i] - w[i] for i in range(n)]
        else:
            du_dia = [w[i] - lb[i] for i in range(n)]
        tong_du_dia = sum(du_dia)
        if tong_du_dia <= 1e-12:
            break
        w = [w[i] + du * du_dia[i] / tong_du_dia for i in range(n)]

    return [min(max(w[i], lb[i]), ub[i]) for i in range(n)]


@traced("engine")
def bang_ty_trong_de_xuat(diem_df: pd.DataFrame, inp: TopDownInput) -> pd.DataFrame:
    """Chuyển điểm ngành thành tỷ trọng đề xuất và độ lệch so với benchmark.

    Công thức:
        1) tilt         = hệ_số_tilt(ngưỡng của điểm)
        2) tỷ_trọng_thô = tỷ_trọng_benchmark × tilt
        3) chuẩn hóa    : tỷ_trọng = tỷ_trọng_thô / Σ tỷ_trọng_thô × 100
        4) khóa độ lệch : |tỷ_trọng − benchmark| ≤ lệch_tối_đa, rồi chuẩn hóa lại
        5) độ_lệch      = tỷ_trọng − benchmark   (đơn vị: điểm phần trăm)

    Bước 4 phản ánh nguyên tắc của Fisher: giảm tỷ trọng không có nghĩa là bán hết;
    giới hạn độ lệch giúp kiểm soát benchmark risk.
    """
    bm = inp.benchmark_weights or {}
    rows = []
    for _, r in diem_df.iterrows():
        code = r["Mã ngành"]
        diem = float(r["Điểm tổng hợp"])
        ng = nguong_cho_diem(diem)
        w_bm = float(bm.get(code, 0.0))
        rows.append(
            {
                "Mã ngành": code,
                "Ngành": r["Ngành"],
                "Điểm tổng hợp": round_pct(diem),
                "Khuyến nghị": ng["nhan"],
                "Hệ số tilt": round_ratio(ng["he_so_tilt"]),
                "Tỷ trọng benchmark %": round_pct(w_bm),
                "_tho": w_bm * float(ng["he_so_tilt"]),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    tong_tho = float(df["_tho"].sum())
    if tong_tho <= 0:
        tam = list(df["Tỷ trọng benchmark %"].astype(float))
    else:
        tam = list(df["_tho"] / tong_tho * 100.0)

    capped = _phan_bo_trong_gioi_han(tam, list(df["Tỷ trọng benchmark %"].astype(float)), float(inp.lech_toi_da))
    df["Tỷ trọng đề xuất %"] = [round_pct(w) for w in capped]
    df["Độ lệch điểm %"] = [round_pct(w - float(b)) for w, b in zip(capped, df["Tỷ trọng benchmark %"])]
    df = df.drop(columns=["_tho"]).sort_values("Điểm tổng hợp", ascending=False).reset_index(drop=True)
    df.insert(0, "STT", range(1, len(df) + 1))

    canh_bao = float(scoring_config().get("gioi_han_lech_benchmark", {}).get("canh_bao_do_lech", 5.0))
    n_lon = int((df["Độ lệch điểm %"].abs() > canh_bao).sum())
    log_event(
        "INFO",
        "engine",
        f"Tính tỷ trọng đề xuất xong. Số ngành có độ lệch > {canh_bao}%: {n_lon}. "
        f"Tổng tỷ trọng = {df['Tỷ trọng đề xuất %'].sum():.1f}%.",
    )
    return df


# ======================================================================================
# 6. Bước 4 — đào sâu nhóm ngành cấp 2
# ======================================================================================


@traced("engine")
def bang_industry_group(code: str, inp: TopDownInput) -> pd.DataFrame:
    """Bảng nhóm ngành cấp 2 kèm điểm thừa hưởng từ ngành mẹ.

    App KHÔNG bịa độ nhạy riêng cho từng nhóm ngành cấp 2 vì tài liệu nguồn không
    cung cấp ma trận độ nhạy định lượng ở cấp này. Thay vào đó app hiển thị điểm của
    ngành mẹ và để người dùng tự nhập điểm tinh chỉnh (−20 đến +20).
    """
    s = sector_by_code(code)
    diem_me = diem_mot_nganh(code, inp)["tong"]
    rows = []
    for i, g in enumerate(s.get("industry_groups", []), start=1):
        rows.append(
            {
                "STT": i,
                "Nhóm ngành cấp 2": g["ten_vi"],
                "Tên quốc tế": g.get("ten_en", ""),
                "Số ngành cấp 3": len(g.get("industries", [])),
                "Điểm thừa hưởng": round_pct(diem_me),
                "Điểm tinh chỉnh": 0.0,
                "Điểm sau tinh chỉnh": round_pct(diem_me),
            }
        )
    return pd.DataFrame(rows)


def ap_dung_tinh_chinh(df: pd.DataFrame) -> pd.DataFrame:
    """Công thức: điểm_sau = khóa(điểm_thừa_hưởng + điểm_tinh_chỉnh, 0, 100)."""
    if df is None or df.empty:
        return df
    out = df.copy()
    out["Điểm sau tinh chỉnh"] = [
        round_pct(max(0.0, min(100.0, float(a) + float(b))))
        for a, b in zip(out["Điểm thừa hưởng"], out["Điểm tinh chỉnh"])
    ]
    return out


# ======================================================================================
# 7. Bước 5 — sàng lọc định lượng
# ======================================================================================

COT_SANG_LOC = [
    "Mã CK",
    "Tên doanh nghiệp",
    "Mã ngành",
    "Vốn hóa (tỷ đồng)",
    "P/E (lần)",
    "P/B (lần)",
    "P/CF (lần)",
    "P/S (lần)",
    "Nợ vay/Vốn chủ (lần)",
    "GTGD bình quân 20 phiên (tỷ đồng)",
]


def mau_bang_sang_loc(n_dong: int = 5, ma_nganh_mac_dinh: str = "FIN") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Mã CK": "",
                "Tên doanh nghiệp": "",
                "Mã ngành": ma_nganh_mac_dinh,
                "Vốn hóa (tỷ đồng)": None,
                "P/E (lần)": None,
                "P/B (lần)": None,
                "P/CF (lần)": None,
                "P/S (lần)": None,
                "Nợ vay/Vốn chủ (lần)": None,
                "GTGD bình quân 20 phiên (tỷ đồng)": None,
            }
            for _ in range(max(1, n_dong))
        ]
    )


def _num(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


@traced("engine")
def chay_sang_loc(df: pd.DataFrame, tieu_chi: dict) -> pd.DataFrame:
    """Sàng lọc định lượng 3 lớp: Capitalization → Valuation → Solvency/Liquidity.

    Mỗi cổ phiếu được đánh dấu Đạt/Không đạt và ghi rõ lý do loại. App không tự xóa
    dòng nào khỏi bảng để người dùng nhìn thấy đầy đủ.
    """
    if df is None or df.empty:
        out = mau_bang_sang_loc(1).iloc[0:0].copy()
        out["Kết quả"] = []
        out["Lý do loại"] = []
        return out

    out = df.copy()
    ket_qua, ly_do = [], []
    for _, r in out.iterrows():
        ma = str(r.get("Mã CK", "") or "").strip()
        if not ma:
            ket_qua.append("Chưa nhập")
            ly_do.append("Dòng trống — chưa nhập mã chứng khoán.")
            continue
        loi: list[str] = []
        von, pe, pb = _num(r.get("Vốn hóa (tỷ đồng)")), _num(r.get("P/E (lần)")), _num(r.get("P/B (lần)"))
        pcf, ps = _num(r.get("P/CF (lần)")), _num(r.get("P/S (lần)"))
        no, tk = _num(r.get("Nợ vay/Vốn chủ (lần)")), _num(r.get("GTGD bình quân 20 phiên (tỷ đồng)"))

        if von is not None and von < float(tieu_chi.get("von_hoa_toi_thieu_ty", 0)):
            loi.append(f"Vốn hóa {fmt_ty(von)} tỷ dưới ngưỡng {fmt_ty(tieu_chi.get('von_hoa_toi_thieu_ty'))} tỷ")
        if pe is not None and pe <= 0:
            loi.append("P/E âm hoặc bằng 0 — doanh nghiệp đang lỗ, cần xử lý riêng")
        elif pe is not None and pe > float(tieu_chi.get("pe_toi_da", 1e9)):
            loi.append(f"P/E {fmt_ratio(pe)} vượt ngưỡng {fmt_ratio(tieu_chi.get('pe_toi_da'))}")
        if pb is not None and pb > float(tieu_chi.get("pb_toi_da", 1e9)):
            loi.append(f"P/B {fmt_ratio(pb)} vượt ngưỡng {fmt_ratio(tieu_chi.get('pb_toi_da'))}")
        if pcf is not None and pcf > float(tieu_chi.get("pcf_toi_da", 1e9)):
            loi.append(f"P/CF {fmt_ratio(pcf)} vượt ngưỡng {fmt_ratio(tieu_chi.get('pcf_toi_da'))}")
        if ps is not None and ps > float(tieu_chi.get("ps_toi_da", 1e9)):
            loi.append(f"P/S {fmt_ratio(ps)} vượt ngưỡng {fmt_ratio(tieu_chi.get('ps_toi_da'))}")
        if no is not None and no > float(tieu_chi.get("no_vay_tren_von_chu_toi_da", 1e9)):
            loi.append(
                f"Nợ vay/Vốn chủ {fmt_ratio(no)} vượt ngưỡng "
                f"{fmt_ratio(tieu_chi.get('no_vay_tren_von_chu_toi_da'))}"
            )
        if tk is not None and tk < float(tieu_chi.get("thanh_khoan_binh_quan_ty_toi_thieu", 0)):
            loi.append(
                f"Thanh khoản {fmt_ty(tk)} tỷ/phiên dưới ngưỡng "
                f"{fmt_ty(tieu_chi.get('thanh_khoan_binh_quan_ty_toi_thieu'))} tỷ"
            )

        ket_qua.append("Đạt" if not loi else "Không đạt")
        ly_do.append("; ".join(loi) if loi else "Đạt toàn bộ tiêu chí sàng lọc")

    out["Kết quả"] = ket_qua
    out["Lý do loại"] = ly_do
    n_dat = sum(1 for k in ket_qua if k == "Đạt")
    log_event("INFO", "engine", f"Sàng lọc định lượng: {n_dat}/{len(out)} mã đạt tiêu chí.")
    return out


# ======================================================================================
# 8. Ghi chú giải thích cho từng dòng (nguyên tắc số 6)
# ======================================================================================


def _sap_xep_dong_gop(chi_tiet: list[dict], n: int = 4) -> tuple[list[dict], list[dict]]:
    ho_tro = sorted([c for c in chi_tiet if float(c["Đóng góp"]) > 0], key=lambda x: -float(x["Đóng góp"]))[:n]
    can_tro = sorted([c for c in chi_tiet if float(c["Đóng góp"]) < 0], key=lambda x: float(x["Đóng góp"]))[:n]
    return ho_tro, can_tro


@traced("engine")
def note_xep_hang_nganh(rowd: dict, inp: TopDownInput) -> str:
    """Ghi chú giải thích cho một dòng trong bảng xếp hạng ngành — có số liệu cụ thể."""
    code = str(rowd.get("Mã ngành", ""))
    s = sector_by_code(code)
    if not s:
        return "Không tìm thấy cấu hình ngành này."

    d_kt, ct_kt = diem_truc_driver(code, NHOM_KT, inp.trien_vong_driver)
    d_ct, ct_ct = diem_truc_driver(code, NHOM_CT, inp.trien_vong_driver)
    d_tl, ct_tl = diem_truc_driver(code, NHOM_TL, inp.trien_vong_driver)
    d_ck = diem_chu_ky(code, inp.pha_chu_ky)
    tong = float(rowd.get("Điểm tổng hợp", 0))
    ng = nguong_cho_diem(tong)
    w_kt, w_ct, w_tl, w_ck, tong_w = _trong_so(inp)
    pha = next((p for p in cycle_config().get("pha_chu_ky", []) if p["id"] == inp.pha_chu_ky), {})

    lines = [
        f"NGÀNH: {s['ten_vi']} ({s.get('ten_en','')}) — mã {code}",
        f"Tính chất: {s.get('tinh_chat','')}",
        f"Mô tả: {s.get('mo_ta','')}",
        "",
        "1) ĐIỂM TỔNG HỢP ĐƯỢC TÍNH NHƯ THẾ NÀO",
        f"   Điểm tổng hợp = ({fmt_ratio(w_kt)} × {fmt_pct(d_kt)} + {fmt_ratio(w_ct)} × {fmt_pct(d_ct)}"
        f" + {fmt_ratio(w_tl)} × {fmt_pct(d_tl)} + {fmt_ratio(w_ck)} × {fmt_pct(d_ck)}) / {fmt_ratio(tong_w)}",
        f"   ⇒ Điểm tổng hợp = {fmt_pct(tong)}",
        "   Mốc 50.0% là trung tính. Điểm càng xa 50 thì tín hiệu càng mạnh.",
        "",
        "2) VÌ SAO XẾP HẠNG NHƯ VẬY",
        f"   Điểm {fmt_pct(tong)} rơi vào ngưỡng {fmt_pct(ng['tu'])} – {fmt_pct(ng['den'])} ⇒ khuyến nghị: {ng['nhan']}.",
        f"   Hệ số tilt tương ứng: {fmt_ratio(ng['he_so_tilt'])} lần tỷ trọng benchmark.",
        "",
        "3) DRIVER ĐANG HỖ TRỢ VÀ ĐANG CẢN TRỞ",
    ]
    for ten_truc, chi_tiet, diem in [(NHOM_KT, ct_kt, d_kt), (NHOM_CT, ct_ct, d_ct), (NHOM_TL, ct_tl, d_tl)]:
        ho_tro, can_tro = _sap_xep_dong_gop(chi_tiet)
        lines.append(f"   [{ten_truc}] điểm {fmt_pct(diem)}")
        if ho_tro:
            lines.append(
                "      Hỗ trợ: "
                + "; ".join(
                    f"{c['Driver']} (độ nhạy {fmt_ratio(c['Độ nhạy'])} × triển vọng "
                    f"{fmt_ratio(c['Triển vọng'])} = {fmt_ratio(c['Đóng góp'])})"
                    for c in ho_tro
                )
            )
        if can_tro:
            lines.append(
                "      Cản trở: "
                + "; ".join(
                    f"{c['Driver']} (độ nhạy {fmt_ratio(c['Độ nhạy'])} × triển vọng "
                    f"{fmt_ratio(c['Triển vọng'])} = {fmt_ratio(c['Đóng góp'])})"
                    for c in can_tro
                )
            )
        if not ho_tro and not can_tro:
            lines.append("      Chưa có driver nào được chấm triển vọng khác 0 ở trục này.")

    lines += [
        "",
        "4) VỊ THẾ CHU KỲ",
        f"   Pha đang chọn: {pha.get('ten_vi', inp.pha_chu_ky)} — điểm chu kỳ {fmt_pct(d_ck)}",
        f"   Đặc điểm pha: {pha.get('dac_diem','')}",
        "",
        "5) CẢNH BÁO KHI SỬ DỤNG",
        "   Fisher nhấn mạnh các driver này không đầy đủ và không đúng cho mọi thời kỳ.",
        "   Điểm số chỉ là khung đặt câu hỏi, không phải tín hiệu mua bán. Phải kiểm tra",
        "   xem kỳ vọng đã nằm trong giá hay chưa trước khi ra quyết định.",
    ]
    return "\n".join(lines)


@traced("engine")
def note_ty_trong(rowd: dict, inp: TopDownInput) -> str:
    """Ghi chú giải thích cho một dòng trong bảng tỷ trọng đề xuất."""
    code = str(rowd.get("Mã ngành", ""))
    s = sector_by_code(code)
    w_bm = float(rowd.get("Tỷ trọng benchmark %", 0))
    w_de = float(rowd.get("Tỷ trọng đề xuất %", 0))
    do_lech = float(rowd.get("Độ lệch điểm %", 0))
    tilt = float(rowd.get("Hệ số tilt", 1.0))
    diem = float(rowd.get("Điểm tổng hợp", 50))
    canh_bao = float(scoring_config().get("gioi_han_lech_benchmark", {}).get("canh_bao_do_lech", 5.0))
    huong = "TĂNG tỷ trọng" if do_lech > 0.05 else ("GIẢM tỷ trọng" if do_lech < -0.05 else "GIỮ trung lập")

    lines = [
        f"NGÀNH: {s.get('ten_vi', code)} — mã {code}",
        "",
        "1) SỐ LIỆU CỤ THỂ",
        f"   Tỷ trọng benchmark (trung lập): {fmt_pct(w_bm)}",
        f"   Hệ số tilt từ điểm {fmt_pct(diem)}: {fmt_ratio(tilt)} lần",
        f"   Tỷ trọng thô = {fmt_pct(w_bm)} × {fmt_ratio(tilt)} = {fmt_pct(w_bm * tilt)}",
        f"   Sau chuẩn hóa về tổng 100% và khóa độ lệch tối đa {fmt_pct(inp.lech_toi_da)}:",
        f"   ⇒ Tỷ trọng đề xuất = {fmt_pct(w_de)}",
        f"   ⇒ Độ lệch = {fmt_pct(w_de)} − {fmt_pct(w_bm)} = {fmt_pct(do_lech)} điểm phần trăm",
        "",
        "2) QUYẾT ĐỊNH",
        f"   {huong} so với benchmark.",
    ]
    if abs(do_lech) > canh_bao:
        lines.append(
            f"   CẢNH BÁO: độ lệch {fmt_pct(abs(do_lech))} lớn hơn ngưỡng cảnh báo {fmt_pct(canh_bao)}. "
            "Đây là một cuộc đánh cược lớn so với benchmark, hiệu suất danh mục sẽ lệch mạnh khỏi chỉ số."
        )
    else:
        lines.append("   Độ lệch nằm trong ngưỡng kiểm soát benchmark risk.")
    lines += [
        "",
        "",
        "3) VÌ SAO ĐÔI KHI ĐIỂM THẤP MÀ TỶ TRỌNG VẪN BẰNG BENCHMARK",
        "   Tỷ trọng đề xuất là con số TƯƠNG ĐỐI, không phải tuyệt đối. Danh mục luôn phải đủ 100%.",
        "   Nếu bạn bi quan với phần lớn thị trường, phép chuẩn hóa về 100% sẽ kéo các ngành bị hạ",
        "   điểm quay lại gần mức benchmark, vì bạn vẫn phải phân bổ toàn bộ vốn đi đâu đó.",
        "   Muốn hạ tỷ trọng cổ phiếu nói chung thì đó là quyết định phân bổ tài sản (phần 70%),",
        "   nằm ngoài phạm vi của module phân bổ ngành này.",
        "",
        "4) NGUYÊN TẮC GỐC (Fisher Investments)",
        "   Giảm tỷ trọng KHÔNG có nghĩa là bán hết về 0%. Giữ một tỷ trọng nhỏ hơn benchmark",
        "   vẫn là quyết định chủ động, đồng thời giữ được đa dạng hóa và kiểm soát rủi ro.",
        "   Mục tiêu của danh mục là tối đa hóa XÁC SUẤT THẮNG BENCHMARK, không phải tối đa hóa",
        "   lợi nhuận tuyệt đối.",
        "",
        "5) LƯU Ý VỀ DỮ LIỆU BENCHMARK",
        "   Nếu bạn đang dùng benchmark giá trị khởi tạo, số liệu tỷ trọng CHƯA được kiểm chứng.",
        "   Hãy cập nhật tỷ trọng ngành từ HOSE hoặc nhà cung cấp dữ liệu chính thống trước khi ra quyết định.",
    ]
    return "\n".join(lines)


@traced("engine")
def note_driver(driver_id: str, inp: TopDownInput) -> str:
    """Ghi chú giải thích cho một dòng trong bảng Portfolio Drivers."""
    d = next((x for x in drivers_config().get("drivers", []) if x["id"] == driver_id), None)
    if not d:
        return "Không tìm thấy driver."
    outlook = float(inp.trien_vong_driver.get(driver_id, 0.0))
    thang = drivers_config().get("thang_trien_vong", {})
    sens_map = drivers_config().get("do_nhay_theo_nganh", {})
    names = sector_name_map()

    xep = sorted(
        [(c, float(sens_map.get(c, {}).get(driver_id, 0))) for c in sector_codes()],
        key=lambda x: -(x[1] * outlook) if outlook != 0 else -x[1],
    )
    lines = [
        f"DRIVER: {d['ten_vi']}",
        f"Nhóm: {d['nhom']}",
        "",
        "1) DIỄN GIẢI",
        f"   {d['dien_giai']}",
        "",
        "2) TRIỂN VỌNG BẠN ĐANG CHỌN",
        f"   {fmt_ratio(outlook)} = {thang.get(str(int(outlook)), 'Trung tính')}",
        "",
        "3) TÁC ĐỘNG LÊN TỪNG NGÀNH (độ nhạy × triển vọng)",
    ]
    for c, sens in xep:
        if sens == 0:
            continue
        lines.append(
            f"   {names.get(c, c):<30} độ nhạy {fmt_ratio(sens):>5}  ×  triển vọng "
            f"{fmt_ratio(outlook):>5}  =  {fmt_ratio(sens * outlook):>5}"
        )
    if outlook == 0:
        lines.append("   (Triển vọng đang là 0 nên đóng góp của driver này bằng 0 ở mọi ngành.)")
    lines += [
        "",
        "4) CẢNH BÁO",
        "   Câu hỏi đúng không phải là driver này tốt hay xấu, mà là driver này sẽ diễn biến",
        "   KHÁC với kỳ vọng đang được định giá sẵn hay không. Thị trường đã phản ánh thông tin",
        "   phổ biến; alpha chỉ đến từ phần bạn biết mà thị trường chưa biết, hoặc bạn đọc đúng",
        "   thông tin mà đám đông đọc sai.",
    ]
    return "\n".join(lines)


@traced("engine")
def note_sang_loc(rowd: dict, tieu_chi: dict) -> str:
    """Ghi chú giải thích cho một dòng trong bảng kết quả sàng lọc."""
    return "\n".join(
        [
            f"MÃ CHỨNG KHOÁN: {rowd.get('Mã CK','')}",
            f"Doanh nghiệp: {rowd.get('Tên doanh nghiệp','')}",
            f"Ngành: {sector_name_map().get(str(rowd.get('Mã ngành','')), rowd.get('Mã ngành',''))}",
            "",
            "1) SỐ LIỆU ĐẦU VÀO",
            f"   Vốn hóa: {fmt_ty(rowd.get('Vốn hóa (tỷ đồng)'))} tỷ đồng",
            f"   P/E: {fmt_ratio(rowd.get('P/E (lần)'))} lần | P/B: {fmt_ratio(rowd.get('P/B (lần)'))} lần | "
            f"P/CF: {fmt_ratio(rowd.get('P/CF (lần)'))} lần | P/S: {fmt_ratio(rowd.get('P/S (lần)'))} lần",
            f"   Nợ vay/Vốn chủ: {fmt_ratio(rowd.get('Nợ vay/Vốn chủ (lần)'))} lần",
            f"   GTGD bình quân 20 phiên: {fmt_ty(rowd.get('GTGD bình quân 20 phiên (tỷ đồng)'))} tỷ đồng",
            "",
            "2) NGƯỠNG ĐANG ÁP DỤNG",
            f"   Vốn hóa tối thiểu {fmt_ty(tieu_chi.get('von_hoa_toi_thieu_ty'))} tỷ (lớp Capitalization)",
            f"   P/E ≤ {fmt_ratio(tieu_chi.get('pe_toi_da'))} | P/B ≤ {fmt_ratio(tieu_chi.get('pb_toi_da'))} | "
            f"P/CF ≤ {fmt_ratio(tieu_chi.get('pcf_toi_da'))} | P/S ≤ {fmt_ratio(tieu_chi.get('ps_toi_da'))} (lớp Valuation)",
            f"   Nợ vay/Vốn chủ ≤ {fmt_ratio(tieu_chi.get('no_vay_tren_von_chu_toi_da'))} (lớp Solvency)",
            f"   Thanh khoản ≥ {fmt_ty(tieu_chi.get('thanh_khoan_binh_quan_ty_toi_thieu'))} tỷ/phiên (lớp Liquidity)",
            "",
            "3) KẾT QUẢ VÀ LÝ DO",
            f"   {rowd.get('Kết quả','')} — {rowd.get('Lý do loại','')}",
            "",
            "4) LƯU Ý QUAN TRỌNG",
            "   Đây mới là Bước 2 của quy trình top-down. Vượt qua sàng lọc KHÔNG có nghĩa là nên mua;",
            "   bộ lọc chỉ thu hẹp phạm vi để bước phân tích cơ bản trở nên khả thi.",
            "   Ngược lại, bị loại cũng không có nghĩa là doanh nghiệp xấu — có thể bộ lọc của bạn",
            "   đang quá chặt so với mặt bằng định giá hiện tại của thị trường.",
            "   Riêng P/E âm: doanh nghiệp đang lỗ nên hệ số P/E mất ý nghĩa định giá, cần đánh giá",
            "   bằng P/B, P/S hoặc giá trị tài sản thay vì loại bỏ máy móc.",
            "",
            "5) BƯỚC TIẾP THEO",
            "   Chuyển các mã đạt sang module Tổng quan doanh nghiệp và Định giá chuyên sâu của Trecapital",
            "   để chạy quy trình phân tích 5 bước và tính biên an toàn.",
        ]
    )


@traced("engine")
def note_industry_group(rowd: dict, code: str) -> str:
    s = sector_by_code(code)
    ten = str(rowd.get("Nhóm ngành cấp 2", ""))
    g = next((x for x in s.get("industry_groups", []) if x["ten_vi"] == ten), {})
    lines = [
        f"NHÓM NGÀNH CẤP 2: {ten}",
        f"Tên quốc tế: {g.get('ten_en','')}",
        f"Thuộc ngành cấp 1: {s.get('ten_vi', code)}",
        "",
        "1) CÁC NGÀNH CẤP 3 BÊN TRONG",
    ]
    for i, ind in enumerate(g.get("industries", []), start=1):
        lines.append(f"   {i}. {ind}")
    lines += [
        "",
        "2) ĐIỂM ĐƯỢC TÍNH NHƯ THẾ NÀO",
        f"   Điểm thừa hưởng từ ngành mẹ: {fmt_pct(rowd.get('Điểm thừa hưởng'))}",
        f"   Điểm tinh chỉnh bạn nhập: {fmt_ratio(rowd.get('Điểm tinh chỉnh'))}",
        f"   ⇒ Điểm sau tinh chỉnh = {fmt_pct(rowd.get('Điểm sau tinh chỉnh'))}",
        "",
        "3) VÌ SAO APP KHÔNG TỰ CHẤM ĐIỂM CẤP 2",
        "   Tài liệu nguồn (bộ Fisher Investments On series) mô tả định tính đặc điểm từng",
        "   nhóm ngành cấp 2 nhưng KHÔNG cung cấp ma trận độ nhạy định lượng ở cấp này.",
        "   Theo nguyên tắc bám sát tài liệu nguồn, app không tự bịa hệ số mà để bạn nhập",
        "   điểm tinh chỉnh dựa trên hiểu biết riêng về thị trường Việt Nam.",
        "",
        "4) GỢI Ý KHI TINH CHỈNH",
        "   Tăng điểm nếu nhóm ngành này nhạy hơn ngành mẹ với driver đang thuận lợi.",
        "   Giảm điểm nếu nhóm này bị ràng buộc riêng (quản lý giá, thuế đặc thù, cạnh tranh",
        "   nhập khẩu) mà ngành mẹ nói chung không chịu.",
    ]
    return "\n".join(lines)


# ======================================================================================
# 9. Tự kiểm tra tính nhất quán dữ liệu (nguyên tắc số 7)
# ======================================================================================


@traced("engine")
def kiem_tra_dong_bo(inp: TopDownInput, diem_df: pd.DataFrame, tt_df: pd.DataFrame) -> pd.DataFrame:
    """Bảng tự kiểm tra tính nhất quán dữ liệu giữa các bước."""
    rows: list[dict] = []

    def add(muc: str, dat: bool, chi_tiet: str, muc_do: str):
        rows.append(
            {
                "Hạng mục kiểm tra": muc,
                "Tình trạng": "Đạt" if dat else "Cảnh báo",
                "Chi tiết": chi_tiet,
                "Mức độ": muc_do,
            }
        )

    bm_sum = sum(float(v) for v in (inp.benchmark_weights or {}).values())
    add(
        "Tổng tỷ trọng benchmark",
        abs(bm_sum - 100.0) <= 0.5,
        f"Tổng hiện tại = {fmt_pct(bm_sum)}. Yêu cầu 100.0% ± 0.5.",
        "Cao",
    )

    thieu = [c for c in sector_codes() if c not in (inp.benchmark_weights or {})]
    add(
        "Đầy đủ 11 ngành trong benchmark",
        not thieu,
        "Đủ 11 ngành." if not thieu else f"Thiếu tỷ trọng cho: {', '.join(thieu)}",
        "Cao",
    )

    if tt_df is not None and not tt_df.empty:
        tong_de_xuat = float(tt_df["Tỷ trọng đề xuất %"].sum())
        add("Tổng tỷ trọng đề xuất", abs(tong_de_xuat - 100.0) <= 0.5, f"Tổng hiện tại = {fmt_pct(tong_de_xuat)}.", "Cao")
        lech_max = float(tt_df["Độ lệch điểm %"].abs().max())
        add(
            "Độ lệch lớn nhất so với benchmark",
            lech_max <= float(inp.lech_toi_da) + 0.5,
            f"Độ lệch lớn nhất = {fmt_pct(lech_max)}, giới hạn = {fmt_pct(inp.lech_toi_da)}.",
            "Trung bình",
        )

    n_khac0 = sum(1 for v in inp.trien_vong_driver.values() if float(v) != 0)
    add(
        "Số driver đã chấm triển vọng",
        n_khac0 >= 5,
        f"Đã chấm {n_khac0}/{len(inp.trien_vong_driver)} driver khác 0. "
        "Dưới 5 driver thì điểm ngành gần như chỉ phản ánh vị thế chu kỳ.",
        "Trung bình",
    )

    if diem_df is not None and not diem_df.empty:
        khoang = float(diem_df["Điểm tổng hợp"].max() - diem_df["Điểm tổng hợp"].min())
        add(
            "Độ phân tán điểm giữa các ngành",
            khoang >= 8.0,
            f"Khoảng cách điểm cao nhất − thấp nhất = {fmt_pct(khoang)}. "
            "Nếu quá hẹp thì khung đang chưa đủ phân biệt giữa các ngành.",
            "Thấp",
        )

    bm_meta = next((b for b in benchmark_config().get("benchmarks", []) if b["id"] == inp.benchmark_id), {})
    add(
        "Độ tin cậy của benchmark đang dùng",
        not bool(bm_meta.get("can_nguoi_dung_cap_nhat", True)),
        bm_meta.get("do_tin_cay", "Không xác định"),
        "Cao",
    )

    df = pd.DataFrame(rows)
    n_cb = int((df["Tình trạng"] == "Cảnh báo").sum())
    log_event("INFO", "engine", f"Kiểm tra đồng bộ: {n_cb}/{len(df)} hạng mục có cảnh báo.")
    return df
