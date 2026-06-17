# V23.53 - Beneish AQI + pd.NA fix

## Sửa lỗi

1. Sửa lỗi Streamlit/Pandas:
   - `TypeError: boolean value of NA is ambiguous` tại `_public_text()` khi bảng có `pd.NA`.
   - Hàm hiển thị giờ xử lý an toàn `None`, `pd.NA`, `NaN` trước khi chuyển sang chuỗi.

2. Sửa logic AQI trong Beneish M-Score:
   - Ưu tiên dữ liệu PP&E/TSCĐ thuần nếu nguồn cung cấp.
   - Nếu nguồn chỉ có block `Tài sản dài hạn` và `Tài sản ngắn hạn + Tài sản dài hạn ≈ Tổng tài sản`, app không còn lấy block này như PP&E để rồi tạo mẫu số AQI bằng 0.
   - Khi không tách được PP&E/TSCĐ thuần, app dùng AQI proxy = `Tài sản dài hạn / Tổng tài sản` và ghi rõ trong cột `Biến nổi bật/cần kiểm tra`.

3. Cập nhật caption trong tab `Thao túng tài chính` để giải thích rõ AQI chuẩn/proxy.

## Kiểm tra

- `python -m py_compile module2_engine.py module2_dashboard.py`: OK.
- `python tools/run_module2_self_check.py`: OK.
- Test riêng: bộ dữ liệu có `Tài sản ngắn hạn + fixed_assets_bil ≈ Tổng tài sản` vẫn tính được AQI proxy, không còn trả thiếu AQI.
