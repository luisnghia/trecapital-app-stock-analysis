# V23.67 - Theory Formula Final Audit

## Mục tiêu
Rà lại toàn bộ công thức theo lý thuyết phân tích tài chính và tài liệu nguồn, không thay đổi cấu trúc/định dạng app.

## Sửa bổ sung sau audit lý thuyết

1. **TTM denominators**
   - TTM tiếp tục cộng các dòng flow trong 4 quý gần nhất.
   - Các mẫu số bình quân như `avg_total_assets_bil`, `avg_equity_bil`, `avg_capital_employed_bil`, `avg_deployed_capital_bil` chuyển sang dùng bình quân các quý trailing thay vì bê nguyên bình quân của quý mới nhất.
   - Lý do: ROE/ROIC/ROA TTM phải dùng vốn/tài sản bình quân của kỳ TTM, không dùng mẫu số một quý.

2. **TTM cash-change và COGS**
   - `cash_and_short_investments_change_bil` chuyển về nhóm flow để TTM = tổng thay đổi 4 quý.
   - `cost_of_goods_sold_bil` chuyển về nhóm flow để TTM phục vụ vòng quay tồn kho/biên gộp đúng kỳ.

3. **Doanh nghiệp tài chính/ngân hàng trong Module 2**
   - FCF, Owner Earnings, NLA, NCAV và P/E không còn có trọng số trong weighted valuation của doanh nghiệp tài chính/ngân hàng/bảo hiểm.
   - P/B tham chiếu là phương pháp lõi; warning ghi rõ P/B mặc định chỉ là proxy và cần kiểm tra ROE bền vững, NPL, dự phòng, CAR, chất lượng tài sản.

## Kiểm thử bổ sung
- Thêm regression test cho TTM flow/average denominator.
- Thêm regression test cho việc loại trọng số các phương pháp không phù hợp ở doanh nghiệp tài chính.

## Kết quả kiểm thử
- `python -m compileall -q .`: OK
- `python tools/run_formula_regression_check.py`: OK
- `python tools/run_self_check.py data_sources/Financial-v1.3.0.xlsm --ticker DCM`: OK
- `python tools/run_module2_self_check.py`: OK
