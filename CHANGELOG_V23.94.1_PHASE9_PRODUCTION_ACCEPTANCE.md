# V23.94.1 — Phase 9 Production Acceptance hotfix

- Đối chiếu payload thật của 9 driver không cần API key từ IMF DataMapper và World Bank WDI.
- Thay series IMF đã ngừng trả dữ liệu `GGX_NGDP` bằng `G_X_G01_GDP_PT` (Government Expenditure, Fiscal Monitor) cho driver `gov_spending`.
- Giữ guardrail: chi tiêu Chính phủ từ IMF chỉ là proxy, không tự chấm điểm và phải được analyst đối chiếu giải ngân thực tế.
- Bổ sung regression test khóa series mới, kỳ dữ liệu và nguyên tắc suggestion không có điểm tự động.
