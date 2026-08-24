# SOURCE_MAPPING_FISHER

Bảng truy vết: mỗi thành phần trong app được lấy từ đâu trong tài liệu nguồn.
Đây là hiện thực của nguyên tắc xây dựng app số 1 (bám sát tài liệu nguồn) và số 2
(nếu dùng tài liệu ngoài nguồn thì phải là nguồn chính thống, uy tín).

---

## A. Tài liệu nguồn đã sử dụng

Toàn bộ 11 tài liệu do người dùng cung cấp, đều thuộc *Fisher Investments Press*
(xuất bản bởi John Wiley & Sons, chủ biên nghiên cứu: Ken Fisher):

| # | Tài liệu | Dùng cho phần nào |
|---|---|---|
| 1 | Fisher Investments on Technology | Khung top-down 3 bước, nguyên lý 70-20-10, Table 7.1 (MSCI World sector weights), Table 7.4 (Portfolio Drivers), bảng pha chu kỳ, quy trình 5 bước, danh sách Strategic Attributes, driver ngành Công nghệ |
| 2 | Fisher Investments on Energy | Driver ngành Năng lượng (cung/cầu dầu và khí, chi phí khai thác) |
| 3 | Fisher Investments on Materials | Driver ngành Nguyên vật liệu (giá hàng hóa, tiêu thụ vật liệu, chi phí sản xuất, "giá xác lập tại biên") |
| 4 | Fisher Investments on Industrials | Driver ngành Công nghiệp (Real GDP, chi tiêu xây dựng, chi tiêu chính phủ và quốc phòng) |
| 5 | Fisher Investments on Consumer Staples | Driver ngành Tiêu dùng thiết yếu, phần *The Business Cycle's Winds of Change*, so sánh Staples vs Discretionary |
| 6 | Fisher Investments on Consumer Discretionary | Driver ngành Tiêu dùng không thiết yếu (thu nhập khả dụng, tiền lương, việc làm là chỉ báo trễ) |
| 7 | Fisher Investments on Telecom | Driver ngành Viễn thông (lãi suất, quản lý giá cước và tần số, Risk Aversion, Value vs Growth) |
| 8 | Fisher Investments on Utilities | Driver ngành Tiện ích (lãi suất, chính sách tiền tệ, lạm phát bất ngờ, giá điện bán buôn, giá khí), *Utilities Outperform During Recessions* |
| 9 | Fisher Investments on Financials | Table 6.4 Portfolio Drivers, phân loại Banks / Diversified Financials / Insurance / Real Estate |
| 10 | Fisher Investments on Health Care | Phân loại ngành, *Defensive Nature of Health Care*, *Innovation and Patent Expirations*, driver chính sách và quản lý giá |
| 11 | Fisher Investments on Emerging Markets | Chương *Developing Portfolio Drivers*, cách chuyển driver thành quyết định phân bổ |

---

## B. Truy vết từng thành phần

### B.1. Khung phương pháp

| Thành phần trong app | Nguồn |
|---|---|
| Quy trình top-down 3 bước | *On Technology*, ch.7 — *Top-Down Deconstructed* (Step 1 Portfolio Drivers → Step 2 Quantitative Factor Screening → Step 3 Stock Selection) |
| Nguyên lý 70-20-10 | *On Technology*, ch.7 — *Top-Down Means Thinking 70-20-10* |
| Bốn lý do top-down ưu việt (Scalability, Enhanced stock selection, Risk control, Macro overview) | *On Technology*, ch.7 |
| Nguyên tắc benchmark, overweight/underweight, "không nhất thiết về 0%" | *On Technology*, ch.7 — *Benchmarks*; *On Financials*, ch.6 — *Managing Against a Financials Benchmark* |
| Phân biệt phân tích tâm lý và làm ngược đám đông (contrarian) | *On Technology*, ch.7 — *Sentiment Drivers* |
| Cảnh báo *home country bias* | *On Technology*, ch.7 — *Political Drivers* |

### B.2. Phân loại ngành (`sector_taxonomy_gics.json`)

| Ngành | Nguồn chương "Sector Breakdown" |
|---|---|
| Công nghệ thông tin | *On Technology*, ch.4 |
| Tiêu dùng không thiết yếu | *On Consumer Discretionary*, ch.4 |
| Tiêu dùng thiết yếu | *On Consumer Staples*, ch.4 |
| Công nghiệp | *On Industrials* — Industrials Sector Breakdown |
| Nguyên vật liệu | *On Materials* |
| Năng lượng | *On Energy*, ch.1 |
| Tiện ích | *On Utilities* |
| Viễn thông | *On Telecom* |
| Tài chính | *On Financials*, ch.1–5 |
| Chăm sóc sức khỏe | *On Health Care*, ch.5 |
| Bất động sản | *On Financials*, ch.5 — Real Estate Industry Group |

Ghi chú: bộ sách viết trước khi GICS tách Real Estate thành sector độc lập (2016) và đổi tên
Telecommunication Services thành Communication Services (2018). App theo cấu trúc 11 sector
hiện hành, giữ Bất động sản làm ngành cấp 1 riêng nhưng nội dung phân loại lấy từ *On Financials*.

### B.3. Portfolio Drivers (`sector_drivers_fisher.json`)

Danh mục 26 driver được xây dựng từ hợp nhất hai bảng gốc:

- *On Technology*, Table 7.4 — Portfolio Drivers (Economic / Political / Sentiment)
- *On Financials*, Table 6.4 — Portfolio Drivers

Cộng thêm các driver đặc thù ngành được nêu trong chương *Sector Drivers* của từng cuốn:

| Driver | Nguồn cụ thể |
|---|---|
| Chu kỳ chi đầu tư và chi IT, book-to-bill | *On Technology*, ch.3 — *Economic Drivers* |
| Đầu tư xây dựng, chi tiêu quốc phòng và hạ tầng | *On Industrials* — *Construction Spending Growth*, *Government Spending* |
| Giá hàng hóa cơ bản, "giá xác lập tại biên" | *On Materials* — *Commodity Prices*, *Prices Are Determined at the Margin* |
| Tiêu dùng cá nhân, thu nhập khả dụng | *On Consumer Discretionary* — *Income and Employment*, *Wage Growth and Disposable Income* |
| Việc làm là chỉ báo TRỄ | *On Consumer Discretionary* — *Employment Is a Lagging Indicator of Economic Growth* |
| Lạm phát bất ngờ, giá điện bán buôn, giá khí | *On Utilities* — *Inflation Surprise*, *Wholesale Electricity Markets*, *Natural Gas Prices* |
| Quản lý giá cước, tần số | *On Telecom* — *Regulatory Changes*, *Intercarrier Compensation*, *Spectrum* |
| Đường cong lãi suất, tăng trưởng tín dụng | *On Financials*, Table 6.4 |
| Bảo hộ sở hữu trí tuệ | *On Technology*, ch.3 — *Intellectual Property Rights* |
| Chính sách công nghiệp | *On Technology*, ch.3 — *Industrial Policy* |
| Chu kỳ Value vs Growth, Risk Aversion | *On Telecom* — *Value Versus Growth*, *Risk Aversion* |
| Đổi mới và hết hạn bằng sáng chế | *On Health Care*, ch.4 — *Innovation and Patent Expirations* |

**Ma trận độ nhạy `[-3; +3]`: đây là phần app tự lượng hóa.** Bộ sách mô tả bằng lời chiều và
mức độ tác động (ví dụ: Tiện ích nhạy mạnh với lãi suất; Công nghệ mang tính giảm phát; Ngân
hàng hưởng lợi khi đường cong dốc lên). App quy đổi các mô tả này sang thang số. Con số cụ thể
là diễn giải của app, không phải số liệu do Fisher công bố — điều này được ghi rõ trong
`_meta.canh_bao` của file cấu hình và hiện trong ghi chú của mọi bảng liên quan.

### B.4. Bảng chu kỳ (`cycle_playbook_fisher.json`)

| Thành phần | Nguồn |
|---|---|
| Năm pha Trough / Early / Mid / Late / Contraction | *On Technology*, ch.3 — biểu đồ pha chu kỳ gắn với Real GDP và Fixed Investment |
| Staples vượt trội khi kinh tế yếu, Discretionary vượt trội khi kinh tế mạnh | *On Consumer Staples*, ch.1 — *The Business Cycle's Winds of Change*; Figure 1.2 và Table 1.4 |
| Tiện ích vượt trội trong suy thoái | *On Utilities* — *Utilities Outperform During Recessions* |
| Viễn thông hưởng lợi khi ngại rủi ro tăng | *On Telecom* — *Risk Aversion* |
| Chăm sóc sức khỏe mang tính phòng thủ | *On Health Care*, ch.4 — *Defensive Nature of Health Care* |

Điểm số `[-3; +3]` cho từng ô là phần app lượng hóa, theo cùng nguyên tắc như mục B.3.

### B.5. Sàng lọc định lượng (`scoring_rules_topdown.json`)

| Thành phần | Nguồn |
|---|---|
| Bộ tiêu chí chặt chẽ: giới hạn ngành, khu vực, vốn hóa, P/E, P/B, P/CF, P/S | *On Technology*, ch.7 — *Strict Criteria* |
| Bộ tiêu chí rộng | *On Technology*, ch.7 — *Broad Criteria* |
| Bốn lớp Capitalization / Valuation / Solvency / Liquidity | *On Technology*, ch.7 — sơ đồ Step 2 (Quantitative Factor Screening) |

Giá trị ngưỡng cụ thể được app điều chỉnh cho thị trường Việt Nam (đơn vị tỷ đồng, mức vốn hóa
và thanh khoản theo quy mô HOSE) và người dùng chỉnh được toàn bộ trong giao diện.

### B.6. Phân tích cổ phiếu 5 bước và Strategic Attributes

| Thành phần | Nguồn |
|---|---|
| Quy trình 5 bước | *On Technology*, ch.8 — *A Five-Step Process*; lặp lại trong *On Financials* ch.7 và *On Emerging Markets* ch.7 |
| Danh sách 15 thuộc tính chiến lược | *On Technology*, ch.8 — *Step 2: Identify Strategic Attributes* |
| Cảnh báo thuộc tính chiến lược phụ thuộc môi trường (ví dụ tích hợp dọc trong ngành bán dẫn) | *On Technology*, ch.8 |
| Nguyên tắc "tối đa hóa xác suất thắng cả nhóm" thay vì "chọn mã tốt nhất" | *On Technology*, ch.7 — *Step 3: Stock Selection* |

### B.7. Số liệu benchmark (`benchmark_weights.json`)

| Benchmark | Độ tin cậy |
|---|---|
| MSCI World 31/12/2008 | **Số liệu gốc** — trích *On Technology*, Table 7.1 |
| VN-Index | **Giá trị khởi tạo, chưa kiểm chứng** — người dùng bắt buộc cập nhật |
| Tự định nghĩa | Người dùng nhập toàn bộ |

App hiện cảnh báo đỏ liên tục khi đang dùng benchmark chưa kiểm chứng, và hạng mục "Độ tin cậy
của benchmark đang dùng" trong bảng tự kiểm tra luôn báo Cảnh báo cho đến khi người dùng chuyển
sang benchmark đã kiểm chứng hoặc tự nhập số liệu từ nguồn chính thống.

### B.8. Điểm Portfolio Driver tự động và quyền ưu tiên analyst

Khi người dùng bấm **Cập nhật dữ liệu vĩ mô mới nhất**, app dùng quy tắc hướng biến đã khai báo
trong `topdown_phase9_sources.json` để chuyển thay đổi của series chính thống thành điểm gợi ý
`[-2; +2]`. Điểm gợi ý hợp lệ trở thành baseline tự động của Portfolio Driver; nguồn không đủ
dữ liệu hoặc chỉ là proxy chưa có quy tắc chấm vẫn giữ trạng thái Research gap.

Thứ tự ưu tiên luôn là: **Analyst override > Điểm gợi ý tự động > Giá trị mặc định**. Khi analyst
điều chỉnh slider, app giữ điểm analyst và các lần rerun/cập nhật tiếp theo không ghi đè. Snapshot
vĩ mô lưu đồng thời điểm hiệu lực, nguồn điểm và baseline tự động gần nhất để có thể audit về sau.
Logic này chỉ áp dụng trong module Fisher Top-Down độc lập; không ghi Q01–Q59, không sửa đánh giá
doanh nghiệp và không tạo quyết định mua/bán.

---

## C. Những gì app KHÔNG lấy từ tài liệu nguồn

Được liệt kê minh bạch để người dùng biết đâu là ranh giới:

1. **Ma trận độ nhạy định lượng** — app lượng hóa từ mô tả định tính (mục B.3).
2. **Điểm số pha chu kỳ** — app lượng hóa từ mô tả định tính (mục B.4).
3. **Trọng số 40/20/20/20 giữa bốn trục điểm** — do app đề xuất, người dùng chỉnh được.
4. **Ngưỡng hệ số tilt (1.6 / 1.3 / 1.0 / 0.7 / 0.4)** — do app đề xuất để chuyển đánh giá
   định tính "overweight / neutral / underweight" của Fisher thành con số vận hành được.
5. **Giới hạn độ lệch 8.0 điểm phần trăm** — do app đề xuất như một cơ chế kiểm soát
   benchmark risk; Fisher nêu nguyên tắc nhưng không đưa con số cụ thể.
6. **Tỷ trọng ngành VN-Index** — giá trị khởi tạo, phải thay bằng số liệu HOSE.
7. **Ngưỡng sàng lọc theo đơn vị tỷ đồng** — quy đổi cho thị trường Việt Nam.

Tất cả bảy mục trên đều là **tham số người dùng chỉnh được trong giao diện**, không phải hằng
số cứng, đúng tinh thần của Fisher: khung phương pháp là thứ có giá trị, còn tham số cụ thể
phải do nhà đầu tư tự xác lập và cập nhật theo thời kỳ.
