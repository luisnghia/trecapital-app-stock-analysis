# Ghi chú kỹ thuật gói deploy

Các thay đổi đã thực hiện so với zip gốc:

1. Làm phẳng cấu trúc: `app.py` nằm ngay root để deploy dễ trên Streamlit Cloud.
2. Xóa `__pycache__`, file `.pyc`, file `.bat`, log/report runtime cũ.
3. Thêm `.gitignore` để tránh commit cache, log, output và secrets.
4. Thêm `runtime.txt` để ưu tiên Python 3.11.
5. Thêm `.streamlit/secrets.toml.example` làm mẫu, không chứa secret thật.
6. Thay README chính bằng hướng dẫn deploy; README gốc được lưu tại `README_APP_ORIGINAL.md`.

Gói chưa thay đổi logic tính toán tài chính, định giá, format bảng, dữ liệu mẫu/tích hợp.
