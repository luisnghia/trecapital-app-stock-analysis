# Secure label, formula restore and company type key fix

- Ẩn cụm cập nhật kỹ thuật như tên endpoint/nguồn nội bộ khỏi dòng Cập nhật trên giao diện.
- Sửa lỗi KeyError do card loại hình doanh nghiệp đọc sai key `Nguồn tư duy`; thống nhất sang `Cơ sở tư duy`.
- Khôi phục/hiển thị rõ tab Công thức & giả định bằng bảng công thức chính và bảng giả định đang dùng ngay trên giao diện.
- Giữ tên nguồn dữ liệu trong mapping nội bộ nhưng không đưa ra giao diện người dùng.

Kiểm tra:
- python -m py_compile: OK
- tools/run_self_check.py ticker DCM: OK
- tools/run_module2_self_check.py: OK
