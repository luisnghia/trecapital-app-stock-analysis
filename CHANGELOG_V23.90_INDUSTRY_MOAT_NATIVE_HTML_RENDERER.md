# V23.90 — Industry & Moat native HTML renderer

## Lỗi production

- Bản V23.89 đã loại bỏ leading indentation nhưng Streamlit Fragment vẫn hiển thị nguyên chuỗi
  `<div>/<table>` như code và tách nội dung bảng thành văn bản không định dạng.
- Lỗi xuất hiện trên iPad sau khi deployment đã nhận đúng menu Phase 6.

## Sửa lỗi

- Chuyển toàn bộ bảng Industry & Moat từ `st.markdown(..., unsafe_allow_html=True)` sang
  `st.html(...)`, đúng renderer HTML chuyên dụng có sẵn trong Streamlit 1.40.2 của dự án.
- Giữ wrapper cuộn ngang nội bộ, tự xuống dòng, sticky-safe width và cỡ chữ/padding tối ưu
  cho màn hình tablet.
- Không thay đổi dữ liệu, công thức, assessment hoặc schema PostgreSQL/Supabase.

## Regression

- Khóa contract không được quay lại đường render Markdown.
- AppTest xác nhận tối thiểu bốn bảng Industry & Moat được tạo thành HTML element thật,
  bắt đầu bằng `<style>` và có wrapper `industry-*`.
