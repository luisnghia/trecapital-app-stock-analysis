# PORTER_MOAT_SCORING_GUIDE

## 1. Nguyên tắc Porter trong từng phần 2

Định giá chuyên sâu không đánh giá lợi thế cạnh tranh bằng cảm tính như “công ty có thương hiệu tốt”. App phân tích theo chuỗi giá trị: hoạt động nào tạo chi phí thấp hơn, hoạt động nào tạo khác biệt hóa, hoạt động nào khó bắt chước và hoạt động nào có bằng chứng từ dữ liệu.

## 2. Thang điểm 100

| Nhóm | Trọng số | Ý nghĩa |
|---|---:|---|
| Hiệu quả vốn / ROIC | 20 | ROIC/ROE cao và bền vững là dấu hiệu moat quan trọng. |
| Cost advantage | 12.5 | Biên gộp, SG&A/doanh thu, vòng quay tài sản, CCC. |
| Differentiation / Pricing power | 12.5 | Biên gộp, biên ròng, thương hiệu, thị phần, khả năng giữ giá. |
| Cấu trúc ngành & chu kỳ | 15 | Mức biến động lợi nhuận, rào cản gia nhập, đòn bẩy. |
| Chất lượng dòng tiền | 15 | CFO/LNST, FCF/LNST, capex, vốn lưu động. |
| Khả năng tái đầu tư | 10 | Doanh thu tăng trưởng nhưng ROIC không suy giảm. |
| Chuỗi giá trị vận hành | 8 | Tồn kho, phải thu, phải trả, chu kỳ chuyển đổi tiền mặt. |
| Quản trị vốn & an toàn tài chính | 7 | Nợ vay, interest coverage, cổ tức, buyback, M&A. |

Tổng trọng số sau V23.62 = 100 điểm. Engine vẫn tự chuẩn hóa `total_score` theo tổng trọng số để tránh lỗi vượt thang nếu sau này cấu hình trọng số thay đổi.

## 3. Xếp hạng

- 80-100: Moat mạnh.
- 60-79: Moat khá.
- 40-59: Moat trung bình.
- Dưới 40: Moat yếu hoặc chưa đủ bằng chứng.

## 4. Chuỗi giá trị

Các hoạt động chính:

1. Logistics đầu vào.
2. Vận hành/sản xuất.
3. Logistics đầu ra.
4. Marketing & bán hàng.
5. Dịch vụ sau bán hàng.

Các hoạt động hỗ trợ:

1. Công nghệ/R&D.
2. Nhân sự.
3. Hạ tầng quản trị.
4. Mua hàng/phân bổ vốn.

## 5. Cách dùng kết quả moat vào định giá

- Moat mạnh: Owner Earnings và Earnings Power có thể là phương pháp chính.
- Moat trung bình: dùng nhiều phương pháp, tăng biên an toàn.
- Moat yếu/chưa rõ: không trả premium; ưu tiên asset value, normalized P/E, P/B hoặc chờ thêm bằng chứng.

