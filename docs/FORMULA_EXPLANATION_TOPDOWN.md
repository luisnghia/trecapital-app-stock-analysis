# FORMULA_EXPLANATION_TOPDOWN

Tài liệu diễn giải toàn bộ công thức được xây dựng trong module Phân tích Top-Down theo ngành.
Đây là yêu cầu bắt buộc theo nguyên tắc xây dựng app số 3.

---

## 1. Nguyên tắc chung

Module này **không đưa ra khuyến nghị mua bán cổ phiếu**. Nó trả lời một câu hỏi duy nhất:
*trong 12 tháng tới, nên phân bổ nhiều hơn hay ít hơn benchmark vào từng ngành?*

Cơ sở lý thuyết là quy trình top-down của Fisher Investments, được trình bày thống nhất trong
chương "The Top-Down Method" của cả 11 cuốn thuộc bộ *Fisher Investments On* series.

### Nguyên lý 70 – 20 – 10

Nghiên cứu của Fisher Investments cho thấy phân rã biến thiên lợi nhuận danh mục:

| Cấp quyết định | Đóng góp | Module phụ trách |
|---|---|---|
| Phân bổ tài sản (cổ phiếu / trái phiếu / tiền mặt) | 70% | Ngoài phạm vi app |
| Phân bổ tiểu nhóm (quốc gia, **ngành**, quy mô, phong cách) | 20% | **Module này** |
| Lựa chọn cổ phiếu | 10% | Module Tổng quan doanh nghiệp và Định giá chuyên sâu |

---

## 2. Đơn vị và định dạng (nguyên tắc số 4)

| Loại số liệu | Định dạng | Ví dụ |
|---|---|---|
| Giá trị tiền | tỷ đồng, **0 chữ số thập phân** | `20,000` |
| Phần trăm | **1 chữ số thập phân** | `67.6%` |
| Hệ số / lần | **1 chữ số thập phân** | `1.3` |
| Giá trị rỗng | `N/A` | |

Hiện thực: `fmt_ty()`, `fmt_pct()`, `fmt_ratio()` trong `module_topdown_engine.py`.

## 3. Quy ước màu (nguyên tắc số 5 và số 8)

**Cột giá trị dương/âm** (Độ nhạy, Triển vọng, Đóng góp, Độ lệch điểm %):

```
value < 0  →  rgba(239,68,68, α)    α = 0.12 + 0.58 × min(|value| / |value_âm_lớn_nhất|, 1)
value > 0  →  rgba(16,185,129, α)   α = 0.10 + 0.52 × min(value / value_dương_lớn_nhất, 1)
```

Số âm càng lớn thì đỏ càng đậm; số dương càng lớn thì xanh ngọc lục bảo càng đậm.
Hiện thực: `_grad_color()` trong `module_topdown_dashboard.py`.

**Cột điểm số** dùng bản đồ nhiệt theo mức độ quan trọng:

| Khoảng điểm | Màu | Ý nghĩa |
|---|---|---|
| 80.0 – 100.0 | Xanh đậm, chữ trắng | Tăng tỷ trọng mạnh |
| 65.0 – 79.9 | Xanh nhạt | Tăng tỷ trọng |
| 45.0 – 64.9 | Vàng | Trung lập |
| 30.0 – 44.9 | Cam | Giảm tỷ trọng |
| 0.0 – 29.9 | Đỏ | Giảm tỷ trọng mạnh |

---

## 4. Công thức lõi: điểm trục driver

Nguồn: chương *Sector Drivers* của từng cuốn Fisher + Table 7.4 *Portfolio Drivers*.

### 4.1. Đầu vào

- **Độ nhạy** `s(ngành, driver)` — hằng số cấu hình, khoảng `[-3; +3]`, nạp từ
  `configs/sector_drivers_fisher.json`. Dương nghĩa là driver tăng thì ngành hưởng lợi.
- **Triển vọng** `o(driver)` — người dùng chấm, khoảng `[-2; +2]`.

### 4.2. Công thức

```
đóng_góp_i  = s(ngành, driver_i) × o(driver_i)

điểm_thô    = Σ đóng_góp_i                        (cộng trên các driver cùng nhóm)
mẫu_số      = Σ |s(ngành, driver_i)| × 2          (2 = |triển vọng| tối đa)

điểm_trục   = 50 + 50 × điểm_thô / mẫu_số         khóa trong [0; 100]
```

### 4.3. Vì sao chuẩn hóa theo `Σ|s|` chứ không phải số driver

Nếu chia cho số driver, một ngành có nhiều driver độ nhạy thấp sẽ bị pha loãng điểm một cách
giả tạo, còn ngành có ít driver nhưng độ nhạy mạnh lại bị đánh giá quá cao. Chia cho tổng trị
tuyệt đối độ nhạy giúp điểm phản ánh đúng **tỷ lệ giữa lực đang tác động và lực tối đa có thể
tác động** lên chính ngành đó.

### 4.4. Cách đọc

- `50.0` = trung tính. Toàn bộ driver ở mức 0 thì mọi ngành đều được 50.0.
- `> 50` = tập hợp driver đang thuận lợi cho ngành.
- `100.0` chỉ đạt được khi **mọi** driver có độ nhạy khác 0 đều được chấm đúng chiều và ở mức cực trị.

Hàm: `diem_truc_driver()`.

---

## 5. Công thức: điểm vị thế chu kỳ

Nguồn: bảng pha chu kỳ trong *Fisher Investments on Technology* chương 3, kết hợp phần
*The Business Cycle's Winds of Change* (Consumer Staples) và *Utilities Outperform During
Recessions* (Utilities).

```
điểm_chu_kỳ = 50 + 50 × điểm_pha(ngành, pha) / 3        khóa trong [0; 100]
```

với `điểm_pha ∈ [-3; +3]` nạp từ `configs/cycle_playbook_fisher.json`.

Hàm: `diem_chu_ky()`.

---

## 6. Công thức: điểm tổng hợp ngành

```
                w_kt × D_kinh_tế + w_ct × D_chính_trị + w_tl × D_tâm_lý + w_ck × D_chu_kỳ
điểm_tổng_hợp = ─────────────────────────────────────────────────────────────────────────
                                  w_kt + w_ct + w_tl + w_ck
```

Trọng số mặc định: `40 / 20 / 20 / 20`, người dùng chỉnh được ở sidebar. Mẫu số là tổng trọng
số thực tế nên app tự chuẩn hóa, người dùng không cần đảm bảo tổng bằng 100.

Hàm: `diem_mot_nganh()`, `cham_diem_tat_ca_nganh()`.

---

## 7. Công thức: từ điểm sang tỷ trọng danh mục

Đây là phần quan trọng nhất và cũng dễ hiểu sai nhất.

### 7.1. Hệ số tilt

Điểm tổng hợp được ánh xạ sang hệ số nhân với tỷ trọng benchmark:

| Điểm | Khuyến nghị | Hệ số tilt |
|---|---|---|
| 80.0 – 100.0 | Tăng tỷ trọng mạnh | 1.6 |
| 65.0 – 79.9 | Tăng tỷ trọng | 1.3 |
| 45.0 – 64.9 | Trung lập theo benchmark | 1.0 |
| 30.0 – 44.9 | Giảm tỷ trọng | 0.7 |
| 0.0 – 29.9 | Giảm tỷ trọng mạnh | 0.4 |

### 7.2. Chuẩn hóa và khóa độ lệch

```
tỷ_trọng_thô_i = benchmark_i × tilt_i
tỷ_trọng_tạm_i = tỷ_trọng_thô_i / Σ tỷ_trọng_thô × 100

cận_dưới_i = max(0; benchmark_i − lệch_tối_đa)
cận_trên_i = benchmark_i + lệch_tối_đa
```

Sau đó chạy **thuật toán phân bổ lặp** để đưa tổng về đúng 100% mà không phá vỡ cận:

```
lặp tối đa 200 lần:
    w ← khóa(w, cận_dưới, cận_trên)
    dư ← 100 − Σw
    nếu |dư| < 1e-9: dừng
    nếu dư > 0: dư_địa_i = cận_trên_i − w_i
    ngược lại : dư_địa_i = w_i − cận_dưới_i
    w_i ← w_i + dư × dư_địa_i / Σ dư_địa
```

**Vì sao cần thuật toán lặp:** nếu chỉ khóa một lần rồi chuẩn hóa lại, phép chuẩn hóa sẽ đẩy
một số ngành vượt trở lại ra ngoài giới hạn. Lỗi này đã bị bắt bởi
`tools/run_topdown_self_check.py` mục 5 trong quá trình phát triển.

Bài toán luôn có nghiệm vì `Σ benchmark = 100`, do đó `Σ cận_dưới ≤ 100 ≤ Σ cận_trên`.

Hàm: `_phan_bo_trong_gioi_han()`, `bang_ty_trong_de_xuat()`.

### 7.3. Độ lệch

```
độ_lệch_i = tỷ_trọng_đề_xuất_i − benchmark_i        (đơn vị: điểm phần trăm)
```

### 7.4. Điểm dễ hiểu sai: tilt là tương đối

Nếu bạn bi quan với **phần lớn** thị trường, phép chuẩn hóa về 100% sẽ kéo các ngành bị hạ điểm
quay lại gần mức benchmark. Lý do: danh mục cổ phiếu luôn phải phân bổ đủ 100% vốn.

Muốn hạ tỷ trọng **cổ phiếu nói chung** thì đó là quyết định phân bổ tài sản — phần 70% trong
nguyên lý 70-20-10 — nằm ngoài phạm vi của module này.

---

## 8. Công thức: điểm nhóm ngành cấp 2

```
điểm_sau_tinh_chỉnh = khóa(điểm_thừa_hưởng_từ_ngành_mẹ + điểm_tinh_chỉnh, 0, 100)
```

với `điểm_tinh_chỉnh ∈ [-20; +20]` do người dùng nhập.

**App cố tình KHÔNG tự chấm điểm cấp 2.** Bộ sách Fisher mô tả định tính đặc điểm từng nhóm
ngành cấp 2 nhưng không cung cấp ma trận độ nhạy định lượng ở cấp này. Theo nguyên tắc số 1
(bám sát tài liệu nguồn) và số 2 (chỉ dùng nguồn chính thống), app không tự bịa hệ số.

Hàm: `bang_industry_group()`, `ap_dung_tinh_chinh()`.

---

## 9. Công thức: sàng lọc định lượng

Nguồn: chương *Top-Down Deconstructed*, mục *Step 2: Quantitative Factor Screening*.

Bốn lớp theo đúng sơ đồ trong sách:

| Lớp | Tiêu chí | Ý nghĩa |
|---|---|---|
| Capitalization | Vốn hóa ≥ ngưỡng | Loại doanh nghiệp quá nhỏ |
| Valuation | P/E, P/B, P/CF, P/S ≤ ngưỡng | Không trả giá quá đắt |
| Solvency | Nợ vay / Vốn chủ ≤ ngưỡng | Loại đòn bẩy quá cao |
| Liquidity | GTGD bình quân ≥ ngưỡng | Đủ thanh khoản để mua bán |

Quy tắc đặc biệt: **P/E ≤ 0 luôn bị đánh dấu không đạt** kèm ghi chú riêng, vì P/E âm không
mang ý nghĩa định giá mà báo hiệu doanh nghiệp đang lỗ — cần xử lý bằng phương pháp khác
(P/B, P/S, giá trị tài sản) chứ không phải bằng ngưỡng P/E.

App **không xóa** dòng không đạt mà giữ lại kèm lý do loại cụ thể, để người dùng thấy được
mình đang loại bỏ những gì.

Hàm: `chay_sang_loc()`.

---

## 10. Tự kiểm tra tính nhất quán (nguyên tắc số 7)

Sau mỗi lần thay đổi tham số, app chạy lại 7 hạng mục kiểm tra:

| Hạng mục | Điều kiện đạt | Mức độ |
|---|---|---|
| Tổng tỷ trọng benchmark | 100.0% ± 0.5 | Cao |
| Đầy đủ 11 ngành trong benchmark | Không thiếu ngành nào | Cao |
| Tổng tỷ trọng đề xuất | 100.0% ± 0.5 | Cao |
| Độ lệch lớn nhất | ≤ giới hạn + 0.5 | Trung bình |
| Số driver đã chấm | ≥ 5 driver khác 0 | Trung bình |
| Độ phân tán điểm | Khoảng cách max − min ≥ 8.0 | Thấp |
| Độ tin cậy benchmark | Không phải giá trị khởi tạo | Cao |

Hàm: `kiem_tra_dong_bo()`.

---

## 11. Cơ chế đồng bộ dữ liệu giữa các module

Toàn bộ tham số nằm trong `st.session_state` và được đọc qua **một hàm duy nhất**
`_current_input()`. Không tab nào giữ bản sao riêng của tham số, nên mọi thay đổi ở sidebar
lập tức lan sang tất cả các bảng.

Kết quả được đẩy sang session dùng chung để các module khác của Trecapital đọc lại:

| Khóa session | Nội dung |
|---|---|
| `topdown_ranking` | Bảng xếp hạng 11 ngành |
| `topdown_weights` | Bảng tỷ trọng đề xuất |
| `topdown_top_sector_code` | Mã ngành điểm cao nhất |
| `topdown_top_sector_name` | Tên ngành điểm cao nhất |
| `topdown_cycle_phase` | Pha chu kỳ đang chọn |

Hàm: `_current_input()`, `_bridge_to_other_modules()`.

---

## 12. Giới hạn và cảnh báo bắt buộc đọc

1. **Ma trận độ nhạy là sự lượng hóa của mô tả định tính.** Bộ sách Fisher mô tả bằng lời rằng
   ngành nào nhạy với driver nào và theo chiều nào; app quy đổi sang thang `[-3; +3]`. Đây là
   diễn giải của app, không phải con số do Fisher công bố.

2. **Benchmark mặc định phải có nguồn và ngày hiệu lực.** App mặc định dùng MSCI Vietnam
   31/07/2026 từ factsheet chính thức của MSCI và cảnh báo khi quá 45 ngày. Lựa chọn VN-Index
   khởi tạo vẫn chưa kiểm chứng; nếu chọn, bắt buộc cập nhật từ HOSE hoặc nhà cung cấp dữ liệu
   chính thống trước khi ra quyết định.

3. **Điểm số không phải tín hiệu mua bán.** Fisher nhấn mạnh: bộ driver không đầy đủ và không
   đúng cho mọi thời kỳ; việc tự tìm ra driver mới đúng mới là nguồn alpha dài hạn.

4. **Thị trường định giá trước chu kỳ.** Bảng pha chu kỳ mô tả nền kinh tế, còn giá cổ phiếu đã
   phản ánh trước. Luôn phải hỏi thêm: kỳ vọng này đã nằm trong giá chưa?

5. **Module này dừng ở cấp ngành.** Mọi quyết định về từng cổ phiếu phải qua module Tổng quan
   doanh nghiệp và Định giá chuyên sâu của Trecapital.
