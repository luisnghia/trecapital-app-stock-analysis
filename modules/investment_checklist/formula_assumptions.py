from __future__ import annotations

"""Formula/assumption registry for the Investment Research & Checklist System.

The registry separates three things that must not be silently mixed:
- SOURCE: directly supported by Michael Shearn / project source documents;
- TREC CAPITAL IMPLEMENTATION: a transparent calculation/bridge rule used by this app;
- ANALYST ASSUMPTION: an input that the source does not lock to one universal number.

Keep this file synchronized with the formulas used in ``services/formulas.py`` and
``trecapital_bridge.py``. It is intentionally human-readable because the project rules require a
formula explanation file for every app module.
"""

FORMULA_ROWS = [
    {
        "Nhóm": "Table 1.1",
        "Chỉ tiêu": "Quality tally",
        "Công thức/logic": "Tổng số tiêu chí được analyst đánh dấu ✓ Có trong 10 tiêu chí Table 1.1.",
        "Giả định / giới hạn": "Không phải BUY/SELL score. — Chưa biết không được đổi thành Không; N/A là phần mở rộng workflow của app.",
        "Nguồn": "Shearn Table 1.1 + Trecapital workflow",
    },
    {
        "Nhóm": "Research workflow",
        "Chỉ tiêu": "Research Completion",
        "Công thức/logic": "Answered / (59 − N/A).",
        "Giả định / giới hạn": "Research Gap và Needs Review không được tính là Answered. Đây là metric tiến độ nghiên cứu của app, không phải điểm chất lượng đầu tư trong sách.",
        "Nguồn": "Trecapital implementation",
    },
    {
        "Nhóm": "Research workflow",
        "Chỉ tiêu": "Assessment",
        "Công thức/logic": "Analyst chọn −2, −1, 0, +1, +2 cho trạng thái Answered/Needs Review.",
        "Giả định / giới hạn": "Unknown/Research Gap/N/A không có numeric assessment. AI không được ghi đè assessment analyst.",
        "Nguồn": "Trecapital analyst overlay",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "TEV",
        "Công thức/logic": "TEV = Market Cap + Interest-bearing Debt − Cash & Cash Equivalents − Short-term Investments.",
        "Giả định / giới hạn": "Nếu nợ vay không xác định thì TEV để trống; không coi nợ vay tổng hợp = 0 là doanh nghiệp không nợ khi thiếu cấu phần.",
        "Nguồn": "Shearn Table 1.2 + Trecapital Data Layer",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "TEV / EBIT",
        "Công thức/logic": "TEV ÷ EBIT.",
        "Giả định / giới hạn": "EBIT ưu tiên dữ liệu trực tiếp; fallback = Gross Profit − |Selling Expense| − |Admin Expense|; cuối cùng mới dùng Pre-tax Profit + |Interest Expense| và phải ghi rõ proxy. EBIT ≤ 0 ⇒ multiple không có ý nghĩa định giá chuẩn.",
        "Nguồn": "Shearn Table 1.2 + Trecapital bridge",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "TEV / EBITDA",
        "Công thức/logic": "TEV ÷ EBITDA.",
        "Giả định / giới hạn": "EBITDA ưu tiên dữ liệu trực tiếp; fallback = EBIT + |D&A|. EBITDA ≤ 0 ⇒ multiple không có ý nghĩa định giá chuẩn.",
        "Nguồn": "Shearn Table 1.2 + Trecapital bridge",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "Normalized Earnings",
        "Công thức/logic": "Ưu tiên normalized pre-tax earnings do analyst/engine cung cấp đúng cùng kỳ. Nếu chưa có, TTM pre-tax profit chỉ là baseline proxy và phải được gắn nhãn proxy.",
        "Giả định / giới hạn": "Không có cửa sổ chuẩn hóa chu kỳ cố định trong bộ nguồn. Với cyclical, raw TTM pre-tax không được coi là normalized earnings để ra point metric.",
        "Nguồn": "Shearn Ch.6 + project valuation source",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "TEV / Normalized Earnings",
        "Công thức/logic": "TEV ÷ Normalized Earnings.",
        "Giả định / giới hạn": "Chỉ tính khi normalized earnings cùng kỳ hợp lệ và dương; không dùng normalized value của năm cũ để hợp thức hóa raw TTM.",
        "Nguồn": "Shearn Table 1.2 + Trecapital period policy",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "Pre-tax Earnings Yield",
        "Công thức/logic": "EBIT ÷ TEV.",
        "Giả định / giới hạn": "Đối chiếu trực tiếp Bảng 1.2: WU TEV/EBIT 10.1x ↔ 9.9%; WFM 19.1x ↔ 5.2%; Dell 6.0x ↔ 16.8%. Vì vậy đây là nghịch đảo TEV/EBIT, không phải Normalized Earnings/TEV.",
        "Nguồn": "Shearn Table 1.2 — verified from published example values",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "Debt / EBITDA",
        "Công thức/logic": "Interest-bearing Debt ÷ EBITDA.",
        "Giả định / giới hạn": "EBITDA ≤ 0 ⇒ leverage multiple không có ý nghĩa chuẩn. Theo dõi xu hướng 10 năm + TTM; một snapshot đơn lẻ không đủ để kết luận sức khỏe bảng cân đối.",
        "Nguồn": "Shearn Table 1.2; Ch.5 balance-sheet analysis",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "EBIT / Interest Expense",
        "Công thức/logic": "EBIT ÷ |Interest Expense|.",
        "Giả định / giới hạn": "Không dùng toàn bộ Financial Expense làm interest expense nếu nguồn chưa tách lãi vay. EBIT âm được giữ như tín hiệu không đủ coverage.",
        "Nguồn": "Shearn Table 1.2 + Trecapital bridge",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "FCF",
        "Công thức/logic": "FCF = CFO − |Capex|.",
        "Giả định / giới hạn": "Nếu nguồn đã có FCF trực tiếp thì ưu tiên giá trị chuẩn hóa; total capex không đồng nghĩa maintenance capex.",
        "Nguồn": "Project FCF/Owner Earnings sources",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "FCF Yield EV",
        "Công thức/logic": "FCF ÷ TEV.",
        "Giả định / giới hạn": "Nếu TEV không xác định thì để trống; FCF âm vẫn giữ để thể hiện cash burn.",
        "Nguồn": "Shearn Table 1.2",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "FCF Yield Market",
        "Công thức/logic": "FCF ÷ Market Cap.",
        "Giả định / giới hạn": "Market Cap phải đồng bộ Giá × cổ phiếu lưu hành; mismatch vật chất phải được cảnh báo/reconcile.",
        "Nguồn": "Shearn Table 1.2 + Trecapital bridge",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "Dividend Yield",
        "Công thức/logic": "Dividend per Share ÷ Market Price.",
        "Giả định / giới hạn": "Dividend/share có thể suy ra từ cash dividend / shares khi cùng kỳ và cùng đơn vị.",
        "Nguồn": "Shearn Table 1.2",
    },
    {
        "Nhóm": "Table 1.2",
        "Chỉ tiêu": "Stock Price vs Target",
        "Công thức/logic": "Market Price ÷ Target Price.",
        "Giả định / giới hạn": "Target lấy từ Module 2 hiện tại; target lịch sử không được hồi tố vào snapshot cũ.",
        "Nguồn": "Shearn Table 1.2 + Module 2 integration",
    },
    {
        "Nhóm": "Valuation integration",
        "Chỉ tiêu": "MOS",
        "Công thức/logic": "MOS = (Target Price − Market Price) ÷ Target Price.",
        "Giả định / giới hạn": "Ngưỡng MOS hành động không được khóa cứng nếu bộ nguồn không quy định; Module 2 quản lý giả định MOS và Checklist chỉ nhận kết quả đồng bộ.",
        "Nguồn": "Project valuation source + Module 2",
    },
    {
        "Nhóm": "Operating efficiency",
        "Chỉ tiêu": "CCC",
        "Công thức/logic": "CCC = DIO + DSO − DPO; DIO = Avg Inventory/COGS×365; DSO = Avg AR/Revenue×365; DPO = Avg AP/COGS×365.",
        "Giả định / giới hạn": "Ưu tiên CCC/DSO/DIO/DPO trực tiếp; proxy chỉ tính khi có số dư bình quân kỳ hiện tại và kỳ trước.",
        "Nguồn": "Shearn Q31/Table 6.6 + Trecapital bridge",
    },
    {
        "Nhóm": "Period normalization",
        "Chỉ tiêu": "TTM",
        "Công thức/logic": "Flow items = tổng 4 quý gần nhất; balance-sheet items = quý gần nhất; denominator bình quân dùng trailing-quarter average khi thích hợp.",
        "Giả định / giới hạn": "Không cộng các số dư cuối kỳ. TTM luôn hiển thị trước lịch sử năm/review trong Opportunity Inventory.",
        "Nguồn": "Trecapital Data Layer implementation",
    },
]

EVALUATION_RULES = [
    "Table 1.1 tally chỉ là screening/filter; không tự biến thành khuyến nghị mua/bán.",
    "59 câu hỏi là research framework. Numeric Assessment là lớp analyst của Trecapital, không phải điểm do Michael Shearn quy định.",
    "Unknown/Research Gap khác Neutral. Không dữ liệu không được tự điền 0 hoặc đánh giá trung tính.",
    "Tỷ lệ chỉ dùng khi mẫu số có ý nghĩa kinh tế: CFO/FCF/OE trên LNST chỉ khi LNST > 0; Capex/CFO chỉ khi CFO > 0; Debt/EBITDA chỉ khi EBITDA > 0. Âm chia âm không được biến thành tín hiệu tốt.",
    "Cyclical có phân phối earnings rộng: raw TTM earnings không được coi là normalized earnings để tạo point valuation metric nếu chưa có chuẩn hóa/scenario.",
    "Bank/Insurance/Securities có BCTC đặc thù: TEV/EBITDA/FCF kiểu doanh nghiệp công nghiệp không được dùng làm kết luận chính nếu không phù hợp bản chất ngành.",
    "Mọi manual override và review change phải có reason; completed review chỉ thay đổi qua review mới, ngoại trừ chức năng admin xóa thủ công có xác nhận riêng.",
    "Snapshot lịch sử không bị source data hiện tại ghi đè; target/MOS lịch sử không hồi tố.",
]

SOURCE_NOTES = [
    "Michael Shearn, The Investment Checklist: Table 1.1 dùng 10 tiêu chí để tally/filter; Table 1.2 là inventory/watchlist với TEV/EBIT, TEV/EBITDA, TEV/Normalized Earnings, pre-tax yield, leverage/coverage, FCF/dividend yield, price/target.",
    "Đối chiếu số liệu chính Bảng 1.2 xác nhận Pre-Tax Earnings Yield = EBIT/TEV: 10.1x ↔ 9.9%, 19.1x ↔ 5.2%, 6.0x ↔ 16.8%.",
    "Shearn nhấn mạnh true operating earnings và việc điều chỉnh accounting/one-off; với phân phối earnings rộng như cyclical nên dùng scenario analysis thay vì tin vào một point estimate.",
    "Quy định Trecapital: công thức phải bám nguồn; dữ liệu thiếu không bịa; module dùng chung Data Layer; bảng tỷ đồng 0 số thập phân, %/hệ số 1 số thập phân; âm đỏ, dương xanh; phải có formula/audit explanation.",
]

GLOSSARY = [
    {"Thuật ngữ": "TEV / EV", "Diễn giải": "Total Enterprise Value / Enterprise Value — giá trị doanh nghiệp dành cho cả chủ nợ và cổ đông sau khi điều chỉnh tiền mặt/tài sản tài chính ngắn hạn."},
    {"Thuật ngữ": "EBIT", "Diễn giải": "Earnings Before Interest and Taxes — lợi nhuận trước lãi vay và thuế; dùng làm proxy lợi nhuận hoạt động trước cấu trúc tài trợ."},
    {"Thuật ngữ": "EBITDA", "Diễn giải": "EBIT trước khấu hao và phân bổ; hữu ích cho so sánh vận hành nhưng không thay thế FCF/Owner Earnings."},
    {"Thuật ngữ": "FCF", "Diễn giải": "Free Cash Flow — dòng tiền tự do; trong module cơ sở là CFO trừ Capex."},
    {"Thuật ngữ": "CFO", "Diễn giải": "Cash Flow from Operations — dòng tiền từ hoạt động kinh doanh."},
    {"Thuật ngữ": "Capex", "Diễn giải": "Capital Expenditure — chi tiêu vốn. Total Capex không đồng nghĩa maintenance capex."},
    {"Thuật ngữ": "CCC", "Diễn giải": "Cash Conversion Cycle = DIO + DSO − DPO; số ngày vốn bị khóa trong chu kỳ vận hành."},
    {"Thuật ngữ": "DIO", "Diễn giải": "Days Inventory Outstanding — số ngày tồn kho bình quân."},
    {"Thuật ngữ": "DSO", "Diễn giải": "Days Sales Outstanding — số ngày phải thu bình quân."},
    {"Thuật ngữ": "DPO", "Diễn giải": "Days Payables Outstanding — số ngày phải trả bình quân."},
    {"Thuật ngữ": "MOS", "Diễn giải": "Margin of Safety — biên an toàn giữa giá trị mục tiêu/nội tại và giá thị trường; ngưỡng hành động phụ thuộc phương pháp/giả định Module 2."},
    {"Thuật ngữ": "TTM / T12M", "Diễn giải": "Trailing Twelve Months — 12 tháng gần nhất. Flow = tổng 4 quý; balance = số dư quý gần nhất."},
    {"Thuật ngữ": "Normalized Earnings", "Diễn giải": "Lợi nhuận đã điều chỉnh để phản ánh earning power bình thường hơn, loại/điều chỉnh one-off hoặc ảnh hưởng chu kỳ khi có căn cứ."},
    {"Thuật ngữ": "Research Gap", "Diễn giải": "Khoảng trống nghiên cứu: chưa có đủ bằng chứng để trả lời; không đồng nghĩa Neutral và không được tự cho điểm 0."},
]
