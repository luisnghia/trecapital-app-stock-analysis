# FORMULA_EXPLANATION_MODULE2

## 1. Nguyên tắc chung

Định giá chuyên sâu không đưa ra một fair value duy nhất. App phân loại doanh nghiệp trước, sau đó chọn trọng số cho từng phương pháp định giá phù hợp. Đây là cách bám triết lý Graham/Buffett/Li Lu: cổ phiếu là quyền sở hữu doanh nghiệp, giá trị phụ thuộc vào chất lượng lợi nhuận, tài sản, dòng tiền, ROIC và biên an toàn.

## 2. Đơn vị và định dạng

- Dữ liệu BCTC trong bảng: tỷ đồng.
- Phần trăm: 1 chữ số thập phân.
- Hệ số/lần: 1 chữ số thập phân.
- Giá trị/cổ phiếu: đồng/cp, không có số thập phân.
- Số âm: đỏ; số dương: xanh ngọc lục bảo.

## 3. Phân loại doanh nghiệp

### Financial / Bank / Insurance
Nếu ngành chứa ngân hàng, bảo hiểm, chứng khoán hoặc tài chính. Không dùng FCF/VLĐ tổng quát làm phương pháp lõi.

### Quality Compounder
Điểm nhận diện: ROIC/ROE cao, CFO/LNST tốt, FCF dương nhiều năm, doanh thu tăng trưởng và dữ liệu đủ dài.

### Cyclical
Điểm nhận diện: ngành hàng hóa/chu kỳ hoặc lợi nhuận biến động mạnh. Cần chuẩn hóa lợi nhuận qua chu kỳ.

### Asset Play / Deep Value
Điểm nhận diện: P/B thấp hoặc tài sản ngắn hạn ròng có ý nghĩa so với vốn hóa.

### Normal Business
Không thuộc nhóm trên hoặc dữ liệu chưa đủ chắc chắn.

## 4. Các phương pháp định giá

### 4.1. Earnings Power / P-E chuẩn hóa

```
EPS chuẩn hóa = LNST trung vị gần đây / số cổ phiếu lưu hành
Giá trị nội tại = EPS chuẩn hóa x P/E mục tiêu
```

P/E mục tiêu được cấu hình tại `configs/valuation_assumptions_phần2.json` hoặc sidebar.

### 4.2. Owner Earnings Value

```
Owner Earnings chuẩn hóa = median Owner Earnings các năm gần đây
OE/cp = Owner Earnings chuẩn hóa / số cổ phiếu lưu hành
Giá trị nội tại = OE/cp x (1 + g) / (required_return - terminal_growth)
```

Cảnh báo: maintenance capex là ước tính. Nếu không tách được capex duy trì và capex mở rộng, app chỉ xem đây là ước lượng sơ bộ.

### 4.3. FCF Capitalization

```
FCF/cp = FCF chuẩn hóa / số cổ phiếu lưu hành
Giá trị nội tại = FCF/cp / (required_return - conservative_growth)
```

Không phù hợp làm phương pháp lõi với ngân hàng/bảo hiểm hoặc doanh nghiệp đang trong chu kỳ đầu tư lớn.

### 4.4. Book Value / P-B tham chiếu

```
BVPS = Vốn chủ sở hữu / số cổ phiếu lưu hành
Giá trị nội tại = BVPS x P/B mục tiêu
```

Phù hợp hơn với ngân hàng, bảo hiểm, chứng khoán hoặc asset play. Cần kiểm tra chất lượng tài sản.

### 4.5. Net Liquid Asset strict và Adjusted NCAV / Liquidation check

```
Net Liquid Asset strict = tiền + đầu tư ngắn hạn + phải thu sau haircut - nợ ngắn hạn
Adjusted NCAV = tài sản ngắn hạn sau haircut, gồm tồn kho sau haircut - tổng nợ phải trả
Giá trị nội tại/cp = giá trị tài sản ròng / số cổ phiếu lưu hành
```

Lưu ý V23.62: NLA strict không cộng tồn kho vì tồn kho không phải tài sản thanh khoản gần như tiền. Nếu dùng tồn kho sau haircut, app trình bày riêng ở dòng Adjusted NCAV / Liquidation check để tránh trộn khái niệm.

Haircut mặc định:

- Tiền/đầu tư ngắn hạn: 0%.
- Phải thu: 25%.
- Tồn kho: 50%.
- TSCĐ chỉ dùng cho liquidation value mở rộng, chưa đưa vào bản V23 lõi.

## 5. Margin of Safety

```
Giá mua MOS 30% = Giá trị nội tại x 70%
Giá mua MOS 50% = Giá trị nội tại x 50%
MOS hiện tại = (Giá trị nội tại - Giá hiện tại) / Giá trị nội tại
```

## 6. Trọng số phương pháp

Trọng số được gán theo phân loại doanh nghiệp và chỉ áp dụng cho các phương pháp có đủ dữ liệu. Sau đó app tự chuẩn hóa tổng trọng số về 100%.



## V23.66 - Cập nhật audit lý thuyết

1. Vốn lưu động vận hành loại trừ tiền, đầu tư ngắn hạn và nợ vay ngắn hạn/current debt.
2. Li Lu deployed capital dùng operating working capital đã loại debt + fixed assets; tránh làm ROIC bị méo bởi debt trong nợ ngắn hạn.
3. ROCE được tính riêng theo công thức EBIT/Core operating profit proxy / Capital Employed.
4. Beneish TATA ưu tiên balance-sheet accruals; fallback cash-flow accrual proxy khi thiếu thành phần và ghi rõ proxy.
5. Module 2 bỏ option Online vnstock/KBS và Online vnstock/VCI; chỉ còn nguồn ưu tiên, FireAnt, Vietstock, Financial tích hợp và CSV mẫu.
