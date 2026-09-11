from __future__ import annotations

"""Vietnamese presentation dictionaries for Deep Company Analysis report V106.

This module is presentation-only. Appendix C remains the source lock for Q01-Q59 English
wording and ordering. Vietnamese strings are display translations, not a second question SSOT.
"""

from typing import Any, Mapping

from modules.deep_company_analysis.appendix_c import QUESTION_IDS, SECTION_ORDER

REPORT_VERSION = "V106"
REPORT_LANGUAGE = "vi"

SECTION_TITLES_VI: dict[str, str] = {
    "understanding_business_basics": "Hiểu doanh nghiệp - Những nền tảng cơ bản",
    "customer_perspective": "Hiểu doanh nghiệp - Góc nhìn khách hàng",
    "business_industry_strengths_weaknesses": "Đánh giá điểm mạnh, điểm yếu của doanh nghiệp và ngành",
    "operating_financial_health": "Đo lường sức khỏe hoạt động và tài chính của doanh nghiệp",
    "distribution_of_earnings_cash_flows": "Đánh giá sự phân bổ lợi nhuận (dòng tiền)",
    "management_background_classification": "Đánh giá chất lượng ban lãnh đạo - Bối cảnh và phân loại: Họ là ai?",
    "management_competence": "Đánh giá chất lượng ban lãnh đạo - Năng lực vận hành doanh nghiệp",
    "management_positive_negative_traits": "Đánh giá chất lượng ban lãnh đạo - Phẩm chất tích cực và tiêu cực",
    "growth_opportunities": "Đánh giá cơ hội tăng trưởng",
    "mergers_acquisitions": "Đánh giá hoạt động sáp nhập và mua lại (M&A)",
}

QUESTION_TITLES_VI: dict[str, str] = {
    "Q01": "Tôi có sẵn sàng dành nhiều thời gian để tìm hiểu doanh nghiệp này không?",
    "Q02": "Nếu trở thành CEO, tôi sẽ đánh giá doanh nghiệp này như thế nào?",
    "Q03": "Tôi có thể mô tả, bằng lời của mình, doanh nghiệp vận hành như thế nào không?",
    "Q04": "Doanh nghiệp kiếm tiền bằng cách nào?",
    "Q05": "Doanh nghiệp đã phát triển và thay đổi như thế nào theo thời gian?",
    "Q06": "Doanh nghiệp hoạt động tại những thị trường nước ngoài nào, và rủi ro khi hoạt động tại các quốc gia đó là gì?",
    "Q07": "Khách hàng cốt lõi của doanh nghiệp là ai?",
    "Q08": "Tệp khách hàng tập trung hay đa dạng?",
    "Q09": "Việc thuyết phục khách hàng mua sản phẩm hoặc dịch vụ là dễ hay khó?",
    "Q10": "Tỷ lệ giữ chân khách hàng của doanh nghiệp là bao nhiêu?",
    "Q11": "Những dấu hiệu nào cho thấy doanh nghiệp định hướng khách hàng?",
    "Q12": "Doanh nghiệp giải quyết 'nỗi đau' nào cho khách hàng?",
    "Q13": "Khách hàng phụ thuộc vào sản phẩm hoặc dịch vụ của doanh nghiệp ở mức độ nào?",
    "Q14": "Nếu doanh nghiệp biến mất vào ngày mai, điều đó sẽ tác động như thế nào đến tệp khách hàng?",
    "Q15": "Doanh nghiệp có lợi thế cạnh tranh bền vững không, và nguồn gốc của lợi thế đó là gì?",
    "Q16": "Doanh nghiệp có khả năng tăng giá mà không làm mất khách hàng không?",
    "Q17": "Doanh nghiệp đang hoạt động trong một ngành tốt hay xấu?",
    "Q18": "Ngành đã phát triển và thay đổi như thế nào theo thời gian?",
    "Q19": "Bối cảnh cạnh tranh ra sao, và mức độ cạnh tranh khốc liệt đến đâu?",
    "Q20": "Doanh nghiệp có mối quan hệ như thế nào với các nhà cung cấp?",
    "Q21": "Những yếu tố nền tảng của doanh nghiệp là gì?",
    "Q22": "Những chỉ số hoạt động nào của doanh nghiệp cần được theo dõi?",
    "Q23": "Doanh nghiệp đang đối mặt với những rủi ro trọng yếu nào?",
    "Q24": "Lạm phát ảnh hưởng đến doanh nghiệp như thế nào?",
    "Q25": "Bảng cân đối kế toán của doanh nghiệp mạnh hay yếu?",
    "Q26": "Tỷ suất sinh lời trên vốn đầu tư (ROIC) của doanh nghiệp là bao nhiêu?",
    "Q27": "Các chuẩn mực và chính sách kế toán mà ban lãnh đạo sử dụng mang tính thận trọng hay thiên về ghi nhận tích cực?",
    "Q28": "Doanh thu của doanh nghiệp có tính lặp lại hay chủ yếu đến từ các giao dịch một lần?",
    "Q29": "Doanh nghiệp mang tính chu kỳ, ngược chu kỳ hoặc có khả năng chống chịu suy thoái ở mức độ nào?",
    "Q30": "Đòn bẩy hoạt động tác động đến lợi nhuận của doanh nghiệp ở mức độ nào?",
    "Q31": "Vốn lưu động ảnh hưởng đến dòng tiền của doanh nghiệp như thế nào?",
    "Q32": "Doanh nghiệp có yêu cầu chi tiêu vốn (Capex) cao hay thấp?",
    "Q33": "Loại nhà quản lý nào đang dẫn dắt công ty?",
    "Q34": "Việc đưa ban lãnh đạo từ bên ngoài vào có những tác động gì đến doanh nghiệp?",
    "Q35": "Nhà quản lý là 'sư tử' hay 'linh cẩu'?",
    "Q36": "Nhà quản lý đã đi lên để trở thành người lãnh đạo doanh nghiệp như thế nào?",
    "Q37": "Các lãnh đạo cấp cao được trả công như thế nào, và họ có được quyền sở hữu/cổ phần bằng cách nào?",
    "Q38": "Ban lãnh đạo đang mua hay bán cổ phiếu?",
    "Q39": "CEO có điều hành doanh nghiệp vì lợi ích của tất cả các bên liên quan không?",
    "Q40": "Ban lãnh đạo cải thiện hoạt động hằng ngày hay vận hành doanh nghiệp theo một kế hoạch chiến lược?",
    "Q41": "CEO và CFO có đưa ra hướng dẫn/dự báo về lợi nhuận không?",
    "Q42": "Doanh nghiệp được quản lý theo mô hình tập trung hay phi tập trung?",
    "Q43": "Ban lãnh đạo có coi trọng nhân viên không?",
    "Q44": "Ban lãnh đạo có biết cách tuyển dụng người phù hợp không?",
    "Q45": "Ban lãnh đạo có tập trung cắt giảm các chi phí không cần thiết không?",
    "Q46": "CEO và CFO có kỷ luật trong các quyết định phân bổ vốn không?",
    "Q47": "CEO và CFO có mua lại cổ phiếu một cách cơ hội, khi giá hấp dẫn không?",
    "Q48": "CEO yêu tiền hay yêu chính doanh nghiệp hơn?",
    "Q49": "Tôi có thể xác định một thời điểm/sự kiện thể hiện tính chính trực của nhà quản lý không?",
    "Q50": "Ban lãnh đạo có rõ ràng và nhất quán trong truyền thông và hành động với các bên liên quan không?",
    "Q51": "Ban lãnh đạo có tư duy độc lập và không bị cuốn theo những gì các doanh nghiệp khác trong ngành đang làm không?",
    "Q52": "CEO có xu hướng tự quảng bá bản thân không?",
    "Q53": "Doanh nghiệp tăng trưởng thông qua M&A hay tăng trưởng hữu cơ?",
    "Q54": "Động lực của ban lãnh đạo khi thúc đẩy tăng trưởng doanh nghiệp là gì?",
    "Q55": "Tăng trưởng trong quá khứ có tạo ra lợi nhuận không, và điều đó có tiếp tục không?",
    "Q56": "Triển vọng tăng trưởng trong tương lai của doanh nghiệp là gì?",
    "Q57": "Ban lãnh đạo đang phát triển doanh nghiệp quá nhanh hay với nhịp độ ổn định?",
    "Q58": "Ban lãnh đạo đưa ra quyết định M&A như thế nào?",
    "Q59": "Các thương vụ mua lại trong quá khứ có thành công không?",
}

STATUS_VI = {
    "unknown": "Chưa rõ",
    "reviewed": "Đã rà soát",
    "complete": "Đã hoàn tất",
    "completed": "Đã hoàn tất",
    "answered": "Đã trả lời",
    "in progress": "Đang nghiên cứu",
    "in_progress": "Đang nghiên cứu",
    "pending": "Chờ rà soát",
    "not started": "Chưa bắt đầu",
    "not_started": "Chưa bắt đầu",
}

METRIC_LABELS_VI = {
    "revenue": "Doanh thu",
    "gross_profit": "Lợi nhuận gộp",
    "gross_margin": "Biên lợi nhuận gộp (GPM)",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "net_income": "LNST hợp nhất",
    "npat_mi": "LNST thuộc cổ đông công ty mẹ (NPAT-MI)",
    "net_margin": "Biên lợi nhuận ròng",
    "cfo": "Dòng tiền từ HĐKD (CFO)",
    "capex": "Chi tiêu vốn (Capex)",
    "fcf": "Dòng tiền tự do (FCF)",
    "cfo_to_ni": "CFO/LNST",
    "fcf_to_ni": "FCF/LNST",
    "cash": "Tiền và tương đương tiền",
    "debt": "Nợ vay",
    "net_cash": "Tiền ròng",
    "equity": "Vốn chủ sở hữu",
    "leverage": "Nợ vay/VCSH",
    "roic": "ROIC",
    "roce": "ROCE",
    "ar": "Phải thu khách hàng",
    "inventory": "Hàng tồn kho",
    "ap": "Phải trả người bán",
    "ccc": "Chu kỳ chuyển đổi tiền mặt (CCC)",
}

GENERIC_COLUMN_LABELS_VI = {
    "metric": "Chỉ tiêu",
    "label": "Chỉ tiêu",
    "period": "Kỳ",
    "period_display": "Kỳ",
    "value": "Giá trị",
    "unit": "Đơn vị",
    "observations": "Số quan sát",
    "median": "Trung vị",
    "trimmed_mean": "Trung bình cắt ngọn",
    "p25": "Phân vị 25%",
    "p75": "Phân vị 75%",
    "trough": "Đáy",
    "peak": "Đỉnh",
    "latest_annual": "Năm gần nhất",
    "latest_ttm": "TTM gần nhất",
    "latest_vs_median_pct": "Gần nhất so với trung vị",
}

EVENT_TYPE_VI = {
    "raw_material_cost": "Nguyên liệu / chi phí đầu vào",
    "audit_governance": "Kiểm toán / quản trị",
    "project_delay": "Chậm tiến độ dự án",
}

EVENT_REASON_VI: dict[tuple[str, str], str] = {
    ("raw_material_cost", "Q20"): "Biến động điều kiện cung ứng/nguyên liệu có thể ảnh hưởng quan hệ với nhà cung cấp và vị thế đàm phán.",
    ("raw_material_cost", "Q23"): "Biến động chi phí đầu vào có thể là rủi ro hoạt động trọng yếu cần chuyên viên phân tích rà soát.",
    ("raw_material_cost", "Q24"): "Thay đổi giá nguyên liệu và chi phí đầu vào có thể là bằng chứng liên quan đến độ nhạy với lạm phát.",
    ("raw_material_cost", "Q45"): "Áp lực chi phí hoặc biện pháp kiểm soát chi phí có thể là bằng chứng liên quan đến kỷ luật chi phí của ban lãnh đạo.",
    ("audit_governance", "Q27"): "Diễn biến kiểm toán/kế toán có thể là bằng chứng về mức độ thận trọng hay tích cực của chính sách kế toán.",
    ("audit_governance", "Q40"): "Sự kiện quản trị có thể là bằng chứng cần rà soát về cách ban lãnh đạo vận hành doanh nghiệp.",
    ("audit_governance", "Q49"): "Sự kiện kiểm toán/quản trị có thể cung cấp bằng chứng liên quan đến tính chính trực của ban lãnh đạo.",
    ("audit_governance", "Q50"): "Sự kiện công bố thông tin/quản trị có thể là bằng chứng về tính rõ ràng và nhất quán trong truyền thông của ban lãnh đạo.",
    ("project_delay", "Q23"): "Chậm tiến độ dự án có thể bộc lộ rủi ro thực thi, thủ tục, chuỗi cung ứng, tài chính hoặc các rủi ro kinh doanh khác.",
    ("project_delay", "Q42"): "Một sự chậm trễ trọng yếu có thể cần đối chiếu với các hướng dẫn/dự báo trước đây của ban lãnh đạo và các lần điều chỉnh sau đó.",
    ("project_delay", "Q55"): "Việc chậm triển khai công suất/dự án có thể ảnh hưởng đến bằng chứng hỗ trợ cho tăng trưởng lịch sử và khả năng tiếp diễn.",
    ("project_delay", "Q56"): "Chậm tiến độ có thể ảnh hưởng đến bằng chứng hỗ trợ cho triển vọng tăng trưởng trong tương lai.",
}


def status_vi(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return "Chưa rõ"
    return STATUS_VI.get(text.lower(), text)


def metric_label_vi(metric: Any, fallback: Any = "") -> str:
    key = "" if metric is None else str(metric).strip()
    return METRIC_LABELS_VI.get(key, str(fallback or key))


def event_reason_vi(row: Mapping[str, Any]) -> str:
    key = (str(row.get("event_type") or ""), str(row.get("question_id") or ""))
    return EVENT_REASON_VI.get(key, str(row.get("mapping_reason") or ""))


def validate_localization_contract() -> tuple[str, ...]:
    errors: list[str] = []
    if tuple(SECTION_TITLES_VI) != SECTION_ORDER:
        errors.append("Vietnamese section order must match Appendix C section order.")
    if tuple(QUESTION_TITLES_VI) != QUESTION_IDS:
        errors.append("Vietnamese Q01-Q59 display translations must cover source order exactly.")
    if len(set(QUESTION_TITLES_VI.values())) != len(QUESTION_IDS):
        errors.append("Vietnamese Q01-Q59 display translations must be unique.")
    return tuple(errors)


__all__ = [
    "EVENT_REASON_VI", "EVENT_TYPE_VI", "GENERIC_COLUMN_LABELS_VI", "METRIC_LABELS_VI",
    "QUESTION_TITLES_VI", "REPORT_LANGUAGE", "REPORT_VERSION", "SECTION_TITLES_VI",
    "STATUS_VI", "event_reason_vi", "metric_label_vi", "status_vi", "validate_localization_contract",
]
