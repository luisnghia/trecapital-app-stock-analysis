# V23.63 – FCF heatmap format & MOS formula consistency check

## Phạm vi sửa
- Không thay đổi cấu trúc app, layout tab, tên trang, CSS chủ đạo hoặc cấu trúc dữ liệu.
- Chỉ sửa formatter bảng FCF và logic fallback EPS/OEPS trong bảng MOS của trang Tổng quan doanh nghiệp.

## Sửa định dạng bảng FCF
- `Bảng phân tích sử dụng dòng tiền theo năm` và `Bảng phân tích sử dụng dòng tiền theo quý` hiện dùng lại formatter `_style_financial_table()` của app.
- Các ô số âm hiển thị heatmap đỏ, số dương/tăng trưởng dương hiển thị heatmap xanh ngọc lục bảo.
- Các dòng tiêu đề nhóm `(I)`, `(II)`, `(III)` vẫn giữ nền riêng và chữ đậm để không phá bố cục bảng.
- Báo cáo Excel tổng hợp cũng ép heatmap cho các ô số trong 2 bảng FCF transposed này, vì tiêu đề cột là kỳ/năm nên formatter cũ không nhận diện được nhóm chỉ tiêu.

## Sửa kiểm tra công thức MOS ở 2 trang
- Phát hiện lỗi ở trang Tổng quan: khi dòng TTM không có `eps_vnd/oeps_vnd`, app có thể fallback sang EPS ở overview. EPS overview có thể là dữ liệu snapshot cũ/khác kỳ, làm phương pháp Graham/Phil Town lệch lớn so với dữ liệu BCTC.
- Đã sửa thứ tự ưu tiên:
  1. Dùng `eps_vnd/oeps_vnd` nếu có trong kỳ đang phân tích.
  2. Nếu thiếu, tự tính từ `net_profit_bil/owner_earnings_bil` và `shares_outstanding_mil`.
  3. Chỉ fallback sang EPS overview khi không có dữ liệu BCTC để tự tính.
- Đồng bộ logic net cash của MOS Li Lu trong trang Tổng quan với nhóm nợ vay chịu lãi đã chuẩn hóa: vay ngắn hạn, phần nợ dài hạn đến hạn trả, vay dài hạn, trái phiếu và lease liabilities.

## Ghi chú về việc giá trị MOS ở 2 trang vẫn có thể khác nhau
- Trang Tổng quan doanh nghiệp là bảng MOS nhanh theo từng phương pháp đơn lẻ: Graham, Phil Town EPS/OEPS, Owner Earnings Yield và Li Lu/MOS_LILU.
- Trang Định giá chuyên sâu là hệ thống định giá chuẩn hóa theo loại doanh nghiệp, dùng trọng số phương pháp, normalized EPS/OE/FCF, P/B, NLA/NCAV và dải Low/Base/High/Weighted.
- Vì vậy kết quả giữa hai trang không bắt buộc phải giống nhau nếu tên phương pháp/giả định khác nhau. Điểm đã sửa là không còn lệch do fallback EPS sai kỳ.

## Test
- Chạy 3 vòng:
  - `tools/run_formula_regression_check.py`
  - `tools/run_self_check.py data_sources/Financial-v1.3.0.xlsm --ticker DCM`
  - `tools/run_module2_self_check.py`
- Compile toàn bộ `.py`: OK.
