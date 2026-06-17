# V23.66 - Formula source audit fixes & remove vnstock KBS/VCI options

## Công thức cập nhật theo audit lý thuyết

1. **Operating Working Capital**
   - Cũ: Current Assets - Cash - Short-term Investments - Current Liabilities.
   - Mới: Current Assets - Cash - Short-term Investments - (Current Liabilities - Short-term Debt - Current Portion of Long-term Debt).
   - Lý do: working capital vận hành phải loại cash, investments và debt.

2. **Li Lu Deployed Capital**
   - Mẫu số ROIC Li Lu dùng operating working capital đã loại debt + fixed assets.
   - Tránh làm ROIC bị sai khi nợ ngắn hạn có vay tài chính.

3. **ROCE riêng**
   - Thêm `roce_pct = core_operating_profit_bil / capital_employed_bil * 100`.
   - `capital_employed_bil = total_assets_bil - current_liabilities_bil`.

4. **Beneish TATA**
   - Ưu tiên balance-sheet accruals: `ΔCA - ΔCash - ΔCL + ΔShort-term debt - Depreciation`.
   - Nếu thiếu dữ liệu thì fallback `LNST - CFO` và ghi rõ proxy.

## Module 2 data source

- Bỏ hoàn toàn option **Online vnstock/KBS** và **Online vnstock/VCI** khỏi Module 2 và Báo cáo tổng hợp.
- Gỡ nhánh xử lý, cache function, import provider và requirement `vnstock`.

## Không thay đổi

- Không đổi cấu trúc tab, layout, CSS chính, format bảng và flow sử dụng app.
