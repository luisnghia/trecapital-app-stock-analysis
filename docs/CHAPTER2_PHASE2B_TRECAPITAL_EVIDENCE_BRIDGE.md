# Chapter 2 Phase 2B — Trecapital Data & Evidence Bridge

## Mục tiêu

Nối Chương 2 — *Understanding the Business: The Basics* với Trecapital canonical financial data và evidence layer, nhưng giữ nguyên nguyên tắc:

- **AI/Data = Research Assistant; user = Investment Analyst.**
- Không ghi đè nội dung analyst đã lưu.
- Không tự viết thay phần `Explain it in your own words` của Q3.
- Không tự kết luận `Skill vs Luck` của Q5.
- Không tự quyết định Q1 Research Interest / Circle of Competence hoặc Q2 CEO Lens.
- Không tạo BUY/HOLD/SELL và không thay Research Gate của Chương 1.

## Workspace thống nhất

Từ bản khóa UX của Chương 2, Chương 1 và Chương 2 không còn là hai mục sidebar độc lập. Cả hai nằm trong cùng page **Phân tích chuyên sâu doanh nghiệp**, mỗi chương là một tab:

- `📗 Chương 1 — Cơ hội đầu tư`
- `📘 Chương 2 — Hiểu doanh nghiệp`

Cách tổ chức này giúp toàn bộ các chương sau tiếp tục mở rộng như các tab của cùng một research workspace và dùng chung ticker/data context.

## Bridge dữ liệu

Page Chương 2 đọc lại bundle Trecapital hiện có của ticker:

- `company_overview_sample.csv`
- `financial_timeseries_year.csv`
- `financial_timeseries_quarter.csv`

và dùng `module1_engine.append_ttm_row()` để giữ cùng canonical financial context với các module khác. Không tạo financial crawler/financial parser riêng cho Chương 2.

### Q4 — Financial economics context

Research Assistant tự dựng context định lượng từ kỳ TTM/gần nhất:

- Revenue (tỷ đồng)
- Revenue growth so annual period gần trước
- Gross profit / Gross margin
- EBIT / EBIT margin
- Net profit
- CFO
- Capex / Capex-to-Revenue
- FCF / FCF margin

Các số này **không thay thế** câu hỏi Shearn “How does the business make money?”. Chúng chỉ cung cấp financial economics context; payer, volume driver, price driver, segment economics và major costs vẫn phải được xác minh từ business disclosure.

## Evidence Agent Chương 2 — source-first

`SourceFirstChapter2EvidenceAgent` mở rộng evidence layer chung của Trecapital theo nguyên tắc **source-first**. Mục tiêu là tránh tình trạng chỉ có link nguồn/search placeholder nhưng không có nội dung đủ để trả lời Q3–Q6.

Engine thực hiện theo tầng:

1. tái sử dụng search/evidence plumbing của Trecapital;
2. chạy đầy đủ 5 nhóm truy vấn riêng của Chương 2, thay vì chỉ hai truy vấn đầu của helper chung;
3. ưu tiên fetch trực tiếp website/IR chính thức của doanh nghiệp khi đã có source mapping đáng tin cậy;
4. khi Q6 vẫn thiếu evidence, có thể đọc và cache text từ BCTN/PDF chính thức đã map cho ticker;
5. lưu **final evidence rows** vào cache để lần chạy offline/restart vẫn dùng lại được evidence đã thu thập.

Năm nhóm truy vấn Chương 2:

1. sản phẩm/dịch vụ, segment, phân phối, nhà máy/quy trình;
2. doanh thu/cơ cấu doanh thu, sản lượng, giá bán, chi phí, khách hàng;
3. lịch sử, thành lập, M&A, mở rộng, công suất, dự án;
4. xuất khẩu, international/foreign market/geography;
5. USD/EUR/CNY/JPY, tỷ giá, ngoại tệ, hedging.

Evidence được lưu trong Trecapital `raw/internet_evidence/<TICKER>/...`. PDF/text chính thức được cache riêng dưới `raw/chapter2_official/<TICKER>/...` khi cần.

## Q3 — Business Operations assistant

Assistant phân loại evidence candidate liên quan:

- product/service;
- business segment;
- manufacturing/service process;
- distribution;
- customer;
- regulation.

Nó tạo một **evidence draft** để analyst chuyển thành `Business Flow`.

Không tự điền:

- `Own Words`;
- `Analogy`;
- `World Without`.

Lý do: mục tiêu phương pháp của Shearn là kiểm tra chính analyst có thể diễn đạt business bằng lời của mình hay không.

## Q5 — Business Evolution assistant

Từ evidence có năm và keyword phù hợp, app tạo `timeline candidates` gồm:

- Year;
- Event;
- Type;
- Evidence.

Các field `Why it happened` và `Impact` để trống cho analyst đánh giá.

Không tự điền `Skill vs Luck`.

Event types là Trecapital implementation layer:

- Founding
- New Product
- New Capacity
- M&A
- Geography
- Business-model Change
- Regulatory Turning Point
- Other

## Q6 — Foreign Markets & Currency evidence

Assistant tìm candidate country/region từ evidence và chỉ điền các trường có evidence rõ:

- Country / Region;
- **Exposure type**;
- Entry year nếu có pattern `since/từ năm/bắt đầu từ ...`;
- Revenue share % chỉ khi snippet đồng thời có keyword revenue/export và tỷ lệ % rõ;
- Evidence URL/title.

`Exposure type` phân biệt ba trường hợp:

- `Thị trường xuất khẩu`;
- `Hiện diện/hoạt động trực tiếp` — ví dụ công ty con, nhà máy, văn phòng;
- `Thị trường nước ngoài — cần xác minh loại exposure`.

Điều này đặc biệt quan trọng: **thị trường xuất khẩu không đồng nghĩa doanh nghiệp có hoạt động trực tiếp ở quốc gia đó**. App không được suy diễn export market thành foreign subsidiary/plant/office.

Không tự phân bổ geographic revenue nếu công ty không disclosure.

**Guardrail địa lý:** tên quốc gia/khu vực được match theo ranh giới từ, không dùng substring thô. Điều này tránh false positive kiểu alias `Ấn Độ / an do` bị ghép nhầm qua hai từ liền nhau trong câu `Thái Lan doanh thu...`. Nếu một evidence cùng lúc nhắc nhiều thị trường, app không gán bừa `Entry year` hay `Revenue share %` cho từng nước.

Currency evidence hiện chỉ nhận diện đồng tiền được đề cập trong source (USD/EUR/CNY/JPY/KRW/VND) và hiển thị evidence candidate. App **không tự suy diễn** net FX exposure, hedge effectiveness hoặc natural hedge.

## Analyst-controlled Apply Draft

Page có nút:

`🧩 Điền các ô trống bằng Research Assistant Draft`

Quy tắc merge:

- chỉ điền field đang trống;
- không ghi đè bất kỳ field analyst đã lưu;
- Q1 và Q2 không được tự điền;
- Q3 `own_words` không được tự điền;
- Q5 `skill_vs_luck` không được tự điền;
- lưu provenance của draft vào payload.

Sau khi apply, analyst phải review/chỉnh sửa và bấm `Lưu Chương 2` để xác nhận nội dung workspace.

## Files

- `pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py` — unified deep-analysis page / chapter tabs.
- `modules/deep_company_analysis/chapter2.py` — analyst workspace / SQLite persistence.
- `modules/deep_company_analysis/chapter2_auto.py` — canonical financial context + evidence classification/extraction + non-overwrite merge.
- `modules/deep_company_analysis/chapter2_evidence.py` — source-first evidence engine, official HTML/PDF cache.
- `modules/deep_company_analysis/chapter2_page_support.py` — reusable Chapter 2 tab/data/evidence bridge.
- `modules/deep_company_analysis/test_chapter2_auto.py` — Phase 2B regression/guardrails.
- `modules/deep_company_analysis/test_chapter2_evidence.py` — official-source extraction and geography guardrails.
- `tools/dgc_chapter2_e2e.py` — live DGC end-to-end diagnostic.

## Acceptance criteria Phase 2B / pre-lock

- Page vẫn chạy khi không có Internet nếu đã có local data/evidence cache.
- Không có parallel financial source.
- Q4 financial metrics lấy từ canonical Trecapital bundle.
- Evidence có source URL/title.
- Source-first engine phải chạy đủ evidence query groups cần cho Q3–Q6.
- Timeline chỉ tạo candidate có năm từ evidence.
- Geographic revenue share không được bịa/suy phân bổ.
- Export market không được trình bày như direct foreign operation.
- Country aliases không được false-positive do substring xuyên ranh giới từ.
- Apply Draft không ghi đè analyst content.
- `own_words`, `skill_vs_luck`, Q1 và Q2 không được auto-fill.
- Full Chapter 1 regression vẫn pass.
- Chapter 2 Phase 2A regression vẫn pass.
- Chạy live DGC end-to-end và công bố rõ phần nào auto-fill được / phần nào vẫn là research gap trước khi khóa Chương 2.
