from __future__ import annotations

"""Source-table guidance for Chapters 5–10 of Michael Shearn's Investment Checklist.

The text is deliberately paraphrased. It is static application guidance and never changes analyst
assessments. There is no invented Table 9.x: Chapter 9 in the book is handled by Q48–Q52 rather
than a numbered source table in the table set used by this module.
"""

from typing import Any


SOURCE_TABLE_ORDER = (
    "5.1", "5.2", "5.3", "5.4",
    "6.1", "6.2", "6.3", "6.4", "6.5", "6.6",
    "7.1",
    "8.1", "8.2", "8.3",
    "10.1",
)

PHASE2_TABLE_GROUPS = {
    "5.1": ("5.1", "5.2"),
    "5.3": ("5.3", "5.4"),
    "6.1": ("6.1", "6.2"),
    "6.3": ("6.3", "6.4", "6.5"),
    "6.6": ("6.6",),
    "8.2": ("8.2", "8.3"),
    "10.1": ("10.1",),
}


def _spec(title: str, objective: str, how_to_read: tuple[str, ...], checks: tuple[str, ...], caution: str, mapping: str) -> dict[str, Any]:
    return {
        "title": title,
        "objective": objective,
        "how_to_read": how_to_read,
        "checks": checks,
        "caution": caution,
        "mapping": mapping,
    }


SOURCE_TABLE_GUIDANCE: dict[str, dict[str, Any]] = {
    "5.1": _spec(
        "Table 5.1 — EBITDA / Interest Expense Ratios",
        "Dùng coverage ratio như một điểm khởi đầu để hiểu khả năng chịu nợ và mức đệm trước chi phí lãi vay.",
        (
            "Đọc EBITDA/Interest theo nhiều kỳ, không chỉ một snapshot quý/năm.",
            "Đặt coverage cạnh độ ổn định cash flow và tính chu kỳ của doanh nghiệp.",
        ),
        (
            "Nếu coverage giảm, xác định do EBITDA suy yếu, lãi suất/nợ tăng hay cả hai.",
            "Kiểm tra maturity, fixed/variable rate, covenant và khả năng refinance.",
        ),
        "Các dải rating trong bảng là ví dụ của Moody's mà Shearn dùng để minh họa; không biến chúng thành ngưỡng 'tốt/xấu' cứng cho mọi ngành.",
        "Balance Sheet & Leverage Analyzer · Q25",
    ),
    "5.2": _spec(
        "Table 5.2 — Debt to EBITDA Ratios",
        "Đánh giá leverage tương đối với earning capacity, nhưng phải đặt ratio vào cấu trúc vốn và chu kỳ kinh doanh.",
        (
            "Theo dõi Debt/EBITDA xuyên chu kỳ và tìm mức xấu nhất chứ không chỉ kỳ hiện tại.",
            "So ratio với khả năng tạo tiền, tài sản bảo đảm và nghĩa vụ ngoài bảng cân đối.",
        ),
        (
            "Phân biệt nợ tăng để đầu tư sinh lời với nợ dùng bù thiếu hụt dòng tiền.",
            "Xem EBITDA có đang ở đỉnh chu kỳ hoặc chứa khoản bất thường làm denominator quá cao hay không.",
        ),
        "Static ratio có thể gây hiểu sai; rating agency chỉ là điểm bắt đầu, không thay cho phân tích doanh nghiệp.",
        "Balance Sheet & Leverage Analyzer · Q25",
    ),
    "5.3": _spec(
        "Table 5.3 — ROIC With Cash vs Excluding Cash",
        "Nhận diện việc excess cash có thể làm ROIC của hoạt động cốt lõi trông thấp hơn thực tế.",
        (
            "Đặt ROIC có cash cạnh ROIC loại excess cash để thấy mức distortion.",
            "Tập trung vào lượng vốn thực sự cần cho hoạt động day-to-day.",
        ),
        (
            "Xác định cash nào thực sự dư thừa, cash nào cần cho vốn lưu động, seasonality hay rủi ro thanh khoản.",
            "Theo dõi ROIC nhiều năm và dùng average investment base khi phù hợp.",
        ),
        "Không mặc định toàn bộ cash là excess cash; loại quá nhiều cash sẽ làm ROIC bị thổi phồng.",
        "ROIC Quality Analyzer · Q26",
    ),
    "5.4": _spec(
        "Table 5.4 — Effect of Depreciation on ROIC",
        "Cho thấy ROIC có thể tăng cơ học khi net book value giảm do depreciation dù earnings không đổi.",
        (
            "So ROIC dùng net assets với góc nhìn gross assets/accumulated depreciation khi tài sản già đi.",
            "Nếu ROIC tăng trong khi earnings trì trệ, kiểm tra denominator có đang co lại hay không.",
        ),
        (
            "Đối chiếu tuổi tài sản, maintenance capex, write-downs và replacement economics.",
            "Cân nhắc goodwill/intangibles và off-balance-sheet obligations theo đặc thù doanh nghiệp.",
        ),
        "Không có một công thức ROIC duy nhất được chấp nhận phổ quát; app phải ghi rõ variant/methodology thay vì âm thầm thay ROIC chuẩn.",
        "ROIC Quality Analyzer · Q26",
    ),
    "6.1": _spec(
        "Table 6.1 — Sysco Allowance for Doubtful Accounts",
        "Kiểm tra mức độ bảo thủ của reserve bằng cách nối provision với charge-offs thực tế qua nhiều kỳ.",
        (
            "So charged-to-expense/provision với customer accounts written off, net of recoveries.",
            "Tìm sự nhất quán giữa reserve estimate và tổn thất thực tế.",
        ),
        (
            "Đọc footnotes về allowance policy và thay đổi assumption.",
            "Xem reserve cùng AR growth, customer credit quality và revenue recognition.",
        ),
        "Provision và charge-off không nhất thiết trùng từng kỳ; trọng tâm là pattern nhiều năm và lý do kinh tế, không phải chênh lệch đơn kỳ.",
        "Accounting Reserve Quality Analyzer · Q27",
    ),
    "6.2": _spec(
        "Table 6.2 — Krispy Kreme Allowance for Doubtful Accounts",
        "Nhận diện khả năng over-reserve/under-reserve được dùng để dịch chuyển earnings giữa các kỳ.",
        (
            "Đặt provision, charge-offs và ending allowance cạnh nhau theo thời gian.",
            "Tìm giai đoạn reserve tăng mạnh nhưng charge-offs không tăng tương ứng, rồi reserve giảm ở các kỳ sau.",
        ),
        (
            "Kiểm tra thay đổi credit terms, acquisition/deconsolidation và reporting policy trước khi kết luận manipulation.",
            "Đối chiếu CFO vs Net Income và các dấu hiệu accounting quality khác.",
        ),
        "Tool này là context cho Q27; không chạy Beneish/M-Score lần thứ hai và không tự kết luận gian lận.",
        "Accounting Reserve Quality Analyzer · Q27",
    ),
    "6.3": _spec(
        "Table 6.3 — Revenue Growth vs EBIT Growth / Operating Leverage",
        "Đo earnings nhạy với thay đổi doanh thu đến mức nào.",
        (
            "So % thay đổi operating income/EBIT với % thay đổi sales/revenue.",
            "DOL cao nghĩa là sai số nhỏ trong forecast doanh thu có thể phóng đại thành sai số lớn ở earnings.",
        ),
        (
            "Quan sát cả up-cycle và down-cycle; DOL từ một cặp năm có thể không đại diện cho cấu trúc dài hạn.",
            "Kết hợp với debt vì operating leverage cao + leverage tài chính cao làm downside lớn hơn.",
        ),
        "DOL là chỉ báo nhạy cảm, không phải hằng số; đừng áp một DOL duy nhất cho mọi scenario.",
        "Operating Leverage & Cost Structure Analyzer · Q29–Q30",
    ),
    "6.4": _spec(
        "Table 6.4 — Southwest Airlines Operating Expenses",
        "Phân rã cost structure để hiểu vì sao doanh nghiệp có operating leverage cao.",
        (
            "Dùng balance sheet để nhận diện asset intensity rồi đọc income statement/MD&A để phân loại fixed, variable và semi-variable.",
            "Xem các khoản như labor contracts, rentals/landing fees, D&A và contractual obligations có tiếp tục tồn tại khi volume giảm không.",
        ),
        (
            "Phân biệt chi phí variable dài hạn nhưng fixed trong ngắn hạn do doanh nghiệp cần thời gian điều chỉnh capacity.",
            "Tìm contractual commitments và union/lease constraints trong notes/MD&A.",
        ),
        "Không tự phân loại fixed/variable chỉ từ tên dòng BCTC; Shearn dựa vào economics và thuyết minh quản trị.",
        "Operating Leverage & Cost Structure Analyzer · Q30",
    ),
    "6.5": _spec(
        "Table 6.5 — Choice Hotels Operating Expenses",
        "Minh họa cấu trúc operating leverage thấp hơn và sự cần thiết phải tách các khoản pass-through/break-even.",
        (
            "Xác định phần chi phí thực sự cần được doanh nghiệp cover để đạt break-even.",
            "Tách khoản marketing/reservation thu từ franchisees và chi lại theo hợp đồng nếu nó không tạo profit/loss kinh tế cho công ty.",
        ),
        (
            "Xem SG&A, leases và advertising theo bản chất kinh tế thay vì nhãn kế toán.",
            "Ước lượng doanh thu có thể giảm bao nhiêu trước khi business chạm break-even, nhưng giữ assumptions minh bạch.",
        ),
        "Pass-through revenue/expense có thể làm quy mô doanh thu/chi phí lớn nhưng không phản ánh operating leverage thực.",
        "Operating Leverage & Cost Structure Analyzer · Q30",
    ),
    "6.6": _spec(
        "Table 6.6 — Cash Conversion Cycle of Different Businesses",
        "Hiểu thời gian cash bị giữ trong operating cycle và quan trọng hơn là nguyên nhân CCC thay đổi.",
        (
            "Theo dõi CCC ít nhất khoảng năm năm và tách DSO, DIO, DPO.",
            "Negative CCC có thể cho thấy supplier/customer funding; CCC rất cao có thể là đặc trưng economics của mô hình.",
        ),
        (
            "Phân biệt cải thiện bền vững với việc tạm kéo dài DPO hoặc liquidate inventory trong khủng hoảng.",
            "Normalize working-capital benefit nếu thay đổi hiện tại khó lặp lại.",
        ),
        "CCC thấp hơn không tự động tốt hơn; nếu supplier buộc điều khoản thanh toán trở lại bình thường, cash-flow benefit có thể đảo chiều.",
        "Working Capital / CCC Analyzer · Q31",
    ),
    "7.1": _spec(
        "Table 7.1 — Lion vs Hyena Management Contrast",
        "Dùng một khung hành vi để suy nghĩ về việc manager xây tổ chức dài hạn hay tối ưu lợi ích/ngắn hạn cho bản thân.",
        (
            "Tìm bằng chứng manager xây team, infrastructure và năng lực bền vững thay vì chỉ tạo kết quả nhanh.",
            "Đánh giá cách manager chia sẻ credit, phát triển người kế cận và hành xử khi điều kiện khó khăn.",
        ),
        (
            "Đối chiếu narrative với tenure, hiring, capital allocation và kết quả qua nhiều chu kỳ.",
            "Ưu tiên hành động quan sát được hơn lời nói hoặc hình ảnh truyền thông.",
        ),
        "Lion/Hyena là khung phân loại định tính của sách, không phải điểm số tự động và không nên gắn nhãn con người chỉ từ vài sự kiện.",
        "Management & Human Intelligence (Phase 5) · Q35 và nhóm Q33–Q38",
    ),
    "8.1": _spec(
        "Table 8.1 — Penn National Gaming Management Tenure Timeline",
        "Theo dõi tenure và turnover của cả senior managers lẫn các vị trí vận hành quan trọng để phát hiện thay đổi năng lực tổ chức.",
        (
            "Lập timeline theo chức danh/năm từ proxy statements và hồ sơ insider/officer phù hợp.",
            "Quan sát ai ở lại lâu, ai rời đi, vị trí nào thay đổi liên tục và thời điểm thay đổi so với diễn biến business.",
        ),
        (
            "Nghiên cứu background từng manager, customer/industry experience và chất lượng các hires.",
            "Nếu người giỏi rời đi hàng loạt, xem đây là tín hiệu cần điều tra sâu chứ không tự kết luận nguyên nhân.",
        ),
        "Turnover là warning signal chứ không phải bằng chứng độc lập về deterioration; cần đọc bối cảnh và lý do thay đổi nhân sự.",
        "Management & Human Intelligence (Phase 5) · Q44 và nhóm Q39–Q45",
    ),
    "8.2": _spec(
        "Table 8.2 — AutoZone Stock Repurchasing History",
        "Đánh giá buyback có thực sự tạo giá trị cho cổ đông và đóng góp bao nhiêu vào EPS growth.",
        (
            "Theo dõi shares outstanding, shares repurchased, average price paid, amount paid và EPS with/without repurchases.",
            "Phân biệt EPS tăng do underlying net income với EPS tăng do denominator (share count) giảm.",
        ),
        (
            "Đánh giá giá mua lại so với intrinsic value tại thời điểm mua nếu có thể.",
            "Kiểm tra funding của buyback: FCF, cash dư hay tăng debt.",
        ),
        "Buyback chỉ tốt khi allocation hợp lý; mua lại quá đắt hoặc vay nợ quá mức có thể phá giá trị dù EPS tăng.",
        "Buyback & Dilution Analyzer · Q46–Q47",
    ),
    "8.3": _spec(
        "Table 8.3 — Stock Options vs Repurchases / Dilution Offset",
        "Tách phần buyback dùng để bù option dilution khỏi phần thực sự làm giảm số cổ phiếu cho cổ đông hiện hữu.",
        (
            "So shares/options issued với shares repurchased theo thời gian.",
            "Tính net share reduction thay vì chỉ nhìn gross buyback.",
        ),
        (
            "Đọc stock plans/ESOP/options và fully diluted share count.",
            "Theo dõi compensation design có khiến dilution lặp lại hay không.",
        ),
        "Gross repurchase lớn có thể tạo cảm giác allocation tốt trong khi phần lớn chỉ bù dilution; app không giả định missing issuance bằng 0.",
        "Buyback & Dilution Analyzer · Q46–Q47",
    ),
    "10.1": _spec(
        "Table 10.1 — Operating Metric vs EPS",
        "Kiểm tra earnings growth có đi cùng growth của operating driver thật hay được tạo bởi nguồn kém bền hơn.",
        (
            "Đặt EPS cạnh operating metric quan trọng nhất của ngành/doanh nghiệp qua nhiều kỳ.",
            "Nếu driver giảm nhưng EPS tăng, điều tra cost cutting, margin/mix, buyback, accounting/tax hoặc yếu tố one-off.",
        ),
        (
            "Chọn driver có quan hệ kinh tế trực tiếp với business: ton-miles, volume, stores/SSS, customers, loan growth/NIM, v.v.",
            "Đánh giá runway, saturation/cannibalization, secular trend và innovation trước khi ngoại suy growth.",
        ),
        "Correlation giữa driver và EPS không tự chứng minh causality; mục tiêu của bảng là buộc analyst tìm nguồn gốc tăng trưởng.",
        "Operating Driver → EPS Analyzer · Q53–Q57",
    ),
}


CHAPTER_9_NOTE = (
    "Chương 9 (Q48–Q52) tập trung vào các đặc điểm tích cực/tiêu cực của management. "
    "Trong bộ bảng nguồn được module rà soát không có Table 9.x để giả lập; app vì vậy không tạo một bảng 9.x không tồn tại."
)


def guidance_for_source_table(table_id: str) -> dict[str, Any] | None:
    return SOURCE_TABLE_GUIDANCE.get(str(table_id).strip())


__all__ = [
    "SOURCE_TABLE_ORDER",
    "PHASE2_TABLE_GROUPS",
    "SOURCE_TABLE_GUIDANCE",
    "CHAPTER_9_NOTE",
    "guidance_for_source_table",
]
