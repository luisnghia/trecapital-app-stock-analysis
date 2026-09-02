# Chapter 2 Phase 2B — Trecapital Data & Evidence Bridge

## Mục tiêu

Nối Chương 2 — *Understanding the Business: The Basics* với Trecapital canonical financial data và evidence layer, nhưng giữ nguyên nguyên tắc:

- **AI/Data = Research Assistant; user = Investment Analyst.**
- Không ghi đè nội dung analyst đã lưu.
- Không tự viết thay phần `Explain it in your own words` của Q3.
- Không tự kết luận `Skill vs Luck` của Q5.
- Không tự quyết định Q1 Research Interest / Circle of Competence hoặc Q2 CEO Lens.
- Không tạo BUY/HOLD/SELL và không thay Research Gate của Chương 1.

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

## Evidence Agent Chương 2

`Chapter2EvidenceAgent` tái sử dụng `adapters.module2_web_research.WebEvidenceAgent` và tìm evidence theo 5 nhóm truy vấn:

1. sản phẩm/dịch vụ, segment, phân phối, nhà máy/quy trình;
2. doanh thu/cơ cấu doanh thu, sản lượng, giá bán, chi phí, khách hàng;
3. lịch sử, thành lập, M&A, mở rộng, công suất, dự án;
4. xuất khẩu, international/foreign market/geography;
5. USD/EUR/CNY/JPY, tỷ giá, ngoại tệ, hedging.

Evidence được lưu lại trong Trecapital `raw/internet_evidence/<TICKER>/...` và có thể được dùng lại khi chạy local/offline mà không phải tìm lại ngay.

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
- Entry year nếu có pattern `since/từ năm/bắt đầu từ ...`;
- Revenue share % chỉ khi snippet đồng thời có keyword revenue/export và tỷ lệ % rõ;
- Evidence URL/title.

Không tự phân bổ geographic revenue nếu công ty không disclosure.

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

- `modules/deep_company_analysis/chapter2.py` — analyst workspace / SQLite persistence.
- `modules/deep_company_analysis/chapter2_auto.py` — canonical financial context + evidence classification/extraction + non-overwrite merge.
- `pages/08_Phan_tich_chuyen_sau_Chuong_2.py` — data/evidence refresh + Research Assistant panel + Chapter 2 workspace.
- `modules/deep_company_analysis/test_chapter2_auto.py` — regression/guardrail tests Phase 2B.

## Acceptance criteria Phase 2B

- Page vẫn chạy khi không có Internet nếu đã có local data/evidence cache.
- Không có parallel financial source.
- Q4 financial metrics lấy từ canonical Trecapital bundle.
- Evidence có source URL/title.
- Timeline chỉ tạo candidate có năm từ evidence.
- Geographic revenue share không được bịa/suy phân bổ.
- Apply Draft không ghi đè analyst content.
- `own_words`, `skill_vs_luck`, Q1 và Q2 không được auto-fill.
- Full Chapter 1 regression vẫn pass.
- Chapter 2 Phase 2A regression vẫn pass.
