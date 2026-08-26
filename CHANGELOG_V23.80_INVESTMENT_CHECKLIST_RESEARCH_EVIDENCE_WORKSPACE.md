# V23.80 — Research Evidence Workspace

- Thêm workspace quản lý nguồn, vị trí trích dẫn, evidence, version và liên kết trực tiếp tới Q01–Q59.
- Evidence phân biệt `supports`, `contradicts`, `context`; không biến Unknown thành Neutral và không tự đưa ra assessment.
- Mỗi source có loại nguồn, nhà phát hành, URL, ngày tài liệu/ngày truy cập và độ tin cậy 1–5.
- Mỗi evidence version là append-only; sửa nội dung bắt buộc tạo version mới và ghi lý do.
- Evidence links thuộc đúng review; completed review khóa mọi thêm/bỏ liên kết.
- Snapshot khi finalize lưu nguyên evidence package và exact evidence versions để không bị hồi tố.
- Analyst Workspace hiển thị evidence của câu hỏi đang chọn, cảnh báo rõ evidence phản bác/mâu thuẫn.
- Coverage matrix cho đủ Q01–Q59, gồm số evidence, verified evidence, mâu thuẫn và materiality cao nhất.
- Review delete xóa evidence links thuộc review nhưng giữ nguồn/evidence dùng lại cho review khác; audit tombstone ghi số link đã xóa.
- SQLite → PostgreSQL migration hỗ trợ các bảng evidence mới và vẫn chấp nhận database legacy chưa có các bảng này.
- Bổ sung test SQLite, PostgreSQL CI, immutable snapshot, review deletion, migration và Streamlit smoke cho toàn bộ evidence sub-sections.

Checkpoint trước khi triển khai: `42aca3a08dd91991188ecd1d6bae5c04f4498bd5` (`V23.79`).
