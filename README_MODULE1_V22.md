# Tổng quan doanh nghiệp V22 - Tổng quan doanh nghiệp

## Nâng cấp chính so với V21

1. Bỏ biểu đồ ROE/ROA/ROIC hiện tại ở tab Tóm tắt.
2. Tóm tắt nhanh tình trạng doanh nghiệp đã tổng hợp thêm phần "Nhận xét tự động theo triết lý đầu tư giá trị" từ tab Phân tích chỉ số TC.
3. Định giá MOS ở tab Tóm tắt được diễn giải cụ thể hơn theo từng phương pháp: giá trị nội tại, giá MOS 50%, giá hiện tại, biên an toàn hiện tại, tín hiệu và cơ sở tính.
4. Chuẩn hóa lại định dạng bảng tại tab ROIC & đầu tư và tab Dữ liệu.
5. Giữ nguyên luồng: nhập mã cổ phiếu -> chọn nguồn dữ liệu -> bấm Tìm kiếm & cập nhật dashboard.

## Quy ước định dạng

- Tỷ đồng: không có số thập phân.
- Phần trăm: 1 số thập phân.
- Hệ số/lần: 1 số thập phân.
- EPS/OEPS/giá: đồng/cp, không có số thập phân.
- Số âm: màu đỏ, âm càng nhiều đỏ càng đậm.
- Số dương/tăng trưởng dương: màu xanh ngọc lục bảo, càng lớn xanh càng đậm.

## Chạy app

Lần đầu hoặc khi cần reset môi trường:

```bat
RESET_ENV_AND_RUN.bat
```

Các lần sau:

```bat
run_phần1.bat
```

## Tài liệu công thức

- `docs/FORMULA_EXPLANATION_V22.md`
- `docs/MOS_VALUATION_METHODS_V22.md`
- `docs/FINANCIAL_RATIO_SCORING_CRITERIA_V22.md`
