# V23.65 - Sửa tiêu đề bảng FCF dùng đúng subheader in đậm

## Nội dung sửa
- Sửa hàm `_render_bold_table_title()` trong `module1_dashboard.py` để render bằng `st.subheader(...)`.
- Hai tiêu đề `Bảng phân tích sử dụng dòng tiền theo năm` và `Bảng phân tích sử dụng dòng tiền theo quý` hiện dùng đúng cùng component với `Bảng PHÂN TÍCH CHỈ SỐ TC theo năm`.
- Loại bỏ CSS `.table-title-bold` cũ vì có thể không tạo cảm giác in đậm giống `st.subheader` trong UI thực tế.

## Phạm vi
- Chỉ thay đổi cách render tiêu đề.
- Không thay đổi cấu trúc tab, bảng, dữ liệu, công thức, formatter heatmap hoặc logic tính toán.
