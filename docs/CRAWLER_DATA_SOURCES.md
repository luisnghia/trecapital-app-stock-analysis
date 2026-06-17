# Data sources - Tổng quan doanh nghiệp V13

## FireAnt

V13 ưu tiên FireAnt theo đúng phần VBA `TCReport_FireAnt.cls` trong file `Financial-v1.3.0.xlsm`:

- `https://www.fireant.vn/api/Data/Markets/Quotes?symbols={ticker}`
- `https://www.fireant.vn/api/Data/Finance/YearlyFinancialInfo?symbol={ticker}&fromYear=...&toYear=...`
- `https://www.fireant.vn/api/Data/Finance/QuarterlyFinancialInfo?symbol={ticker}&fromYear=...&fromQuarter=...&toYear=...&toQuarter=...`
- `https://www.fireant.vn/api/Data/Finance/LastestFinancialReports?symbol={ticker}&type={1..4}&year=...&quarter=...&count=...`

Mapping report type theo VBA:

- `1`: Cân đối kế toán
- `2`: Kết quả kinh doanh
- `3`: Lưu chuyển tiền tệ trực tiếp
- `4`: Lưu chuyển tiền tệ gián tiếp
- `5`: Chỉ số tài chính qua `YearlyFinancialInfo` / `QuarterlyFinancialInfo`

## Không dùng trong V13

- Không dùng `vnstock`.
- Không dùng Playwright.
- Không tự động ghi dữ liệu rỗng vào dashboard.

Nếu FireAnt trả lỗi hoặc đổi cấu trúc, xem thư mục `raw_data/` và tab `Nhật ký nguồn`.
