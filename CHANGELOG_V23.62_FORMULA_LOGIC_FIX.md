# V23.62 - Formula logic fix, giữ nguyên cấu trúc/định dạng app

## Mục tiêu
Rà soát và sửa các lỗi công thức lõi nhưng không thay đổi layout, cấu trúc trang, tên tab, CSS/format bảng hiện hữu.

## Nội dung sửa

1. **Free Cash Flow / Capex**
   - Chuẩn hóa Capex khi tính công thức thành dòng tiền ra `-abs(capex_bil)`.
   - FCF = CFO - Capex outflow; tránh sai khi nguồn dữ liệu lưu Capex là số dương.

2. **Owner Earnings proxy**
   - Maintenance Capex proxy = rolling average của `-abs(capex_bil)`.
   - Owner Earnings proxy = CFO + maintenance capex signed outflow.
   - Ghi rõ đây là proxy khi chưa tách được maintenance/growth capex.

3. **Change in Working Capital**
   - Chỉ cộng các khoản vận hành: phải thu, tồn kho, phải trả, trả trước và tài sản ngắn hạn vận hành khác.
   - Không gộp interest paid, tax paid, other operating cash in/out vào Change in WC.

4. **DuPont**
   - Asset turnover dùng doanh thu / tổng tài sản bình quân.
   - Equity multiplier dùng tổng tài sản bình quân / vốn chủ sở hữu bình quân.

5. **Net debt / Interest coverage**
   - Net debt dùng tổng nợ vay chịu lãi gồm vay ngắn hạn, phần dài hạn đến hạn trả, vay dài hạn, trái phiếu, lease liabilities.
   - Interest coverage ưu tiên interest_expense/interest_paid, chỉ dùng financial_expense làm fallback.

6. **NLA / NCAV**
   - Tách `Net Liquid Asset strict` khỏi `Adjusted NCAV / Liquidation check`.
   - NLA strict không cộng tồn kho.
   - Tồn kho sau haircut chỉ nằm ở dòng Adjusted NCAV / Liquidation check.

7. **Porter Moat Score**
   - Chỉnh tổng trọng số về 100 điểm.
   - Engine vẫn chuẩn hóa total_score theo tổng trọng số để tránh vượt thang.

8. **Module 2 Markdown Export**
   - Khi export markdown, summary dùng đúng annual_df hiện có thay vì DataFrame rỗng.

## Test
- Chạy 3 vòng `tools/run_self_check.py`.
- Chạy 3 vòng `tools/run_module2_self_check.py`.
- Chạy 3 vòng `tools/run_formula_regression_check.py` để bắt trực tiếp các lỗi công thức Capex, WC, DuPont, Net debt, NLA/NCAV và Moat score.
