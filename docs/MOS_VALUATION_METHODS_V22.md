# MOS VALUATION METHODS V22

## Đánh giá sheet MOS và MOS_LILU

### Sheet MOS

Các nhóm công thức chính trong sheet MOS là đúng hướng về mặt nghiệp vụ, nhưng cần hiểu đúng phạm vi:

1. Benjamin Graham `sqrt(22.5 × EPS × BVPS)` là công thức phòng thủ, phù hợp để kiểm tra nhanh biên an toàn trên nền EPS và BVPS có chất lượng.
2. Ken Fisher P/S trong sheet phù hợp hơn với vai trò bộ lọc định giá/tâm lý thị trường, không nên dùng như công thức giá trị nội tại duy nhất.
3. Phil Town EPS/OEPS chiết khấu hợp lý về logic nhưng rất nhạy với giả định tăng trưởng, P/E mục tiêu và tỷ lệ chiết khấu.
4. Chỉ số `(tăng trưởng + cổ tức) / P/E` là bộ lọc tăng trưởng nhanh, không phải định giá nội tại.
5. Phần định giá Owner Earnings đúng hướng hơn EPS kế toán khi chất lượng lợi nhuận cần kiểm tra.

### Sheet MOS_LILU

MOS_LILU đúng trọng tâm Li Lu ở các điểm:

```text
Deployed Capital = Operating Working Capital + Fixed Assets
ROIC Operating Profit = Operating Profit / Deployed Capital
ROIC Owner Earnings = Owner Earnings / Deployed Capital
```

App V22 chuẩn hóa lại cách tính bằng bình quân đầu kỳ/cuối kỳ để tránh trộn số bình quân với số cuối kỳ. Phần net cash được dùng trong định giá earnings-power:

```text
Equity Value = Earnings Power × Multiple + Net Cash
```

Các tỷ lệ MC/OP, MC/OE, MC/EPS và phiên bản net-of-cash là đúng tinh thần kiểm tra “doanh nghiệp có rẻ không”, nhưng không đủ để kết luận nếu chưa trả lời các câu hỏi trong sheet: mô hình kinh doanh tốt không, quản lý có đáng tin không, bear case là gì, tại sao thị trường cho cơ hội này.

## Nguyên tắc dùng kết quả MOS trong app

- Không kết luận mua/bán.
- Hiển thị nhiều phương pháp để tạo vùng giá trị, không dùng một con số duy nhất.
- Ưu tiên phương pháp dựa trên Owner Earnings khi FCF/OE ổn định.
- Nếu EPS/FCF/OE âm hoặc thiếu dữ liệu, app bỏ phương pháp đó thay vì tạo giá trị sai.
- Giá MOS 50% là vùng cần kiểm tra thêm, không phải lệnh mua tự động.


## Hiển thị MOS chi tiết trong V22

Tab Tóm tắt hiển thị cụ thể từng phương pháp định giá gồm: giá trị nội tại, giá MOS 50%, giá hiện tại, biên an toàn hiện tại, tín hiệu và cơ sở tính.

Cách đọc đề xuất:

1. Không xem giá MOS là khuyến nghị mua/bán tự động.
2. Ưu tiên vùng MOS thận trọng và trung vị.
3. Kiểm tra lại giả định tăng trưởng EPS/OEPS, chất lượng Owner Earnings, net cash, deployed capital và bear case.
4. Phương pháp Li Lu/MOS_LILU chỉ có ý nghĩa khi hiểu rõ mô hình kinh doanh và vốn triển khai thực tế.
