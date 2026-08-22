# V23.79 — Investment Checklist secret-safe smoke fix

- Đọc PostgreSQL/Supabase URL từ biến môi trường trước, đồng bộ với resolver của Core Research System.
- Dùng `st.secrets.load_if_toml_exists()` để kiểm tra secrets tùy chọn mà không tạo bốn ô lỗi đỏ khi chạy local/dev bằng SQLite.
- Giữ nguyên hỗ trợ ba khóa root-level và `[connections.postgresql].url`.
- Bổ sung Streamlit AppTest tái hiện đúng trường hợp không có `secrets.toml` và khóa regression: không exception, không `st.error`.
- Bổ sung full-page smoke deterministic cho luồng Fast Entry: mở nguyên trang Checklist, tái sử dụng active bundle và không gọi lại nguồn dữ liệu.

Checkpoint trước sửa: `4834af255d8bee63d31ac266d3331f45483504ca` (`V23.78`).
