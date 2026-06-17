# V23.15 - Sửa WACC, note giải thích và màu tín hiệu

## 1. WACC doanh nghiệp

App luôn tự tính lại WACC theo từng kỳ, không giữ giá trị WACC cũ từ nguồn nếu công thức không đồng nhất.

Công thức:

```text
WACC = We × Ke + Wd × Kd × (1 - Tax Rate)
```

Trong đó:

```text
E = Giá trị vốn hóa thị trường. Ưu tiên market_cap_bil; nếu thiếu dùng số cổ phiếu × giá / 1.000; nếu vẫn thiếu dùng vốn chủ sở hữu làm proxy.
D = Nợ vay chịu lãi gộp. Ưu tiên interest_bearing_debt_bil; nếu thiếu cộng vay ngắn hạn + vay dài hạn + trái phiếu + thuê tài chính.
We = E / (E + D)
Wd = D / (E + D)
Kd = Chi phí lãi vay / Nợ vay chịu lãi bình quân. Ưu tiên interest_paid_bil hoặc interest_expense_bil; financial_expense_bil chỉ là fallback.
Ke = Lãi suất phi rủi ro + Beta × phần bù rủi ro thị trường. Beta ưu tiên nguồn thị trường; nếu thiếu dùng beta proxy theo biến động lợi nhuận, doanh thu và đòn bẩy.
Tax Rate = Chi phí thuế / LNTT, chặn 0%-35% để loại bỏ kỳ bất thường.
```

Các cột kiểm tra bổ sung trong tab ROIC & đầu tư: `equity_weight_pct`, `debt_weight_pct`, `after_tax_cost_of_debt_pct`, `beta_source`, `wacc_quality`, `wacc_formula_detail`.

## 2. Note giải thích

Note của bảng MOS/scorecard/moat/chuỗi giá trị bổ sung:

- chỉ tiêu nào làm tăng/giảm điểm;
- điểm đạt trên trọng số;
- tỷ lệ đạt;
- ngưỡng đọc Tốt/Theo dõi/Cảnh báo;
- số liệu chính của doanh nghiệp đang phân tích.

## 3. Màu tín hiệu

- Cảnh báo/rủi ro/chưa đạt/yếu: đỏ nhạt, mức nghiêm trọng đỏ đậm hơn.
- Tốt/đạt/mạnh/an toàn: tím nhạt.
- Theo dõi/cần kiểm tra/chưa rõ/trung bình: vàng.

Áp dụng cho các cột `Tín hiệu`, `Mức độ`, `Tình trạng`, `Khuyến nghị`, `Kết luận`.
