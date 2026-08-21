# Investment Research & Checklist — Công thức & giả định

Tài liệu vận hành này đi cùng `modules/investment_checklist/formula_assumptions.py` và code tính trong `services/formulas.py` / `trecapital_bridge.py`.

## Nguyên tắc nguồn

1. Công thức, nguyên lý và tư duy đầu tư phải bám tài liệu nguồn của dự án.
2. Nếu bộ nguồn không khóa cứng một giả định định lượng, app phải ghi rõ chưa xác định/analyst-configurable thay vì tự tạo mặc định kinh tế mới.
3. Không dữ liệu không được chuyển thành số 0 hoặc một đánh giá trung tính.
4. Table 1.1 tally là screening/filter, không phải khuyến nghị BUY/SELL.
5. Numeric Assessment −2..+2, Confidence, Materiality và Research Completion là lớp workflow của Trecapital; không trình bày như thang điểm do Michael Shearn quy định.
6. Snapshot lịch sử là as-of record; dữ liệu hoặc target/MOS hiện tại không được hồi tố vào snapshot cũ.
7. Các doanh nghiệp tài chính và doanh nghiệp chu kỳ phải có industry/source overlay để tránh dùng công thức không phù hợp bản chất kinh tế.

## Table 1.2 — công thức chính

| Chỉ tiêu | Công thức | Xử lý thiếu dữ liệu / giả định |
|---|---|---|
| TEV | Market Cap + Interest-bearing Debt − Cash & Cash Equivalents − Short-term Investments | Debt chưa xác định ⇒ TEV để trống; không suy diễn debt=0. |
| TEV/EBIT | TEV / EBIT | EBIT ưu tiên dữ liệu trực tiếp; fallback được ghi rõ. EBIT ≤ 0 ⇒ multiple định giá để trống. |
| TEV/EBITDA | TEV / EBITDA | EBITDA ≤ 0 ⇒ valuation multiple để trống. |
| Normalized Earnings | Ưu tiên normalized pre-tax earnings được engine/analyst xác nhận đúng cùng kỳ | Raw TTM pre-tax chỉ là baseline proxy cho DN thường; cyclical chưa chuẩn hóa ⇒ để trống. Normalized annual năm cũ không được dùng để hợp thức hóa raw TTM. |
| TEV/Normalized Earnings | TEV / Normalized Earnings | Chỉ tính khi normalized earnings cùng kỳ hợp lệ và dương. |
| Pre-tax Earnings Yield | EBIT / TEV | Được xác minh trực tiếp từ Bảng 1.2 Shearn: WU 10.1x ↔ 9.9%; WFM 19.1x ↔ 5.2%; Dell 6.0x ↔ 16.8%. Đây là nghịch đảo TEV/EBIT, không phải Normalized Earnings/TEV. |
| Debt/EBITDA | Interest-bearing Debt / EBITDA | EBITDA ≤ 0 ⇒ ratio leverage không có ý nghĩa chuẩn. Nên xem 10Y + TTM thay vì một snapshot. |
| EBIT/Interest | EBIT / abs(Interest Expense) | Không thay toàn bộ Financial Expense cho Interest Expense khi chưa tách được lãi vay. EBIT âm vẫn có thể hiển thị như tín hiệu không đủ coverage. |
| FCF | CFO − abs(Capex) | Ưu tiên FCF trực tiếp nếu Data Layer đã chuẩn hóa. Total capex không đồng nghĩa maintenance capex. |
| FCF Yield EV | FCF / TEV | FCF âm được giữ vì là tín hiệu cash burn; TEV thiếu ⇒ để trống. |
| FCF Yield Market | FCF / Market Cap | Market Cap phải reconcile với Price × Shares khi lệch vật chất. |
| Dividend Yield | Dividend/share / Market Price | Giá không hợp lệ ⇒ để trống. |
| Stock Price vs Target | Market Price / Target Price | Target lịch sử không hồi tố. |
| MOS | (Target Price − Market Price) / Target Price | Ngưỡng MOS hành động do Module 2 quản lý; nguồn không khóa một ngưỡng duy nhất cho mọi doanh nghiệp. |
| CCC | DIO + DSO − DPO | Proxy chỉ tính từ Avg Inventory/AR/AP khi có kỳ trước. |

## TTM

- Flow items: tổng 4 quý gần nhất.
- Balance-sheet items: số dư quý gần nhất.
- Các ratio cần denominator bình quân sử dụng average balance phù hợp khi đủ dữ liệu.
- Không cộng các số dư cuối kỳ.
- Trong lịch sử Opportunity Inventory, TTM luôn hiển thị trước các review/năm cũ.

## Overlay ngành

### Cyclical

Michael Shearn phân biệt doanh nghiệp có distribution of future earnings hẹp và rộng. Khi earnings distribution rộng như cyclical, point estimate dựa trên raw TTM dễ gây sai lệch. Vì vậy raw TTM pre-tax profit không được gắn nhãn `Normalized Earnings`; chỉ dùng khi có normalized input cùng kỳ hoặc scenario/analyst adjustment. TEV/EBIT và Pre-tax Earnings Yield hiện tại vẫn có thể được theo dõi như chỉ tiêu watchlist, nhưng không được biến thành point valuation kết luận cho cyclical.

### Bank / Insurance / Securities

TEV/EBITDA, FCF và CCC theo kiểu doanh nghiệp công nghiệp không được dùng làm kết luận chính. Phase hiện tại của Checklist chủ động khóa các metric công nghiệp này thay vì hiển thị số có vẻ chính xác nhưng sai bản chất kinh tế.

## Table 1.1 và 59Q

- `✓` = có; `X` = không có; `—` = chưa biết; `N/A` = lớp workflow mở rộng của app.
- Quality tally = số tiêu chí `✓` trong 10 tiêu chí Table 1.1.
- Research Completion = Answered / (59 − N/A).
- Research Gap không phải Neutral.
- Assessment −2..+2 chỉ áp dụng cho `Answered` / `Needs Review`; Research Gap / N/A / Not Reviewed không có numeric assessment.
- AI, khi được bổ sung ở phase sau, chỉ là Research Assistant; analyst giữ kết luận cuối cùng.

## Manual review deletion

Lịch sử bình thường là append-only. Xóa review là ngoại lệ hành chính có chủ đích để dọn review test/sai:

- bắt buộc nhập lý do;
- bắt buộc nhập chuỗi xác nhận chính xác;
- xóa assessment/screening/snapshot thuộc review đó;
- nối lại `prior_review_id` của review sau về prior của review bị xóa;
- giữ audit tombstone để biết review nào đã bị xóa và vì sao.

## Thuật ngữ tối thiểu

- **TEV/EV:** Total Enterprise Value / Enterprise Value.
- **EBIT:** Earnings Before Interest and Taxes.
- **EBITDA:** EBIT trước khấu hao và phân bổ.
- **FCF:** Free Cash Flow.
- **CFO:** Cash Flow from Operations.
- **Capex:** Capital Expenditure.
- **CCC:** Cash Conversion Cycle = DIO + DSO − DPO.
- **DIO/DSO/DPO:** số ngày tồn kho/phải thu/phải trả.
- **MOS:** Margin of Safety.
- **TTM/T12M:** Trailing Twelve Months.
- **Research Gap:** khoảng trống nghiên cứu; không phải Neutral.

## Format hiển thị

- tỷ đồng: 0 số thập phân;
- phần trăm: 1 số thập phân;
- hệ số/lần: 1 số thập phân;
- số âm: đỏ theo cường độ;
- số dương: xanh ngọc lục bảo theo cường độ;
- warning/signal phải phân cấp rõ mức độ và không che mất uncertainty.

## Nguồn chính của module

- Michael Shearn — *The Investment Checklist*: Table 1.1, Table 1.2, Ch.5 ROIC/balance-sheet, Ch.6 earnings distribution/cash flows, Q01–Q59.
- Bộ nguồn định giá Trecapital: Owner Earnings, Working Capital, ROIC, Capital Employed, Net Liquid Assets, Graham/Buffett/Howard Marks/Li Lu/Peter Lynch.
- `Nguyên-tắc-xây-dựng-app.txt`: quy tắc formula explanation, format, shared Data Layer, audit/log và no-fabrication.
