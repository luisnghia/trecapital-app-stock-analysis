from __future__ import annotations

"""Formula registry for Investment Checklist Phase 2 quantitative tools.

`Nguồn` distinguishes Shearn-source logic from Trecapital implementation/extensions. These rows are
for audit/explanation; the executable formulas live in quantitative_tools.py and are protected by tests.
"""

PHASE2_FORMULA_ROWS = [
    {
        "Tool": "Balance Sheet & Leverage",
        "Chỉ tiêu": "Net Debt",
        "Công thức / logic": "Interest-bearing Debt − Cash & Short-term Investments.",
        "Giả định / giới hạn": "Debt thiếu cấu phần ⇒ Unknown, không thay bằng 0. Không dùng tổng liabilities làm debt.",
        "Nguồn": "Shearn Ch.5 + Trecapital Data Layer",
    },
    {
        "Tool": "Balance Sheet & Leverage",
        "Chỉ tiêu": "Debt / EBITDA",
        "Công thức / logic": "Interest-bearing Debt ÷ EBITDA.",
        "Giả định / giới hạn": "EBITDA ≤ 0 ⇒ không hiển thị leverage multiple chuẩn.",
        "Nguồn": "Shearn Table 5.1–5.2 / Table 1.2 context",
    },
    {
        "Tool": "Balance Sheet & Leverage",
        "Chỉ tiêu": "EBIT / Interest",
        "Công thức / logic": "EBIT ÷ |Interest Expense|.",
        "Giả định / giới hạn": "Chỉ dùng interest expense/interest paid/borrowing cost đã tách; không lấy toàn bộ financial expense.",
        "Nguồn": "Shearn leverage/coverage analysis + Trecapital implementation",
    },
    {
        "Tool": "ROIC Quality",
        "Chỉ tiêu": "ROIC Trecapital",
        "Công thức / logic": "Consume trực tiếp roic_standard_pct/roic_pct từ Trecapital Data Layer.",
        "Giả định / giới hạn": "Đây là standardized metric và là Single Source of Truth; Checklist không âm thầm tính ROIC chuẩn thứ hai.",
        "Nguồn": "Trecapital Data Layer",
    },
    {
        "Tool": "ROIC Quality",
        "Chỉ tiêu": "ROIC Shearn – Ex Cash",
        "Công thức / logic": "NOPAT ÷ Average standardized invested-capital base (ex cash).",
        "Giả định / giới hạn": "Analytical variant; investment base bình quân hai kỳ khi có dữ liệu.",
        "Nguồn": "Shearn Table 5.3 + Trecapital analytical view",
    },
    {
        "Tool": "ROIC Quality",
        "Chỉ tiêu": "ROIC Shearn – Incl Cash",
        "Công thức / logic": "NOPAT ÷ Average (invested-capital base + cash/ST investments).",
        "Giả định / giới hạn": "Dùng để nhìn distortion do excess cash; không thay ROIC chuẩn.",
        "Nguồn": "Shearn Table 5.3",
    },
    {
        "Tool": "ROIC Quality",
        "Chỉ tiêu": "ROIC Shearn – Ex Goodwill",
        "Công thức / logic": "NOPAT ÷ Average (invested-capital base − goodwill/intangibles) khi field có dữ liệu.",
        "Giả định / giới hạn": "Loại goodwill có thể che việc management overpay M&A; analyst phải xem cả hai view.",
        "Nguồn": "Shearn Ch.5 / Table 5.3–5.4 discussion",
    },
    {
        "Tool": "Accounting Reserve Quality",
        "Chỉ tiêu": "CFO / Net Income",
        "Công thức / logic": "CFO ÷ Net Income.",
        "Giả định / giới hạn": "Evidence chất lượng earnings, không phải fraud score. Net income ≤ 0 ⇒ ratio chuẩn để trống.",
        "Nguồn": "Shearn earnings-quality context + Trecapital implementation",
    },
    {
        "Tool": "Accounting Reserve Quality",
        "Chỉ tiêu": "Provision / Actual charge-off",
        "Công thức / logic": "Provision ÷ actual charge-off/write-off khi cả hai line-item tồn tại.",
        "Giả định / giới hạn": "Không có line-item ⇒ để trống. Không tính lại Beneish M-Score trong Checklist.",
        "Nguồn": "Shearn Tables 6.1–6.2",
    },
    {
        "Tool": "Operating Leverage",
        "Chỉ tiêu": "Degree of Operating Leverage (DOL)",
        "Công thức / logic": "%Δ EBIT ÷ %Δ Revenue.",
        "Giả định / giới hạn": "Bỏ quan sát khi |ΔRevenue| < 1% hoặc prior EBIT ≤ 0 để tránh ratio bùng nổ/méo.",
        "Nguồn": "Shearn Table 6.3 / Ch.6",
    },
    {
        "Tool": "Operating Leverage",
        "Chỉ tiêu": "Revenue stress",
        "Công thức / logic": "EBIT change ≈ median recent valid DOL × Revenue shock; scenarios −5%, −10%, −20%.",
        "Giả định / giới hạn": "Scenario sensitivity, không phải forecast và không phải bảng gốc của Shearn.",
        "Nguồn": "Trecapital extension based on Shearn DOL",
    },
    {
        "Tool": "Working Capital / CCC",
        "Chỉ tiêu": "DSO / DIO / DPO / CCC",
        "Công thức / logic": "DSO=Avg AR/Revenue×365; DIO=Avg Inventory/COGS×365; DPO=Avg AP/COGS×365; CCC=DIO+DSO−DPO.",
        "Giả định / giới hạn": "Ưu tiên metric trực tiếp của Trecapital; proxy dùng số dư bình quân hai kỳ. CCC thấp không tự động = tốt.",
        "Nguồn": "Shearn Table 6.6 + project specification",
    },
    {
        "Tool": "Working Capital / CCC",
        "Chỉ tiêu": "Cash released/(absorbed)",
        "Công thức / logic": "−Δ Operating WC, với Operating WC = AR + Inventory − AP.",
        "Giả định / giới hạn": "Proxy tập trung working-capital vận hành; analyst phải xem các khoản operating WC đặc thù khác nếu trọng yếu.",
        "Nguồn": "Trecapital implementation supporting Shearn Q31",
    },
    {
        "Tool": "Maintenance Capex Context",
        "Chỉ tiêu": "D&A rough proxy",
        "Công thức / logic": "Nếu chưa xác định maintenance capex, depreciation chỉ được hiển thị như rough approximation.",
        "Giả định / giới hạn": "Không đổi nhãn D&A thành maintenance capex. Nếu Trecapital có maintenance_capex_bil thì hiển thị riêng.",
        "Nguồn": "Shearn Key Points Ch.6",
    },
    {
        "Tool": "Buyback & Dilution",
        "Chỉ tiêu": "Net share reduction",
        "Công thức / logic": "Prior-period shares outstanding − current-period shares outstanding.",
        "Giả định / giới hạn": "Đo thay đổi số CP thực tế; không khẳng định toàn bộ thay đổi đến từ buyback nếu thiếu thuyết minh.",
        "Nguồn": "Shearn Table 8.2 + Trecapital implementation",
    },
    {
        "Tool": "Buyback & Dilution",
        "Chỉ tiêu": "Net buyback after dilution",
        "Công thức / logic": "Gross shares repurchased − shares issued/ESOP/options.",
        "Giả định / giới hạn": "Chỉ tính khi Data Layer có cả hai line-item; thiếu ⇒ Unknown, không giả định 0.",
        "Nguồn": "Shearn Tables 8.2–8.3",
    },
    {
        "Tool": "Buyback & Dilution",
        "Chỉ tiêu": "EPS without share-count change",
        "Công thức / logic": "Current Net Income × 1,000 ÷ prior-period shares outstanding (triệu cp).",
        "Giả định / giới hạn": "Analytical proxy để cô lập share-count effect; không phải reported EPS.",
        "Nguồn": "Shearn Table 8.2 methodology + Trecapital implementation",
    },
    {
        "Tool": "Operating Driver → EPS",
        "Chỉ tiêu": "Driver/EPS divergence",
        "Công thức / logic": "So sánh YoY operating-driver growth với EPS growth; flag khi hai hướng phân kỳ.",
        "Giả định / giới hạn": "Flag chỉ yêu cầu điều tra nguyên nhân; không tự đánh giá tốt/xấu. Driver theo ngành sẽ được nâng cấp ở Phase 3.",
        "Nguồn": "Shearn Table 10.1 + Trecapital implementation",
    },
]
