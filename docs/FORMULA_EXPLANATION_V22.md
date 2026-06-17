# FORMULA EXPLANATION V22 - Tổng quan doanh nghiệp

## 1. Nguyên tắc chung

V22 xem file Excel gốc là bản thiết kế nghiệp vụ và kiểm tra lại công thức theo các tài liệu nguồn. App không đưa ra khuyến nghị mua/bán, mà trình bày dữ liệu, công thức, vùng giá MOS tham khảo và các cảnh báo để người dùng tự ra quyết định.

Quy ước hiển thị:
- Số tiền: tỷ đồng, không có số thập phân.
- Phần trăm: 1 số thập phân.
- Hệ số/lần: 1 số thập phân.
- EPS/OEPS/giá: đồng/cp, không có số thập phân.
- Bảng số liệu: âm màu đỏ đậm dần; dương/tăng trưởng dương màu xanh ngọc lục bảo đậm dần.

## 2. Dữ liệu năm và TTM

V22 giữ 10 năm lịch sử và bổ sung 1 dòng TTM khi có tối thiểu 4 quý gần nhất.

Cách tính TTM:

```text
TTM flow item = tổng 4 quý gần nhất
```

Áp dụng cho doanh thu, lợi nhuận, CFO, Capex, FCF, Owner Earnings, cổ tức đã trả, chi phí tài chính, thuế, các dòng tiền.

Với các chỉ tiêu dạng số dư như tài sản, vốn chủ sở hữu, tiền, đầu tư tài chính ngắn hạn, nợ vay, số cổ phiếu lưu hành:

```text
TTM balance item = số dư quý gần nhất
```

## 3. ROE, ROA, ROIC

```text
ROE tự tính = LNST / Vốn chủ sở hữu bình quân
ROA tự tính = LNST / Tổng tài sản bình quân
```

Vốn chủ sở hữu bình quân và tài sản bình quân dùng trung bình đầu kỳ/cuối kỳ khi dữ liệu có đủ.

ROIC chuẩn:

```text
Core Operating Profit = Lợi nhuận gộp - Chi phí bán hàng - Chi phí QLDN
NOPAT = Core Operating Profit × (1 - Thuế suất hiệu dụng)
Capital Employed = Total Assets - Current Liabilities
Average Capital Employed = bình quân đầu kỳ/cuối kỳ
ROIC chuẩn = NOPAT / Average Capital Employed
```

Capital Employed được sử dụng nhất quán với định nghĩa vốn được doanh nghiệp sử dụng để tạo lợi nhuận; có thể tính bằng Total Assets - Current Liabilities hoặc Fixed Assets + Working Capital.

## 4. ROIC theo MOS_LILU

ROIC theo MOS_LILU là chỉ tiêu phân tích chuyên sâu, không thay ROIC chuẩn.

```text
Operating Working Capital = Current Assets - Cash - Short-term Investments - Accounts Payable
Deployed Capital = Operating Working Capital + Fixed Assets
Average Deployed Capital = bình quân đầu kỳ/cuối kỳ
ROIC Operating Profit MOS_LILU = Core Operating Profit / Average Deployed Capital
ROIC Owner Earnings MOS_LILU = Owner Earnings / Average Deployed Capital
```

Lưu ý: với doanh nghiệp nắm giữ nhiều tiền và đầu tư tài chính ngắn hạn, mẫu số Deployed Capital có thể nhỏ, làm ROIC MOS_LILU rất cao. Đây là đặc điểm phân tích vốn thực sự triển khai, không nên đọc như ROIC kế toán thông thường.

## 5. Free Cash Flow và Owner Earnings

```text
FCF = CFO - Capex outflow
```

Trong dữ liệu FireAnt/Excel, Capex thường là số âm nên app quy đổi Capex thành dòng tiền ra `-abs(capex_bil)` trước khi tính. Vì vậy dữ liệu capex âm hay dương đều được chuẩn hóa thành CFO trừ tiền chi đầu tư tài sản dài hạn.

Owner Earnings theo hướng Buffett:

```text
Owner Earnings = CFO - Maintenance Capex
```

Vì dữ liệu công khai không tách rõ maintenance capex và growth capex, app dùng proxy:

```text
Maintenance Capex ≈ dòng tiền Capex ra bình quân trượt = average(-abs(capex_bil))
```

V22 tiếp tục hiển thị cả FCF và Owner Earnings vì hai chỉ tiêu có thể khác nhau lớn trong doanh nghiệp thâm dụng vốn hoặc đang đầu tư chu kỳ.

## 6. Định giá MOS

V22 thêm bảng định giá MOS ở tab Tóm tắt. Đây là vùng giá tham khảo để kiểm tra biên an toàn, không phải khuyến nghị mua/bán.

### 6.1 Benjamin Graham EPS × BVPS

```text
Giá trị nội tại = sqrt(22.5 × EPS × BVPS)
Giá MOS 50% = Giá trị nội tại × 50%
```

Ý nghĩa: công thức phòng thủ, dùng khi EPS và BVPS đáng tin cậy. Không phù hợp khi EPS âm, doanh nghiệp chu kỳ cực mạnh hoặc tài sản sổ sách không phản ánh thực chất.

### 6.2 Phil Town/EPS hoặc OEPS chiết khấu

```text
EPS tương lai = EPS hiện tại × (1 + g)^10
Giá trị hiện tại = EPS tương lai × Target P/E / (1 + Discount Rate)^10
Giá MOS 50% = Giá trị hiện tại × 50%
```

V22 giới hạn tăng trưởng dự phóng để tránh ngoại suy quá lạc quan. Nếu dùng OEPS, công thức ưu tiên dòng tiền chủ sở hữu hơn lợi nhuận kế toán.

### 6.3 Owner Earnings Yield

```text
Giá trị nội tại = OEPS × 10
Giá MOS 50% = Giá trị nội tại × 50%
```

Tương đương yêu cầu lợi suất Owner Earnings khoảng 10% trước MOS.

### 6.4 Li Lu/MOS_LILU earnings power + net cash

```text
Net Cash = Cash + Short-term Investments - Short-term Debt - Long-term Debt
Giá trị vốn chủ sở hữu = Core Operating Profit × Multiple + Net Cash
Giá trị/cp = Giá trị vốn chủ sở hữu / Số cổ phiếu lưu hành
```

Với Owner Earnings:

```text
Giá trị vốn chủ sở hữu = Owner Earnings × Multiple + Net Cash
```

Ý nghĩa: tách phần tiền/đầu tư tài chính dư thừa khỏi hoạt động, sau đó vốn hóa lợi nhuận cốt lõi hoặc Owner Earnings. Cách đọc này bám tinh thần Li Lu khi đánh giá doanh nghiệp có tài sản hữu hình, vốn triển khai thấp và biên an toàn rõ.

## 7. Cảnh báo/tổng hợp đánh giá

Ô “Cảnh báo / điểm cần kiểm tra” trong tab Tóm tắt tổng hợp từ:
- Đánh giá tổng quan ROE/ROIC/P/E/CFO/FCF/OE.
- Điểm dòng tiền và các tình huống FCF.
- Điểm chỉ số tài chính và các tình huống chất lượng tài chính.
- Kết quả định giá MOS.

Mục tiêu là giúp người dùng nhìn một nơi duy nhất để biết doanh nghiệp cần kiểm tra gì trước khi đi sâu vào từng tab.


## Bổ sung V22

- Bỏ biểu đồ ROE/ROA/ROIC ở tab Tóm tắt để tránh trùng lặp với tab DuPont và ROIC & đầu tư.
- Tóm tắt nhanh tình trạng doanh nghiệp nay gồm ba phần: tổng quan nhanh, nhận xét tự động theo triết lý đầu tư giá trị, và định giá MOS chi tiết.
- Bảng ROIC & đầu tư và tab Dữ liệu được chuẩn hóa lại định dạng: tỷ đồng không thập phân, phần trăm 1 số thập phân, hệ số 1 số thập phân, EPS/OEPS/giá đồng/cp không thập phân.
- Bảng dữ liệu vẫn dùng heatmap âm đỏ đậm dần, dương/tăng trưởng dương xanh ngọc lục bảo đậm dần.
