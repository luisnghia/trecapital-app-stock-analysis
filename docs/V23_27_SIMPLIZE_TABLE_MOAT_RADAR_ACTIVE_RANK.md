# V23.27 - Simplize peer table, Porter Moat radar, active ticker ranking

## Nội dung sửa

1. Thêm biểu đồ màng nhện tại tab **Porter Moat Score**:
   - Lấy dữ liệu từ bảng **Bảng điểm lợi thế cạnh tranh theo Porter**.
   - Điểm nhiệt = `Điểm đạt / Trọng số % * 100`, quy đổi về thang 0-100.

2. Nâng cấp So sánh doanh nghiệp - danh sách cổ phiếu cùng ngành từ Simplize:
   - Parser Simplize lấy thêm các cột giống bảng Simplize: giá hiện tại, biến động giá, 7 ngày, 1 năm, P/E, P/B, ROE, tăng trưởng LNST 3 năm dự phóng, tỷ suất cổ tức, sàn, vốn hóa.
   - Bảng hiển thị bằng `st.dataframe`, có thể sort bằng cách click tiêu đề cột.
   - Dữ liệu vẫn lưu vào `data_cache/peer_universe_phần2.csv` và raw audit trong `raw_data/simplize_peers/`.

3. Khi chạy so sánh peer:
   - Mã đang phân tích luôn được đưa vào danh sách xếp hạng, kể cả khi người dùng chưa chọn trong multiselect.
   - Tổng số mã so sánh vẫn giới hạn tối đa 10, trong đó mã đang phân tích chiếm 1 vị trí.
   - Dòng mã đang phân tích trong bảng kết quả được tô nền vàng/xanh riêng để dễ phân biệt.

## Lưu ý

Nếu Simplize thay đổi cấu trúc trang, app vẫn giữ nguyên cơ chế audit raw và cho import CSV thủ công. Không dùng fallback suy đoán danh sách peer.
