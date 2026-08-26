from __future__ import annotations

"""Paraphrased analysis guidance grounded in Michael Shearn's *The Investment Checklist*.

This registry is intentionally static application content: it does not call external sources and it
never writes analyst assessments. The goal is to place the book's analytical questions beside each
metric/table so the numbers remain evidence for human judgment rather than automatic scores.

Source references use chapter/table labels from the book rather than long quotations.
"""

from typing import Any, Iterable


BOOK_TITLE = "Michael Shearn — The Investment Checklist: The Art of In-Depth Research"

_METADATA_COLUMNS = {
    "Kỳ", "Nguồn", "Scenario", "Signal", "EPS source", "Review #", "As of", "Type", "Status",
    "Ticker", "Company", "Mã", "Doanh nghiệp", "Δ Thesis",
}


def _g(read: str, check: str, caution: str = "") -> dict[str, str]:
    return {"read": read, "check": check, "caution": caution}


BOOK_GUIDANCE: dict[str, dict[str, Any]] = {
    "Table 1.1": {
        "source": "Chương 1 · Table 1.1 — Sample Criteria Checklist",
        "purpose": (
            "Dùng bộ tiêu chí như một bộ lọc để so sánh các doanh nghiệp khác nhau và làm rõ trade-off. "
            "Tổng số dấu ✓ là screening tally, không phải tín hiệu BUY/SELL."
        ),
        "principles": (
            "Giữ tiêu chuẩn nhất quán; đừng nới tiêu chí chỉ để giữ lại một ý tưởng.",
            "Dấu —/Unknown là thông tin chưa biết, không phải đánh giá trung tính.",
            "Một doanh nghiệp tốt ở vài mặt vẫn có thể chứa rủi ro lớn ở những tiêu chí còn lại; đọc cả cấu hình, không chỉ Total.",
        ),
        "metrics": {
            "Recurring Revenue": _g(
                "Doanh thu lặp lại tạo một nền doanh thu có thể dự báo tốt hơn doanh thu one-off.",
                "Xác định phần doanh thu thực sự lặp lại, độ bền hợp đồng/quan hệ, retention và khả năng khách hàng trì hoãn/hủy mua.",
                "Không đồng nhất doanh thu lặp lại với doanh thu chắc chắn; churn và thay đổi hành vi khách hàng vẫn phải theo dõi.",
            ),
            "Long Runway": _g(
                "Runway là dư địa tăng trưởng còn lại chứ không phải tốc độ tăng trưởng đã đạt trong quá khứ.",
                "Kiểm tra khả năng nhân rộng mô hình, quy mô thị trường còn lại, mức bão hòa, cannibalization và giới hạn địa lý/kênh phân phối.",
                "Không ngoại suy một điểm thành công đơn lẻ thành tăng trưởng dài hạn.",
            ),
            "Proven Management": _g(
                "Track record dài giúp đánh giá cách quản lý xử lý nhiều hoàn cảnh kinh doanh.",
                "Xem tenure, lịch sử phân bổ vốn, cách ứng xử qua chu kỳ, chất lượng giao tiếp và kết quả vận hành thực tế.",
                "Ấn tượng cá nhân/charisma không thay thế được bằng chứng lịch sử.",
            ),
            "Franchise/Moat": _g(
                "Điểm mạnh chỉ có giá trị lớn khi khó bị sao chép và có khả năng duy trì.",
                "Xác định nguồn lợi thế, độ khó copy, sức mạnh định giá, switching cost, scale/distribution/brand và phản ứng của đối thủ.",
                "Đừng gọi mọi competitive strength là sustainable competitive advantage.",
            ),
            "Strong Financials": _g(
                "Sức khỏe tài chính phải được nhìn qua khả năng tạo lợi nhuận/cash flow bền vững và chất lượng bảng cân đối.",
                "Theo dõi nhiều năm: earnings quality, CFO/FCF, margins, leverage và khả năng chịu chu kỳ.",
                "Một năm đẹp hoặc một ratio đẹp không đủ để kết luận.",
            ),
            "High ROIC": _g(
                "ROIC cho biết doanh nghiệp tạo bao nhiêu lợi nhuận hoạt động trên vốn cần để vận hành.",
                "Kiểm tra tính bền vững và các méo do cash dư thừa, goodwill, depreciation, asset write-down và off-balance-sheet obligations.",
                "Không có một biến thể ROIC phù hợp cho mọi doanh nghiệp; methodology phải minh bạch.",
            ),
            "Limited Competition": _g(
                "Cạnh tranh hạn chế thường làm doanh nghiệp dễ theo dõi hơn và giảm áp lực lên economics.",
                "Xem số đối thủ thực, intensity, substitute products, low-cost entrants và đối thủ đặt chuẩn ngành.",
                "Ít đối thủ hiện tại không đảm bảo ngành sẽ không thay đổi.",
            ),
            "Low Capital Expenditures": _g(
                "Capex bảo trì thấp cho phép giữ lại nhiều excess cash flow để tái đầu tư hoặc phân phối cho cổ đông.",
                "Tách maintenance capex và growth capex; xem Capex/Revenue, Capex/D&A, tuổi tài sản và nhu cầu thay thế.",
                "Capex thấp do trì hoãn bảo trì có thể chỉ dời chi phí sang tương lai.",
            ),
            "Diversified Customer Base": _g(
                "Khách hàng đa dạng làm giảm rủi ro mất một khách hàng lớn hoặc quyền thương lượng quá mạnh của một bên mua.",
                "Kiểm tra top customers, % doanh thu, customer concentration, churn và mức độ phụ thuộc lẫn nhau.",
                "Đa dạng về số lượng nhưng cùng chịu một chu kỳ kinh tế vẫn có thể là concentration risk kinh tế.",
            ),
            "Strong Balance Sheet": _g(
                "Bảng cân đối mạnh tạo khả năng sống sót và hành động khi tín dụng khan hiếm.",
                "Đánh giá debt capacity theo độ ổn định cash flow, coverage, maturity, fixed/variable rates, covenants và nghĩa vụ ngoài bảng cân đối.",
                "Không dùng một static ratio tại một thời điểm để thay cho phân tích nhiều kỳ.",
            ),
            "Total": _g(
                "Tally cho biết doanh nghiệp đáp ứng bao nhiêu tiêu chí screening.",
                "Đọc kèm các tiêu chí bị X/Unknown để hiểu trade-off và vùng cần nghiên cứu thêm.",
                "Total cao không phải khuyến nghị mua; Total thấp cũng không thay thế định giá và nghiên cứu sâu.",
            ),
        },
    },
    "Table 1.2": {
        "source": "Chương 1 · Table 1.2 — Inventory of Ideas",
        "purpose": (
            "Theo dõi một inventory/watchlist có cấu trúc để so sánh các cơ hội và nhận biết khi valuation trở nên hấp dẫn hơn, "
            "thay vì bắt đầu nghiên cứu vội vàng khi giá vừa biến động."
        ),
        "principles": (
            "Dùng các metric valuation cùng với hiểu biết về chất lượng doanh nghiệp; metric thấp không tự động là rẻ.",
            "Ưu tiên economics/cash flow và tính bền vững của earnings hơn một multiple đơn lẻ.",
            "Các cột Target/MOS của Trecapital là phần mở rộng của app; phải gắn với giả định định giá và không được coi là kết luận từ sách.",
        ),
        "metrics": {
            "TEV": _g("Giá trị doanh nghiệp dùng làm nền cho các multiple operating earnings.", "Kiểm tra Market Cap, interest-bearing debt, cash và short-term investments được đưa vào đúng kỳ.", "TEV sai nếu debt/cash thiếu hoặc stale."),
            "EBIT": _g("Lợi nhuận hoạt động trước lãi vay và thuế; không cộng lại depreciation như EBITDA.", "Xem tính bình thường hóa và độ ổn định qua chu kỳ.", "EBIT một kỳ đỉnh chu kỳ có thể làm valuation giả rẻ."),
            "EBITDA": _g("Earnings trước D&A, hữu ích để so sánh nhưng bỏ qua một chi phí kinh tế có thể rất thật.", "Đối chiếu Capex/D&A và nhu cầu maintenance capex.", "Không dùng EBITDA như thay thế cash flow ở doanh nghiệp asset-heavy."),
            "Normalized earnings": _g("Earnings đã cố gắng loại yếu tố bất thường để phản ánh earning power thông thường.", "Kiểm tra rõ khoản nào được loại/chuẩn hóa và liệu điều chỉnh có lặp lại hay không.", "Normalization quá lạc quan có thể phóng đại earning power."),
            "TEV/EBIT": _g("Multiple của enterprise value trên EBIT; nghịch đảo gần với pre-tax operating earnings yield.", "So sánh theo thời gian, peer và chất lượng/cyclicality của EBIT.", "Multiple thấp không đủ nếu EBIT sắp suy giảm."),
            "TEV/EBITDA": _g("Multiple valuation trên EBITDA.", "Đọc cùng maintenance capex và EBIT/Interest, đặc biệt ở doanh nghiệp thâm dụng tài sản.", "Có thể trông rẻ khi depreciation/capex là chi phí kinh tế lớn."),
            "TEV/Norm.E": _g("Multiple dựa trên normalized earnings.", "Kiểm tra consistency của normalized base trước khi so sánh.", "Độ tin cậy phụ thuộc chất lượng normalization."),
            "Pre-tax yield": _g("Yield trước thuế dùng để theo dõi mức earnings tương đối so với TEV.", "Đặt cạnh history và rủi ro earnings; yield cao chỉ đáng giá nếu earnings bền.", "Yield cao do earnings peak-cycle không tạo margin of safety thật."),
            "Total Debt": _g("Nợ tạo nghĩa vụ cố định và refinancing risk.", "Xem maturity, interest rate, recourse/non-recourse, covenants và debt-like obligations ngoài bảng cân đối.", "Không chỉ nhìn số nợ tuyệt đối; debt capacity phụ thuộc độ ổn định cash flow."),
            "Debt/EBITDA": _g("Đo leverage so với EBITDA.", "Đánh giá nhiều kỳ và theo cyclicality; doanh nghiệp cash flow biến động cần cushion cao hơn.", "Không có một ngưỡng an toàn áp dụng cho mọi ngành."),
            "EBIT/Interest": _g("Coverage bảo thủ hơn EBITDA/Interest vì không cộng lại depreciation.", "Xem xu hướng coverage, cash-flow predictability và kỳ đáo hạn nợ.", "Coverage kế toán vẫn nên đối chiếu cash coverage khi có dữ liệu."),
            "FCF": _g("Cash còn lại sau hoạt động và tái đầu tư được dùng để đánh giá economics thực.", "Kiểm tra CFO quality, working capital và maintenance/growth capex.", "FCF một kỳ có thể bị working-capital timing hoặc capex timing làm méo."),
            "FCF Yield EV": _g("FCF tương đối với enterprise value.", "So sánh qua thời gian và với durability của cash flow.", "Yield cao nhưng FCF không bền không phải bargain."),
            "FCF Yield Mkt": _g("FCF tương đối với market capitalization.", "Đọc cùng leverage vì equity yield có thể bị nợ làm phóng đại rủi ro.", "Không bỏ qua debt khi chỉ nhìn FCF/Market Cap."),
            "CCC": _g("Thời gian tiền bị giữ trong receivables + inventory sau khi trừ thời gian được supplier tài trợ.", "Tách DSO/DIO/DPO để hiểu vì sao CCC thay đổi.", "CCC giảm do kéo dài DPO không nhất thiết phản ánh vận hành tốt hơn."),
            "Market cap": _g("Giá trị vốn chủ sở hữu theo thị trường.", "Dùng như market input, không thay thế intrinsic value.", "Market cap thay đổi theo giá, không nói trực tiếp chất lượng business."),
            "Giá": _g("Giá cổ phiếu hiện tại là đầu vào so sánh với giá trị, không phải bản thân giá trị.", "Xem cùng target/range và mức độ chắc chắn của các giả định.", "Giá giảm không tự động tạo cơ hội nếu fundamentals xấu đi."),
            "FCF est./share": _g("Ước tính FCF trên mỗi cổ phiếu để nối cash economics với equity valuation.", "Kiểm tra FCF base, share count và dilution.", "Đây là estimate của app/analyst, không phải số liệu gốc của Shearn."),
            "Target": _g("Giá trị/target dùng để so sánh cơ hội trong inventory.", "Kiểm tra methodology, assumptions, normalized earnings và range uncertainty.", "Đây là phần định giá của Trecapital, không phải một target được sách quy định."),
            "MOS": _g("Khoảng chênh giữa giá thị trường và target/value theo implementation Trecapital.", "Đọc cùng độ tin cậy của intrinsic value và business risk.", "MOS số học không bù được thesis sai hoặc earnings không bền."),
            "Nguồn": _g("Cho biết origin của số liệu/snapshot.", "Ưu tiên dữ liệu hiện hành và hiểu rõ proxy/analyst override.", "Source metadata không phải chỉ tiêu đầu tư."),
            "Kỳ": _g("Mốc thời gian của dữ liệu.", "So sánh đúng FY/TTM và tránh trộn các kỳ không tương đương.", "TTM hiện tại không nên mặc định so growth trực tiếp với một FY nếu không comparable."),
        },
    },
    "Balance Sheet & Leverage Analyzer": {
        "source": "Chương 5 · Q25 · Tables 5.1–5.2 và phần coverage/static ratios",
        "purpose": "Đánh giá khả năng chịu nợ bằng cash-flow stability, coverage và cấu trúc nghĩa vụ; không kết luận từ một ratio snapshot.",
        "principles": (
            "Nợ phải được trả bằng cash; khi có thể hãy đối chiếu earnings coverage với cash coverage.",
            "EBIT/Interest bảo thủ hơn EBITDA/Interest khi depreciation phản ánh maintenance economics thực.",
            "Ngưỡng leverage/coverage phải thay đổi theo độ biến động cash flow và ngành.",
        ),
        "metrics": {
            "Total Debt": _g("Tổng interest-bearing debt đang tài trợ doanh nghiệp.", "Kiểm tra thêm maturity, fixed/variable rates, covenants, recourse và nghĩa vụ ngoài bảng cân đối.", "Debt tuyệt đối không cho biết riêng khả năng trả nợ."),
            "Cash + STI": _g("Nguồn liquidity có thể bù một phần nghĩa vụ tài chính.", "Xác định cash nào thực sự available và cash nào cần cho vận hành.", "Không mặc định toàn bộ cash là excess cash."),
            "Net Debt": _g("Debt sau khi trừ cash/ST investments, một chỉ dấu nhanh về burden tài chính.", "Đặt cạnh cash-flow distribution và refinancing schedule.", "Net debt thấp vẫn có thể che maturity/covenant risk."),
            "EBITDA": _g("Earnings trước D&A dùng trong một số coverage/leverage ratios.", "So sánh với EBIT và maintenance capex.", "Adding back depreciation có thể làm khả năng trả nợ trông tốt hơn economics thật."),
            "Debt/EBITDA": _g("Số lần EBITDA tương ứng với debt.", "Theo dõi nhiều kỳ và điều chỉnh kỳ vọng theo cyclicality/cash-flow stability.", "Không áp một cut-off duy nhất cho mọi business."),
            "EBIT": _g("Operating earnings sau depreciation, phù hợp hơn khi depreciation là chi phí kinh tế thực.", "Đánh giá normalized EBIT qua chu kỳ.", "Peak EBIT làm coverage đẹp giả tạo."),
            "Interest": _g("Fixed financial charge phải được phục vụ bằng cash.", "Xem fixed/variable rate và khả năng interest tăng khi refinancing.", "Interest hiện tại có thể thấp tạm thời nếu nợ sắp đáo hạn."),
            "EBIT/Interest": _g("Mức EBIT cover interest bao nhiêu lần.", "Xem trend và mức cushion cần thiết theo độ ổn định earnings.", "Coverage thấp + high operating leverage/debt là tổ hợp rủi ro."),
            "Current Assets": _g("Nguồn lực ngắn hạn trong static liquidity view.", "Xem chất lượng AR/inventory và seasonality.", "Book value của current assets không phải lúc nào cũng chuyển thành cash ngang giá."),
            "Current Liabilities": _g("Nghĩa vụ ngắn hạn tạo nhu cầu liquidity.", "Xem composition và timing, không chỉ tổng số.", "Supplier financing và debt maturity có bản chất khác nhau."),
            "Current Ratio": _g("Static ratio current assets/current liabilities tại một thời điểm.", "Theo dõi qua nhiều quý/năm, đặc biệt với seasonal businesses và covenant limits.", "Shearn cảnh báo static ratios có thể gây hiểu sai nếu chỉ nhìn một snapshot."),
            "Kỳ": _g("Kỳ tài chính của ratio.", "Đọc trend nhiều kỳ thay vì một điểm.", "Seasonality có thể làm các kỳ khác nhau khó so trực tiếp."),
        },
    },
    "ROIC Quality Analyzer": {
        "source": "Chương 5 · Q26 · Tables 5.3–5.4",
        "purpose": "Kiểm tra chất lượng và độ bền của ROIC, đồng thời nhìn các distortion từ cash, goodwill/intangibles và depreciation.",
        "principles": (
            "Không có một cách điều chỉnh investment base phù hợp cho mọi doanh nghiệp; phải hiểu bản chất tài sản cần cho hoạt động.",
            "Excluding goodwill giúp thấy tangible return nhưng có thể che việc management đã trả quá cao cho acquisition.",
            "Book value tài sản giảm do depreciation có thể làm ROIC tăng cơ học dù earnings không đổi.",
        ),
        "metrics": {
            "ROIC Trecapital": _g("ROIC chuẩn hóa hiện hành của Trecapital.", "Dùng làm baseline và so với các Shearn analytical variants.", "Không âm thầm thay baseline bằng một variant có kết quả đẹp hơn."),
            "NOPAT": _g("Operating profit sau thuế dùng làm numerator của ROIC.", "Kiểm tra EBIT/tax normalization và các khoản bất thường.", "NOPAT cao bất thường một kỳ có thể làm ROIC méo."),
            "Avg Capital Employed (incl cash)": _g("Average capital base giảm ảnh hưởng của một balance-sheet snapshot.", "Xem cash, goodwill, asset write-down và debt-like obligations có phù hợp trong base không.", "Một denominator quá thấp làm ROIC phóng đại."),
            "ROIC Shearn – Incl Cash": _g("Analytical view giữ cash trong investment base.", "Hữu ích như conservative/full-capital view và để so với Ex Cash.", "Cash thực sự cần cho hoạt động không nên tùy tiện loại bỏ."),
            "ROIC Shearn – Ex Cash": _g("Loại cash/STI khỏi base để quan sát return trên operating capital khi cash thực sự dư thừa.", "Xác định phần cash excess so với liquidity cần thiết.", "Loại toàn bộ cash có thể làm ROIC quá cao."),
            "ROIC Shearn – Ex Goodwill": _g("Loại goodwill/intangibles để xem tangible return.", "Đối chiếu acquisition history và xem intangible nào thực sự cần để vận hành.", "Có thể che acquisition overpayment hoặc loại nhầm economic assets cần thiết."),
            "Cash + STI": _g("Thành phần có thể gây dilution ROIC nếu dư thừa.", "Phân biệt operating cash và excess cash.", "Không tự động coi mọi cash là excess."),
            "Goodwill/Intangibles": _g("Dấu vết của acquisitions/intangible assets trong capital base.", "Xem goodwill có đến từ overpayment và intangible có cần tiếp tục tái đầu tư không.", "Excluding goodwill không xóa chi phí kinh tế management đã bỏ ra."),
            "Kỳ": _g("Mốc thời gian của ROIC và capital base.", "Theo dõi qua nhiều năm để phân biệt structural return và một kỳ bất thường.", "ROIC một kỳ không nói đủ về moat hoặc reinvestment runway."),
        },
    },
    "Accounting Reserve Quality Analyzer": {
        "source": "Chương 6 · Q27 · Tables 6.1–6.2 và Key Points",
        "purpose": "Tìm dấu hiệu accounting policy quá liberal/conservative bằng cách đối chiếu earnings với cash và reserve estimates với outcomes thực tế.",
        "principles": (
            "So provision với actual charge-offs qua nhiều năm; reserve có thể được dùng để dịch chuyển earnings giữa kỳ.",
            "CFO gần Net Income là một dấu hiệu chất lượng cần xem, nhưng không phải rule tuyệt đối.",
            "AR/Inventory tăng nhanh hơn revenue là tín hiệu điều tra, không phải bằng chứng tự động về gian lận.",
        ),
        "metrics": {
            "Net income": _g("Reported accounting earnings.", "Đối chiếu với CFO và các accounting assumptions/reserves.", "Earnings có thể bị timing, reserve hoặc capitalization policy làm méo."),
            "CFO": _g("Cash generated from operations.", "So với Net Income qua nhiều kỳ và giải thích chênh lệch.", "Working-capital timing có thể làm CFO lệch tạm thời."),
            "CFO / Net income": _g("Một cách nhìn mức cash conversion của earnings.", "Tìm pattern dài hạn và nguyên nhân khi ratio lệch đáng kể.", "Không dùng một cut-off duy nhất để kết luận accounting quality."),
            "Provision": _g("Estimate management ghi nhận cho expected losses/allowances.", "So với actual charge-offs/write-offs và thay đổi reserve qua ít nhất vài năm.", "Over/under-reserving có thể smooth earnings."),
            "Actual charge-off/write-off": _g("Outcome thực tế của khoản loss/write-off.", "So với provision đã ghi trước đó.", "Timing giữa provision và charge-off có thể không cùng kỳ; cần đọc footnotes."),
            "Provision / charge-off": _g("Quan hệ estimate so với loss thực tế.", "Tìm sự lệch kéo dài hoặc biến động reserve không đi cùng actual losses.", "Một năm riêng lẻ dễ bị timing làm méo."),
            "Revenue growth": _g("Baseline tăng trưởng doanh thu để đối chiếu receivables/inventory.", "So với AR/Inventory growth và revenue-recognition policy.", "Growth cao không tự động là chất lượng cao nếu cash conversion yếu."),
            "AR growth": _g("Tốc độ tăng khoản phải thu.", "Nếu AR tăng nhanh hơn revenue, kiểm tra collection, customer quality và recognition timing.", "Seasonality/acquisition có thể giải thích chênh lệch; cần evidence bổ sung."),
            "Inventory growth": _g("Tốc độ tăng hàng tồn kho.", "Nếu inventory vượt xa revenue, kiểm tra obsolescence, demand, write-down policy và buildup trước tăng trưởng.", "Inventory build có thể hợp lý hoặc là tín hiệu demand yếu; không tự động kết luận."),
            "Kỳ": _g("Kỳ dữ liệu accounting quality.", "Ưu tiên pattern nhiều năm thay vì một điểm.", "TTM/FY phải comparable trước khi tính growth."),
        },
    },
    "Operating Leverage & Cost Structure Analyzer": {
        "source": "Chương 6 · Q29–Q30 · Tables 6.3–6.5",
        "purpose": "Hiểu mức thay đổi revenue có thể khuếch đại thành thay đổi EBIT và nguyên nhân kinh tế nằm trong cấu trúc fixed/variable costs.",
        "principles": (
            "DOL cao làm earnings khó dự báo hơn vì thay đổi sales nhỏ có thể tạo swing earnings lớn.",
            "High operating leverage đi cùng high debt làm downside nghiêm trọng hơn.",
            "Phân loại fixed/variable/semi-variable cần đọc business economics/MD&A; ratios từ BCTC chỉ là evidence.",
        ),
        "metrics": {
            "Revenue": _g("Top-line tạo nền cho operating leverage.", "Xem biến động revenue và nguyên nhân volume/price/mix.", "Revenue level một mình không nói fixed-cost burden."),
            "Revenue growth": _g("% thay đổi sales dùng trong DOL.", "Chỉ dùng các kỳ comparable; xem cycle và one-off shocks.", "Thay đổi rất nhỏ có thể làm DOL toán học cực đoan."),
            "EBIT": _g("Operating earnings chịu tác động của revenue và cost structure.", "So với revenue để thấy mức khuếch đại.", "EBIT âm/near-zero làm DOL khó diễn giải."),
            "EBIT growth": _g("% thay đổi operating income.", "Đặt cạnh revenue growth và giải thích fixed/variable costs.", "Một restructuring/cost cut có thể làm growth không phản ánh recurring economics."),
            "DOL": _g("Xấp xỉ %Δ EBIT / %Δ Revenue theo cách Shearn dùng để nhìn earnings sensitivity.", "Theo dõi nhiều năm và kết hợp cost structure/break-even logic.", "DOL là noisy ratio; đừng biến nó thành một threshold cứng."),
            "PP&E / Assets": _g("Proxy cho asset intensity, có thể gợi ý fixed-capital burden.", "Đọc cùng D&A, maintenance capex và utilization.", "Asset intensity không tự động bằng fixed-cost percentage."),
            "SG&A / Revenue": _g("Cho thấy overhead tương đối với sales.", "Xem SG&A co giãn thế nào khi revenue thay đổi.", "Không mặc định toàn bộ SG&A là fixed."),
            "D&A / Revenue": _g("D&A relative to sales phản ánh phần nào asset intensity.", "Đối chiếu Capex và tuổi tài sản để hiểu economic fixed cost.", "Depreciation là accounting charge nhưng có thể đại diện maintenance economics rất thật."),
            "Kỳ": _g("Kỳ của revenue/EBIT comparison.", "Ưu tiên chuỗi dài qua nhiều trạng thái chu kỳ.", "Một boom/bust year có thể làm DOL không đại diện bình thường."),
        },
    },
    "Operating Leverage Stress": {
        "source": "Trecapital extension dựa trên khái niệm DOL ở Chương 6 · Q30; không phải bảng gốc của Shearn",
        "purpose": "Biến DOL lịch sử thành scenario để hình dung downside sensitivity; đây là stress test, không phải forecast.",
        "principles": (
            "Dùng scenario để đặt câu hỏi về downside và break-even, không coi kết quả là dự báo chính xác.",
            "Fixed/variable costs thực tế có thể thay đổi khi management cắt chi phí, đóng capacity hoặc renegotiate contracts.",
        ),
        "metrics": {
            "Revenue shock": _g("Giả định % thay đổi doanh thu trong scenario.", "Thử nhiều mức giảm hợp lý với cyclicality của business.", "Không phải forecast xác suất."),
            "DOL used": _g("DOL lịch sử được dùng làm sensitivity input.", "Kiểm tra có đại diện normal conditions không.", "DOL lịch sử có thể không giữ nguyên trong stress."),
            "Revenue stressed": _g("Doanh thu sau shock giả định.", "Đặt cạnh break-even/capacity economics nếu có.", "Chỉ là mechanical scenario."),
            "EBIT change": _g("Thay đổi EBIT suy ra từ DOL × revenue shock.", "Dùng để nhận biết mức earnings amplification.", "Không phản ánh management actions hoặc nonlinear cost response."),
            "EBIT stressed": _g("EBIT sau stress theo mô hình đơn giản.", "Đặt cạnh interest/fixed obligations để xem khả năng chịu đựng.", "Không phải projected EBIT chính thức."),
            "Scenario": _g("Nhãn kịch bản.", "Dùng để phân biệt các shock assumptions.", "Metadata, không phải metric kinh tế độc lập."),
        },
    },
    "Working Capital / CCC Analyzer": {
        "source": "Chương 6 · Q31 · Table 6.6 và Key Points",
        "purpose": "Hiểu doanh nghiệp phải bỏ ra hay giải phóng bao nhiêu cash khi vận hành và tăng trưởng, đồng thời tách nguyên nhân qua DSO/DIO/DPO.",
        "principles": (
            "Working-capital needs phụ thuộc business model, capital intensity và tốc độ chuyển inventory thành cash.",
            "Sustainable working-capital improvements giải phóng cash; deterioration hút cash khỏi owners.",
            "CCC thấp hơn không mặc định tốt hơn nếu cải thiện đến từ kéo dài thanh toán suppliers.",
        ),
        "metrics": {
            "DSO": _g("Số ngày bình quân thu tiền từ khách hàng.", "Xem trend, customer terms và AR quality.", "DSO tăng có thể báo collection yếu hoặc mix thay đổi; cần context."),
            "DIO": _g("Số ngày inventory nằm trước khi chuyển thành sales/cash.", "Xem obsolescence, demand và inventory policy.", "DIO thấp không luôn tốt nếu doanh nghiệp thiếu hàng/mất sales."),
            "DPO": _g("Số ngày doanh nghiệp dùng supplier financing trước khi trả.", "Xem payment terms và quan hệ supplier.", "DPO tăng có thể giải phóng cash nhưng cũng có thể là dấu hiệu liquidity stress."),
            "CCC": _g("DIO + DSO − DPO, thời gian cash bị khóa trong operating cycle.", "Tách từng component để giải thích thay đổi.", "Không tự chấm 'CCC thấp = tốt'."),
            "Operating WC": _g("Vốn hoạt động bị buộc trong receivables + inventory − payables theo implementation hiện tại.", "Xem composition và business model.", "Cùng một số WC có thể có quality rất khác tùy cấu phần."),
            "Δ Operating WC": _g("Thay đổi vốn hoạt động giữa các kỳ.", "Xác định tăng trưởng đang hút cash hay giải phóng cash.", "Acquisition/seasonality có thể làm delta không recurring."),
            "ΔWC / Revenue": _g("Quy mô cash tied-up/released tương đối với revenue.", "Theo dõi pattern để đánh giá cash intensity của growth.", "Một kỳ bất thường không nên dùng làm steady-state assumption."),
            "Cash released/(absorbed)": _g("Dấu cash impact của thay đổi WC: release hỗ trợ cash flow, absorption làm giảm cash flow.", "Kiểm tra nguyên nhân release có bền không.", "Cash release từ trì hoãn supplier payment có thể không bền."),
            "Kỳ": _g("Kỳ của working-capital metrics.", "So sánh các kỳ cùng season nếu business có seasonality.", "Quarter/FY mix có thể làm days metrics khó so."),
        },
    },
    "Maintenance Capex Context": {
        "source": "Chương 6 · Q32 và Key Points — Maintenance Capital Expenditures",
        "purpose": "Ước lượng lượng cash phải tái đầu tư chỉ để duy trì current cash flows/assets trước khi xem phần cash thực sự phân phối được.",
        "principles": (
            "Maintenance capex giữ doanh nghiệp ở steady state; growth capex nhằm mở rộng future cash flow.",
            "Nếu công ty không tách maintenance/growth capex, depreciation chỉ là rough approximation và cần judgment theo asset type.",
            "Deferred maintenance có thể làm FCF hiện tại đẹp hơn nhưng tạo capex/downtime lớn trong tương lai.",
        ),
        "metrics": {
            "Capex": _g("Tổng cash đầu tư vào property/equipment trong kỳ.", "Tách maintenance vs growth bằng disclosures/MD&A khi có thể.", "Total capex không bằng maintenance capex."),
            "Maintenance Capex Trecapital (ước tính)": _g("Ước tính phần capex cần để giữ steady-state theo methodology Trecapital.", "Đối chiếu disclosure, D&A và asset age.", "Là estimate của app, không phải reported line item nếu nguồn không tách."),
            "D&A rough proxy": _g("Depreciation/amortization dùng như rough maintenance proxy khi không có estimate tốt hơn.", "Xem asset type và growth state để điều chỉnh lên/xuống.", "Shearn chỉ coi đây là approximation, không phải maintenance capex thực tế."),
            "Capex / Revenue": _g("Mức capital intensity tương đối với sales.", "Theo dõi qua chu kỳ và peer để hiểu vốn cần cho mỗi đồng doanh thu.", "Growth phase có thể làm ratio cao tạm thời."),
            "Capex / D&A": _g("So actual capital spending với accounting depreciation.", "Ratio kéo dài >/< 1 cần giải thích bằng growth, asset age hoặc deferred replacement.", "Không dùng ratio để tự động tách maintenance/growth capex."),
            "CFO": _g("Operating cash trước capex.", "Kiểm tra khả năng tự tài trợ reinvestment.", "CFO có thể bị working-capital timing làm biến động."),
            "FCF": _g("Cash còn sau capex theo implementation hiện tại.", "Xem FCF qua nhiều năm và điều chỉnh maintenance economics.", "FCF một kỳ cao do hoãn capex không nhất thiết bền."),
            "Kỳ": _g("Kỳ của capex/cash-flow context.", "Xem nhiều năm vì replacement cycles có thể dài.", "Một kỳ capex thấp không chứng minh business structurally low-capex."),
        },
    },
    "Buyback & Dilution Analyzer": {
        "source": "Chương 8 · Q46–Q47 · Tables 8.2–8.3",
        "purpose": "Đo buyback có thực sự giảm share count và tăng per-share economics hay chỉ bù dilution từ options/ESOP.",
        "principles": (
            "Đánh giá repurchase bằng hiệu ứng thực lên shares outstanding và EPS, không chỉ số tiền công ty thông báo mua lại.",
            "Phần repurchase chỉ để offset options dilution không nên được coi như value-adding capital allocation tương đương net repurchase.",
            "Buyback tốt còn phụ thuộc giá mua; app cần giữ riêng phân tích intrinsic value khi dữ liệu/valuation phù hợp.",
        ),
        "metrics": {
            "Shares outstanding": _g("Số cổ phiếu lưu hành cuối/đại diện kỳ, phản ánh dilution hoặc contraction thực.", "Theo dõi trend nhiều năm và các corporate actions.", "Weighted average vs ending shares có thể khác nhau."),
            "Net share reduction": _g("Mức giảm share count thực so với kỳ trước.", "Xác nhận do buyback chứ không do reverse split/other actions.", "Có thể khác gross repurchase do shares issued."),
            "Share count change vs prior displayed period": _g("% thay đổi share count.", "Xem có dilution kéo dài hay net reduction bền.", "Một kỳ không đủ đánh giá discipline."),
            "Buyback amount": _g("Cash management dùng cho repurchases.", "So với FCF, leverage và các lựa chọn capital allocation khác.", "Số tiền lớn không đồng nghĩa value creation nếu mua quá đắt."),
            "Gross buyback shares": _g("Tổng số shares được mua lại.", "So với options/ESOP/new issuance.", "Gross buyback có thể phóng đại net benefit."),
            "Shares issued / ESOP / options": _g("Nguồn dilution bù ngược buyback.", "Theo dõi stock plans và compensation disclosures.", "Dilution là cost kinh tế đối với existing owners."),
            "Net buyback after dilution": _g("Gross repurchase trừ shares issued khi dữ liệu đủ.", "Dùng để xem bao nhiêu repurchase thực sự làm giảm owner dilution.", "Thiếu issued-share data thì không được giả định bằng 0."),
            "EPS reported/derived": _g("EPS thực/derived sau ảnh hưởng share count.", "Đối chiếu với net income và share-count trend.", "EPS tăng có thể đến từ buyback chứ không phải business earnings growth."),
            "EPS source": _g("Nhãn reported hay derived.", "Ưu tiên hiểu source trước khi so sánh.", "Metadata, không phải quality score."),
            "EPS without share-count change": _g("Analytical proxy giữ prior share count để tách hiệu ứng mechanical của buyback.", "So với EPS hiện tại để ước lượng contribution từ share reduction.", "Không phải reported EPS của công ty."),
            "EPS uplift from share-count change": _g("% EPS uplift do thay đổi share count theo proxy.", "Phân biệt per-share engineering với operating growth.", "EPS uplift không tự động tạo value nếu buyback dùng vốn kém hiệu quả."),
            "Kỳ": _g("Kỳ của buyback/share data.", "Theo dõi nhiều năm để đánh giá capital-allocation pattern.", "Corporate-action timing có thể làm một kỳ méo."),
        },
    },
    "Operating Driver → EPS Analyzer": {
        "source": "Chương 10 · Q53–Q57 · Table 10.1",
        "purpose": "Đặt EPS cạnh operating driver thật của business để phân biệt earnings growth có nền tảng vận hành hay đến từ nguồn kém bền hơn.",
        "principles": (
            "Driver phải phù hợp business/industry; Shearn minh họa railroad bằng revenue ton-miles chứ không dùng một metric cho mọi ngành.",
            "Nếu EPS tăng trong khi driver giảm, cần tìm nguồn khác như cost cutting, mix, leverage hoặc share-count change.",
            "Không dự báo tương lai bằng cách ngoại suy một success story; kiểm tra runway, saturation, secular demand và innovation.",
        ),
        "metrics": {
            "Operating driver": _g("Operating metric phản ánh activity/economic engine của business.", "Chọn metric theo ngành và kiểm tra nó có thật sự dẫn earnings không.", "Revenue chỉ là fallback, không phải driver tối ưu cho mọi business."),
            "Operating driver growth": _g("Tốc độ thay đổi underlying activity.", "So với EPS growth và giải thích divergence.", "Một driver duy nhất có thể chưa đủ nếu business có nhiều revenue engines."),
            "EPS reported/derived": _g("Per-share earnings outcome.", "Đặt cạnh operating driver, margin, net income và share count.", "EPS có thể tăng nhờ buyback/cost cuts dù operating activity yếu."),
            "EPS source": _g("Cho biết EPS reported hay derived.", "Kiểm tra consistency khi so time series.", "Metadata, không phải investment conclusion."),
            "EPS growth": _g("Tốc độ tăng per-share earnings.", "So với driver growth để xác định earnings source.", "TTM hiện tại không nên so trực tiếp với FY nếu thiếu prior comparable TTM."),
            "Signal": _g("Cảnh báo divergence đơn giản giữa driver và EPS.", "Dùng như câu hỏi nghiên cứu tiếp theo: margin? cost cut? dilution? cycle?", "Không phải auto assessment hoặc BUY/SELL signal."),
            "Kỳ": _g("Kỳ của driver/EPS.", "So comparable periods và trend dài hạn.", "Mix TTM/FY có thể gây growth signal sai nếu không comparable."),
        },
    },
}


# Dynamic operating-driver aliases from the Trecapital Data Layer.
_DRIVER_LABELS = {
    "Revenue", "Sales volume", "Volume", "Capacity utilization", "Same-store sales", "Store count",
    "Customer count", "Transactions", "Loan growth", "NIM",
}


def canonical_metric(table_key: str, metric: str) -> str:
    name = str(metric)
    if table_key == "Operating Driver → EPS Analyzer":
        if name in _DRIVER_LABELS:
            return "Operating driver"
        if name.endswith(" growth") and name.removesuffix(" growth") in _DRIVER_LABELS:
            return "Operating driver growth"
    return name


def guidance_for(table_key: str, columns: Iterable[str] | None = None) -> dict[str, Any] | None:
    spec = BOOK_GUIDANCE.get(table_key)
    if spec is None:
        return None
    if columns is None:
        return spec
    rows = []
    metrics = spec.get("metrics", {})
    seen: set[str] = set()
    for col in columns:
        canonical = canonical_metric(table_key, str(col))
        if canonical in seen:
            continue
        seen.add(canonical)
        item = metrics.get(canonical)
        if item is None and str(col) in _METADATA_COLUMNS:
            continue
        if item is not None:
            rows.append({"metric": str(col), "canonical": canonical, **item})
    return {**spec, "metric_rows": rows}


def uncovered_metrics(table_key: str, columns: Iterable[str]) -> list[str]:
    spec = BOOK_GUIDANCE.get(table_key, {})
    metrics = spec.get("metrics", {})
    missing = []
    for col in columns:
        name = str(col)
        canonical = canonical_metric(table_key, name)
        if name in _METADATA_COLUMNS and canonical not in metrics:
            continue
        if canonical not in metrics:
            missing.append(name)
    return missing
