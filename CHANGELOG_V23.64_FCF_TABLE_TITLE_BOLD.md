# V23.64 - Đồng bộ in đậm tiêu đề bảng FCF & dòng tiền

## Nội dung sửa
- Cập nhật tiêu đề `Bảng phân tích sử dụng dòng tiền theo năm` và `Bảng phân tích sử dụng dòng tiền theo quý` sang dạng tiêu đề in đậm mạnh, đồng bộ cảm giác thị giác với `Bảng PHÂN TÍCH CHỈ SỐ TC theo năm`.
- Bổ sung style header cho bảng FCF để tiêu đề cột được nhấn mạnh hơn, vẫn giữ nguyên formatter heatmap số âm đỏ / số dương xanh ngọc lục bảo.
- Không thay đổi cấu trúc tab, bố cục bảng, dữ liệu, công thức hay logic tính toán.

## Test
- `python -m py_compile module1_dashboard.py`: OK
- `python tools/run_formula_regression_check.py`: OK
- `python tools/run_self_check.py data_sources/Financial-v1.3.0.xlsm --ticker DCM`: OK
- `python tools/run_module2_self_check.py`: OK
- Compile toàn bộ file `.py`: OK
