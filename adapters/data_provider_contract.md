# Chuẩn dữ liệu đầu vào cho Tổng quan doanh nghiệp

Tổng quan doanh nghiệp không phụ thuộc trực tiếp vào FireAnt/Vietstock. Mọi nguồn dữ liệu cần được chuẩn hóa về các trường sau:

| Field | Ý nghĩa | Đơn vị |
|---|---|---|
| ticker | Mã cổ phiếu | Text |
| company_name | Tên công ty | Text |
| exchange | Sàn | HOSE/HNX/UPCOM |
| industry | Ngành | Text |
| sub_industry | Phân ngành | Text |
| market_cap_bil | Vốn hóa | Tỷ đồng |
| shares_outstanding_mil | Cổ phiếu lưu hành | Triệu cp |
| current_price | Giá hiện tại | Đồng/cp |
| eps | EPS | Đồng/cp |
| pe | P/E | Lần |
| pb | P/B | Lần |
| ps | P/S | Lần |
| roe | ROE | % |
| roa | ROA | % |
| roic | ROIC | % |
| updated_at | Thời điểm cập nhật | Text/datetime |

## Gợi ý tích hợp nguồn dữ liệu

- `provider_csv.py`: đọc file CSV/Excel đã xuất từ FireAnt/Vietstock.
- `provider_fireant.py`: lấy dữ liệu từ FireAnt hoặc file Excel Add-in nếu có quyền truy xuất.
- `provider_vietstock.py`: lấy dữ liệu từ Vietstock DataFeed/API hoặc file xuất VietstockFinance.

Nguyên tắc: provider nào cũng phải trả về object/dict cùng cấu trúc để dashboard không phải sửa.
