# V23.33 - Auto summary checklist, full assessment table & stable row notes

## Nội dung cập nhật

1. **Định giá chuyên sâu - Tóm tắt tự động**
   - Bổ sung dòng **Đặc điểm cần kiểm tra** ngay trong khối **Tóm tắt tự động** theo loại doanh nghiệp đang được phân loại.
   - Đồng bộ thêm nội dung này ở card phân loại doanh nghiệp màu vàng thương hiệu.

2. **Bảng Đánh giá trọng yếu theo dữ liệu doanh nghiệp**
   - Chuyển bảng sang chế độ **full table**: không giới hạn chiều cao/không cuộn trong bảng.
   - Tăng chiều cao component để người dùng xem toàn bộ nội dung bảng và vùng note ngay bên dưới.

3. **Khôi phục chức năng chọn dòng để hiện note**
   - Đổi cơ chế lưu note từ JSON trực tiếp trong attribute sang **UTF-8 base64** để tránh lỗi khi note có tiếng Việt, dấu xuống dòng, dấu nháy hoặc ký tự đặc biệt.
   - Đổi cơ chế click từ gắn event từng dòng sang **event delegation** trên table, ổn định hơn khi Streamlit rerender component.
   - Áp dụng cho các bảng explainable của **Định giá chuyên sâu** và các bảng explainable của **Tổng quan doanh nghiệp** đang dùng chung cơ chế click-note.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py phần1_dashboard.py phần2_dashboard.py phần1_engine.py phần2_engine.py`: đạt.
