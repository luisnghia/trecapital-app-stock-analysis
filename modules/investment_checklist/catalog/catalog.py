from __future__ import annotations

import csv
from pathlib import Path

SCREENING_CRITERIA = [
    ("recurring_revenue", "Recurring Revenue", "Doanh thu tái diễn/định kỳ"),
    ("long_runway", "Long Runway", "Dư địa tăng trưởng dài hạn"),
    ("proven_management", "Proven Management", "Ban lãnh đạo đã được kiểm chứng"),
    ("franchise_moat", "Franchise / Moat", "Franchise / lợi thế cạnh tranh bền vững"),
    ("strong_financials", "Strong Financials", "Đặc điểm tài chính mạnh"),
    ("high_roic", "High ROIC", "ROIC cao"),
    ("limited_competition", "Limited Competition", "Cạnh tranh hạn chế"),
    ("low_capex", "Low Capital Expenditures", "Yêu cầu chi tiêu vốn thấp"),
    ("diversified_customers", "Diversified Customer Base", "Cơ sở khách hàng đa dạng"),
    ("strong_balance_sheet", "Strong Balance Sheet", "Bảng cân đối mạnh"),
]

GUIDANCE = {
"Q01":"Tự đánh giá mức độ hứng thú và khả năng duy trì nghiên cứu dài hạn. Nếu không muốn dành thời gian hiểu sâu doanh nghiệp, ghi rõ lý do và cân nhắc dừng nghiên cứu.",
"Q02":"Hãy nhìn doanh nghiệp như người điều hành: yếu tố nào quyết định thành bại, tiền kiếm ở đâu, vốn cần ở đâu, rủi ro vận hành nào phải ưu tiên theo dõi.",
"Q03":"Mô tả chuỗi vận hành bằng ngôn ngữ của chính mình: đầu vào → hoạt động cốt lõi → phân phối → khách hàng → thu tiền. Tránh sao chép mô tả IR.",
"Q04":"Tách các động cơ kiếm tiền: sản phẩm/dịch vụ, phân khúc, khách hàng, địa lý, định giá, volume và biên lợi nhuận. Xác định nguồn lợi nhuận thực sự.",
"Q05":"Lập timeline các thay đổi lớn về sản phẩm, khách hàng, địa lý, mô hình doanh thu, tài sản và chiến lược. Phân biệt tiến hóa hữu cơ với thay đổi do M&A.",
"Q06":"Xác định tỷ trọng hoạt động nước ngoài, rủi ro tỷ giá, pháp lý, chính trị, chuỗi cung ứng và khả năng chuyển tiền/lợi nhuận. Không chỉ nhìn doanh thu địa lý.",
"Q07":"Xác định người ra quyết định mua, người sử dụng và người trả tiền. Mô tả nhu cầu, ngân sách, tần suất mua và yếu tố lựa chọn nhà cung cấp.",
"Q08":"Đo mức tập trung theo khách hàng/top 5/top 10 hoặc nhóm khách hàng. Xem mất một khách hàng lớn sẽ ảnh hưởng doanh thu, công suất và dòng tiền ra sao.",
"Q09":"Đánh giá sales cycle, chi phí chuyển đổi, mức thử nghiệm/chứng nhận, độ khó thuyết phục khách hàng mới và vai trò của thương hiệu/kênh phân phối.",
"Q10":"Tìm retention/churn/renewal/repeat purchase hoặc proxy phù hợp. Nếu doanh nghiệp không công bố, đánh dấu Research Gap thay vì giả định trung tính.",
"Q11":"Tìm bằng chứng hành vi: chất lượng dịch vụ, phản hồi khiếu nại, NPS/review, chính sách đổi trả, đầu tư hỗ trợ khách hàng và cách management nói về khách hàng.",
"Q12":"Nêu pain point cụ thể mà sản phẩm giải quyết và giá trị kinh tế/thời gian/rủi ro mà khách hàng tiết kiệm. Pain càng thiết yếu càng cần bằng chứng mạnh.",
"Q13":"Đánh giá switching cost, tích hợp quy trình, dữ liệu, đào tạo, chứng nhận, mạng lưới và rủi ro gián đoạn nếu đổi nhà cung cấp.",
"Q14":"Thực hiện thought experiment: nếu doanh nghiệp biến mất ngày mai, khách hàng có thay thế ngay được không, mất bao lâu, tốn bao nhiêu và hoạt động nào bị gián đoạn.",
"Q15":"Liệt kê từng nguồn lợi thế cạnh tranh, bằng chứng định lượng/định tính, mức dễ sao chép và thời gian tồn tại. Không đồng nhất 'điểm mạnh' với moat bền vững.",
"Q16":"Kiểm tra tăng giá cùng biến động volume, churn, market share và gross margin. Phân biệt pricing power với việc chỉ chuyển chi phí đầu vào sang khách hàng.",
"Q17":"Đánh giá cấu trúc kinh tế của ngành: tăng trưởng, cường độ vốn, pricing, lợi nhuận trung bình, số đối thủ, rào cản gia nhập và biến động chu kỳ.",
"Q18":"Lập lịch sử ngành: công nghệ, quy định, cấu trúc cung/cầu, consolidation, kênh phân phối và những lần mô hình lợi nhuận thay đổi.",
"Q19":"So sánh đối thủ về thị phần, giá, chi phí, margin, ROIC và operating metrics. Tìm nguyên nhân khác biệt chứ không dừng ở xếp hạng.",
"Q20":"Đánh giá quyền lực nhà cung cấp, mức tập trung, hợp đồng, khả năng thay thế, độ phụ thuộc đầu vào và lịch sử đứt gãy/đàm phán giá.",
"Q21":"Xác định các fundamentals quyết định giá trị doanh nghiệp và theo dõi qua nhiều năm/TTM. Tập trung vào động lực kinh tế thực thay vì chỉ EPS.",
"Q22":"Chọn bộ operating metrics mà nếu xấu đi sẽ báo hiệu business deterioration. Ghi rõ metric, nguồn, tần suất cập nhật và ngưỡng cần xem lại.",
"Q23":"Lập danh sách rủi ro theo xác suất × tác động × khả năng phục hồi; ưu tiên rủi ro có thể phá thesis, bảng cân đối hoặc lợi thế cạnh tranh.",
"Q24":"Phân tích khả năng chuyển giá, cấu trúc fixed/variable cost, nhu cầu vốn lưu động, capex thay thế và tác động lạm phát lên cầu/biên lợi nhuận.",
"Q25":"Đánh giá thanh khoản, leverage, kỳ hạn nợ, interest coverage, covenant và nghĩa vụ ngoài bảng cân đối qua chu kỳ; tránh kết luận từ một snapshot.",
"Q26":"Xem ROIC qua chu kỳ, chất lượng numerator/denominator, excess cash/goodwill và khả năng tái đầu tư. ROIC cao nhưng không tái đầu tư được cần đánh giá khác compounder.",
"Q27":"Kiểm tra revenue recognition, reserve, write-off, capitalization, depreciation, impairment, one-off và CFO vs lợi nhuận. Tách policy hợp lý khỏi hành vi làm đẹp earnings.",
"Q28":"Phân loại doanh thu recurring/repeat/transactional/one-off; đánh giá renewal, visibility và mức phụ thuộc vào giao dịch mới.",
"Q29":"Đặt doanh thu/lợi nhuận trong nhiều chu kỳ kinh tế và ngành. Xác định biến số chu kỳ chủ chốt và mức suy giảm trong stress period.",
"Q30":"So biến động EBIT với doanh thu và phân rã fixed/variable/semi-variable cost. Operating leverage cao làm dự báo và downside nhạy hơn.",
"Q31":"Phân tích DSO/DIO/DPO/CCC và Operating Working Capital. Hỏi tại sao WC hấp thụ/giải phóng tiền và liệu thay đổi có bền vững hay do trì hoãn thanh toán.",
"Q32":"Tách growth capex và maintenance capex nếu có thể; xem capex/doanh thu, capex/D&A, tuổi tài sản và khả năng chuyển lợi nhuận thành FCF.",
"Q33":"Mô tả kiểu lãnh đạo dựa trên lịch sử hành động: operator, allocator, founder, professional manager… Không chỉ dựa vào hình ảnh truyền thông.",
"Q34":"So kết quả trước/sau khi thuê quản lý bên ngoài: văn hóa, turnover, capital allocation, margin, tăng trưởng và tốc độ ra quyết định.",
"Q35":"Dùng khung lion/hyena như công cụ phản tư về dài hạn, đạo đức, học hỏi, teamwork và cơ hội chủ nghĩa. Cần dẫn chứng hành vi cụ thể.",
"Q36":"Lập timeline nghề nghiệp của CEO/CFO/COO; xem họ trưởng thành nội bộ hay đi ngang, thành tích ở từng vai trò và ai đã cùng họ xây tổ chức.",
"Q37":"Đọc compensation: fixed/bonus/equity, KPI, vesting, ownership, dilution và mức liên kết với giá trị dài hạn thay vì EPS ngắn hạn.",
"Q38":"Theo dõi mua/bán của insider theo bối cảnh, quy mô so với tài sản nắm giữ, chương trình bán định kỳ và thời điểm định giá.",
"Q39":"Tìm bằng chứng CEO cân bằng khách hàng, nhân viên, nhà cung cấp, chủ nợ và cổ đông; tránh kết luận từ khẩu hiệu stakeholder.",
"Q40":"Xem management có xây hệ thống cải tiến vận hành liên tục hay phụ thuộc vào chiến dịch/kế hoạch lớn. Tìm bằng chứng KPI, process và execution cadence.",
"Q41":"Lập track record guidance: mục tiêu đã đưa, kết quả thực tế, tần suất sửa guidance và cách management giải thích sai lệch.",
"Q42":"Xác định mức tập trung/phân quyền, quyền P&L, tốc độ quyết định, kiểm soát vốn và accountability. Đánh giá mô hình có phù hợp quy mô/ngành không.",
"Q43":"Tìm bằng chứng về retention nhân sự, đào tạo, thăng tiến nội bộ, an toàn, văn hóa, chi phí nhân sự và cách management xử lý giai đoạn khó khăn.",
"Q44":"Xem chất lượng đội ngũ được tuyển, tỷ lệ thăng tiến, succession, turnover vị trí chủ chốt và thành tích của các hires quan trọng.",
"Q45":"Phân biệt kỷ luật chi phí bền vững với cắt chi phí làm hỏng năng lực dài hạn. Xem SG&A, R&D, bảo trì, nhân sự và chất lượng dịch vụ.",
"Q46":"Lập lịch sử phân bổ CFO: capex, M&A, nợ, cổ tức, buyback, giữ tiền. Đánh giá return hậu quyết định và tính nhất quán với intrinsic value.",
"Q47":"Đánh giá buyback theo giá mua, intrinsic value, nguồn vốn và dilution. Gross buyback không có ý nghĩa nếu chủ yếu bù ESOP/options.",
"Q48":"Dùng bằng chứng về cách CEO dùng thời gian, tiền, ownership và lựa chọn dài hạn để suy luận động cơ. Không kết luận về tính cách chỉ từ phát biểu.",
"Q49":"Tìm một hoặc nhiều thời điểm management chọn minh bạch/đúng đắn dù bất lợi ngắn hạn. Nếu không có bằng chứng, giữ trạng thái Research Gap.",
"Q50":"So điều management nói với điều họ làm qua nhiều năm: guidance, M&A, capex, buyback, mục tiêu dài hạn và cách thừa nhận sai lầm.",
"Q51":"Tìm quyết định đi ngược thông lệ ngành có cơ sở kinh tế rõ ràng; phân biệt independent thinking với đơn giản là khác biệt.",
"Q52":"Đánh giá mức tự quảng bá, tần suất media, ngôn ngữ phóng đại, focus vào giá cổ phiếu so với hoạt động và mức thay đổi thông điệp theo thị trường.",
"Q53":"Tách organic growth và acquired growth; tính tỷ trọng vốn dùng cho M&A, contribution sau mua và chất lượng integration.",
"Q54":"Xem incentive và ngôn ngữ của management: tăng trưởng vì economics/runway hay vì quy mô, prestige, target ngắn hạn, compensation.",
"Q55":"So revenue/EPS/FCF với operating driver và invested capital. Tăng trưởng chỉ có giá trị nếu tạo thêm lợi nhuận/dòng tiền với return hợp lý.",
"Q56":"Xác định runway bằng TAM thực tế, penetration, unit economics, capacity, geographic/product adjacencies và rào cản thực thi. Không ngoại suy đơn giản quá khứ.",
"Q57":"Kiểm tra tốc độ mở rộng so với khả năng tự tài trợ, nhân sự, chất lượng, working capital và leverage. Tăng quá nhanh có thể phá economics.",
"Q58":"Mô tả quy trình M&A: tiêu chí, valuation, due diligence, nguồn vốn, integration, accountability và ngưỡng walk-away.",
"Q59":"Lập hậu kiểm từng thương vụ: giá mua, mục tiêu ban đầu, doanh thu/EBIT/ROIC sau 1/3/5 năm, impairment, synergy và tác động nợ/dilution.",
}


def load_questions(csv_path: str | Path) -> list[dict]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 59:
        raise ValueError(f"Expected 59 questions, got {len(rows)} from {path}")
    out = []
    for idx, row in enumerate(rows, start=1):
        qid = row["question_id"].strip()
        out.append({
            "question_id": qid,
            "question_no": idx,
            "group_name": row["group_name"].strip(),
            "question_vi": row["question_vi"].strip(),
            "guidance": GUIDANCE[qid],
            "research_mode": row["research_mode"].strip(),
            "supporting_tool": row.get("supporting_tool", "").strip() or None,
        })
    return out
