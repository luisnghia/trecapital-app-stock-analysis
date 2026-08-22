# Investment Checklist Phase 3A — Industry Overlay, Sign Policy và Watchlist

## Phạm vi checkpoint

V23.81 triển khai Phase 3A theo nguyên tắc evidence-first:

1. KPI theo loại doanh nghiệp và ngành.
2. Operating-driver coverage cho Q22 và Q55–Q57.
3. Porter/Moat scorecard và Porter Value Chain cho doanh nghiệp phi tài chính.
4. Bridge dữ liệu sang các cụm Q15–Q20, Q22–Q26, Q29–Q32 và Q55–Q57.
5. Không gọi AI/network, không tự ghi assessment và không tải peer trong mỗi lần đổi Question.

Peer ranking vẫn dùng trang `So sánh doanh nghiệp` hiện có. Phase 3A chỉ tạo bridge để tránh phá Fast Entry; tích hợp peer snapshot vào review là checkpoint sau.

## Chính sách dấu thống nhất

Một phép chia có thể đúng toán học nhưng sai ý nghĩa kinh tế. App áp dụng các rule sau:

| Chỉ tiêu | Điều kiện tính chuẩn | Trường hợp không đạt điều kiện |
|---|---|---|
| CFO/LNST, FCF/LNST, OE/LNST | LNST > 0 | N/A; đọc trực tiếp dấu CFO/FCF/OE và trạng thái lỗ |
| ABS(Capex)/CFO | CFO > 0 | N/A, 0 điểm, cảnh báo CFO không đủ nền |
| ABS(ΔWC)/LNTT và các ratio/LNTT | LNTT > 0 | N/A; đọc bridge CFO/thuyết minh |
| Debt/EBITDA | EBITDA > 0 | N/A; không hiển thị multiple âm giả |
| ROE/ROA/ROIC | Mẫu số vốn/tài sản > 0 | N/A |
| Margin, turnover, CCC proxy | Doanh thu/COGS/số dư bình quân phù hợp và dương | N/A |
| Growth EPS/LNST | Nền kỳ trước > 0 | Gắn nhãn chuyển trạng thái lỗ–lãi; không tính % |

Số âm ở tử số vẫn được giữ khi mẫu số dương và ratio có ý nghĩa. Ví dụ CFO âm / LNST dương là một tỷ lệ âm hợp lệ và phải tạo cảnh báo.

## Phase 3A theo company type

- `normal`: doanh thu, margins, ROIC, CFO/LNST sign-safe, FCF, CCC, Net Debt/EBITDA; Porter/Moat và Value Chain.
- `cyclical`: cùng nền phi tài chính nhưng operating drivers ưu tiên volume, ASP, commodity spread, capacity utilization; raw point earnings không được coi là normalized earnings.
- `bank`: ROE, ROA, NIM, CASA, LDR, NPL, Group 2, LLR, CAR, CIR, credit cost, loan/deposit growth.
- `insurance`: ROE, premium growth, loss ratio, combined ratio, investment yield, solvency.
- `securities`: ROE, brokerage revenue/margin, margin loans/equity, proprietary trading share và liquidity.

KPI không có trong Trecapital Data Layer được ghi `Research gap`, không suy diễn bằng 0. Với bank/insurance/securities, app không chạy score Porter công nghiệp dựa trên FCF/CCC/TEV-EBITDA.

## Watchlist Table 1.2

Selectable dataframe của Streamlit 1.40 có thể bỏ qua `Styler.format`. Vì vậy Watchlist chuyển dữ liệu thành chuỗi hiển thị trước khi render, rồi mới dùng Styler cho màu/highlight:

- tỷ đồng và giá: 0 số thập phân, có dấu phân cách hàng nghìn;
- ratio: 1 số thập phân + `x`;
- phần trăm/CAGR/MOS/yield: 1 số thập phân + `%`;
- CCC: 0 số thập phân + `ngày`;
- thiếu dữ liệu: `—`, không hiện `None`;
- số âm đỏ, số dương xanh ngọc lục bảo;
- analyst correction: vàng hoa mai, ưu tiên cao hơn heat color.

## Acceptance tests

- Ca DCM: CFO = -2.650 tỷ, Capex âm ⇒ Capex/CFO N/A, 0/10, cảnh báo.
- LNST âm và CFO âm không tạo CFO/LNST dương.
- EBITDA âm không tạo Debt/EBITDA âm/“rẻ”.
- Accrual/Moat không nhận điểm từ tỷ lệ âm/âm.
- EPS loss-to-profit không tạo growth %; buyback uplift không tính trên nền lỗ.
- Watchlist không rò số thô sáu chữ số thập phân hoặc `None`.
- Bank overlay không hiển thị FCF/CCC công nghiệp.
- Streamlit smoke render sạch Industry & Moat.
