# V23.21 – Giao diện giá hiện tại và so sánh doanh nghiệp cùng ngành

## 1. Điều chỉnh giao diện card

- Card **Giá hiện tại** được chuyển xuống ngay dưới dòng mã cổ phiếu và tên doanh nghiệp ở cả Tổng quan doanh nghiệp và Định giá chuyên sâu.
- Các card KPI/metric được tăng khoảng 20% về padding, chiều cao tối thiểu và cỡ chữ để dễ đọc hơn.
- Card giá hiện tại vẫn hiển thị thời điểm cập nhật để tránh nhầm lẫn giữa giá thị trường và dữ liệu BCTC.

## 2. Tab dữ liệu doanh nghiệp cùng ngành

Định giá chuyên sâu bổ sung tab **Dữ liệu DN cùng ngành**. Tab này tạo một kho dữ liệu peer có thể kiểm toán được tại:

```text
data_cache/peer_universe_phần2.csv
```

Các cột chính gồm:

- `ticker`: mã cổ phiếu.
- `company_name`: tên doanh nghiệp.
- `exchange`: sàn giao dịch.
- `industry`: ngành.
- `sub_industry`: phân ngành.
- `peer_group`: nhóm ngành/nhóm so sánh.
- `source`: nguồn tạo/cập nhật dữ liệu.
- `note`: ghi chú analyst.
- `updated_at`: thời điểm cập nhật.

Người dùng có thể nhập nhanh mã, upload CSV hoặc chỉnh trực tiếp trong bảng data editor.

## 3. Lệnh so sánh 10 doanh nghiệp cùng ngành

Sau khi có danh sách peer, người dùng chọn tối đa 10 mã và bấm **So sánh 10 doanh nghiệp cùng ngành**. App sẽ tải dữ liệu theo nguồn đã chọn và tính:

- Giá hiện tại, giá trị weighted, MOS hiện tại.
- P/E, P/B.
- ROE, ROIC, biên gộp, biên ròng.
- CAGR doanh thu 5 năm, CAGR LNST 5 năm.
- CFO/LNST, FCF/LNST.
- Nợ ròng/VCSH.
- Porter Moat score, moat level.
- Điểm chất lượng, điểm dòng tiền, điểm định giá, điểm tổng hợp và xếp hạng.

## 4. Nguyên tắc chấm điểm peer

Điểm tổng hợp dùng để lọc tương đối, không thay thế phân tích riêng từng mã:

```text
Điểm tổng hợp = 30% chất lượng sinh lời/vốn
               + 25% chất lượng dòng tiền
               + 25% Porter Moat
               + 20% định giá/MOS
               - phạt rủi ro đòn bẩy nếu nợ ròng/VCSH cao
```

Cách đọc kết quả:

- Điểm cao + đạt MOS yêu cầu: ưu tiên phân tích sâu.
- Điểm cao nhưng chưa đạt MOS: doanh nghiệp tốt nhưng cần chờ giá hoặc xác nhận tăng trưởng.
- Điểm trung bình/thấp: chỉ dùng làm đối chiếu hoặc cần kiểm tra lại dữ liệu/rủi ro.

## 5. Audit

Kết quả so sánh có thể tải CSV. Mỗi dòng trong bảng có note giải thích, giúp kiểm tra lại số liệu đầu vào, công thức và lý do kết luận.
