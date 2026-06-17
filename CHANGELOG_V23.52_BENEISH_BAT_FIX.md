# V23.52 - Beneish M-Score BAT Fix

## Sửa lỗi
- Sửa lỗi Windows CMD báo `'Porter' is not recognized`, `'App' is not recognized` do ký tự `&` trong dòng `echo` của file `.bat` bị CMD hiểu là ký tự tách lệnh.
- Escape ký tự `&` thành `^&` trong `run_app.bat`, `run_module2.bat`, `install_and_run_app.bat`, `install_and_run_module2.bat`.
- Sửa `RESET_ENV_AND_RUN.bat` gọi nhầm `install_and_run_phần1.bat` sang `install_and_run_app.bat`.

## Cải thiện tab Beneish
- Khi thiếu biến M-Score, app hiển thị thẻ cảnh báo màu vàng thay vì cảnh báo đỏ như rủi ro gian lận.
- Bổ sung ghi chú: nếu thiếu AQI thì thường do nguồn dữ liệu chưa có đủ Tài sản ngắn hạn / Tài sản dài hạn / Tổng tài sản.

## Kiểm tra
- `python -m py_compile module2_dashboard.py module2_engine.py app.py`: OK.
- `python tools/run_module2_self_check.py`: OK.
