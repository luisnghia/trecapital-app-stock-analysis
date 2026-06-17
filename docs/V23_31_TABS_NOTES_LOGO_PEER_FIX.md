# V23.31 - Tab biểu đồ tài chính, note số liệu, logo page và peer row fix

Các chỉnh sửa chính:

1. Gộp tab `Biểu đồ năm + TTM` và `Biểu đồ 20 quý` thành một tab `Biểu đồ tài chính`, bên trong có 2 tab con `Năm + TTM` và `20 quý`.
2. Bổ sung CSS/logic heatmap cho các bảng đánh giá định tính và điểm số; tiêu đề bảng in đậm.
3. Note click dòng được bổ sung số liệu cụ thể: ROIC, WACC, ROE, CFO/LNST, FCF/LNST, CAGR doanh thu/LNST/Owner Earnings, FCF, Capex, CCC, nợ vay... tùy nhóm đánh giá.
4. Logo Trecapital chuyển từ sidebar sang header page để không bị ẩn khi sidebar thu gọn.
5. Dòng mã đang phân tích trong danh sách Simplize được giữ đủ ticker/tên và ưu tiên dữ liệu đầy đủ nhất khi trùng mã; dòng được tick mặc định và nhận diện bằng biểu tượng 🎯/màu thương hiệu.
6. Bảng diễn giải loại hình doanh nghiệp: cột `Loại doanh nghiệp` in đậm.
7. Tổng quan doanh nghiệp không còn hiển thị ngành/phân ngành chỉ bằng mã số như 2353; app chuyển mã ICB phổ biến sang tên ngành dễ đọc.
